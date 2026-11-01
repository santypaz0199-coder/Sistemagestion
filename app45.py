
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
