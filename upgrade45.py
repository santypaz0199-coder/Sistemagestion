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
    print(f"[upgrade45] escrito: {relpath}")


PERMISOS_DISPONIBLES = [
    ('clientes', 'Clientes', 'bi-people'),
    ('ventas', 'Ventas', 'bi-cart'),
    ('productos', 'Productos', 'bi-box-seam'),
    ('gastos', 'Gastos', 'bi-cash-coin'),
    ('reportes', 'Reportes', 'bi-graph-up'),
    ('objetivos', 'Objetivos', 'bi-bullseye'),
    ('emails', 'Emails', 'bi-envelope'),
    ('campanas', 'Campañas', 'bi-megaphone'),
    ('solicitudes', 'Solicitudes', 'bi-inbox'),
    ('catalogos', 'Catálogos', 'bi-tags'),
    ('usuarios', 'Usuarios', 'bi-person-badge'),
    ('configuracion', 'Configuración', 'bi-gear'),
]


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade45] sin DB."); return
    conn = sqlite3.connect(db)

    # 1. Columna solo_propio en usuarios
    cols = [r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    if 'solo_propio' not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN solo_propio INTEGER DEFAULT 0")
        print("[upgrade45] + usuarios.solo_propio")

    # 2. Tabla usuarios_permisos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_permisos (
            usuario_id INTEGER NOT NULL,
            modulo TEXT NOT NULL,
            PRIMARY KEY (usuario_id, modulo),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)
    print("[upgrade45] tabla usuarios_permisos OK")

    # 3. Migrar permisos: por cada usuario, copiar permisos de su rol actual
    usuarios = conn.execute("SELECT id, rol FROM usuarios").fetchall()
    migrados = 0
    for u in usuarios:
        uid = u[0]
        rol = u[1]
        # Si ya tiene permisos individuales, no tocar
        ya_tiene = conn.execute("SELECT COUNT(*) FROM usuarios_permisos WHERE usuario_id=?", (uid,)).fetchone()[0]
        if ya_tiene > 0:
            continue

        if rol == 'admin':
            conn.execute("UPDATE usuarios SET solo_propio=0 WHERE id=?", (uid,))
            # admin no necesita permisos individuales
        elif rol == 'vendedor':
            conn.execute("UPDATE usuarios SET solo_propio=1 WHERE id=?", (uid,))
            permisos = ['clientes', 'ventas', 'emails', 'campanas']
            for m in permisos:
                conn.execute("INSERT OR IGNORE INTO usuarios_permisos (usuario_id, modulo) VALUES (?, ?)", (uid, m))
        else:
            # Rol personalizado: copiar los permisos que tenia ese rol
            permisos_rol = conn.execute("SELECT modulo FROM roles_permisos WHERE rol_nombre=?", (rol,)).fetchall()
            for p in permisos_rol:
                conn.execute("INSERT OR IGNORE INTO usuarios_permisos (usuario_id, modulo) VALUES (?, ?)", (uid, p[0]))
            conn.execute("UPDATE usuarios SET solo_propio=0 WHERE id=?", (uid,))
        migrados += 1

    print(f"[upgrade45] {migrados} usuario(s) migrados con permisos individuales")

    # 4. Normalizar rol: dejar solo 'admin' o 'usuario'
    conn.execute("UPDATE usuarios SET rol='admin' WHERE rol='admin'")
    conn.execute("UPDATE usuarios SET rol='usuario' WHERE rol != 'admin'")
    print("[upgrade45] roles normalizados (admin / usuario)")

    conn.commit(); conn.close()


APP45_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash
from app44 import app
from app import admin_required, login_manager
from database import get_db


PERMISOS_DISPONIBLES = [
    ('clientes', 'Clientes', 'bi-people'),
    ('ventas', 'Ventas', 'bi-cart'),
    ('productos', 'Productos', 'bi-box-seam'),
    ('gastos', 'Gastos', 'bi-cash-coin'),
    ('reportes', 'Reportes', 'bi-graph-up'),
    ('objetivos', 'Objetivos', 'bi-bullseye'),
    ('emails', 'Emails', 'bi-envelope'),
    ('campanas', 'Campañas', 'bi-megaphone'),
    ('solicitudes', 'Solicitudes', 'bi-inbox'),
    ('catalogos', 'Catálogos', 'bi-tags'),
    ('usuarios', 'Usuarios', 'bi-person-badge'),
    ('configuracion', 'Configuración', 'bi-gear'),
]


class User_v3(UserMixin):
    def __init__(self, id, nombre, email, rol, permisos, solo_propio, foto_perfil=None):
        self.id = id
        self.nombre = nombre
        self.email = email
        self.rol = rol
        self.permisos = permisos or []
        self.solo_propio = solo_propio or 0
        self.foto_perfil = foto_perfil

    @property
    def es_admin(self):
        return self.rol == 'admin'

    @property
    def es_vendedor(self):
        return self.solo_propio == 1

    def puede(self, modulo):
        if self.es_admin:
            return True
        return modulo in self.permisos


@login_manager.user_loader
def load_user_v3(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE id=? AND activo=1", (user_id,)).fetchone()
    if not row:
        conn.close()
        return None
    permisos = []
    if row['rol'] != 'admin':
        ps = conn.execute("SELECT modulo FROM usuarios_permisos WHERE usuario_id=?", (user_id,)).fetchall()
        permisos = [p['modulo'] for p in ps]
    conn.close()
    return User_v3(row['id'], row['nombre'], row['email'], row['rol'],
                   permisos, row['solo_propio'], row['foto_perfil'])


# ===== CRUD de usuarios (con permisos individuales) =====
def _guardar_permisos(conn, uid, permisos):
    conn.execute("DELETE FROM usuarios_permisos WHERE usuario_id=?", (uid,))
    for m in permisos:
        if m in [p[0] for p in PERMISOS_DISPONIBLES]:
            conn.execute("INSERT OR IGNORE INTO usuarios_permisos (usuario_id, modulo) VALUES (?, ?)",
                         (uid, m))


@app.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def usuarios_nuevo_v3():
    conn = get_db()
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        rol = request.form.get('rol', 'usuario')
        solo_propio = 1 if request.form.get('solo_propio') else 0
        permisos = request.form.getlist('permisos')

        if rol not in ('admin', 'usuario'):
            rol = 'usuario'

        if not nombre or not email or not password:
            conn.close(); flash('Completa todos los campos.', 'error')
            return render_template('usuarios/form.html', usuario=None, valores=request.form,
                                   permisos_disponibles=PERMISOS_DISPONIBLES, permisos_actuales=[])
        if conn.execute("SELECT id FROM usuarios WHERE lower(email)=?", (email,)).fetchone():
            conn.close(); flash('Ya existe un usuario con ese email.', 'error')
            return render_template('usuarios/form.html', usuario=None, valores=request.form,
                                   permisos_disponibles=PERMISOS_DISPONIBLES, permisos_actuales=[])

        cur = conn.execute("""INSERT INTO usuarios (nombre,email,password_hash,rol,solo_propio)
            VALUES (?,?,?,?,?)""",
            (nombre, email, generate_password_hash(password), rol, solo_propio))
        nuevo_uid = cur.lastrowid
        if rol != 'admin':
            _guardar_permisos(conn, nuevo_uid, permisos)
        conn.commit(); conn.close()
        flash('Usuario creado.', 'success')
        return redirect(url_for('usuarios_lista'))

    conn.close()
    return render_template('usuarios/form.html', usuario=None, valores={},
                           permisos_disponibles=PERMISOS_DISPONIBLES, permisos_actuales=[])


@app.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def usuarios_editar_v4(id):
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
    if not usuario:
        conn.close(); flash('Usuario no encontrado.', 'error')
        return redirect(url_for('usuarios_lista'))

    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        email = request.form['email'].strip().lower()
        password = request.form.get('password', '').strip()
        rol = request.form.get('rol', 'usuario')
        solo_propio = 1 if request.form.get('solo_propio') else 0
        activo = 1 if request.form.get('activo') else 0
        email_r = request.form.get('email_remitente', '').strip()
        nombre_r = request.form.get('nombre_remitente', '').strip()
        permisos = request.form.getlist('permisos')

        if rol not in ('admin', 'usuario'):
            rol = 'usuario'

        existe = conn.execute("SELECT id FROM usuarios WHERE lower(email)=? AND id!=?", (email, id)).fetchone()
        if existe:
            conn.close(); flash('Email ya existe.', 'error')
            return redirect(url_for('usuarios_editar', id=id))

        if password:
            conn.execute("""UPDATE usuarios SET nombre=?,email=?,rol=?,activo=?,password_hash=?,
                email_remitente=?,nombre_remitente=?,solo_propio=? WHERE id=?""",
                (nombre, email, rol, activo, generate_password_hash(password),
                 email_r or None, nombre_r or None, solo_propio, id))
        else:
            conn.execute("""UPDATE usuarios SET nombre=?,email=?,rol=?,activo=?,
                email_remitente=?,nombre_remitente=?,solo_propio=? WHERE id=?""",
                (nombre, email, rol, activo, email_r or None, nombre_r or None, solo_propio, id))

        if rol == 'admin':
            conn.execute("DELETE FROM usuarios_permisos WHERE usuario_id=?", (id,))
        else:
            _guardar_permisos(conn, id, permisos)

        conn.commit(); conn.close()
        flash('Usuario actualizado.', 'success')
        return redirect(url_for('usuarios_lista'))

    ps = conn.execute("SELECT modulo FROM usuarios_permisos WHERE usuario_id=?", (id,)).fetchall()
    permisos_actuales = [p['modulo'] for p in ps]
    conn.close()
    return render_template('usuarios/form.html', usuario=dict(usuario), valores={},
                           permisos_disponibles=PERMISOS_DISPONIBLES,
                           permisos_actuales=permisos_actuales)


app.view_functions['usuarios_nuevo'] = usuarios_nuevo_v3
app.view_functions['usuarios_editar'] = usuarios_editar_v4


# ===== Eliminar la ruta /roles (redirige a usuarios) =====
def roles_redirect():
    return redirect(url_for('usuarios_lista'))

app.view_functions['roles_lista'] = roles_redirect


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


USUARIOS_FORM = r'''{% extends "base.html" %}
{% block title %}{{ 'Editar' if usuario else 'Nuevo' }} usuario{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if usuario else 'Nuevo' }} usuario</h4>
<a href="{{ url_for('usuarios_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

{% set v = valores if valores else (usuario if usuario else {}) %}
{% set es_admin_user = (v.get('rol') == 'admin') %}
{% set solo_propio_user = v.get('solo_propio') %}

<div class="card shadow-sm"><div class="card-body">
<form method="post" id="form-usuario">
<div class="row g-3">
<div class="col-md-6"><label class="form-label">Nombre *</label><input name="nombre" class="form-control" required value="{{ v.get('nombre') or '' }}"></div>
<div class="col-md-6"><label class="form-label">Email de login *</label><input type="email" name="email" class="form-control" required value="{{ v.get('email') or '' }}"></div>
<div class="col-md-6">
<label class="form-label">Contrasena {{ '(dejar vacio para no cambiar)' if usuario else '*' }}</label>
<input type="password" name="password" class="form-control" {% if not usuario %}required{% endif %}>
</div>
<div class="col-md-6">
<label class="form-label">Tipo de usuario *</label>
<select name="rol" id="rol-select" class="form-select" required onchange="toggleAdmin()">
<option value="usuario" {% if v.get('rol') == 'usuario' or not v.get('rol') %}selected{% endif %}>Usuario normal</option>
<option value="admin" {% if v.get('rol') == 'admin' %}selected{% endif %}>Admin (acceso total)</option>
</select>
</div>
</div>

<!-- Bloque: permisos (solo si NO es admin) -->
<div id="bloque-permisos" class="mt-4" {% if es_admin_user %}style="display:none;"{% endif %}>
<hr>
<h6 class="text-muted small mb-2"><i class="bi bi-shield-check"></i> Permisos de este usuario</h6>
<div class="form-text mb-3">Tilda los modulos que puede ver. El <strong>Dashboard</strong> siempre es visible.</div>

<div class="form-check border rounded p-2 mb-2" style="background:#fff8e6;">
<input class="form-check-input" type="checkbox" name="solo_propio" value="1" id="solo_propio" {% if solo_propio_user %}checked{% endif %}>
<label class="form-check-label" for="solo_propio">
<strong>Solo ve sus propios clientes y ventas</strong>
<div class="small text-muted">Como un vendedor: solo accede a lo que el mismo cargo. Si lo destildas, ve todos los datos a los que tiene permiso.</div>
</label>
</div>

<div class="row g-2">
{% for modulo, nombre, icono in permisos_disponibles %}
<div class="col-md-4">
<div class="form-check border rounded p-2">
<input class="form-check-input" type="checkbox" name="permisos" value="{{ modulo }}" id="perm-{{ modulo }}"
       {% if modulo in permisos_actuales %}checked{% endif %}>
<label class="form-check-label" for="perm-{{ modulo }}">
<i class="bi {{ icono }}"></i> {{ nombre }}
</label>
</div>
</div>
{% endfor %}
</div>
</div>

<!-- Bloque: admin -->
<div id="bloque-admin" class="mt-4" {% if not es_admin_user %}style="display:none;"{% endif %}>
<div class="alert alert-info py-2 small mb-0">
<i class="bi bi-info-circle"></i> El admin siempre tiene <strong>acceso total</strong> a todos los modulos y funciones.
</div>
</div>

<div class="row g-3 mt-4">
<div class="col-12"><hr><h6 class="text-muted small">Remitente de email</h6></div>
<div class="col-md-6">
<label class="form-label">Email remitente</label>
<input name="email_remitente" type="email" class="form-control" value="{{ v.get('email_remitente') or '' }}" placeholder="pedro@familiazaragoza.com">
<div class="form-text">Con que correo salen los mails que envia este usuario.</div>
</div>
<div class="col-md-6">
<label class="form-label">Nombre remitente</label>
<input name="nombre_remitente" class="form-control" value="{{ v.get('nombre_remitente') or '' }}" placeholder="Pedro - Familia Zaragoza">
</div>
{% if usuario %}
<div class="col-12">
<div class="form-check">
<input class="form-check-input" type="checkbox" name="activo" id="activo" {% if v.get('activo') %}checked{% endif %}>
<label class="form-check-label" for="activo">Usuario activo</label>
</div>
</div>
{% endif %}
</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>

<script>
function toggleAdmin() {
  const rol = document.getElementById('rol-select').value;
  document.getElementById('bloque-permisos').style.display = (rol === 'admin') ? 'none' : 'block';
  document.getElementById('bloque-admin').style.display = (rol === 'admin') ? 'block' : 'none';
}
</script>
{% endblock %}
'''


def patch_base_html():
    """Elimina el link de Roles del menu."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade45] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'roles_lista' not in contenido:
        print("[upgrade45] base.html ya no tiene Roles")
        return

    # Eliminar la linea del menu de roles
    import re
    # Busca el bloque del <a> de roles y lo borra
    patron = r'<a href="\{\{ url_for\(\'roles_lista\'\) \}\}".*?</a>\n?'
    nuevo, n = re.subn(patron, '', contenido, flags=re.DOTALL)
    if n > 0:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(nuevo)
        print(f"[upgrade45] link Roles eliminado del menu ({n} ocurrencia)")
    else:
        print("[upgrade45] ADVERTENCIA: no se encontro el link de Roles con el patron")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app45; app45.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 45: Permisos individuales por usuario (sin pestaña Roles) ===")
    migrar()
    escribir('app45.py', APP45_PY)
    escribir('templates/usuarios/form.html', USUARIOS_FORM)
    patch_base_html()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app45.py)")
    print("")
    print("IMPORTANTE: cerra sesion y volve a entrar para que tome el nuevo load_user")


if __name__ == '__main__':
    main()