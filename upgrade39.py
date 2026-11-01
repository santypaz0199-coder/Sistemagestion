# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade39] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade39] sin DB."); return
    conn = sqlite3.connect(db)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    if 'email_remitente' not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN email_remitente TEXT")
        print("[upgrade39] + usuarios.email_remitente")
    if 'nombre_remitente' not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN nombre_remitente TEXT")
        print("[upgrade39] + usuarios.nombre_remitente")

    # Agregar columna remitente a emails_enviados
    cols_e = [r[1] for r in conn.execute("PRAGMA table_info(emails_enviados)").fetchall()]
    if 'remitente' not in cols_e:
        conn.execute("ALTER TABLE emails_enviados ADD COLUMN remitente TEXT")
        print("[upgrade39] + emails_enviados.remitente")

    # Backfill: darle al admin el correo hola@ si todavia no tiene
    admin = conn.execute("SELECT id FROM usuarios WHERE rol='admin' AND activo=1 LIMIT 1").fetchone()
    if admin:
        # Ver si existe email empresa
        emp_email = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_email'").fetchone()
        emp_nombre = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_nombre'").fetchone()
        if emp_email:
            conn.execute("""UPDATE usuarios SET email_remitente=?, nombre_remitente=?
                WHERE id=? AND (email_remitente IS NULL OR email_remitente='')""",
                (emp_email[0], emp_nombre[0] if emp_nombre else 'Familia Zaragoza', admin[0]))
            print("[upgrade39] admin tiene remitente por defecto")

    conn.commit(); conn.close()


APP39_PY = r'''
import os, re
from datetime import date
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app37 import app
from app import permiso_required, admin_required
from database import get_db
from app4 import enviar_email, get_config, render_plantilla, construir_contexto, _cargar_orden, UPLOADS


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
    msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

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
        # Todos los correos configurados
        emails_vistos = set()
        # 1. Del config
        emp_email = get_config('empresa_email')
        emp_nombre = get_config('empresa_nombre')
        notif_email = get_config('smtp_remitente_email')
        notif_nombre = get_config('smtp_remitente_nombre')
        if emp_email:
            remitentes.append({'email': emp_email, 'nombre': emp_nombre or 'Familia Zaragoza', 'label': 'Trato general'})
            emails_vistos.add(emp_email.lower())
        if notif_email and notif_email.lower() not in emails_vistos:
            remitentes.append({'email': notif_email, 'nombre': notif_nombre or 'Familia Zaragoza', 'label': 'Notificaciones'})
            emails_vistos.add(notif_email.lower())
        # 2. De los usuarios
        rows = conn.execute("SELECT id, nombre, email_remitente, nombre_remitente FROM usuarios WHERE activo=1 AND email_remitente IS NOT NULL AND email_remitente != ''").fetchall()
        for r in rows:
            if r['email_remitente'].lower() not in emails_vistos:
                remitentes.append({
                    'email': r['email_remitente'],
                    'nombre': r['nombre_remitente'] or r['nombre'],
                    'label': f"{r['nombre']}",
                })
                emails_vistos.add(r['email_remitente'].lower())
    else:
        # Solo el propio del vendedor
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
    from app4 import PLANTILLAS_DEFAULT
    if tipo not in PLANTILLAS_DEFAULT:
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
'''


EMAILS_NUEVO = r'''{% extends "base.html" %}
{% block title %}Redactar correo{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Redactar correo</h4>
<div class="text-muted small">Se envia de inmediato al destinatario</div>
</div>
<a href="{{ url_for('emails_historial') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="card shadow-sm"><div class="card-body">
<form method="post" enctype="multipart/form-data">
<div class="row g-3">

<div class="col-md-6">
<label class="form-label">Destinatario *</label>
<div class="input-group">
<select id="cliente-select" class="form-select">
<option value="">-- Elegir cliente o escribir abajo --</option>
{% for c in clientes %}
<option value="{{ c.email }}">{{ c.nombre_completo }} &lt;{{ c.email }}&gt;</option>
{% endfor %}
</select>
</div>
<input name="destinatario" id="dest-input" type="email" class="form-control mt-2" placeholder="email@ejemplo.com" required>
<div class="form-text">Podes elegir un cliente (autocompleta) o escribir directo.</div>
</div>

<div class="col-md-6">
<label class="form-label">Enviar desde</label>
{% if current_user.es_admin %}
<select name="remitente_email" class="form-select">
{% for r in remitentes %}
<option value="{{ r.email }}">{{ r.label }} · {{ r.email }}</option>
{% endfor %}
</select>
<div class="form-text">El cliente vera este nombre como remitente.</div>
{% else %}
{% if remitentes %}
{% set r = remitentes[0] %}
<div class="form-control-plaintext">
<span class="badge bg-secondary">{{ r.nombre }}</span> &lt;{{ r.email }}&gt;
</div>
<div class="form-text">Se envia desde tu correo asignado. Pedile al admin si necesitas cambiarlo.</div>
{% else %}
<div class="alert alert-warning py-2 small mb-0">No tenes correo remitente asignado. Pedile al admin.</div>
{% endif %}
{% endif %}
</div>

<div class="col-12">
<label class="form-label">Asunto *</label>
<input name="asunto" class="form-control" required placeholder="Ej: Consulta sobre tu pedido">
</div>

<div class="col-12">
<label class="form-label">Cuerpo *</label>
<textarea name="cuerpo" class="form-control" rows="10" required placeholder="Escribi el mensaje..."></textarea>
</div>

<div class="col-12">
<label class="form-label">Adjunto (opcional)</label>
<input type="file" name="adjunto" class="form-control">
<div class="form-text">Cualquier archivo. Max 10 MB.</div>
</div>

</div>
<div class="mt-4 d-flex gap-2">
<button class="btn btn-dark"><i class="bi bi-send"></i> Enviar correo</button>
<a href="{{ url_for('emails_historial') }}" class="btn btn-outline-secondary">Cancelar</a>
</div>
</form>
</div></div>

<script>
document.getElementById('cliente-select').addEventListener('change', function() {
  if (this.value) {
    document.getElementById('dest-input').value = this.value;
  }
});
</script>
{% endblock %}
'''


EMAILS_HISTORIAL = r'''{% extends "base.html" %}
{% block title %}Emails{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Historial de emails enviados</h4>
<div class="text-muted small">Ultimos 300 envios</div>
</div>
<a href="{{ url_for('emails_nuevo') }}" class="btn btn-dark"><i class="bi bi-pencil-square"></i> Redactar correo</a>
</div>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light">
<tr><th>Fecha</th><th>Orden</th><th>Tipo</th><th>Remitente</th><th>Destinatario</th><th>Asunto</th><th>Estado</th></tr>
</thead>
<tbody>
{% for e in emails %}
<tr>
<td class="small">{{ e.fecha }}</td>
<td class="small">{{ e.numero_interno or '-' }}</td>
<td><span class="badge bg-secondary">{{ e.tipo }}</span></td>
<td class="small text-muted">{{ e.remitente or '—' }}</td>
<td class="small">{{ e.destinatario }}</td>
<td class="small">{{ e.asunto }}</td>
<td>{% if e.estado=='ok' %}<span class="badge bg-success">OK</span>{% else %}<span class="badge bg-danger">Error</span>{% endif %}</td>
</tr>
{% else %}
<tr><td colspan="7" class="text-center text-muted py-4">Sin emails enviados.</td></tr>
{% endfor %}
</tbody></table></div></div>
{% endblock %}
'''


def patch_ventas_detalle():
    """Agrega el selector de remitente (solo admin) en el bloque de notificaciones."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta):
        print("[upgrade39] no existe ventas/detalle.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'selector-remitente' in contenido:
        print("[upgrade39] ventas/detalle ya tiene selector de remitente"); return

    buscar = '''<div class="mb-2">
<label class="form-label small">Destinatario</label>
<input name="destinatario" type="email" class="form-control form-control-sm" value="{{ orden.cliente_email or '' }}" required>
</div>'''

    if buscar not in contenido:
        print("[upgrade39] no se encontro el bloque de destinatario en detalle")
        return

    nuevo = '''<div class="mb-2">
<label class="form-label small">Destinatario</label>
<input name="destinatario" type="email" class="form-control form-control-sm" value="{{ orden.cliente_email or '' }}" required>
</div>
{% if current_user.es_admin and remitentes_disponibles %}
<div class="mb-2 selector-remitente">
<label class="form-label small">Enviar desde</label>
<select name="remitente_email" class="form-select form-select-sm">
{% for r in remitentes_disponibles %}
<option value="{{ r.email }}">{{ r.label }} · {{ r.email }}</option>
{% endfor %}
</select>
</div>
{% endif %}'''

    contenido = contenido.replace(buscar, nuevo)  # reemplaza todas las ocurrencias
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade39] selector de remitente agregado a ventas/detalle.html")


def patch_detalle_route():
    """Hace que el detalle de la orden pase los remitentes al template."""
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'ventas_detalle_v3' in contenido:
        print("[upgrade39] detalle ya parcheado")
        return

    add = '''

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

    conn.close()
    return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, medios=medios, transportistas=transportistas,
                           archivos=archivos, emails=emails,
                           remitentes_disponibles=remitentes_disponibles)


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
'''
    with open(ruta, 'a', encoding='utf-8') as f:
        f.write(add)
    print("[upgrade39] rutas de detalle, mi cuenta y usuarios parcheadas")


def patch_usuarios_form():
    """Agrega los campos de remitente al form de usuarios."""
    ruta = os.path.join(BASE, 'templates', 'usuarios', 'form.html')
    if not os.path.exists(ruta):
        print("[upgrade39] no existe usuarios/form.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'email_remitente' in contenido:
        print("[upgrade39] usuarios/form ya tiene campos de remitente"); return

    buscar = '<div class="col-md-6"><label class="form-label">Contrasena'
    if buscar not in contenido:
        print("[upgrade39] no se encontro el campo contrasena")
        return

    nuevo = '''<div class="col-md-6"><label class="form-label">Contrasena'''

    # Insertar despues del campo contrasena, agregando los de remitente
    buscar2 = '</div>\n{% if usuario %}<div class="col-12"><div class="form-check">'
    if buscar2 not in contenido:
        # Fallback: insertar antes del boton guardar
        buscar2 = '<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>'
        if buscar2 not in contenido:
            print("[upgrade39] no se encontro el boton guardar"); return
        nuevo2 = '''<div class="col-12 mt-3"><hr><h6 class="text-muted small">Remitente de email</h6></div>
<div class="col-md-6">
<label class="form-label">Email remitente</label>
<input name="email_remitente" type="email" class="form-control" value="{{ usuario.email_remitente if usuario else '' }}" placeholder="pedro@familiazaragoza.com">
<div class="form-text">Con que correo salen los mails que envia este usuario.</div>
</div>
<div class="col-md-6">
<label class="form-label">Nombre remitente</label>
<input name="nombre_remitente" class="form-control" value="{{ usuario.nombre_remitente if usuario else '' }}" placeholder="Pedro - Familia Zaragoza">
<div class="form-text">Es lo que ve el cliente en "De:".</div>
</div>
''' + buscar2
        contenido = contenido.replace(buscar2, nuevo2, 1)
    else:
        nuevo2 = '</div>\n<div class="col-12 mt-3"><hr><h6 class="text-muted small">Remitente de email</h6></div>\n<div class="col-md-6"><label class="form-label">Email remitente</label><input name="email_remitente" type="email" class="form-control" value="{{ usuario.email_remitente if usuario else \'\' }}" placeholder="pedro@familiazaragoza.com"><div class="form-text">Con que correo salen los mails que envia este usuario.</div></div>\n<div class="col-md-6"><label class="form-label">Nombre remitente</label><input name="nombre_remitente" class="form-control" value="{{ usuario.nombre_remitente if usuario else \'\' }}" placeholder="Pedro - Familia Zaragoza"><div class="form-text">Es lo que ve el cliente en "De:".</div></div>\n{% if usuario %}<div class="col-12"><div class="form-check">'
        contenido = contenido.replace(buscar2, nuevo2, 1)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade39] campos de remitente agregados a usuarios/form.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app39; app39.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 39: Emails con remitente por vendedor + correo manual (U34) ===")
    migrar()
    escribir('app39.py', APP39_PY)
    escribir('templates/emails/nuevo.html', EMAILS_NUEVO)
    escribir('templates/emails/historial.html', EMAILS_HISTORIAL)
    patch_ventas_detalle()
    patch_detalle_route()
    patch_usuarios_form()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app39.py)")


if __name__ == '__main__':
    main()