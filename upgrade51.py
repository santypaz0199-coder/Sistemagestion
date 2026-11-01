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
    print(f"[upgrade51] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade51] sin DB."); return
    conn = sqlite3.connect(db)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mayoristas_cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_completo TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            telefono TEXT,
            cuit TEXT,
            password_hash TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            cliente_id INTEGER,
            aprobado_por INTEGER,
            aprobado_en TEXT,
            motivo_rechazo TEXT,
            creado TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (aprobado_por) REFERENCES usuarios(id)
        )
    """)
    print("[upgrade51] tabla mayoristas_cuentas OK")

    conn.commit(); conn.close()


APP51_PY = r'''
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from app49 import catalogo_bp
from database import get_db


# ===== Helpers de sesion del mayorista =====
def get_current_mayorista():
    if hasattr(g, '_mayorista_actual'):
        return g._mayorista_actual
    mid = session.get('mayorista_id')
    if not mid:
        g._mayorista_actual = None
        return None
    conn = get_db()
    row = conn.execute("SELECT * FROM mayoristas_cuentas WHERE id=?", (mid,)).fetchone()
    conn.close()
    g._mayorista_actual = dict(row) if row else None
    return g._mayorista_actual


@catalogo_bp.app_context_processor
def _ctx_mayorista():
    return {
        'current_mayorista': get_current_mayorista(),
        'current_year': datetime.now().year,
    }


def mayorista_requerido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not get_current_mayorista():
            flash('Ingresa a tu cuenta para acceder.', 'warning')
            return redirect(url_for('catalogo.login'))
        return f(*args, **kwargs)
    return wrapper


# ===== Rutas =====
@catalogo_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if get_current_mayorista():
        return redirect(url_for('catalogo.mi_cuenta'))

    if request.method == 'POST':
        nombre = request.form.get('nombre_completo', '').strip()
        email = request.form.get('email', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        cuit = request.form.get('cuit', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        terminos = request.form.get('terminos')

        errores = []
        if not nombre: errores.append('Nombre es obligatorio.')
        if not email or '@' not in email: errores.append('Email invalido.')
        if not password or len(password) < 6: errores.append('La contrasena debe tener al menos 6 caracteres.')
        if password != password2: errores.append('Las contrasenas no coinciden.')
        if not terminos: errores.append('Debes aceptar los terminos.')

        if errores:
            for e in errores:
                flash(e, 'error')
            return render_template('catalogo/registro.html', form=request.form)

        conn = get_db()
        if conn.execute("SELECT id FROM mayoristas_cuentas WHERE lower(email)=?", (email,)).fetchone():
            conn.close()
            flash('Ya existe una cuenta con ese email.', 'error')
            return render_template('catalogo/registro.html', form=request.form)

        conn.execute("""INSERT INTO mayoristas_cuentas
            (nombre_completo, email, telefono, cuit, password_hash, estado)
            VALUES (?, ?, ?, ?, ?, 'pendiente')""",
            (nombre, email, telefono or None, cuit or None,
             generate_password_hash(password)))
        cuenta_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        # Enviar email de bienvenida (pendiente de aprobacion)
        try:
            from app4 import enviar_email, render_plantilla, get_config
            ctx = {
                'nombre': nombre,
                'email': email,
                'firma': get_config('firma_email'),
            }
            asunto = 'Tu cuenta fue creada - Familia Zaragoza ®'
            cuerpo = f"""Hola {nombre},

Recibimos tu solicitud de registro en Familia Zaragoza.

Tu cuenta esta pendiente de aprobacion. En las proximas horas vas a recibir un email confirmando que ya podes ingresar y hacer pedidos.

Gracias por elegirnos.

{get_config('firma_email')}"""
            enviar_email(email, asunto, cuerpo)
        except Exception as e:
            print(f"[registro email] {e}")

        conn.close()
        flash('Cuenta creada. Te enviamos un email de confirmacion. Espera la aprobacion para poder comprar.', 'success')
        return redirect(url_for('catalogo.login'))

    return render_template('catalogo/registro.html', form={})


@catalogo_bp.route('/login', methods=['GET', 'POST'])
def login():
    if get_current_mayorista():
        return redirect(url_for('catalogo.mi_cuenta'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        conn = get_db()
        row = conn.execute("SELECT * FROM mayoristas_cuentas WHERE lower(email)=?", (email,)).fetchone()
        conn.close()

        if not row or not check_password_hash(row['password_hash'], password):
            flash('Email o contrasena incorrectos.', 'error')
            return render_template('catalogo/login.html', form=request.form)

        if row['estado'] == 'rechazado':
            flash('Tu cuenta fue rechazada. Contactanos por email.', 'error')
            return render_template('catalogo/login.html', form=request.form)

        session['mayorista_id'] = row['id']
        flash(f'Bienvenido, {row["nombre_completo"]}.', 'success')
        if row['estado'] == 'pendiente':
            flash('Tu cuenta esta pendiente de aprobacion. Podes ver el catalogo pero no hacer pedidos aun.', 'warning')
        return redirect(request.args.get('next') or url_for('catalogo.index'))

    return render_template('catalogo/login.html', form={})


@catalogo_bp.route('/logout')
def logout():
    session.pop('mayorista_id', None)
    flash('Sesion cerrada.', 'success')
    return redirect(url_for('catalogo.index'))


@catalogo_bp.route('/mi-cuenta', methods=['GET', 'POST'])
@mayorista_requerido
def mi_cuenta():
    m = get_current_mayorista()
    if request.method == 'POST':
        accion = request.form.get('accion', 'perfil')
        conn = get_db()
        if accion == 'perfil':
            nombre = request.form.get('nombre_completo', '').strip()
            telefono = request.form.get('telefono', '').strip()
            cuit = request.form.get('cuit', '').strip()
            if not nombre:
                conn.close(); flash('El nombre es obligatorio.', 'error')
                return redirect(url_for('catalogo.mi_cuenta'))
            conn.execute("""UPDATE mayoristas_cuentas SET nombre_completo=?, telefono=?, cuit=? WHERE id=?""",
                         (nombre, telefono or None, cuit or None, m['id']))
            conn.commit(); conn.close()
            flash('Datos actualizados.', 'success')
            return redirect(url_for('catalogo.mi_cuenta'))
        elif accion == 'password':
            actual = request.form.get('password_actual', '')
            nueva = request.form.get('password_nueva', '')
            if not check_password_hash(m['password_hash'], actual):
                conn.close(); flash('La contrasena actual no es correcta.', 'error')
                return redirect(url_for('catalogo.mi_cuenta'))
            if len(nueva) < 6:
                conn.close(); flash('La nueva contrasena debe tener al menos 6 caracteres.', 'error')
                return redirect(url_for('catalogo.mi_cuenta'))
            conn.execute("UPDATE mayoristas_cuentas SET password_hash=? WHERE id=?",
                         (generate_password_hash(nueva), m['id']))
            conn.commit(); conn.close()
            flash('Contrasena actualizada.', 'success')
            return redirect(url_for('catalogo.mi_cuenta'))

    return render_template('catalogo/mi_cuenta.html', mayorista=m)


# ===== Panel de admin: gestion de mayoristas =====
from app48 import app as main_app
from app import admin_required
from flask_login import login_required


@main_app.route('/mayoristas')
@login_required
@admin_required
def mayoristas_lista():
    estado = request.args.get('estado', 'pendiente')
    conn = get_db()
    if estado == 'todas':
        cuentas = conn.execute("SELECT * FROM mayoristas_cuentas ORDER BY id DESC").fetchall()
    else:
        cuentas = conn.execute("SELECT * FROM mayoristas_cuentas WHERE estado=? ORDER BY id DESC",
                               (estado,)).fetchall()
    counts = {
        'pendiente': conn.execute("SELECT COUNT(*) FROM mayoristas_cuentas WHERE estado='pendiente'").fetchone()[0],
        'aprobado': conn.execute("SELECT COUNT(*) FROM mayoristas_cuentas WHERE estado='aprobado'").fetchone()[0],
        'rechazado': conn.execute("SELECT COUNT(*) FROM mayoristas_cuentas WHERE estado='rechazado'").fetchone()[0],
    }
    conn.close()
    return render_template('mayoristas/lista.html', cuentas=cuentas, estado=estado, counts=counts)


@main_app.route('/mayoristas/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def mayoristas_aprobar(id):
    from flask_login import current_user
    conn = get_db()
    cuenta = conn.execute("SELECT * FROM mayoristas_cuentas WHERE id=?", (id,)).fetchone()
    if not cuenta:
        conn.close(); flash('Cuenta no encontrada.', 'error')
        return redirect(url_for('mayoristas_lista'))

    # Buscar si ya existe cliente con ese email
    cliente_existente = conn.execute("SELECT id FROM clientes WHERE lower(email)=?",
                                      (cuenta['email'].lower(),)).fetchone()
    if cliente_existente:
        cliente_id = cliente_existente['id']
        conn.execute("UPDATE clientes SET es_mayorista=1, activo=1 WHERE id=?", (cliente_id,))
    else:
        cur = conn.execute("""INSERT INTO clientes
            (nombre_completo, tipo_doc, nro_doc, email, telefono,
             es_minorista, es_mayorista, activo, vendedor_id)
            VALUES (?, ?, ?, ?, ?, 0, 1, 1, ?)""",
            (cuenta['nombre_completo'], 'CUIT', cuenta['cuit'], cuenta['email'],
             cuenta['telefono'], current_user.id))
        cliente_id = cur.lastrowid

    conn.execute("""UPDATE mayoristas_cuentas SET estado='aprobado',
        cliente_id=?, aprobado_por=?, aprobado_en=datetime('now') WHERE id=?""",
        (cliente_id, current_user.id, id))
    conn.commit(); conn.close()

    # Email de aprobacion
    try:
        from app4 import enviar_email, get_config
        cuerpo = f"""Hola {cuenta['nombre_completo']},

Tu cuenta fue aprobada. Ya podes ingresar al catalogo y hacer pedidos.

https://familiazaragoza.com/catalogo/login

{get_config('firma_email')}"""
        enviar_email(cuenta['email'], 'Tu cuenta fue aprobada - Familia Zaragoza ®', cuerpo)
    except Exception as e:
        print(f"[aprobar email] {e}")

    flash(f'Cuenta de {cuenta["nombre_completo"]} aprobada. Cliente creado/actualizado.', 'success')
    return redirect(url_for('mayoristas_lista'))


@main_app.route('/mayoristas/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def mayoristas_rechazar(id):
    from flask_login import current_user
    motivo = request.form.get('motivo', '').strip()
    conn = get_db()
    cuenta = conn.execute("SELECT * FROM mayoristas_cuentas WHERE id=?", (id,)).fetchone()
    if not cuenta:
        conn.close(); flash('Cuenta no encontrada.', 'error')
        return redirect(url_for('mayoristas_lista'))

    conn.execute("""UPDATE mayoristas_cuentas SET estado='rechazado',
        aprobado_por=?, aprobado_en=datetime('now'), motivo_rechazo=? WHERE id=?""",
        (current_user.id, motivo or None, id))
    conn.commit(); conn.close()

    try:
        from app4 import enviar_email, get_config
        cuerpo = f"""Hola {cuenta['nombre_completo']},

Lamentablemente no pudimos aprobar tu cuenta en este momento.

{f'Motivo: {motivo}' if motivo else ''}

Si crees que es un error, responde este email y lo revisamos.

{get_config('firma_email')}"""
        enviar_email(cuenta['email'], 'Sobre tu registro - Familia Zaragoza ®', cuerpo)
    except Exception as e:
        print(f"[rechazar email] {e}")

    flash('Cuenta rechazada.', 'success')
    return redirect(url_for('mayoristas_lista'))
'''


# Sobrescribir app49.py con el import de request corregido + nuevo contenido completo
APP49_PY_FIXED = r'''
from flask import Blueprint, render_template, abort, request
from database import get_db

catalogo_bp = Blueprint('catalogo', __name__, url_prefix='/catalogo',
                         template_folder='templates/catalogo')


def _categorias_arbol(conn):
    cats = conn.execute("SELECT * FROM categorias_productos WHERE activo=1 ORDER BY nombre").fetchall()
    padres = [c for c in cats if not c['parent_id']]
    hijos = {}
    for c in cats:
        if c['parent_id']:
            hijos.setdefault(c['parent_id'], []).append(c)
    return padres, hijos


@catalogo_bp.route('/')
def index():
    conn = get_db()
    padres, hijos = _categorias_arbol(conn)

    categoria_id = request.args.get('categoria', type=int)
    if categoria_id:
        cat = conn.execute("SELECT * FROM categorias_productos WHERE id=? AND activo=1", (categoria_id,)).fetchone()
        if not cat:
            conn.close()
            abort(404)
        ids = [categoria_id] + [h['id'] for h in hijos.get(categoria_id, [])]
        placeholders = ','.join(['?'] * len(ids))
        productos = conn.execute(f"""
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.categoria_id IN ({placeholders})
            ORDER BY p.nombre
        """, ids).fetchall()
    else:
        productos = conn.execute("""
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1
            ORDER BY p.nombre
        """).fetchall()

    conn.close()
    return render_template('catalogo/index.html',
                           productos=productos, padres=padres, hijos=hijos,
                           categoria_actual=categoria_id)


@catalogo_bp.route('/producto/<int:id>')
def producto_detalle(id):
    conn = get_db()
    producto = conn.execute("""
        SELECT p.*, c.nombre as categoria_nombre
        FROM productos p
        LEFT JOIN categorias_productos c ON c.id = p.categoria_id
        WHERE p.id=? AND p.activo=1
    """, (id,)).fetchone()
    if not producto:
        conn.close()
        abort(404)
    conn.close()
    return render_template('catalogo/producto.html', producto=producto)


# Importar el resto de rutas del modulo app51
from app51 import registro, login, logout, mi_cuenta
'''


CATALOGO_BASE = r'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{% block title %}Familia Zaragoza ® - Catálogo{% endblock %}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --cat-bg: #0a0a0a;
  --cat-surface: #141414;
  --cat-surface-2: #1c1c1c;
  --cat-border: #262626;
  --cat-text: #f0f0f0;
  --cat-text-muted: #8a8a8a;
  --cat-accent: #c9a96e;
  --cat-accent-hover: #dfc08a;
}
* { -webkit-font-smoothing: antialiased; }
body {
  background: var(--cat-bg);
  color: var(--cat-text);
  font-family: 'Inter', system-ui, sans-serif;
  line-height: 1.6;
  min-height: 100vh;
}
.cat-header {
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--cat-border);
  position: sticky; top: 0;
  background: rgba(10,10,10,.85);
  backdrop-filter: blur(12px);
  z-index: 100;
}
.cat-brand {
  font-size: 1.1rem; font-weight: 700;
  letter-spacing: .15em; text-transform: uppercase;
  color: var(--cat-text); text-decoration: none;
}
.cat-brand:hover { color: var(--cat-accent); }
.cat-nav a {
  color: var(--cat-text-muted); text-decoration: none;
  font-size: .85rem; font-weight: 500;
  text-transform: uppercase; letter-spacing: .08em;
  margin-left: 2rem; transition: color .2s;
}
.cat-nav a:hover, .cat-nav a.active { color: var(--cat-text); }
.cat-hero { padding: 5rem 0 3rem; text-align: center; }
.cat-hero h1 { font-size: 3rem; font-weight: 300; letter-spacing: -.02em; margin-bottom: 1rem; }
.cat-hero p { color: var(--cat-text-muted); max-width: 500px; margin: 0 auto; }
.cat-subcats {
  display: flex; gap: .75rem; justify-content: center; flex-wrap: wrap;
  padding: 1.5rem 0; border-bottom: 1px solid var(--cat-border);
}
.cat-subcats a {
  color: var(--cat-text-muted); text-decoration: none;
  font-size: .85rem; padding: .4rem 1rem;
  border: 1px solid var(--cat-border); border-radius: 20px;
  transition: all .2s;
}
.cat-subcats a:hover, .cat-subcats a.active {
  background: var(--cat-accent); border-color: var(--cat-accent); color: #0a0a0a;
}
.cat-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 2rem; padding: 3rem 0;
}
.cat-card {
  background: var(--cat-surface); border: 1px solid var(--cat-border);
  border-radius: 12px; overflow: hidden;
  transition: transform .25s, border-color .25s;
  text-decoration: none; color: inherit;
  display: flex; flex-direction: column;
}
.cat-card:hover { transform: translateY(-4px); border-color: var(--cat-accent); color: inherit; }
.cat-card-img {
  aspect-ratio: 1; background: var(--cat-surface-2);
  display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.cat-card-img img { width: 100%; height: 100%; object-fit: cover; transition: transform .4s; }
.cat-card:hover .cat-card-img img { transform: scale(1.04); }
.cat-card-img .placeholder-icon { font-size: 3rem; color: var(--cat-border); }
.cat-card-body { padding: 1.25rem 1.5rem; flex: 1; display: flex; flex-direction: column; }
.cat-card-cat { font-size: .7rem; text-transform: uppercase; letter-spacing: .1em; color: var(--cat-text-muted); margin-bottom: .4rem; }
.cat-card-title { font-size: 1.05rem; font-weight: 500; margin-bottom: .75rem; line-height: 1.3; }
.cat-card-price { font-size: 1.1rem; font-weight: 600; color: var(--cat-accent); margin-top: auto; }
.cat-detail { padding: 4rem 0; }
.cat-detail-img {
  aspect-ratio: 1; background: var(--cat-surface);
  border-radius: 16px; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
}
.cat-detail-img img { width: 100%; height: 100%; object-fit: cover; }
.cat-detail-info h1 { font-size: 2rem; font-weight: 300; margin-bottom: .5rem; }
.cat-detail-price { font-size: 1.75rem; font-weight: 600; color: var(--cat-accent); margin: 1.5rem 0; }
.cat-btn {
  background: var(--cat-accent); color: #0a0a0a; border: none;
  padding: .8rem 2rem; font-weight: 600; font-size: .9rem;
  text-transform: uppercase; letter-spacing: .05em;
  border-radius: 6px; transition: background .2s, transform .2s;
  text-decoration: none; display: inline-block; cursor: pointer;
}
.cat-btn:hover { background: var(--cat-accent-hover); color: #0a0a0a; transform: translateY(-2px); }
.cat-btn-outline { background: transparent; border: 1px solid var(--cat-border); color: var(--cat-text); }
.cat-btn-outline:hover { border-color: var(--cat-text); background: transparent; }
.cat-footer { padding: 3rem 0; border-top: 1px solid var(--cat-border); text-align: center; color: var(--cat-text-muted); font-size: .8rem; margin-top: 4rem; }
.text-muted-cat { color: var(--cat-text-muted) !important; }
/* Formularios del catalogo */
.cat-form-card {
  background: var(--cat-surface);
  border: 1px solid var(--cat-border);
  border-radius: 16px;
  padding: 2.5rem;
  max-width: 480px;
  margin: 0 auto;
}
.cat-form-card h1 { font-size: 1.75rem; font-weight: 400; margin-bottom: .5rem; }
.cat-form-card .subtitle { color: var(--cat-text-muted); font-size: .9rem; margin-bottom: 2rem; }
.cat-form-card .form-label { color: var(--cat-text-muted); font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; font-weight: 500; }
.cat-form-card .form-control {
  background: var(--cat-surface-2);
  border: 1px solid var(--cat-border);
  color: var(--cat-text);
  padding: .75rem 1rem;
  border-radius: 8px;
}
.cat-form-card .form-control:focus {
  background: var(--cat-surface-2);
  border-color: var(--cat-accent);
  color: var(--cat-text);
  box-shadow: 0 0 0 3px rgba(201,169,110,.15);
}
.cat-form-card .form-control::placeholder { color: #555; }
.cat-form-card .form-text { color: var(--cat-text-muted); font-size: .78rem; }
.cat-form-card a { color: var(--cat-accent); text-decoration: none; }
.cat-form-card a:hover { color: var(--cat-accent-hover); }
.badge-cat { padding: .35rem .75rem; border-radius: 6px; font-size: .75rem; font-weight: 600; }
.badge-pendiente { background: rgba(245,158,11,.15); color: #f59e0b; }
.badge-aprobado { background: rgba(16,185,129,.15); color: #10b981; }
.badge-rechazado { background: rgba(239,68,68,.15); color: #ef4444; }
/* Alertas del catálogo */
.cat-alert { padding: .85rem 1.1rem; border-radius: 10px; font-size: .88rem; margin-bottom: 1rem; }
.cat-alert-success { background: rgba(16,185,129,.12); color: #4ade80; border: 1px solid rgba(16,185,129,.25); }
.cat-alert-danger { background: rgba(239,68,68,.12); color: #f87171; border: 1px solid rgba(239,68,68,.25); }
.cat-alert-warning { background: rgba(245,158,11,.12); color: #fbbf24; border: 1px solid rgba(245,158,11,.25); }
.cat-alert-info { background: rgba(6,182,212,.12); color: #22d3ee; border: 1px solid rgba(6,182,212,.25); }
</style>
{% block extra_head %}{% endblock %}
</head>
<body>

<header class="cat-header">
  <div class="container d-flex justify-content-between align-items-center">
    <a href="{{ url_for('catalogo.index') }}" class="cat-brand">Familia Zaragoza ®</a>
    <nav class="cat-nav d-none d-md-flex">
      <a href="{{ url_for('catalogo.index') }}" class="{% if not categoria_actual %}active{% endif %}">Catálogo</a>
      {% for p in padres %}
      <a href="{{ url_for('catalogo.index', categoria=p.id) }}" class="{% if categoria_actual == p.id %}active{% endif %}">{{ p.nombre }}</a>
      {% endfor %}
    </nav>
    <div class="d-flex align-items-center gap-3">
      {% if current_mayorista %}
      <a href="{{ url_for('catalogo.mi_cuenta') }}" class="text-decoration-none text-muted-cat small">
        <i class="bi bi-person-circle"></i> {{ current_mayorista.nombre_completo.split()[0] }}
      </a>
      <a href="{{ url_for('catalogo.logout') }}" class="text-decoration-none text-muted-cat" title="Salir"><i class="bi bi-box-arrow-right"></i></a>
      {% else %}
      <a href="{{ url_for('catalogo.login') }}" class="cat-btn cat-btn-outline" style="padding:.4rem 1rem;font-size:.8rem;">Ingresar</a>
      {% endif %}
    </div>
  </div>
</header>

<main>
{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}
<div class="container mt-3">
{% for cat, msg in messages %}
<div class="cat-alert cat-alert-{{ 'danger' if cat=='error' else cat }}">{{ msg }}</div>
{% endfor %}
</div>
{% endif %}
{% endwith %}

{% block content %}{% endblock %}
</main>

<footer class="cat-footer">
  <div class="container">
    <p class="mb-1">Familia Zaragoza ® — Yerba Mate Barbacuá</p>
    <p class="mb-0">© {{ current_year }} Todos los derechos reservados.</p>
  </div>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''


CATALOGO_REGISTRO = r'''{% extends "catalogo/base.html" %}
{% block title %}Crear cuenta — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <div class="cat-form-card">
    <h1>Crear cuenta</h1>
    <p class="subtitle">Registrate como mayorista. Tu cuenta debe ser aprobada antes de poder hacer pedidos.</p>

    <form method="post">
      <div class="mb-3">
        <label class="form-label">Nombre completo *</label>
        <input name="nombre_completo" class="form-control" required value="{{ form.get('nombre_completo', '') }}">
      </div>
      <div class="mb-3">
        <label class="form-label">Email *</label>
        <input type="email" name="email" class="form-control" required value="{{ form.get('email', '') }}">
      </div>
      <div class="row g-2 mb-3">
        <div class="col-md-6">
          <label class="form-label">Telefono</label>
          <input name="telefono" class="form-control" value="{{ form.get('telefono', '') }}" placeholder="+54 9...">
        </div>
        <div class="col-md-6">
          <label class="form-label">CUIT / CUIL</label>
          <input name="cuit" class="form-control" value="{{ form.get('cuit', '') }}">
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label">Contrasena * <span class="form-text">(min 6 caracteres)</span></label>
        <input type="password" name="password" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Repetir contrasena *</label>
        <input type="password" name="password2" class="form-control" required>
      </div>
      <div class="mb-4">
        <div class="form-check">
          <input class="form-check-input" type="checkbox" name="terminos" id="terminos" required>
          <label class="form-check-label" for="terminos" style="color:var(--cat-text-muted);font-size:.85rem;">
            Acepto los terminos y condiciones
          </label>
        </div>
      </div>
      <button class="cat-btn w-100">Crear cuenta</button>
    </form>

    <p class="text-center mt-4 mb-0" style="color:var(--cat-text-muted);font-size:.9rem;">
      Ya tenes cuenta? <a href="{{ url_for('catalogo.login') }}">Ingresa</a>
    </p>
  </div>
</div>
{% endblock %}
'''


CATALOGO_LOGIN = r'''{% extends "catalogo/base.html" %}
{% block title %}Ingresar — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <div class="cat-form-card">
    <h1>Ingresar</h1>
    <p class="subtitle">Accede a tu cuenta para hacer pedidos.</p>

    <form method="post">
      <div class="mb-3">
        <label class="form-label">Email</label>
        <input type="email" name="email" class="form-control" required value="{{ form.get('email', '') }}" autofocus>
      </div>
      <div class="mb-4">
        <label class="form-label">Contrasena</label>
        <input type="password" name="password" class="form-control" required>
      </div>
      <button class="cat-btn w-100">Ingresar</button>
    </form>

    <p class="text-center mt-4 mb-0" style="color:var(--cat-text-muted);font-size:.9rem;">
      No tenes cuenta? <a href="{{ url_for('catalogo.registro') }}">Registrate</a>
    </p>
  </div>
</div>
{% endblock %}
'''


CATALOGO_MI_CUENTA = r'''{% extends "catalogo/base.html" %}
{% block title %}Mi cuenta — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <div class="cat-form-card" style="max-width:600px;">
    <div class="d-flex justify-content-between align-items-start mb-2">
      <h1>Mi cuenta</h1>
      {% if mayorista.estado == 'pendiente' %}<span class="badge-cat badge-pendiente">Pendiente</span>
      {% elif mayorista.estado == 'aprobado' %}<span class="badge-cat badge-aprobado">Aprobada</span>
      {% else %}<span class="badge-cat badge-rechazado">Rechazada</span>{% endif %}
    </div>
    <p class="subtitle">{{ mayorista.email }}</p>

    {% if mayorista.estado == 'pendiente' %}
    <div class="cat-alert cat-alert-warning">
      <i class="bi bi-hourglass-split"></i> Tu cuenta esta pendiente de aprobacion. Te vamos a avisar por email cuando este habilitada.
    </div>
    {% elif mayorista.estado == 'rechazado' %}
    <div class="cat-alert cat-alert-danger">
      <i class="bi bi-x-circle"></i> Tu cuenta fue rechazada.{% if mayorista.motivo_rechazo %} Motivo: {{ mayorista.motivo_rechazo }}{% endif %}
    </div>
    {% endif %}

    <h6 class="mt-4 mb-3" style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;">Datos personales</h6>
    <form method="post">
      <input type="hidden" name="accion" value="perfil">
      <div class="mb-3">
        <label class="form-label">Nombre completo</label>
        <input name="nombre_completo" class="form-control" required value="{{ mayorista.nombre_completo }}">
      </div>
      <div class="row g-2 mb-3">
        <div class="col-md-6">
          <label class="form-label">Telefono</label>
          <input name="telefono" class="form-control" value="{{ mayorista.telefono or '' }}">
        </div>
        <div class="col-md-6">
          <label class="form-label">CUIT / CUIL</label>
          <input name="cuit" class="form-control" value="{{ mayorista.cuit or '' }}">
        </div>
      </div>
      <button class="cat-btn">Guardar cambios</button>
    </form>

    <hr style="border-color:var(--cat-border);margin:2.5rem 0;">

    <h6 class="mb-3" style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;">Cambiar contrasena</h6>
    <form method="post">
      <input type="hidden" name="accion" value="password">
      <div class="mb-3">
        <label class="form-label">Contrasena actual</label>
        <input type="password" name="password_actual" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Nueva contrasena</label>
        <input type="password" name="password_nueva" class="form-control" required>
      </div>
      <button class="cat-btn cat-btn-outline">Actualizar contrasena</button>
    </form>
  </div>
</div>
{% endblock %}
'''


MAYORISTAS_LISTA = r'''{% extends "base.html" %}
{% block title %}Mayoristas{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Cuentas de mayoristas</h4>
<div class="text-muted small">Aproba o rechaza las cuentas del catalogo publico</div>
</div>
</div>

<ul class="nav nav-pills mb-3">
<li class="nav-item"><a class="nav-link {% if estado=='pendiente' %}active{% endif %}" href="{{ url_for('mayoristas_lista', estado='pendiente') }}"><i class="bi bi-hourglass-split"></i> Pendientes {% if counts.pendiente %}<span class="badge bg-warning text-dark ms-1">{{ counts.pendiente }}</span>{% endif %}</a></li>
<li class="nav-item"><a class="nav-link {% if estado=='aprobado' %}active{% endif %}" href="{{ url_for('mayoristas_lista', estado='aprobado') }}"><i class="bi bi-check-circle"></i> Aprobadas ({{ counts.aprobado }})</a></li>
<li class="nav-item"><a class="nav-link {% if estado=='rechazado' %}active{% endif %}" href="{{ url_for('mayoristas_lista', estado='rechazado') }}"><i class="bi bi-x-circle"></i> Rechazadas ({{ counts.rechazado }})</a></li>
<li class="nav-item"><a class="nav-link {% if estado=='todas' %}active{% endif %}" href="{{ url_for('mayoristas_lista', estado='todas') }}">Todas</a></li>
</ul>

{% if cuentas %}
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light">
<tr><th>Fecha</th><th>Nombre</th><th>Email</th><th>Telefono</th><th>CUIT</th><th>Estado</th><th class="text-end">Acciones</th></tr>
</thead>
<tbody>
{% for c in cuentas %}
<tr>
<td class="small text-muted">{{ c.creado[:16] if c.creado else '' }}</td>
<td class="fw-semibold">{{ c.nombre_completo }}</td>
<td class="small">{{ c.email }}</td>
<td class="small">{{ c.telefono or '—' }}</td>
<td class="small">{{ c.cuit or '—' }}</td>
<td>
{% if c.estado == 'pendiente' %}<span class="badge bg-warning text-dark">Pendiente</span>
{% elif c.estado == 'aprobado' %}<span class="badge bg-success">Aprobada</span>
{% else %}<span class="badge bg-danger">Rechazada</span>{% endif %}
</td>
<td class="text-end text-nowrap">
{% if c.estado == 'pendiente' %}
<form method="post" action="{{ url_for('mayoristas_aprobar', id=c.id) }}" class="d-inline" onsubmit="return confirm('Aprobar la cuenta de {{ c.nombre_completo }}? Se creara el cliente automaticamente.')">
<button class="btn btn-sm btn-success"><i class="bi bi-check-lg"></i> Aprobar</button>
</form>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openRechazar({{ c.id }}, {{ c.nombre_completo|tojson }})"><i class="bi bi-x-lg"></i> Rechazar</button>
{% elif c.estado == 'rechazado' %}
<span class="small text-muted">{{ c.motivo_rechazo or '—' }}</span>
{% endif %}
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
{% else %}
<div class="card shadow-sm"><div class="card-body text-center py-5">
<i class="bi bi-people fs-1 text-muted"></i>
<p class="text-muted mt-3 mb-0">No hay cuentas en este estado.</p>
</div></div>
{% endif %}

<div class="modal fade" id="rechazarModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="rechazar-form" method="post">
<div class="modal-header"><h6 class="modal-title">Rechazar <span id="rechazar-nombre"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="small text-muted">Se le va a enviar un email al mayorista avisandole del rechazo.</p>
<div class="mb-2"><label class="form-label">Motivo (opcional)</label>
<textarea name="motivo" class="form-control" rows="3" placeholder="Ej: CUIT invalido"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">Rechazar</button>
</div>
</form></div></div></div>

<script>
function openRechazar(id, nombre) {
  document.getElementById('rechazar-form').action = '/mayoristas/' + id + '/rechazar';
  document.getElementById('rechazar-nombre').textContent = nombre;
  new bootstrap.Modal(document.getElementById('rechazarModal')).show();
}
</script>
{% endblock %}
'''


def patch_base_html():
    """Agrega el link de Mayoristas al menu solo para admin."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade51] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'mayoristas_lista' in contenido:
        print("[upgrade51] base.html ya tiene Mayoristas")
        return

    # Insertar antes de Usuarios
    buscar = '<a href="{{ url_for(\'usuarios_lista\') }}"'
    if buscar not in contenido:
        print("[upgrade51] no se encontro el link de usuarios"); return

    nuevo = ('<a href="{{ url_for(\'mayoristas_lista\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'mayoristas\') %}active{% endif %}">'
             '<i class="bi bi-person-plus"></i> Mayoristas</a>\n' + buscar)
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade51] link Mayoristas agregado a base.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 51: Registro y login de mayoristas (F6.2) ===")
    migrar()
    escribir('app51.py', APP51_PY)
    # Corregir app49 para que importe request
    escribir('app49.py', APP49_PY_FIXED)
    escribir('templates/catalogo/base.html', CATALOGO_BASE)
    escribir('templates/catalogo/registro.html', CATALOGO_REGISTRO)
    escribir('templates/catalogo/login.html', CATALOGO_LOGIN)
    escribir('templates/catalogo/mi_cuenta.html', CATALOGO_MI_CUENTA)
    escribir('templates/mayoristas/lista.html', MAYORISTAS_LISTA)
    patch_base_html()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()