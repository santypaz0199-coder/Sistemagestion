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
    print(f"[upgrade44] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade44] sin DB."); return
    conn = sqlite3.connect(db)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    if 'foto_perfil' not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN foto_perfil TEXT")
        print("[upgrade44] + usuarios.foto_perfil")
    if 'telefono' not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN telefono TEXT")
        print("[upgrade44] + usuarios.telefono")

    # Config: logo empresa
    if not conn.execute("SELECT clave FROM configuracion WHERE clave='empresa_logo'").fetchone():
        conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('empresa_logo', '')")
        print("[upgrade44] + config empresa_logo")

    conn.commit(); conn.close()


APP44_PY = r'''
import os
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app43 import app
from app import admin_required
from database import get_db

BASE = os.path.dirname(os.path.abspath(__file__))
PERFILES_DIR = os.path.join(BASE, 'uploads', 'perfiles')
os.makedirs(PERFILES_DIR, exist_ok=True)
LOGOS_DIR = os.path.join(BASE, 'uploads', 'logos')
os.makedirs(LOGOS_DIR, exist_ok=True)

EXT_IMG = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'}
MAX_SIZE = 3 * 1024 * 1024  # 3 MB


def _guardar_imagen(file, carpeta):
    if not file or not file.filename:
        return None, None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in EXT_IMG:
        return None, f'Formato no permitido. Usa: {", ".join(EXT_IMG)}'
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE:
        return None, 'La imagen supera 3 MB.'
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre = f"{timestamp}_{secure_filename(file.filename)}"
    file.save(os.path.join(carpeta, nombre))
    return nombre, None


@app.route('/api/avatar/<path:nombre>')
@login_required
def ver_avatar(nombre):
    ruta = os.path.join(PERFILES_DIR, secure_filename(nombre))
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta)


@app.route('/api/logo-empresa')
@login_required
def ver_logo_empresa():
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_logo'").fetchone()
    conn.close()
    if not row or not row['valor']:
        abort(404)
    ruta = os.path.join(LOGOS_DIR, secure_filename(row['valor']))
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta)


# ===== Mi Cuenta =====
@app.route('/mi-cuenta', methods=['GET', 'POST'])
@login_required
def mi_cuenta_v3():
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (current_user.id,)).fetchone()

    if request.method == 'POST':
        accion = request.form.get('accion', 'perfil')

        if accion == 'perfil':
            nombre = request.form.get('nombre', '').strip()
            telefono = request.form.get('telefono', '').strip()
            email = request.form.get('email', '').strip().lower()

            if not nombre:
                conn.close(); flash('El nombre es obligatorio.', 'error')
                return redirect(url_for('mi_cuenta'))
            if not email or '@' not in email:
                conn.close(); flash('Email invalido.', 'error')
                return redirect(url_for('mi_cuenta'))
            # Verificar que el nuevo email no este en uso por otro
            existe = conn.execute("SELECT id FROM usuarios WHERE lower(email)=? AND id!=?", (email, current_user.id)).fetchone()
            if existe:
                conn.close(); flash('Ese email ya esta en uso por otro usuario.', 'error')
                return redirect(url_for('mi_cuenta'))

            foto_nombre = usuario['foto_perfil']
            # Eliminar foto si lo piden
            if request.form.get('eliminar_foto') == '1':
                if foto_nombre:
                    try: os.remove(os.path.join(PERFILES_DIR, foto_nombre))
                    except Exception: pass
                foto_nombre = None
            # Nueva foto
            nueva_foto, err = _guardar_imagen(request.files.get('foto'), PERFILES_DIR)
            if err:
                conn.close(); flash(err, 'error')
                return redirect(url_for('mi_cuenta'))
            if nueva_foto:
                if foto_nombre:
                    try: os.remove(os.path.join(PERFILES_DIR, foto_nombre))
                    except Exception: pass
                foto_nombre = nueva_foto

            conn.execute("""UPDATE usuarios SET nombre=?, telefono=?, email=?, foto_perfil=? WHERE id=?""",
                         (nombre, telefono or None, email, foto_nombre, current_user.id))
            conn.commit(); conn.close()
            flash('Perfil actualizado. Cerra y volve a entrar si cambiaste el email.', 'success')
            return redirect(url_for('mi_cuenta'))

        elif accion == 'password':
            actual = request.form.get('actual', '')
            nueva = request.form.get('nueva', '')
            confirmar = request.form.get('confirmar', '')
            if not check_password_hash(usuario['password_hash'], actual):
                conn.close(); flash('La contrasena actual no es correcta.', 'error')
                return redirect(url_for('mi_cuenta'))
            if len(nueva) < 6:
                conn.close(); flash('La nueva contrasena debe tener al menos 6 caracteres.', 'error')
                return redirect(url_for('mi_cuenta'))
            if nueva != confirmar:
                conn.close(); flash('Las contrasenas no coinciden.', 'error')
                return redirect(url_for('mi_cuenta'))
            conn.execute("UPDATE usuarios SET password_hash=? WHERE id=?",
                         (generate_password_hash(nueva), current_user.id))
            conn.commit(); conn.close()
            flash('Contrasena actualizada.', 'success')
            return redirect(url_for('mi_cuenta'))

    conn.close()
    return render_template('mi_cuenta.html', usuario=dict(usuario))


app.view_functions['mi_cuenta'] = mi_cuenta_v3


# ===== Config: Logo empresa =====
def configuracion_firma_v2():
    conn = get_db()
    if request.method == 'POST':
        for k in ['firma_email', 'empresa_nombre', 'empresa_telefono', 'empresa_web', 'empresa_email']:
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                         "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
                         (k, request.form.get(k, '')))
        # Logo
        logo_actual_row = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_logo'").fetchone()
        logo_actual = logo_actual_row['valor'] if logo_actual_row else None

        if request.form.get('eliminar_logo') == '1':
            if logo_actual:
                try: os.remove(os.path.join(LOGOS_DIR, logo_actual))
                except Exception: pass
            conn.execute("UPDATE configuracion SET valor='' WHERE clave='empresa_logo'")
            flash('Logo eliminado.', 'success')
        else:
            nuevo_logo, err = _guardar_imagen(request.files.get('logo'), LOGOS_DIR)
            if err:
                conn.close(); flash(err, 'error')
                return redirect(url_for('configuracion_firma'))
            if nuevo_logo:
                if logo_actual:
                    try: os.remove(os.path.join(LOGOS_DIR, logo_actual))
                    except Exception: pass
                conn.execute("UPDATE configuracion SET valor=? WHERE clave='empresa_logo'", (nuevo_logo,))
                flash('Logo actualizado.', 'success')

        conn.commit(); conn.close()
        flash('Configuracion guardada.', 'success')
        return redirect(url_for('configuracion_firma'))

    cfg = {}
    for k in ['firma_email', 'empresa_nombre', 'empresa_telefono', 'empresa_web', 'empresa_email', 'empresa_logo']:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
        cfg[k] = row['valor'] if row else ''
    conn.close()
    return render_template('configuracion/firma.html', cfg=cfg, tiene_logo=bool(cfg.get('empresa_logo')))


app.view_functions['configuracion_firma'] = configuracion_firma_v2


# ===== Vista de impresion: incluir logo =====
@app.context_processor
def _ctx_logo():
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_logo'").fetchone()
    conn.close()
    return {'empresa_logo_nombre': row['valor'] if row and row['valor'] else None}


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


MI_CUENTA_HTML = r'''{% extends "base.html" %}
{% block title %}Mi cuenta{% endblock %}
{% block content %}
<h4 class="mb-4">Mi cuenta</h4>

<div class="row g-3">
<!-- Columna izquierda: foto -->
<div class="col-md-3">
<div class="card shadow-sm"><div class="card-body text-center">
{% if usuario.foto_perfil %}
<img src="{{ url_for('ver_avatar', nombre=usuario.foto_perfil) }}" style="width:120px;height:120px;border-radius:50%;object-fit:cover;border:3px solid #e8ecf3;">
{% else %}
<div style="width:120px;height:120px;border-radius:50%;background:#eef2ff;color:#3b5bdb;display:inline-flex;align-items:center;justify-content:center;font-size:2.5rem;font-weight:700;border:3px solid #e8ecf3;">
{{ usuario.nombre[0]|upper if usuario.nombre else 'U' }}
</div>
{% endif %}
<div class="mt-3">
<div class="fw-semibold">{{ usuario.nombre }}</div>
<div class="small text-muted">{{ usuario.email }}</div>
<div class="mt-2"><span class="badge bg-secondary">{{ usuario.rol }}</span></div>
</div>
</div></div>
</div>

<!-- Columna derecha: forms -->
<div class="col-md-9">

<!-- Datos personales -->
<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-person"></i> Datos personales</h6>
<form method="post" enctype="multipart/form-data">
<input type="hidden" name="accion" value="perfil">
<div class="row g-3">
<div class="col-md-6">
<label class="form-label">Nombre *</label>
<input name="nombre" class="form-control" required value="{{ usuario.nombre }}">
</div>
<div class="col-md-6">
<label class="form-label">Email de login *</label>
<input type="email" name="email" class="form-control" required value="{{ usuario.email }}">
<div class="form-text">Si lo cambias, tenes que volver a iniciar sesion.</div>
</div>
<div class="col-md-6">
<label class="form-label">Telefono personal</label>
<input name="telefono" class="form-control" value="{{ usuario.telefono or '' }}" placeholder="+54 9 11 1234-5678">
<div class="form-text">Solo visible para el equipo.</div>
</div>
<div class="col-md-6">
<label class="form-label">Foto de perfil</label>
<input type="file" name="foto" class="form-control" accept="image/*">
<div class="form-text">JPG, PNG, WEBP o GIF. Max 3 MB.</div>
</div>
{% if usuario.foto_perfil %}
<div class="col-12">
<div class="form-check">
<input class="form-check-input" type="checkbox" name="eliminar_foto" value="1" id="eliminar_foto">
<label class="form-check-label small text-danger" for="eliminar_foto">Eliminar foto actual</label>
</div>
</div>
{% endif %}
</div>
<div class="mt-3"><button class="btn btn-dark">Guardar cambios</button></div>
</form>
</div></div>

<!-- Cambio de contraseña -->
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-key"></i> Cambiar contrasena</h6>
<form method="post">
<input type="hidden" name="accion" value="password">
<div class="row g-3">
<div class="col-md-4">
<label class="form-label">Contrasena actual *</label>
<input type="password" name="actual" class="form-control" required>
</div>
<div class="col-md-4">
<label class="form-label">Nueva (min 6) *</label>
<input type="password" name="nueva" class="form-control" required>
</div>
<div class="col-md-4">
<label class="form-label">Confirmar nueva *</label>
<input type="password" name="confirmar" class="form-control" required>
</div>
</div>
<div class="mt-3"><button class="btn btn-outline-dark">Actualizar contrasena</button></div>
</form>
</div></div>

</div>
</div>
{% endblock %}
'''


CONFIG_FIRMA_HTML = r'''{% extends "base.html" %}
{% block title %}Firma y datos empresa{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Firma, datos de empresa y logo</h4>
<a href="{{ url_for('configuracion') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="card shadow-sm"><div class="card-body">
<form method="post" enctype="multipart/form-data">
<div class="row g-3">

<div class="col-md-4">
<label class="form-label">Nombre empresa</label>
<input name="empresa_nombre" class="form-control" value="{{ cfg.empresa_nombre or 'Familia Zaragoza ®' }}">
</div>
<div class="col-md-4">
<label class="form-label">Telefono</label>
<input name="empresa_telefono" class="form-control" value="{{ cfg.empresa_telefono }}">
</div>
<div class="col-md-4">
<label class="form-label">Web</label>
<input name="empresa_web" class="form-control" value="{{ cfg.empresa_web }}">
</div>
<div class="col-md-6">
<label class="form-label">Email atencion al cliente</label>
<input name="empresa_email" class="form-control" value="{{ cfg.empresa_email or 'hola@familiazaragoza.com' }}">
</div>
<div class="col-12">
<label class="form-label">Firma de emails</label>
<textarea name="firma_email" rows="5" class="form-control">{{ cfg.firma_email }}</textarea>
</div>

<div class="col-12 mt-3"><hr><h6 class="text-muted small">Logo de la empresa</h6></div>
<div class="col-12">
<div class="d-flex align-items-start gap-3">
{% if tiene_logo %}
<div class="text-center">
<img src="{{ url_for('ver_logo_empresa') }}" style="max-width:180px; max-height:120px; border:1px solid #e8ecf3; border-radius:8px; padding:8px; background:#fff;">
<div class="form-check mt-2">
<input class="form-check-input" type="checkbox" name="eliminar_logo" value="1" id="eliminar_logo">
<label class="form-check-label small text-danger" for="eliminar_logo">Eliminar logo</label>
</div>
</div>
{% else %}
<div style="width:180px;height:120px;border:2px dashed #e8ecf3;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#9ca3af;">
<i class="bi bi-image fs-1"></i>
</div>
{% endif %}
<div class="flex-grow-1">
<input type="file" name="logo" class="form-control" accept="image/*">
<div class="form-text">PNG o SVG preferentemente (fondo transparente). Max 3 MB.</div>
<div class="form-text">Se usa en impresiones, PDFs y emails.</div>
</div>
</div>
</div>

</div>
<div class="mt-4"><button class="btn btn-dark">Guardar todo</button></div>
</form>
</div></div>
{% endblock %}
'''


def patch_base_html():
    """Avatar en el sidebar."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade44] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'user.foto_perfil' in contenido and 'ver_avatar' in contenido:
        print("[upgrade44] avatar ya estaba"); return

    # Reemplazar el bloque de icono+nbombre por avatar dinámico
    buscar = '''<div class="d-flex align-items-center gap-2 mb-2"><i class="bi bi-person-circle fs-5 text-secondary"></i><div><div class="text-white">{{ current_user.nombre }}</div><small class="text-secondary">{{ 'Admin' if current_user.es_admin else 'Vendedor' }}</small></div></div>'''

    nuevo = '''<div class="d-flex align-items-center gap-2 mb-2">
{% set u = current_user %}
{% if u.foto_perfil is defined and u.foto_perfil %}
<img src="{{ url_for('ver_avatar', nombre=u.foto_perfil) }}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,255,255,.2);">
{% else %}
<i class="bi bi-person-circle fs-5 text-secondary"></i>
{% endif %}
<div>
<div class="text-white">{{ u.nombre }}</div>
<small class="text-secondary">{{ u.rol|capitalize if u.rol else 'Usuario' }}</small>
</div>
</div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade44] avatar dinamico agregado al sidebar")
    else:
        print("[upgrade44] ADVERTENCIA: no se encontro el bloque de usuario en el sidebar")


def patch_imprimir():
    """Mostrar logo en la vista de impresion si existe."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'imprimir.html')
    if not os.path.exists(ruta):
        print("[upgrade44] no existe ventas/imprimir.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'empresa_logo_nombre' in contenido:
        print("[upgrade44] imprimir ya tiene logo dinamico"); return

    buscar = '''<div class="empresa">
<h1>{{ empresa.nombre }}</h1>'''

    nuevo = '''<div class="empresa">
{% if empresa_logo_nombre %}
<div style="margin-bottom:8px;"><img src="{{ url_for('ver_logo_empresa') }}" style="max-height:60px; max-width:180px;"></div>
{% endif %}
<h1>{{ empresa.nombre }}</h1>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade44] logo agregado a la impresion")
    else:
        print("[upgrade44] ADVERTENCIA: no se encontro el bloque de empresa en imprimir")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app44; app44.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 44: Mi Cuenta extendida + logo empresa (U42) ===")
    migrar()
    escribir('app44.py', APP44_PY)
    escribir('templates/mi_cuenta.html', MI_CUENTA_HTML)
    escribir('templates/configuracion/firma.html', CONFIG_FIRMA_HTML)
    patch_base_html()
    patch_imprimir()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app44.py)")


if __name__ == '__main__':
    main()