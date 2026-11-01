
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
            return render_template('usuarios/form.html', usuario=None, valores=request.form, roles=_get_roles(conn))
            
        ok_pw, msg_pw = validar_password(password)
        if not ok_pw:
            conn.close(); flash(msg_pw, 'error')
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
            ok_pw, msg_pw = validar_password(password)
            if not ok_pw:
                conn.close(); flash(msg_pw, 'error')
                return redirect(url_for('usuarios_editar', id=id))
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
