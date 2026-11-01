
from datetime import date
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from app49 import catalogo_bp
from app51 import get_current_mayorista, mayorista_requerido
from database import get_db


def _get_carrito():
    """Devuelve el carrito desde la sesion."""
    return session.get('carrito', {})


def _save_carrito(carrito):
    session['carrito'] = carrito
    session.modified = True


def _carrito_count():
    return sum(item.get('cantidad', 0) for item in _get_carrito().values())


@catalogo_bp.app_context_processor
def _ctx_carrito():
    return {'carrito_count': _carrito_count()}


@catalogo_bp.route('/carrito')
@mayorista_requerido
def carrito():
    m = get_current_mayorista()
    conn = get_db()
    carrito_data = _get_carrito()

    items = []
    subtotal = 0
    for pid_str, item in carrito_data.items():
        pid = int(pid_str)
        prod = conn.execute("SELECT id, nombre, sku, precio, foto FROM productos WHERE id=? AND activo=1",
                             (pid,)).fetchone()
        if not prod:
            continue
        cant = item.get('cantidad', 0)
        precio = prod['precio'] or 0
        sub = cant * precio
        subtotal += sub
        items.append({
            'producto': dict(prod),
            'cantidad': cant,
            'precio': precio,
            'subtotal': sub,
        })

    # Calcular envío para mostrarlo en el carrito
    from app95 import calcular_envio_carrito
    info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, 'sucursal')

    conn.close()
    return render_template('catalogo/carrito.html', items=items, subtotal=subtotal, mayorista=m, info_envio=info_envio)


@catalogo_bp.route('/carrito/agregar/<int:producto_id>', methods=['POST'])
@mayorista_requerido
def carrito_agregar(producto_id):
    m = get_current_mayorista()
    if m['estado'] != 'aprobado':
        return jsonify({'ok': False, 'error': 'Tu cuenta aun no esta aprobada.'}), 403

    try:
        cantidad = float(request.form.get('cantidad', 1) or 1)
    except ValueError:
        cantidad = 1
    if cantidad <= 0:
        cantidad = 1

    conn = get_db()
    prod = conn.execute("SELECT id, nombre FROM productos WHERE id=? AND activo=1", (producto_id,)).fetchone()
    conn.close()
    if not prod:
        return jsonify({'ok': False, 'error': 'Producto no encontrado.'}), 404

    carrito = _get_carrito()
    key = str(producto_id)
    actual = carrito.get(key, {}).get('cantidad', 0)
    carrito[key] = {'cantidad': actual + cantidad}
    _save_carrito(carrito)

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'count': _carrito_count(),
                        'mensaje': f'Agregado: {prod["nombre"]}'})

    flash(f'Producto agregado: {prod["nombre"]}', 'success')
    return redirect(url_for('catalogo.carrito'))


@catalogo_bp.route('/carrito/actualizar/<int:producto_id>', methods=['POST'])
@mayorista_requerido
def carrito_actualizar(producto_id):
    try:
        cantidad = float(request.form.get('cantidad', 1) or 1)
    except ValueError:
        cantidad = 1
    carrito = _get_carrito()
    key = str(producto_id)
    if key in carrito:
        if cantidad <= 0:
            carrito.pop(key)
        else:
            carrito[key]['cantidad'] = cantidad
        _save_carrito(carrito)
    flash('Carrito actualizado.', 'success')
    return redirect(url_for('catalogo.carrito'))


@catalogo_bp.route('/carrito/quitar/<int:producto_id>', methods=['POST'])
@mayorista_requerido
def carrito_quitar(producto_id):
    carrito = _get_carrito()
    key = str(producto_id)
    if key in carrito:
        carrito.pop(key)
        _save_carrito(carrito)
    flash('Producto eliminado del carrito.', 'success')
    return redirect(url_for('catalogo.carrito'))


@catalogo_bp.route('/carrito/vaciar', methods=['POST'])
@mayorista_requerido
def carrito_vaciar():
    session.pop('carrito', None)
    flash('Carrito vaciado.', 'success')
    return redirect(url_for('catalogo.carrito'))


@catalogo_bp.route('/checkout', methods=['GET', 'POST'])
@mayorista_requerido
def checkout():
    m = get_current_mayorista()
    if m['estado'] != 'aprobado':
        flash('Tu cuenta debe estar aprobada para poder hacer pedidos.', 'error')
        return redirect(url_for('catalogo.carrito'))

    carrito_data = _get_carrito()
    if not carrito_data:
        flash('Tu carrito esta vacio.', 'warning')
        return redirect(url_for('catalogo.carrito'))

    conn = get_db()
    items = []
    subtotal = 0
    for pid_str, item in carrito_data.items():
        pid = int(pid_str)
        prod = conn.execute("SELECT * FROM productos WHERE id=? AND activo=1", (pid,)).fetchone()
        if not prod: continue
        cant = item.get('cantidad', 0)
        precio = prod['precio'] or 0
        sub = cant * precio
        subtotal += sub
        items.append({'producto': dict(prod), 'cantidad': cant, 'precio': precio, 'subtotal': sub})

    if not items:
        conn.close()
        flash('Tu carrito quedo vacio.', 'warning')
        return redirect(url_for('catalogo.carrito'))

    transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1 ORDER BY nombre").fetchall()

    if request.method == 'POST':
        tipo_envio = request.form.get('tipo_envio', '').strip()
        notas = request.form.get('notas', '').strip()
        accion = request.form.get('accion', 'pagar')
        requiere_factura = 1 if request.form.get('requiere_factura') else 0

        if tipo_envio not in ('retira_deposito', 'transporte', 'envio_personalizado'):
            conn.close(); flash('Tenes que elegir un tipo de envio.', 'error')
            return redirect(url_for('catalogo.checkout'))

        dest_nombre = request.form.get('destinatario_nombre', '').strip() or m['nombre_completo']
        dest_prov = request.form.get('destinatario_provincia', '').strip() or m.get('provincia', '')
        dest_loc = request.form.get('destinatario_localidad', '').strip() or m.get('localidad', '')
        dest_cp = request.form.get('destinatario_cp', '').strip() or m.get('codigo_postal', '')
        dest_calle = request.form.get('destinatario_calle', '').strip()
        dest_detalles = request.form.get('destinatario_detalles', '').strip()

        if tipo_envio == 'envio_personalizado':
            notas = request.form.get('notas_coordinacion', '') + ' ' + notas

        transportista_id = None
        nro_guia = None
        destino_tipo = None
        sucursal_detalle = None

        if tipo_envio == 'transporte':
            destino_tipo = request.form.get('destino_tipo', '').strip()
            if destino_tipo not in ('domicilio', 'sucursal'):
                conn.close(); flash('Elegi domicilio o sucursal.', 'error')
                return redirect(url_for('catalogo.checkout'))
            if destino_tipo == 'sucursal':
                sucursal_detalle = request.form.get('sucursal_detalle', '').strip() or 'A definir'
            if destino_tipo == 'domicilio' and not (dest_calle and dest_loc and dest_prov):
                conn.close(); flash('Para domicilio: calle, localidad y provincia son obligatorios.', 'error')
                return redirect(url_for('catalogo.checkout'))

        canal = conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)='tienda online'").fetchone()
        canal_id = canal['id'] if canal else None
        cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (m['cliente_id'],)).fetchone()
        vendedor_id = cliente['vendedor_id'] if cliente and cliente['vendedor_id'] else 1

        n = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM ordenes_venta").fetchone()[0]
        numero = f"ORD-{n:06d}"

        from app95 import calcular_envio_carrito
        destino_calc = request.form.get('destino_tipo') or 'sucursal'
        info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, destino_calc)
        if tipo_envio == 'envio_personalizado':
            info_envio['costo_envio'] = 0
            info_envio['requiere_cotizacion'] = False

        total_con_envio = subtotal + info_envio.get('costo_envio', 0)

        cur = conn.execute("""INSERT INTO ordenes_venta
            (numero_interno, cliente_id, usuario_id, canal_id, tipo, fecha, estado,
             estado_facturacion, subtotal, descuento, total, notas,
             tipo_envio, destino_tipo, sucursal_detalle, transportista_id, nro_guia,
             destinatario_nombre, destinatario_provincia, destinatario_localidad,
             destinatario_cp, destinatario_calle, destinatario_detalles, origen, costo_envio, requiere_factura)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, m['cliente_id'], vendedor_id, canal_id, 'mayorista',
             date.today().isoformat(), 'pendiente_pago', 'pendiente' if requiere_factura else 'no_requiere',
             subtotal, 0, total_con_envio, notas,
             tipo_envio, destino_tipo, sucursal_detalle, transportista_id, nro_guia,
             dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles, 'catalogo', info_envio.get('costo_envio', 0), requiere_factura))
        orden_id = cur.lastrowid

        for it in items:
            conn.execute("INSERT INTO orden_items (orden_id, producto_id, cantidad, precio_unitario, subtotal) VALUES (?,?,?,?,?)",
                         (orden_id, it['producto']['id'], it['cantidad'], it['precio'], it['subtotal']))

        conn.commit()
        conn.close()
        session.pop('carrito', None)
        _notificar_pedido(orden_id, numero, m, items, total_con_envio, tipo_envio)

        if accion == 'guardar':
            flash(f'Orden {numero} guardada. Recordá que tenés 24hs para subir el comprobante antes de que se cancele.', 'warning')
            return redirect(url_for('catalogo.mis_pedidos'))
        else:
            flash(f'Pedido {numero} recibido. Por favor subí el comprobante para completar la compra.', 'success')
            return redirect(url_for('catalogo.mi_pedido_detalle', id=orden_id))

    from app95 import calcular_envio_carrito
    info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, 'sucursal')
    total_con_envio = subtotal + info_envio.get('costo_envio', 0)
    conn.close()
    return render_template('catalogo/checkout.html', items=items, subtotal=subtotal, mayorista=m,
                           transportistas=transportistas, info_envio=info_envio, total_con_envio=total_con_envio)

def _notificar_pedido(orden_id, numero, mayorista, items, total, tipo_envio):
    try:
        from app4 import enviar_email, get_config
        firma = get_config('firma_email')
        detalle = '\n'.join([f"  - {it['producto']['nombre']} x {it['cantidad']:g} = ${it['subtotal']:.2f}" for it in items])
        envio_txt = {'retira_deposito': 'Retira en deposito',
                     'envio_personal': 'Envio personal',
                     'transporte': 'Envio por transporte'}.get(tipo_envio, tipo_envio)

        # Cargar datos de pago
        conn_dp = None
        try:
            from app57 import _datos_pago
            from database import get_db as _get_db
            conn_dp = _get_db()
            dp = _datos_pago(conn_dp)
            conn_dp.close()
        except Exception:
            dp = {}

        datos_pago_txt = ''
        if dp.get('pago_alias'): datos_pago_txt += f"- Alias: {dp['pago_alias']}\n"
        if dp.get('pago_cbu'): datos_pago_txt += f"- CBU: {dp['pago_cbu']}\n"
        if dp.get('pago_titular'): datos_pago_txt += f"- Titular: {dp['pago_titular']}\n"
        if dp.get('pago_cuit'): datos_pago_txt += f"- CUIT: {dp['pago_cuit']}\n"
        if dp.get('pago_banco'): datos_pago_txt += f"- Banco: {dp['pago_banco']}\n"
        if not datos_pago_txt:
            datos_pago_txt = "- (los datos de pago se muestran en el sistema)"

        # Al mayorista
        cuerpo = f"""Hola {mayorista['nombre_completo']},

Recibimos tu pedido {numero}.

Detalle:
{detalle}

Total: ${total:.2f}

Tipo de envio: {envio_txt}

Para confirmar el pedido, transferi el total a:
{datos_pago_txt}

Cuando hagas la transferencia, subi el comprobante desde "Mis pedidos" en el catalogo.
Apenas lo aprobemos, te enviamos la confirmacion.

{firma}"""
        enviar_email(mayorista['email'], f'Pedido {numero} recibido - Familia Zaragoza ®', cuerpo)

        # Al admin
        admin_email = get_config('empresa_email') or get_config('smtp_remitente_email')
        if admin_email:
            cuerpo_admin = f"""Nuevo pedido del catalogo publico:

Pedido: {numero}
Cliente: {mayorista['nombre_completo']} <{mayorista['email']}>

Detalle:
{detalle}

Total: ${total:.2f}
Tipo envio: {envio_txt}

Revisalo en: /ventas/{orden_id}

{firma}"""
            enviar_email(admin_email, f'Nuevo pedido #{numero} - {mayorista["nombre_completo"]}', cuerpo_admin)
    except Exception as e:
        print(f"[notificar pedido] {e}")


@catalogo_bp.route('/mis-pedidos')
@mayorista_requerido
def mis_pedidos():
    m = get_current_mayorista()
    if not m['cliente_id']:
        return render_template('catalogo/mis_pedidos.html', pedidos=[], mayorista=m)

    conn = get_db()
    pedidos = conn.execute("""
        SELECT o.*, cv.nombre as canal_nombre
        FROM ordenes_venta o
        LEFT JOIN canales_venta cv ON cv.id = o.canal_id
        WHERE o.cliente_id = ?
        ORDER BY o.id DESC
        LIMIT 100
    """, (m['cliente_id'],)).fetchall()
    conn.close()
    return render_template('catalogo/mis_pedidos.html', pedidos=pedidos, mayorista=m)


@catalogo_bp.route('/mis-pedidos/<int:id>')
@mayorista_requerido
def mi_pedido_detalle(id):
    m = get_current_mayorista()
    if not m['cliente_id']:
        return redirect(url_for('catalogo.mis_pedidos'))

    conn = get_db()
    orden = conn.execute("""SELECT * FROM ordenes_venta WHERE id=? AND cliente_id=?""",
                          (id, m['cliente_id'])).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('catalogo.mis_pedidos'))

    items = conn.execute("""SELECT oi.*, p.nombre as producto_nombre, p.sku, p.foto
        FROM orden_items oi JOIN productos p ON p.id = oi.producto_id
        WHERE oi.orden_id=?""", (id,)).fetchall()

    # Cargar datos de pago
    from app57 import _datos_pago
    datos_pago = _datos_pago(conn)
    conn.close()
    return render_template('catalogo/mi_pedido_detalle.html', orden=orden, items=items, mayorista=m, datos_pago=datos_pago)
