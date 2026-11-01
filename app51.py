
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

        provincia = request.form.get('provincia', '').strip()
        localidad = request.form.get('localidad', '').strip()
        cp = request.form.get('codigo_postal', '').strip()
        calle = request.form.get('calle', '').strip()
        altura = request.form.get('altura', '').strip()
        piso = request.form.get('piso', '').strip()
        depto = request.form.get('depto', '').strip()

        conn.execute("""INSERT INTO mayoristas_cuentas
            (nombre_completo, email, telefono, cuit, password_hash, estado, provincia, localidad, codigo_postal, calle, altura, piso, depto)
            VALUES (?, ?, ?, ?, ?, 'pendiente', ?, ?, ?, ?, ?, ?, ?)""",
            (nombre, email, telefono or None, cuit or None,
             generate_password_hash(password), provincia, localidad, cp, calle, altura, piso, depto))
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
