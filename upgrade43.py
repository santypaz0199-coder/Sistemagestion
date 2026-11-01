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
    print(f"[upgrade43] escrito: {relpath}")


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
        print("[upgrade43] sin DB."); return
    conn = sqlite3.connect(db)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            nombre TEXT PRIMARY KEY,
            descripcion TEXT,
            es_sistema INTEGER DEFAULT 0,
            creado TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("[upgrade43] tabla roles OK")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles_permisos (
            rol_nombre TEXT NOT NULL,
            modulo TEXT NOT NULL,
            PRIMARY KEY (rol_nombre, modulo),
            FOREIGN KEY (rol_nombre) REFERENCES roles(nombre) ON DELETE CASCADE
        )
    """)
    print("[upgrade43] tabla roles_permisos OK")

    conn.execute("INSERT OR IGNORE INTO roles (nombre, descripcion, es_sistema) VALUES (?, ?, 1)",
                 ('admin', 'Acceso total al sistema'))
    conn.execute("INSERT OR IGNORE INTO roles (nombre, descripcion, es_sistema) VALUES (?, ?, 1)",
                 ('vendedor', 'Solo ve sus ventas y sus clientes'))
    print("[upgrade43] roles admin y vendedor OK")

    permisos_vendedor = ['clientes', 'ventas', 'emails', 'campanas']
    for m in permisos_vendedor:
        conn.execute("INSERT OR IGNORE INTO roles_permisos (rol_nombre, modulo) VALUES (?, ?)",
                     ('vendedor', m))
    print(f"[upgrade43] permisos vendedor: {', '.join(permisos_vendedor)}")

    conn.commit(); conn.close()


APP43_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, UserMixin
from app40 import app
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


class User_v2(UserMixin):
    def __init__(self, id, nombre, email, rol, permisos):
        self.id = id
        self.nombre = nombre
        self.email = email
        self.rol = rol
        self.permisos = permisos or []

    @property
    def es_admin(self):
        return self.rol == 'admin'

    @property
    def es_vendedor(self):
        return self.rol == 'vendedor'

    def puede(self, modulo):
        if self.rol == 'admin':
            return True
        return modulo in self.permisos


def _cargar_permisos(conn, rol):
    if rol == 'admin':
        return ['*']
    rows = conn.execute("SELECT modulo FROM roles_permisos WHERE rol_nombre=?", (rol,)).fetchall()
    return [r['modulo'] for r in rows]


@login_manager.user_loader
def load_user_v2(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE id=? AND activo=1", (user_id,)).fetchone()
    if not row:
        conn.close()
        return None
    permisos = _cargar_permisos(conn, row['rol'])
    conn.close()
    return User_v2(row['id'], row['nombre'], row['email'], row['rol'], permisos)


@app.route('/roles')
@login_required
@admin_required
def roles_lista():
    conn = get_db()
    roles = conn.execute("""
        SELECT r.*,
        (SELECT COUNT(*) FROM usuarios WHERE rol = r.nombre AND activo = 1) as total_usuarios
        FROM roles r ORDER BY r.es_sistema DESC, r.nombre
    """).fetchall()

    permisos_por_rol = {}
    for r in roles:
        if r['nombre'] == 'admin':
            permisos_por_rol[r['nombre']] = ['*TODOS*']
        else:
            ps = conn.execute("SELECT modulo FROM roles_permisos WHERE rol_nombre=?", (r['nombre'],)).fetchall()
            permisos_por_rol[r['nombre']] = [p['modulo'] for p in ps]

    conn.close()
    return render_template('roles/lista.html', roles=roles,
                           permisos_por_rol=permisos_por_rol,
                           permisos_disponibles=PERMISOS_DISPONIBLES)


@app.route('/roles/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def roles_nuevo():
    conn = get_db()
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip().lower().replace(' ', '_')
        descripcion = request.form.get('descripcion', '').strip()
        permisos = request.form.getlist('permisos')

        if not nombre:
            conn.close(); flash('Nombre obligatorio.', 'error')
            return redirect(url_for('roles_nuevo'))
        if nombre in ('admin', 'vendedor'):
            conn.close(); flash('Ese nombre esta reservado.', 'error')
            return redirect(url_for('roles_nuevo'))
        if conn.execute("SELECT nombre FROM roles WHERE nombre=?", (nombre,)).fetchone():
            conn.close(); flash('Ya existe un rol con ese nombre.', 'error')
            return redirect(url_for('roles_nuevo'))

        conn.execute("INSERT INTO roles (nombre, descripcion, es_sistema) VALUES (?, ?, 0)",
                     (nombre, descripcion))
        for m in permisos:
            if m in [p[0] for p in PERMISOS_DISPONIBLES]:
                conn.execute("INSERT OR IGNORE INTO roles_permisos (rol_nombre, modulo) VALUES (?, ?)",
                             (nombre, m))
        conn.commit(); conn.close()
        flash(f'Rol "{nombre}" creado.', 'success')
        return redirect(url_for('roles_lista'))

    conn.close()
    return render_template('roles/form.html', rol=None,
                           permisos_disponibles=PERMISOS_DISPONIBLES,
                           permisos_actuales=[])


@app.route('/roles/<nombre>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def roles_editar(nombre):
    conn = get_db()
    rol = conn.execute("SELECT * FROM roles WHERE nombre=?", (nombre,)).fetchone()
    if not rol:
        conn.close(); flash('Rol no encontrado.', 'error')
        return redirect(url_for('roles_lista'))

    if request.method == 'POST':
        descripcion = request.form.get('descripcion', '').strip()
        permisos = request.form.getlist('permisos')

        conn.execute("UPDATE roles SET descripcion=? WHERE nombre=?", (descripcion, nombre))

        if nombre != 'admin':
            conn.execute("DELETE FROM roles_permisos WHERE rol_nombre=?", (nombre,))
            for m in permisos:
                if m in [p[0] for p in PERMISOS_DISPONIBLES]:
                    conn.execute("INSERT OR IGNORE INTO roles_permisos (rol_nombre, modulo) VALUES (?, ?)",
                                 (nombre, m))
        conn.commit(); conn.close()
        flash('Rol actualizado.', 'success')
        return redirect(url_for('roles_lista'))

    permisos_actuales = []
    if nombre != 'admin':
        ps = conn.execute("SELECT modulo FROM roles_permisos WHERE rol_nombre=?", (nombre,)).fetchall()
        permisos_actuales = [p['modulo'] for p in ps]

    conn.close()
    return render_template('roles/form.html', rol=dict(rol),
                           permisos_disponibles=PERMISOS_DISPONIBLES,
                           permisos_actuales=permisos_actuales)


@app.route('/roles/<nombre>/eliminar', methods=['POST'])
@login_required
@admin_required
def roles_eliminar(nombre):
    conn = get_db()
    rol = conn.execute("SELECT * FROM roles WHERE nombre=?", (nombre,)).fetchone()
    if not rol:
        conn.close(); flash('Rol no encontrado.', 'error')
        return redirect(url_for('roles_lista'))

    if rol['es_sistema']:
        conn.close(); flash('No podes eliminar un rol del sistema.', 'error')
        return redirect(url_for('roles_lista'))

    en_uso = conn.execute("SELECT COUNT(*) FROM usuarios WHERE rol=? AND activo=1", (nombre,)).fetchone()[0]
    if en_uso > 0:
        conn.close()
        flash(f'No podes eliminar este rol: {en_uso} usuario(s) lo estan usando.', 'error')
        return redirect(url_for('roles_lista'))

    conn.execute("DELETE FROM roles WHERE nombre=?", (nombre,))
    conn.commit(); conn.close()
    flash('Rol eliminado.', 'success')
    return redirect(url_for('roles_lista'))


def _get_roles(conn):
    return conn.execute("SELECT nombre, descripcion FROM roles ORDER BY es_sistema DESC, nombre").fetchall()


def usuarios_nuevo_v2():
    from werkzeug.security import generate_password_hash
    conn = get_db()
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        rol = request.form['rol']
        if not nombre or not email or not password:
            conn.close(); flash('Completa todos los campos.', 'error')
            return render_template('usuarios/form.html', usuario=None, valores=request.form,
                                   roles=_get_roles(conn))
        if not conn.execute("SELECT nombre FROM roles WHERE nombre=?", (rol,)).fetchone():
            conn.close(); flash('Rol invalido.', 'error')
            return render_template('usuarios/form.html', usuario=None, valores=request.form,
                                   roles=_get_roles(conn))
        if conn.execute("SELECT id FROM usuarios WHERE lower(email)=?", (email,)).fetchone():
            conn.close(); flash('Ya existe un usuario con ese email.', 'error')
            return render_template('usuarios/form.html', usuario=None, valores=request.form,
                                   roles=_get_roles(conn))
        conn.execute("INSERT INTO usuarios (nombre,email,password_hash,rol) VALUES (?,?,?,?)",
                     (nombre, email, generate_password_hash(password), rol))
        conn.commit(); conn.close()
        flash('Usuario creado.', 'success')
        return redirect(url_for('usuarios_lista'))
    roles = _get_roles(conn)
    conn.close()
    return render_template('usuarios/form.html', usuario=None, valores={}, roles=roles)


def usuarios_editar_v3(id):
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
        if not conn.execute("SELECT nombre FROM roles WHERE nombre=?", (rol,)).fetchone():
            conn.close(); flash('Rol invalido.', 'error')
            return redirect(url_for('usuarios_editar', id=id))
        existe = conn.execute("SELECT id FROM usuarios WHERE lower(email)=? AND id!=?", (email, id)).fetchone()
        if existe:
            conn.close(); flash('Email ya existe.', 'error')
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
    roles = _get_roles(conn)
    conn.close()
    return render_template('usuarios/form.html', usuario=dict(usuario), valores={}, roles=roles)


app.view_functions['usuarios_nuevo'] = usuarios_nuevo_v2
app.view_functions['usuarios_editar'] = usuarios_editar_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


ROLES_LISTA = r'''{% extends "base.html" %}
{% block title %}Roles{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Roles y permisos</h4>
<div class="text-muted small">Defini que puede ver cada tipo de usuario</div>
</div>
<a href="{{ url_for('roles_nuevo') }}" class="btn btn-dark"><i class="bi bi-plus-lg"></i> Nuevo rol</a>
</div>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th>Rol</th><th>Descripcion</th><th>Permisos</th><th class="text-end">Usuarios</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for r in roles %}
<tr>
<td>
<span class="fw-semibold">{{ r.nombre }}</span>
{% if r.es_sistema %}<span class="badge bg-secondary ms-1" style="font-size:.6rem;">SISTEMA</span>{% endif %}
</td>
<td class="small text-muted">{{ r.descripcion or '—' }}</td>
<td>
{% set ps = permisos_por_rol.get(r.nombre, []) %}
{% if ps == ['*TODOS*'] %}
<span class="badge bg-success">Acceso total</span>
{% elif ps %}
{% for p in ps %}<span class="badge bg-light text-dark border me-1 mb-1">{{ p }}</span>{% endfor %}
{% else %}
<span class="text-muted small">Sin permisos</span>
{% endif %}
</td>
<td class="text-end">{{ r.total_usuarios }}</td>
<td class="text-end text-nowrap">
<a href="{{ url_for('roles_editar', nombre=r.nombre) }}" class="btn btn-sm btn-outline-secondary" title="Editar"><i class="bi bi-pencil"></i></a>
{% if not r.es_sistema %}
<form method="post" action="{{ url_for('roles_eliminar', nombre=r.nombre) }}" class="d-inline"
      onsubmit="return confirm('Eliminar el rol {{ r.nombre }}?')">
<button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
</form>
{% endif %}
</td>
</tr>
{% endfor %}
</tbody></table></div></div>

<div class="alert alert-light border mt-3 small">
<i class="bi bi-info-circle"></i>
<strong>Como funciona:</strong>
<ul class="mb-0 ps-3">
<li><strong>admin</strong>: siempre ve todo (no editable).</li>
<li><strong>vendedor</strong>: ve solo sus propias ventas y clientes asignados.</li>
<li><strong>Roles personalizados</strong>: ven los modulos que les asignes.</li>
</ul>
</div>
{% endblock %}
'''


ROLES_FORM = r'''{% extends "base.html" %}
{% block title %}{{ 'Editar' if rol else 'Nuevo' }} rol{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar rol: ' + rol.nombre if rol else 'Nuevo rol' }}</h4>
<a href="{{ url_for('roles_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-6">
<label class="form-label">Nombre interno *</label>
{% if rol %}
<input class="form-control" value="{{ rol.nombre }}" disabled>
<div class="form-text">El nombre no se puede cambiar despues de crear.</div>
{% else %}
<input name="nombre" class="form-control" required placeholder="Ej: tesorero" pattern="[a-z0-9_]+">
<div class="form-text">Solo letras minusculas, numeros y guion bajo.</div>
{% endif %}
</div>
<div class="col-md-6">
<label class="form-label">Descripcion</label>
<input name="descripcion" class="form-control" value="{{ rol.descripcion if rol else '' }}" placeholder="Para que sirve este rol">
</div>
</div>

<div class="mt-4 mb-2">
<label class="form-label fw-semibold">Permisos de acceso</label>
{% if rol and rol.nombre == 'admin' %}
<div class="alert alert-info py-2 small mb-0">
<i class="bi bi-info-circle"></i> El rol <strong>admin</strong> siempre tiene acceso total. No se puede editar.
</div>
{% else %}
<div class="form-text mb-2">Tilda los modulos que puede ver este rol. El <strong>Dashboard</strong> siempre es visible.</div>
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
{% endif %}
</div>

<div class="mt-4 d-flex gap-2">
<button class="btn btn-dark">Guardar</button>
<a href="{{ url_for('roles_lista') }}" class="btn btn-outline-secondary">Cancelar</a>
</div>
</form>
</div></div>
{% endblock %}
'''


USUARIOS_FORM = r'''{% extends "base.html" %}
{% block title %}{{ 'Editar' if usuario else 'Nuevo' }} usuario{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if usuario else 'Nuevo' }} usuario</h4>
<a href="{{ url_for('usuarios_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-6"><label class="form-label">Nombre *</label><input name="nombre" class="form-control" required value="{{ usuario.nombre if usuario else valores.get('nombre','') }}"></div>
<div class="col-md-6"><label class="form-label">Email de login *</label><input type="email" name="email" class="form-control" required value="{{ usuario.email if usuario else valores.get('email','') }}"></div>
<div class="col-md-6">
<label class="form-label">Rol *</label>
<select name="rol" class="form-select" required>
{% for r in roles %}
<option value="{{ r.nombre }}" {% if usuario and usuario.rol == r.nombre %}selected{% endif %}>{{ r.nombre }}{% if r.descripcion %} — {{ r.descripcion }}{% endif %}</option>
{% endfor %}
</select>
<a href="{{ url_for('roles_lista') }}" class="small text-decoration-none">Gestionar roles</a>
</div>
<div class="col-md-6"><label class="form-label">Contrasena {{ '(dejar vacio para no cambiar)' if usuario else '*' }}</label><input type="password" name="password" class="form-control" {% if not usuario %}required{% endif %}></div>

<div class="col-12 mt-3"><hr><h6 class="text-muted small">Remitente de email</h6></div>
<div class="col-md-6">
<label class="form-label">Email remitente</label>
<input name="email_remitente" type="email" class="form-control" value="{{ usuario.email_remitente if usuario else '' }}" placeholder="pedro@familiazaragoza.com">
</div>
<div class="col-md-6">
<label class="form-label">Nombre remitente</label>
<input name="nombre_remitente" class="form-control" value="{{ usuario.nombre_remitente if usuario else '' }}" placeholder="Pedro - Familia Zaragoza">
</div>

{% if usuario %}
<div class="col-12">
<div class="form-check">
<input class="form-check-input" type="checkbox" name="activo" id="activo" {% if usuario.activo %}checked{% endif %}>
<label class="form-check-label" for="activo">Usuario activo</label>
</div>
</div>
{% endif %}
</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>
{% endblock %}
'''


def patch_base_html():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade43] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'roles_lista' in contenido:
        print("[upgrade43] base.html ya tiene Roles")
        return

    buscar = '<a href="{{ url_for(\'usuarios_lista\') }}"'
    if buscar not in contenido:
        print("[upgrade43] no se encontro link de usuarios"); return

    nuevo = ('<a href="{{ url_for(\'roles_lista\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'roles\') %}active{% endif %}">'
             '<i class="bi bi-shield-lock"></i> Roles</a>\n' + buscar)
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade43] link Roles agregado a base.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app43; app43.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 43: Roles personalizables (U41) ===")
    migrar()
    escribir('app43.py', APP43_PY)
    escribir('templates/roles/lista.html', ROLES_LISTA)
    escribir('templates/roles/form.html', ROLES_FORM)
    escribir('templates/usuarios/form.html', USUARIOS_FORM)
    patch_base_html()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app43.py)")
    print("")
    print("IMPORTANTE: cerra sesion y volve a entrar para que tome el nuevo load_user")


if __name__ == '__main__':
    main()