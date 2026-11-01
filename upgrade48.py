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
    print(f"[upgrade48] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade48] sin DB."); return
    conn = sqlite3.connect(db)

    # Tabla remitentes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remitentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            activo INTEGER DEFAULT 1,
            creado TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("[upgrade48] tabla remitentes OK")

    # Migrar los remitentes que ya estan configurados
    existentes = []
    for clave in ('empresa_email', 'smtp_remitente_email'):
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,)).fetchone()
        if row and row[0]:
            existentes.append(row[0])

    # Agregar los de cada usuario
    usuarios_r = conn.execute("SELECT email_remitente FROM usuarios WHERE email_remitente IS NOT NULL AND email_remitente != ''").fetchall()
    for r in usuarios_r:
        if r[0]:
            existentes.append(r[0])

    # Insertar los que falten
    agregados = 0
    for email in set(existentes):
        if not email: continue
        ya = conn.execute("SELECT id FROM remitentes WHERE lower(email)=lower(?)", (email,)).fetchone()
        if not ya:
            # Determinar nombre segun de donde venga
            if email.lower().startswith('hola@'):
                nombre = 'Familia Zaragoza (Atencion)'
            elif email.lower().startswith('notificacion@'):
                nombre = 'Familia Zaragoza (Notificaciones)'
            else:
                usuario = conn.execute("SELECT nombre FROM usuarios WHERE lower(email_remitente)=lower(?)", (email,)).fetchone()
                nombre = usuario[0] if usuario else email.split('@')[0].capitalize()
            conn.execute("INSERT INTO remitentes (email, nombre, activo) VALUES (?, ?, 1)", (email, nombre))
            agregados += 1
    if agregados:
        print(f"[upgrade48] {agregados} remitentes migrados")

    # Claves nuevas de config
    for k, default in [
        ('remitente_atencion_email', 'hola@familiazaragoza.com'),
        ('remitente_notificaciones_email', 'notificacion@familiazaragoza.com'),
        ('remitente_campanas_email', 'hola@familiazaragoza.com'),
    ]:
        if not conn.execute("SELECT clave FROM configuracion WHERE clave=?", (k,)).fetchone():
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?)", (k, default))
            print(f"[upgrade48] + config {k}")

    conn.commit(); conn.close()


APP48_PY = r'''
import os
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app45 import app
from app import admin_required
from database import get_db
from app4 import enviar_email, get_config


def _remitentes_activos(conn):
    return conn.execute("SELECT * FROM remitentes WHERE activo=1 ORDER BY email").fetchall()


@app.route('/configuracion/remitentes', methods=['GET', 'POST'])
@login_required
@admin_required
def configuracion_remitentes():
    conn = get_db()
    if request.method == 'POST':
        accion = request.form.get('accion', 'config')

        if accion == 'agregar':
            email = request.form.get('email', '').strip().lower()
            nombre = request.form.get('nombre', '').strip()
            if not email or '@' not in email or not nombre:
                conn.close(); flash('Email y nombre son obligatorios.', 'error')
                return redirect(url_for('configuracion_remitentes'))
            ya = conn.execute("SELECT id FROM remitentes WHERE lower(email)=?", (email,)).fetchone()
            if ya:
                conn.close(); flash('Ese email ya esta en la lista.', 'error')
                return redirect(url_for('configuracion_remitentes'))
            conn.execute("INSERT INTO remitentes (email, nombre, activo) VALUES (?, ?, 1)", (email, nombre))
            conn.commit(); conn.close()
            flash('Remitente agregado.', 'success')
            return redirect(url_for('configuracion_remitentes'))

        elif accion == 'toggle':
            rid = int(request.form.get('remitente_id', 0))
            conn.execute("UPDATE remitentes SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (rid,))
            conn.commit(); conn.close()
            flash('Estado actualizado.', 'success')
            return redirect(url_for('configuracion_remitentes'))

        elif accion == 'eliminar':
            rid = int(request.form.get('remitente_id', 0))
            conn.execute("DELETE FROM remitentes WHERE id=?", (rid,))
            conn.commit(); conn.close()
            flash('Remitente eliminado.', 'success')
            return redirect(url_for('configuracion_remitentes'))

        elif accion == 'config':
            # Guardar default para cada proposito + smtp
            claves = ['remitente_atencion_email', 'remitente_notificaciones_email', 'remitente_campanas_email']
            for k in claves:
                v = request.form.get(k, '').strip()
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (k, v))

            # Actualizar nombres de remitentes del sistema
            for key in ['remitente_atencion_nombre', 'remitente_notificaciones_nombre', 'remitente_campanas_nombre']:
                v = request.form.get(key, '').strip()
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (key, v))

            # SMTP
            for k in ['smtp_host', 'smtp_puerto', 'smtp_usuario', 'smtp_password', 'smtp_seguridad']:
                v = request.form.get(k, '').strip()
                if k == 'smtp_password' and not v:
                    continue
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (k, v))

            # Actualizar el default smtp_remitente_email para que coincida con notificaciones
            notif = request.form.get('remitente_notificaciones_email', '').strip()
            notif_nombre = request.form.get('remitente_notificaciones_nombre', '').strip()
            if notif:
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('smtp_remitente_email', ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (notif,))
                if notif_nombre:
                    conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('smtp_remitente_nombre', ?) "
                                 "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (notif_nombre,))

            # Actualizar empresa_email (atencion al cliente)
            aten = request.form.get('remitente_atencion_email', '').strip()
            aten_nombre = request.form.get('remitente_atencion_nombre', '').strip()
            if aten:
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('empresa_email', ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (aten,))
                if aten_nombre:
                    conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('empresa_nombre', ?) "
                                 "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (aten_nombre,))

            conn.commit(); conn.close()
            flash('Configuracion de remitentes guardada.', 'success')
            return redirect(url_for('configuracion_remitentes'))

        elif accion == 'probar':
            destino = request.form.get('probar_destino', '').strip()
            from_email = request.form.get('probar_desde', '').strip()
            from_nombre = request.form.get('probar_nombre', '').strip() or 'Familia Zaragoza'
            if not destino:
                conn.close(); flash('Ingresa el email de destino.', 'error')
                return redirect(url_for('configuracion_remitentes'))

            # Override temporal del remitente para la prueba
            remitente_override = {'email': from_email, 'nombre': from_nombre} if from_email else None
            ok, msg = _enviar_con_remitente(destino, 'Prueba de envio - Sistema FZ',
                                             'Este es un email de prueba del sistema.\n\nSi lo recibis, todo funciona OK.',
                                             remitente_override=remitente_override)
            conn.close()
            flash(('OK: ' + msg) if ok else msg, 'success' if ok else 'error')
            return redirect(url_for('configuracion_remitentes'))

    # GET: cargar todo para mostrar
    remitentes = _remitentes_activos(conn)
    remitentes_inactivos = conn.execute("SELECT * FROM remitentes WHERE activo=0 ORDER BY email").fetchall()

    cfg = {}
    for k in ['smtp_host', 'smtp_puerto', 'smtp_usuario', 'smtp_seguridad',
              'remitente_atencion_email', 'remitente_notificaciones_email',
              'remitente_campanas_email', 'remitente_atencion_nombre',
              'remitente_notificaciones_nombre', 'remitente_campanas_nombre']:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
        cfg[k] = row['valor'] if row and row['valor'] else ''

    smtp_pass = conn.execute("SELECT valor FROM configuracion WHERE clave='smtp_password'").fetchone()
    cfg['smtp_password_set'] = bool(smtp_pass and smtp_pass['valor'])

    conn.close()
    return render_template('configuracion/remitentes.html',
                           remitentes=remitentes,
                           remitentes_inactivos=remitentes_inactivos,
                           cfg=cfg)


def _enviar_con_remitente(destinatario, asunto, cuerpo, remitente_override=None, adjuntos=None):
    from app39 import _enviar_con_remitente as env
    return env(destinatario, asunto, cuerpo, remitente_override, adjuntos)


# ===== Actualizar rutas de envio para respetar las nuevas configuraciones =====
def _get_remitente_por_proposito(conn, proposito):
    """proposito: 'atencion', 'notificaciones', 'campanas'"""
    clave_email = f'remitente_{proposito}_email'
    clave_nombre = f'remitente_{proposito}_nombre'
    email = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave_email,)).fetchone()
    nombre = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave_nombre,)).fetchone()
    return {
        'email': email['valor'] if email else None,
        'nombre': nombre['valor'] if nombre else 'Familia Zaragoza',
    }


app.view_functions['configuracion_remitentes'] = configuracion_remitentes


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


CONFIG_REMITENTES_HTML = r'''{% extends "base.html" %}
{% block title %}Remitentes{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Remitentes y SMTP</h4>
<div class="text-muted small">Configura todos los correos que puede usar el sistema para enviar</div>
</div>
<a href="{{ url_for('configuracion') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">

<!-- Columna izquierda: lista de remitentes + agregar -->
<div class="col-md-5">

<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-envelope-plus"></i> Agregar remitente</h6>
<form method="post">
<input type="hidden" name="accion" value="agregar">
<div class="mb-2">
<label class="form-label small">Email *</label>
<input name="email" type="email" class="form-control form-control-sm" required placeholder="pedro@familiazaragoza.com">
<div class="form-text">El correo debe estar confirmado en Mailrelay.</div>
</div>
<div class="mb-2">
<label class="form-label small">Nombre visible *</label>
<input name="nombre" class="form-control form-control-sm" required placeholder="Pedro - Familia Zaragoza">
<div class="form-text">Lo que ve el cliente en "De:".</div>
</div>
<button class="btn btn-dark btn-sm w-100">Agregar remitente</button>
</form>
</div></div>

<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-list-check"></i> Remitentes activos</h6>
{% if remitentes %}
<table class="table table-sm mb-0">
<tbody>
{% for r in remitentes %}
<tr>
<td>
<div class="fw-semibold small">{{ r.nombre }}</div>
<div class="text-muted" style="font-size:.75rem;">{{ r.email }}</div>
</td>
<td class="text-end text-nowrap">
<form method="post" class="d-inline">
<input type="hidden" name="accion" value="toggle">
<input type="hidden" name="remitente_id" value="{{ r.id }}">
<button class="btn btn-sm btn-outline-secondary" title="Desactivar"><i class="bi bi-pause"></i></button>
</form>
<form method="post" class="d-inline" onsubmit="return confirm('Eliminar este remitente?')">
<input type="hidden" name="accion" value="eliminar">
<input type="hidden" name="remitente_id" value="{{ r.id }}">
<button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
</form>
</td>
</tr>
{% endfor %}
</tbody>
</table>
{% else %}
<p class="text-muted small mb-0">No hay remitentes activos.</p>
{% endif %}

{% if remitentes_inactivos %}
<hr class="my-3">
<div class="small text-muted mb-2">Inactivos:</div>
{% for r in remitentes_inactivos %}
<div class="d-flex justify-content-between align-items-center mb-1">
<div>
<span class="text-muted small">{{ r.nombre }} &lt;{{ r.email }}&gt;</span>
</div>
<form method="post" class="d-inline">
<input type="hidden" name="accion" value="toggle">
<input type="hidden" name="remitente_id" value="{{ r.id }}">
<button class="btn btn-sm btn-outline-success py-0 px-2"><i class="bi bi-play"></i></button>
</form>
</div>
{% endfor %}
{% endif %}
</div></div>

</div>

<!-- Columna derecha: config de propositos + SMTP -->
<div class="col-md-7">

<form method="post">
<input type="hidden" name="accion" value="config">

<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-tag"></i> Remitente para cada proposito</h6>
<div class="form-text mb-3">Configura que correo se usa en cada tipo de envio.</div>

<div class="mb-3">
<label class="form-label small fw-semibold">📧 Notificaciones automaticas</label>
<div class="row g-2">
<div class="col-md-7">
<select name="remitente_notificaciones_email" class="form-select form-select-sm">
{% for r in remitentes %}
<option value="{{ r.email }}" {% if cfg.remitente_notificaciones_email == r.email %}selected{% endif %}>{{ r.email }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-5">
<input name="remitente_notificaciones_nombre" class="form-control form-control-sm" value="{{ cfg.remitente_notificaciones_nombre or 'Familia Zaragoza' }}" placeholder="Nombre visible">
</div>
</div>
<div class="form-text">Se usa para: pagos acreditados, envios, entregas, facturas.</div>
</div>

<div class="mb-3">
<label class="form-label small fw-semibold">📢 Campañas masivas</label>
<div class="row g-2">
<div class="col-md-7">
<select name="remitente_campanas_email" class="form-select form-select-sm">
{% for r in remitentes %}
<option value="{{ r.email }}" {% if cfg.remitente_campanas_email == r.email %}selected{% endif %}>{{ r.email }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-5">
<input name="remitente_campanas_nombre" class="form-control form-control-sm" value="{{ cfg.remitente_campanas_nombre or 'Familia Zaragoza' }}" placeholder="Nombre visible">
</div>
</div>
<div class="form-text">Se usa para: promociones, novedades, ofertas.</div>
</div>

<div class="mb-0">
<label class="form-label small fw-semibold">🏢 Atencion al cliente</label>
<div class="row g-2">
<div class="col-md-7">
<select name="remitente_atencion_email" class="form-select form-select-sm">
{% for r in remitentes %}
<option value="{{ r.email }}" {% if cfg.remitente_atencion_email == r.email %}selected{% endif %}>{{ r.email }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-5">
<input name="remitente_atencion_nombre" class="form-control form-control-sm" value="{{ cfg.remitente_atencion_nombre or 'Familia Zaragoza' }}" placeholder="Nombre visible">
</div>
</div>
<div class="form-text">Se muestra en la firma, impresiones y emails personales del admin.</div>
</div>
</div></div>

<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-hdd-network"></i> Servidor SMTP (Mailrelay)</h6>
<div class="row g-2">
<div class="col-md-8">
<label class="form-label small">Host *</label>
<input name="smtp_host" class="form-control form-control-sm" value="{{ cfg.smtp_host }}" placeholder="smtp1.s.ipzmarketing.com">
</div>
<div class="col-md-4">
<label class="form-label small">Puerto</label>
<input name="smtp_puerto" class="form-control form-control-sm" value="{{ cfg.smtp_puerto or '587' }}">
</div>
<div class="col-md-6">
<label class="form-label small">Usuario SMTP *</label>
<input name="smtp_usuario" class="form-control form-control-sm" value="{{ cfg.smtp_usuario }}">
</div>
<div class="col-md-6">
<label class="form-label small">Contraseña SMTP *</label>
<input type="password" name="smtp_password" class="form-control form-control-sm" placeholder="{% if cfg.smtp_password_set %}•••••••• (dejar vacio para no cambiar){% endif %}">
</div>
<div class="col-md-6">
<label class="form-label small">Cifrado</label>
<select name="smtp_seguridad" class="form-select form-select-sm">
<option value="tls" {% if cfg.smtp_seguridad == 'tls' or not cfg.smtp_seguridad %}selected{% endif %}>STARTTLS (recomendado)</option>
<option value="ssl" {% if cfg.smtp_seguridad == 'ssl' %}selected{% endif %}>SSL/TLS</option>
</select>
</div>
</div>
</div></div>

<button class="btn btn-dark w-100"><i class="bi bi-save"></i> Guardar configuracion</button>
</form>

<!-- Probar conexion -->
<div class="card shadow-sm mt-3"><div class="card-body">
<h6 class="mb-2"><i class="bi bi-send-check"></i> Probar envio</h6>
<p class="small text-muted mb-2">Manda un email de prueba con la configuracion guardada.</p>
<form method="post">
<input type="hidden" name="accion" value="probar">
<div class="row g-2">
<div class="col-md-6">
<label class="form-label small">Enviar a *</label>
<input name="probar_destino" type="email" class="form-control form-control-sm" required placeholder="tu@email.com">
</div>
<div class="col-md-6">
<label class="form-label small">Desde</label>
<select name="probar_desde" class="form-select form-select-sm">
{% for r in remitentes %}
<option value="{{ r.email }}" {% if cfg.remitente_notificaciones_email == r.email %}selected{% endif %}>{{ r.email }}</option>
{% endfor %}
</select>
</div>
</div>
<button class="btn btn-outline-primary btn-sm mt-2"><i class="bi bi-send"></i> Enviar prueba</button>
</form>
</div></div>

</div>
</div>
{% endblock %}
'''


def patch_configuracion_index():
    ruta = os.path.join(BASE, 'templates', 'configuracion', 'index.html')
    if not os.path.exists(ruta):
        print("[upgrade48] no existe configuracion/index.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'configuracion_remitentes' in contenido:
        print("[upgrade48] ya existe el link de remitentes"); return

    buscar = '<div class="col-md-4"><a href="{{ url_for(\'configuracion_smtp\') }}"'
    if buscar not in contenido:
        print("[upgrade48] no se encontro la tarjeta de SMTP para insertar antes"); return

    nuevo = '''<div class="col-md-4"><a href="{{ url_for('configuracion_remitentes') }}" class="text-decoration-none"><div class="card shadow-sm h-100" style="border-left:3px solid #8b5cf6;"><div class="card-body">
<i class="bi bi-envelope-paper fs-2" style="color:#8b5cf6;"></i>
<h6 class="mt-2">Remitentes y SMTP</h6>
<p class="text-muted small mb-0">Todos los correos en un solo lugar + servidor SMTP.</p>
</div></div></a></div>

''' + buscar

    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade48] tarjeta Remitentes agregada a Configuracion")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 48: Pantalla unificada Remitentes + SMTP (U48) ===")
    migrar()
    escribir('app48.py', APP48_PY)
    escribir('templates/configuracion/remitentes.html', CONFIG_REMITENTES_HTML)
    patch_configuracion_index()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app48.py)")


if __name__ == '__main__':
    main()