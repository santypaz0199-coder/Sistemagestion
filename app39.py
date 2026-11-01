
import os, re
from datetime import date
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app37 import app
from app import permiso_required, admin_required
from database import get_db
from app4 import enviar_email, get_config, render_plantilla, construir_contexto, _cargar_orden, UPLOADS, _plantilla_html_correo


def _validar_remitente(remitente):
    """Si el remitente es invalido (ej: admin@local), usar el default configurado."""
    if not remitente:
        return None
    email = remitente.get('email', '') if isinstance(remitente, dict) else str(remitente)
    if not email or '@local' in email or '.' not in email.split('@')[-1]:
        # Remitente invalido, usar el default
        from app4 import get_config
        default_email = get_config('smtp_remitente_email') or 'hola@familiazaragoza.com'
        default_nombre = get_config('smtp_remitente_nombre') or 'Familia Zaragoza'
        return {'email': default_email, 'nombre': default_nombre}
    return remitente


def _enviar_con_remitente(destinatario, asunto, cuerpo, remitente_override=None, adjuntos=None):
    """
    Wrapper que permite forzar un remitente distinto al default.
    remitente_override: dict con {'email': ..., 'nombre': ...} o None
    """
    if not remitente_override:
        return enviar_email(destinatario, asunto, cuerpo, adjuntos=adjuntos)

    # Reimplementamos el envio con remitente custom
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication

    if not destinatario or '@' not in destinatario:
        return False, 'Email del destinatario invalido.'
    host = get_config('smtp_host')
    puerto = int(get_config('smtp_puerto') or 587)
    usuario = get_config('smtp_usuario')
    password = get_config('smtp_password')
    seg = get_config('smtp_seguridad', 'tls')
    rem_email = remitente_override.get('email') or get_config('smtp_remitente_email')
    rem_nombre = remitente_override.get('nombre') or get_config('smtp_remitente_nombre', 'Familia Zaragoza')

    if not host or not usuario or not password or not rem_email:
        return False, 'Configura el SMTP en Configuracion antes de enviar.'

    msg = MIMEMultipart()
    msg['From'] = f'{rem_nombre} <{rem_email}>'
    msg['To'] = destinatario
    msg['Subject'] = asunto
    firma = get_config('firma_email')
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


def _remitentes_disponibles(conn):
    """Lista de remitentes que el usuario actual puede usar."""
    remitentes = []
    if current_user.es_admin:
        # 1. Leer de la tabla oficial de remitentes (Configuración -> Remitentes y SMTP)
        try:
            rows = conn.execute("SELECT email, nombre FROM remitentes WHERE activo=1 ORDER BY id").fetchall()
            for r in rows:
                remitentes.append({'email': r['email'], 'nombre': r['nombre'], 'label': r['nombre']})
        except Exception:
            pass
            
        # 2. Fallback: si la tabla está vacía, usamos lo que dice la configuración vieja
        if not remitentes:
            emp_email = get_config('empresa_email')
            if emp_email:
                remitentes.append({'email': emp_email, 'nombre': get_config('empresa_nombre') or 'Familia Zaragoza', 'label': 'Trato general'})
            notif_email = get_config('smtp_remitente_email')
            if notif_email and notif_email.lower() != (emp_email or '').lower():
                remitentes.append({'email': notif_email, 'nombre': get_config('smtp_remitente_nombre') or 'Familia Zaragoza', 'label': 'Notificaciones'})
                
    else:
        # Para vendedores: solo su propio remitente
        row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if row and row['email_remitente']:
            remitentes.append({
                'email': row['email_remitente'],
                'nombre': row['nombre_remitente'] or row['nombre'],
                'label': f"{row['nombre']}",
            })
        else:
            # Fallback al default
            remitentes.append({
                'email': get_config('smtp_remitente_email'),
                'nombre': get_config('smtp_remitente_nombre', 'Familia Zaragoza'),
                'label': 'Notificaciones',
            })
    return remitentes


def _remitente_por_email(conn, email):
    """Dado un email, devuelve el dict {email, nombre}."""
    if not email:
        return None
    # Buscar en config
    emp_email = get_config('empresa_email')
    if emp_email and emp_email.lower() == email.lower():
        return {'email': emp_email, 'nombre': get_config('empresa_nombre', 'Familia Zaragoza')}
    notif_email = get_config('smtp_remitente_email')
    if notif_email and notif_email.lower() == email.lower():
        return {'email': notif_email, 'nombre': get_config('smtp_remitente_nombre', 'Familia Zaragoza')}
    # Buscar en usuarios
    row = conn.execute("SELECT nombre, nombre_remitente FROM usuarios WHERE lower(email_remitente)=lower(?)", (email,)).fetchone()
    if row:
        return {'email': email, 'nombre': row['nombre_remitente'] or row['nombre']}
    return {'email': email, 'nombre': get_config('smtp_remitente_nombre', 'Familia Zaragoza')}


# ===== Override del endpoint de envio de emails por orden =====
@app.route('/ventas/<int:id>/email/<tipo>', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_email_enviar_v2(id, tipo):
    TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'entrega', 'factura'}
    if tipo not in TIPOS_VALIDOS:
        from flask import abort
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

    # Remitente elegido (si es admin puede elegir, vendedor automatico)
    remitente_email = request.form.get('remitente_email', '').strip()
    remitente_override = None
    if remitente_email and current_user.es_admin:
        remitente_override = _remitente_por_email(conn, remitente_email)

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

    # Si no hay override (vendedor), usar SU propio remitente
    if remitente_override is None and not current_user.es_admin:
        row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if row and row['email_remitente']:
            remitente_override = {'email': row['email_remitente'],
                                   'nombre': row['nombre_remitente'] or row['nombre']}

    # Validar que el remitente sea un email valido (evita admin@local)
    remitente_override = _validar_remitente(remitente_override)

    ok, msg = _enviar_con_remitente(destino, asunto, cuerpo,
                                     remitente_override=remitente_override,
                                     adjuntos=adjuntos)

    remitente_usado = remitente_override['email'] if remitente_override else get_config('smtp_remitente_email')

    conn.execute("""INSERT INTO emails_enviados
        (destinatario, asunto, tipo, orden_id, estado, remitente) VALUES (?,?,?,?,?,?)""",
        (destino, asunto, tipo, id, 'ok' if ok else 'error', remitente_usado))
    conn.commit(); conn.close()
    flash(msg, 'success' if ok else 'error')
    return redirect(url_for('ventas_detalle', id=id))


app.view_functions['ventas_email_enviar'] = ventas_email_enviar_v2


# ===== Correo manual =====
@app.route('/emails/nuevo', methods=['GET', 'POST'])
@login_required
def emails_nuevo():
    conn = get_db()
    if request.method == 'POST':
        destinatario = request.form.get('destinatario', '').strip()
        asunto = request.form.get('asunto', '').strip()
        cuerpo = request.form.get('cuerpo', '').strip()
        remitente_email = request.form.get('remitente_email', '').strip()

        if not destinatario or '@' not in destinatario:
            conn.close(); flash('Ingresa un email valido.', 'error')
            return redirect(url_for('emails_nuevo'))
        if not asunto:
            conn.close(); flash('El asunto es obligatorio.', 'error')
            return redirect(url_for('emails_nuevo'))
        if not cuerpo:
            conn.close(); flash('El cuerpo del correo es obligatorio.', 'error')
            return redirect(url_for('emails_nuevo'))

        remitente_override = None
        if current_user.es_admin and remitente_email:
            remitente_override = _remitente_por_email(conn, remitente_email)
        elif not current_user.es_admin:
            row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
            if row and row['email_remitente']:
                remitente_override = {'email': row['email_remitente'],
                                       'nombre': row['nombre_remitente'] or row['nombre']}

        # Validar remitente
        remitente_override = _validar_remitente(remitente_override)

        # Adjunto opcional
        adjuntos = []
        archivo = request.files.get('adjunto')
        if archivo and archivo.filename:
            from werkzeug.utils import secure_filename
            nombre_seg = secure_filename(f'manual_{date.today().isoformat()}_{archivo.filename}')
            ruta = os.path.join(UPLOADS, nombre_seg)
            archivo.save(ruta)
            adjuntos.append((ruta, archivo.filename))

        ok, msg = _enviar_con_remitente(destinatario, asunto, cuerpo,
                                         remitente_override=remitente_override,
                                         adjuntos=adjuntos)
        remitente_usado = remitente_override['email'] if remitente_override else get_config('smtp_remitente_email')
        conn.execute("""INSERT INTO emails_enviados
            (destinatario, asunto, tipo, orden_id, estado, remitente) VALUES (?,?,?,?,?,?)""",
            (destinatario, asunto, 'manual', None, 'ok' if ok else 'error', remitente_usado))
        conn.commit(); conn.close()
        flash(msg, 'success' if ok else 'error')
        return redirect(url_for('emails_historial'))

    clientes = conn.execute("SELECT id, nombre_completo, email FROM clientes WHERE activo=1 AND email IS NOT NULL AND email != '' ORDER BY nombre_completo").fetchall()
    remitentes = _remitentes_disponibles(conn)
    conn.close()
    return render_template('emails/nuevo.html', clientes=clientes, remitentes=remitentes)


# ===== Editar remitente del usuario (Mi Cuenta) =====
@app.route('/mi-cuenta/remitente', methods=['POST'])
@login_required
def mi_cuenta_remitente():
    email_r = request.form.get('email_remitente', '').strip()
    nombre_r = request.form.get('nombre_remitente', '').strip()
    conn = get_db()
    conn.execute("UPDATE usuarios SET email_remitente=?, nombre_remitente=? WHERE id=?",
                 (email_r or None, nombre_r or None, current_user.id))
    conn.commit(); conn.close()
    flash('Remitente actualizado.', 'success')
    return redirect(url_for('mi_cuenta'))


# ===== Admin edita remitente de cualquier usuario =====
@app.route('/usuarios/<int:id>/remitente', methods=['POST'])
@login_required
@admin_required
def usuarios_remitente(id):
    email_r = request.form.get('email_remitente', '').strip()
    nombre_r = request.form.get('nombre_remitente', '').strip()
    conn = get_db()
    conn.execute("UPDATE usuarios SET email_remitente=?, nombre_remitente=? WHERE id=?",
                 (email_r or None, nombre_r or None, id))
    conn.commit(); conn.close()
    flash('Remitente actualizado.', 'success')
    return redirect(url_for('usuarios_editar', id=id))


# ===== Historial con remitente =====
@app.route('/emails')
@login_required
@admin_required
def emails_historial_v2():
    conn = get_db()
    emails = conn.execute("""SELECT e.*, o.numero_interno FROM emails_enviados e
        LEFT JOIN ordenes_venta o ON o.id=e.orden_id
        ORDER BY e.id DESC LIMIT 300""").fetchall()
    conn.close()
    return render_template('emails/historial.html', emails=emails)


app.view_functions['emails_historial'] = emails_historial_v2


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)


# ===== Override del detalle para inyectar remitentes =====
@app.route('/ventas/<int:id>')
@login_required
@permiso_required('ventas')
def ventas_detalle_v3(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))

    items = conn.execute("""SELECT oi.*, p.nombre as producto_nombre, p.sku
        FROM orden_items oi JOIN productos p ON p.id=oi.producto_id
        WHERE oi.orden_id=?""", (id,)).fetchall()
    pagos = conn.execute("""SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg
        LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id
        WHERE pg.orden_id=? ORDER BY pg.id""", (id,)).fetchall()
    total_pagado = sum(p['monto'] for p in pagos)
    medios = conn.execute("SELECT * FROM medios_pago WHERE activo=1 ORDER BY nombre").fetchall()
    transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1 ORDER BY nombre").fetchall()
    archivos = conn.execute("SELECT * FROM archivos WHERE orden_id=? ORDER BY id DESC", (id,)).fetchall()
    emails = conn.execute("SELECT * FROM emails_enviados WHERE orden_id=? ORDER BY id DESC LIMIT 20", (id,)).fetchall()

    remitentes_disponibles = _remitentes_disponibles(conn)

    # Cargar Provincias y Localidades para los selectores de envío
    provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
    locs_rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    localidades_por_provincia = {}
    for r in locs_rows:
        localidades_por_provincia.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})

    # URL base del transportista actual (para construir el link de seguimiento)
    transportista_url_actual = None
    if orden['transportista_id']:
        t_row = conn.execute("SELECT url_seguimiento FROM transportistas WHERE id=?",
                              (orden['transportista_id'],)).fetchone()
        if t_row:
            transportista_url_actual = t_row['url_seguimiento']

    conn.close()
    return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, medios=medios, transportistas=transportistas,
                           archivos=archivos, emails=emails,
                           remitentes_disponibles=remitentes_disponibles,
                           transportista_url_actual=transportista_url_actual,
                           provincias=provincias, localidades_por_provincia=localidades_por_provincia)


app.view_functions['ventas_detalle'] = ventas_detalle_v3


# ===== Mi Cuenta con remitente =====
def mi_cuenta_v2():
    from werkzeug.security import check_password_hash, generate_password_hash
    conn = get_db()
    if request.method == 'POST':
        # Cambio de password
        actual = request.form.get('actual', '')
        nueva = request.form.get('nueva', '')
        confirmar = request.form.get('confirmar', '')
        row = conn.execute("SELECT * FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if not check_password_hash(row['password_hash'], actual):
            conn.close(); flash('La contrasena actual no es correcta.', 'error')
            return redirect(url_for('mi_cuenta'))
        if len(nueva) < 6 or nueva != confirmar:
            conn.close(); flash('Revisa la nueva contrasena.', 'error')
            return redirect(url_for('mi_cuenta'))
        conn.execute("UPDATE usuarios SET password_hash=? WHERE id=?",
                     (generate_password_hash(nueva), current_user.id))
        conn.commit(); conn.close()
        flash('Contrasena actualizada.', 'success')
        return redirect(url_for('mi_cuenta'))

    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
    conn.close()
    return render_template('mi_cuenta.html', usuario=dict(usuario))


app.view_functions['mi_cuenta'] = mi_cuenta_v2


# ===== Usuarios editar (agregar remitente) =====
def usuarios_editar_v2(id):
    from werkzeug.security import generate_password_hash
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
    if not usuario:
        conn.close(); flash('Usuario no encontrado.', 'error')
        return redirect(url_for('usuarios_lista'))
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        email = request.form['email'].strip().lower()
        rol = request.form['rol']
        password = request.form.get('password', '').strip()
        activo = 1 if request.form.get('activo') else 0
        email_r = request.form.get('email_remitente', '').strip()
        nombre_r = request.form.get('nombre_remitente', '').strip()
        existe = conn.execute("SELECT id FROM usuarios WHERE lower(email)=? AND id!=?", (email, id)).fetchone()
        if existe:
            conn.close(); flash('Email de login ya existe.', 'error')
            return redirect(url_for('usuarios_editar', id=id))
        if password:
            conn.execute("""UPDATE usuarios SET nombre=?,email=?,rol=?,activo=?,password_hash=?,
                email_remitente=?,nombre_remitente=? WHERE id=?""",
                (nombre, email, rol, activo, generate_password_hash(password),
                 email_r or None, nombre_r or None, id))
        else:
            conn.execute("""UPDATE usuarios SET nombre=?,email=?,rol=?,activo=?,
                email_remitente=?,nombre_remitente=? WHERE id=?""",
                (nombre, email, rol, activo, email_r or None, nombre_r or None, id))
        conn.commit(); conn.close()
        flash('Usuario actualizado.', 'success')
        return redirect(url_for('usuarios_lista'))
    conn.close()
    return render_template('usuarios/form.html', usuario=dict(usuario), valores={})


app.view_functions['usuarios_editar'] = usuarios_editar_v2
