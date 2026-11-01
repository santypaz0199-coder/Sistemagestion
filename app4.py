
import os
from datetime import date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app3 import app, admin_required
from database import get_db, init_db

UPLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOADS, exist_ok=True)


def get_config(clave, default=''):
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return row['valor'] if row and row['valor'] is not None else default


def set_config(clave, valor):
    conn = get_db()
    conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                 "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (clave, valor))
    conn.commit(); conn.close()


def render_plantilla(texto, ctx):
    for k, v in ctx.items():
        texto = texto.replace('{{' + k + '}}', str(v) if v is not None else '')
    return texto



def _plantilla_html_correo(cuerpo_texto, firma):
    import html
    # Convertimos saltos de linea a <br> y escapamos HTML por seguridad
    cuerpo_html = html.escape(cuerpo_texto).replace('\n', '<br>')
    firma_html = html.escape(firma or '').replace('\n', '<br>')
    
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
</head>
<body style="margin:0; padding:0; background-color:#f4f6fb; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
<table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color:#f4f6fb; padding: 40px 20px;">
<tr><td align="center">
<table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 12px rgba(0,0,0,0.05);">
<!-- Encabezado -->
<tr><td align="center" style="background-color:#0f172a; padding:30px;">
<h1 style="margin:0; color:#ffffff; font-size:24px; font-weight:700; letter-spacing:1px;">FAMILIA ZARAGOZA ®</h1>
</td></tr>
<!-- Cuerpo -->
<tr><td style="padding: 40px 30px; color:#334155; font-size:15px; line-height:1.6;">
{cuerpo_html}
</td></tr>
<!-- Firma -->
<tr><td style="padding: 0 30px 40px 30px; color:#64748b; font-size:13px; line-height:1.5; border-top:1px solid #f1f5f9;">
<br>
{firma_html}
</td></tr>
</table>
</div>
</td></tr>
</table>
</body>
</html>"""


def enviar_email(destinatario, asunto, cuerpo, adjuntos=None):
    if not destinatario or '@' not in destinatario:
        return False, 'Email del destinatario invalido.'
    host = get_config('smtp_host')
    puerto = int(get_config('smtp_puerto') or 587)
    usuario = get_config('smtp_usuario')
    password = get_config('smtp_password')
    rem_email = get_config('smtp_remitente_email')
    rem_nombre = get_config('smtp_remitente_nombre', 'Familia Zaragoza')
    seg = get_config('smtp_seguridad', 'tls')
    if not host or not usuario or not password or not rem_email:
        return False, 'Configura el SMTP en Configuracion antes de enviar.'

    msg = MIMEMultipart()
    msg['From'] = f'{rem_nombre} <{rem_email}>'
    msg['To'] = destinatario
    msg['Subject'] = asunto
    from flask import has_app_context
    from app4 import get_config as _get_conf
    firma = _get_conf('firma_email') if has_app_context() else 'Familia Zaragoza'
    cuerpo_html = _plantilla_html_correo(cuerpo, firma)
    msg.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))

    if adjuntos:
        for path, nombre in adjuntos:
            try:
                with open(path, 'rb') as f:
                    data = f.read()
                part = MIMEApplication(data, Name=nombre)
                part['Content-Disposition'] = f'attachment; filename="{nombre}"'
                msg.attach(part)
            except Exception as e:
                print(f"[email] error adjunto {nombre}: {e}")

    try:
        if seg == 'ssl' or puerto == 465:
            server = smtplib.SMTP_SSL(host, puerto, timeout=20)
        else:
            server = smtplib.SMTP(host, puerto, timeout=20)
            server.starttls()
        server.login(usuario, password)
        server.sendmail(rem_email, [destinatario], msg.as_string())
        server.quit()
        return True, 'Enviado.'
    except Exception as e:
        return False, f'Error SMTP: {e}'


def link_seguimiento(orden):
    """Devuelve un bloque HTML/texto con el link o numero segun el transportista."""
    if not orden['transportista_nombre'] or not orden['nro_guia']:
        return 'Aun no tenemos los datos de seguimiento. Te los enviamos a la brevedad.'
    conn = get_db()
    t = conn.execute("SELECT * FROM transportistas WHERE id=?", (orden['transportista_id'],)).fetchone()
    conn.close()
    url_tpl = (t['url_seguimiento'] or '') if t else ''
    guia = orden['nro_guia']
    if not url_tpl:
        return f'Numero de seguimiento: {guia}'
    if '{guia}' in url_tpl:
        url = url_tpl.replace('{guia}', guia)
        return f'Podes seguir tu envio en: {url}'
    return (f'Numero de seguimiento: {guia}\n\n'
            f'Ingresalo en el sitio del correo para ver el estado: {url_tpl}')


def detalle_productos_texto(conn, orden_id):
    items = conn.execute("""SELECT oi.cantidad, oi.precio_unitario, oi.subtotal, p.nombre, p.sku
        FROM orden_items oi JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?""", (orden_id,)).fetchall()
    lines = []
    for it in items:
        sku = f' ({it["sku"]})' if it['sku'] else ''
        lines.append(f'  - {it["nombre"]}{sku} x {it["cantidad"]:g} = ${it["subtotal"]:.2f}')
    return '\n'.join(lines)


def datos_envio_texto(orden):
    partes = []
    if orden['destinatario_nombre']: partes.append(f'Destinatario: {orden["destinatario_nombre"]}')
    direccion = []
    if orden['destinatario_calle']: direccion.append(orden['destinatario_calle'])
    if orden['destinatario_localidad']: direccion.append(orden['destinatario_localidad'])
    if orden['destinatario_provincia']: direccion.append(orden['destinatario_provincia'])
    if orden['destinatario_cp']: direccion.append(f'CP {orden["destinatario_cp"]}')
    if direccion: partes.append('Direccion: ' + ', '.join(direccion))
    if orden['destinatario_detalles']: partes.append(f'Detalles: {orden["destinatario_detalles"]}')
    return '\n'.join(partes) if partes else 'Datos de envio pendientes.'


def construir_contexto(orden, conn, tipo):
    ctx = {
        'cliente_nombre': orden['cliente_nombre'],
        'numero_orden': orden['numero_interno'],
        'fecha': orden['fecha'],
        'total': f'{orden["total"]:.2f}',
        'firma': get_config('firma_email'),
        'transportista': orden['transportista_nombre'] or '',
        'nro_guia': orden['nro_guia'] or '',
    }
    if tipo in ('confirmacion', 'envio'):
        ctx['detalle_productos'] = detalle_productos_texto(conn, orden['id'])
        ctx['datos_envio'] = datos_envio_texto(orden)
    if tipo == 'envio':
        ctx['info_seguimiento'] = link_seguimiento(orden)
    return ctx


# ===== Configuracion =====
@app.route('/configuracion')
@login_required
@admin_required
def configuracion():
    return render_template('configuracion/index.html')


@app.route('/configuracion/smtp', methods=['GET', 'POST'])
@login_required
@admin_required
def configuracion_smtp():
    if request.method == 'POST':
        if request.form.get('accion') == 'probar':
            destino = request.form.get('probar_destino', '').strip()
            ok, msg = enviar_email(destino, 'Prueba SMTP - Sistema FZ',
                                    'Este es un mail de prueba del sistema. Si lo recibiste, la configuracion SMTP funciona correctamente.')
            flash(('OK: ' + msg) if ok else msg, 'success' if ok else 'error')
            return redirect(url_for('configuracion_smtp'))
        for k in ['smtp_host', 'smtp_puerto', 'smtp_usuario', 'smtp_password',
                  'smtp_remitente_email', 'smtp_remitente_nombre', 'smtp_seguridad']:
            set_config(k, request.form.get(k, '').strip())
        flash('Configuracion SMTP guardada.', 'success')
        return redirect(url_for('configuracion_smtp'))
    cfg = {k: get_config(k) for k in ['smtp_host', 'smtp_puerto', 'smtp_usuario', 'smtp_password',
                                       'smtp_remitente_email', 'smtp_remitente_nombre', 'smtp_seguridad']}
    return render_template('configuracion/smtp.html', cfg=cfg)


@app.route('/configuracion/firma', methods=['GET', 'POST'])
@login_required
@admin_required
def configuracion_firma():
    if request.method == 'POST':
        set_config('firma_email', request.form.get('firma_email', ''))
        set_config('empresa_nombre', request.form.get('empresa_nombre', ''))
        set_config('empresa_telefono', request.form.get('empresa_telefono', ''))
        set_config('empresa_web', request.form.get('empresa_web', ''))
        flash('Firma guardada.', 'success')
        return redirect(url_for('configuracion_firma'))
    cfg = {k: get_config(k) for k in ['firma_email', 'empresa_nombre', 'empresa_telefono', 'empresa_web']}
    return render_template('configuracion/firma.html', cfg=cfg)


@app.route('/configuracion/plantillas')
@login_required
@admin_required
def configuracion_plantillas():
    tipos = [
        ('confirmacion', 'Confirmacion de orden', 'Enviar orden'),
        ('pago', 'Pago acreditado', 'Notificar pago'),
        ('envio', 'Envio en camino', 'Notificar envio'),
        ('entrega', 'Entrega realizada', 'Notificar entrega'),
        ('factura', 'Envio de factura', 'Enviar factura'),
    ]
    return render_template('configuracion/plantillas.html', tipos=tipos)


VARIABLES_POR_TIPO = {
    'confirmacion': ['cliente_nombre', 'numero_orden', 'fecha', 'total', 'detalle_productos', 'datos_envio', 'firma'],
    'pago': ['cliente_nombre', 'numero_orden', 'fecha', 'total', 'firma'],
    'envio': ['cliente_nombre', 'numero_orden', 'fecha', 'total', 'detalle_productos', 'datos_envio', 'info_seguimiento', 'transportista', 'nro_guia', 'firma'],
    'entrega': ['cliente_nombre', 'numero_orden', 'fecha', 'total', 'firma'],
    'factura': ['cliente_nombre', 'numero_orden', 'fecha', 'total', 'firma'],
}


@app.route('/configuracion/plantillas/<tipo>', methods=['GET', 'POST'])
@login_required
@admin_required
def configuracion_plantilla_editar(tipo):
    if tipo not in PLANTILLAS_DEFAULT:
        abort(404)
    if request.method == 'POST':
        set_config(f'plantilla_{tipo}_asunto', request.form.get('asunto', ''))
        set_config(f'plantilla_{tipo}_cuerpo', request.form.get('cuerpo', ''))
        flash('Plantilla guardada.', 'success')
        return redirect(url_for('configuracion_plantillas'))
    cfg = {
        'asunto': get_config(f'plantilla_{tipo}_asunto', PLANTILLAS_DEFAULT[tipo]['asunto']),
        'cuerpo': get_config(f'plantilla_{tipo}_cuerpo', PLANTILLAS_DEFAULT[tipo]['cuerpo']),
    }
    return render_template('configuracion/plantilla_editar.html', tipo=tipo, cfg=cfg,
                           variables=VARIABLES_POR_TIPO.get(tipo, []))


# ===== Emails de orden =====
def _cargar_orden(conn, id):
    return conn.execute("""SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email,
        u.nombre as vendedor_nombre, cv.nombre as canal_nombre, t.nombre as transportista_nombre
        FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id JOIN usuarios u ON u.id=o.usuario_id
        LEFT JOIN canales_venta cv ON cv.id=o.canal_id LEFT JOIN transportistas t ON t.id=o.transportista_id
        WHERE o.id=?""", (id,)).fetchone()


@app.route('/ventas/<int:id>/email/<tipo>', methods=['POST'])
@login_required
def ventas_email_enviar(id, tipo):
    if tipo not in PLANTILLAS_DEFAULT:
        abort(404)
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))

    destino = request.form.get('destinatario') or orden['cliente_email']
    if not destino or '@' not in destino:
        conn.close(); flash('El cliente no tiene email. Editalo o ingresa uno manual.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    ctx = construir_contexto(orden, conn, tipo)
    asunto = render_plantilla(get_config(f'plantilla_{tipo}_asunto'), ctx)
    cuerpo = render_plantilla(get_config(f'plantilla_{tipo}_cuerpo'), ctx)

    adjuntos = []
    adj_ids = request.form.getlist('adjunto_id')
    if adj_ids:
        for aid in adj_ids:
            a = conn.execute("SELECT * FROM archivos WHERE id=? AND orden_id=?", (int(aid), id)).fetchone()
            if a:
                ruta = os.path.join(UPLOADS, a['ruta_local'])
                if os.path.exists(ruta):
                    adjuntos.append((ruta, a['nombre_original']))

    ok, msg = enviar_email(destino, asunto, cuerpo, adjuntos=adjuntos)
    conn.execute("""INSERT INTO emails_enviados (destinatario, asunto, tipo, orden_id, estado)
        VALUES (?,?,?,?,?)""", (destino, asunto, tipo, id, 'ok' if ok else 'error'))
    conn.commit(); conn.close()
    flash(msg, 'success' if ok else 'error')
    return redirect(url_for('ventas_detalle', id=id))


# ===== Adjuntos =====
@app.route('/ventas/<int:id>/adjunto', methods=['POST'])
@login_required
def ventas_adjunto_subir(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))
    f = request.files.get('archivo')
    if not f or not f.filename:
        conn.close(); flash('Selecciona un archivo.', 'error'); return redirect(url_for('ventas_detalle', id=id))
    nombre_orig = f.filename
    seguro = secure_filename(f'{id}_{date.today().isoformat()}_{nombre_orig}') or f'{id}_archivo.pdf'
    ruta_disco = os.path.join(UPLOADS, seguro)
    f.save(ruta_disco)
    tipo = request.form.get('tipo', 'otro')
    conn.execute("INSERT INTO archivos (orden_id, tipo, nombre_original, ruta_local) VALUES (?,?,?,?)",
                 (id, tipo, nombre_orig, seguro))
    conn.commit(); conn.close()
    flash('Archivo subido.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


@app.route('/ventas/<int:id>/adjunto/<int:aid>/eliminar', methods=['POST'])
@login_required
def ventas_adjunto_eliminar(id, aid):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); return redirect(url_for('ventas_lista'))
    a = conn.execute("SELECT * FROM archivos WHERE id=? AND orden_id=?", (aid, id)).fetchone()
    if a:
        ruta = os.path.join(UPLOADS, a['ruta_local'])
        if os.path.exists(ruta):
            try: os.remove(ruta)
            except Exception: pass
        conn.execute("DELETE FROM archivos WHERE id=?", (aid,))
        conn.commit()
    conn.close()
    flash('Adjunto eliminado.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


@app.route('/ventas/<int:id>/adjunto/<int:aid>/descargar')
@login_required
def ventas_adjunto_descargar(id, aid):
    conn = get_db()
    a = conn.execute("SELECT * FROM archivos WHERE id=? AND orden_id=?", (aid, id)).fetchone()
    conn.close()
    if not a:
        abort(404)
    ruta = os.path.join(UPLOADS, a['ruta_local'])
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta, as_attachment=True, download_name=a['nombre_original'])


# ===== Historial de emails =====
@app.route('/emails')
@login_required
@admin_required
def emails_historial():
    conn = get_db()
    emails = conn.execute("""SELECT e.*, o.numero_interno FROM emails_enviados e
        LEFT JOIN ordenes_venta o ON o.id=e.orden_id
        ORDER BY e.id DESC LIMIT 300""").fetchall()
    conn.close()
    return render_template('emails/historial.html', emails=emails)


if __name__ == '__main__':
    init_db()
    print("=== Sistema Familia Zaragoza (app4) ===")
    print("Abrir: http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)
