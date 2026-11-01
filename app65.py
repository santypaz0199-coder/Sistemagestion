
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app64 import app
from app import admin_required
from database import get_db


def _contar_pendientes(conn):
    return conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='subido' AND estado='pendiente_pago'").fetchone()[0]


# ===== B2B unificado =====
@app.route('/b2b')
@login_required
@admin_required
def b2b_index():
    tab = request.args.get('tab', 'cuentas')
    conn = get_db()

    # Cuentas
    if tab == 'cuentas':
        estado = request.args.get('estado', 'pendiente')
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
        pagos_pendientes_count = _contar_pendientes(conn)
        conn.close()
        return render_template('mayoristas/lista.html',
                               tab='cuentas', cuentas=cuentas, estado=estado, counts=counts,
                               pagos_pendientes_count=pagos_pendientes_count)

    # Pagos pendientes
    elif tab == 'pagos':
        filtro = request.args.get('filtro', 'subido')
        if filtro == 'subido':
            rows = conn.execute("""
                SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email
                FROM ordenes_venta o
                JOIN clientes c ON c.id = o.cliente_id
                WHERE o.comprobante_estado = 'subido'
                AND o.estado = 'pendiente_pago'
                ORDER BY o.comprobante_subido_en ASC
            """).fetchall()
        elif filtro == 'todos':
            rows = conn.execute("""
                SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email
                FROM ordenes_venta o
                JOIN clientes c ON c.id = o.cliente_id
                WHERE o.comprobante_estado IN ('subido','aprobado','rechazado')
                ORDER BY o.id DESC LIMIT 100
            """).fetchall()
        else:
            rows = []

        counts = {
            'subido': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='subido' AND estado='pendiente_pago'").fetchone()[0],
            'aprobado': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='aprobado'").fetchone()[0],
            'rechazado': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='rechazado'").fetchone()[0],
        }
        conn.close()
        return render_template('mayoristas/lista_pagos.html',
                               tab='pagos', rows=rows, filtro=filtro, counts=counts)

    conn.close()
    return redirect(url_for('b2b_index', tab='cuentas'))


# Redirects de compatibilidad
def _redir_mayoristas():
    return redirect(url_for('b2b_index', tab='cuentas'))

def _redir_pagos():
    return redirect(url_for('b2b_index', tab='pagos'))

app.view_functions['mayoristas_lista'] = _redir_mayoristas
app.view_functions['pagos_pendientes_lista'] = _redir_pagos


# ===== Aprobar/Rechazar cuentas (ya existen pero las re-registramos) =====
@app.route('/b2b/cuenta/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def b2b_cuenta_aprobar(id):
    from flask_login import current_user
    conn = get_db()
    cuenta = conn.execute("SELECT * FROM mayoristas_cuentas WHERE id=?", (id,)).fetchone()
    if not cuenta:
        conn.close(); flash('Cuenta no encontrada.', 'error')
        return redirect(url_for('b2b_index', tab='cuentas'))

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

    try:
        from app4 import enviar_email, get_config
        cuerpo = f"""Hola {cuenta['nombre_completo']},

Tu cuenta fue aprobada. Ya podes ingresar al catalogo y hacer pedidos.

https://familiazaragoza.com/catalogo/login

{get_config('firma_email')}"""
        enviar_email(cuenta['email'], 'Tu cuenta fue aprobada - Familia Zaragoza ®', cuerpo)
    except Exception as e:
        print(f"[b2b aprobar email] {e}")

    flash(f'Cuenta de {cuenta["nombre_completo"]} aprobada.', 'success')
    return redirect(url_for('b2b_index', tab='cuentas'))


@app.route('/b2b/cuenta/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def b2b_cuenta_rechazar(id):
    from flask_login import current_user
    motivo = request.form.get('motivo', '').strip()
    conn = get_db()
    cuenta = conn.execute("SELECT * FROM mayoristas_cuentas WHERE id=?", (id,)).fetchone()
    if not cuenta:
        conn.close(); flash('Cuenta no encontrada.', 'error')
        return redirect(url_for('b2b_index', tab='cuentas'))

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
        print(f"[b2b rechazar email] {e}")

    flash('Cuenta rechazada.', 'success')
    return redirect(url_for('b2b_index', tab='cuentas'))


# Aprobar/Rechazar pagos (re-registramos apuntando de vuelta a B2B)
@app.route('/b2b/pago/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def b2b_pago_aprobar(id):
    from flask_login import current_user
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('b2b_index', tab='pagos'))

    if not orden['stock_descontado']:
        try:
            from app import aplicar_descuento_stock
            aplicar_descuento_stock(conn, id, current_user.id)
        except Exception as e:
            print(f"[b2b pago aprobar stock] {e}")

    conn.execute("""UPDATE ordenes_venta SET
        estado='pagado_sin_enviar',
        comprobante_estado='aprobado',
        comprobante_aprobado_por=?,
        comprobante_aprobado_en=datetime('now')
        WHERE id=?""",
        (current_user.id, id))
    conn.commit()

    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
    conn.close()

    if cliente and cliente['email']:
        try:
            from app4 import get_config
            from app39 import _enviar_con_remitente
            cuerpo = f"""Hola {cliente['nombre_completo']},

Tu pago fue aprobado. Tu pedido {orden['numero_interno']} ya esta en preparacion.

En cuanto lo despachemos te enviamos el numero de seguimiento.

{get_config('firma_email')}"""
            _enviar_con_remitente(cliente['email'], f'Pago aprobado - Pedido {orden["numero_interno"]}', cuerpo, None)
        except Exception as e:
            print(f"[b2b notificar aprobado] {e}")

    flash(f'Pedido {orden["numero_interno"]} marcado como pagado.', 'success')
    return redirect(url_for('b2b_index', tab='pagos'))


@app.route('/b2b/pago/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def b2b_pago_rechazar(id):
    motivo = request.form.get('motivo', '').strip()
    if not motivo:
        flash('Indica el motivo.', 'error')
        return redirect(url_for('b2b_index', tab='pagos'))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('b2b_index', tab='pagos'))

    conn.execute("""UPDATE ordenes_venta SET
        comprobante_estado='rechazado',
        comprobante_motivo_rechazo=?
        WHERE id=?""", (motivo, id))
    conn.commit()

    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
    conn.close()

    if cliente and cliente['email']:
        try:
            from app4 import get_config
            from app39 import _enviar_con_remitente
            cuerpo = f"""Hola {cliente['nombre_completo']},

Revisamos el comprobante de tu pedido {orden['numero_interno']} y no pudimos aprobarlo.

Motivo: {motivo}

Podes subir un nuevo comprobante desde "Mis pedidos" en el catalogo.

{get_config('firma_email')}"""
            _enviar_con_remitente(cliente['email'], f'Comprobante rechazado - Pedido {orden["numero_interno"]}', cuerpo, None)
        except Exception as e:
            print(f"[b2b notificar rechazo] {e}")

    flash('Comprobante rechazado.', 'warning')
    return redirect(url_for('b2b_index', tab='pagos'))


# Redirects viejos de aprobar/rechazar
def _redir_aprob(id):
    return redirect(url_for('b2b_cuenta_aprobar', id=id), 307)

def _redir_rechaz(id):
    return redirect(url_for('b2b_cuenta_rechazar', id=id), 307)

app.view_functions['mayoristas_aprobar'] = _redir_aprob
app.view_functions['mayoristas_rechazar'] = _redir_rechaz
app.view_functions['pagos_pendientes_aprobar'] = lambda id: redirect(url_for('b2b_pago_aprobar', id=id), 307)
app.view_functions['pagos_pendientes_rechazar'] = lambda id: redirect(url_for('b2b_pago_rechazar', id=id), 307)
