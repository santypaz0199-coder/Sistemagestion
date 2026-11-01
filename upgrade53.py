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
    print(f"[upgrade53] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade53] sin DB."); return
    conn = sqlite3.connect(db)

    # Asegurar que existe el canal "Tienda online"
    if not conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)='tienda online'").fetchone():
        conn.execute("INSERT INTO canales_venta (nombre, activo) VALUES ('Tienda online', 1)")
        print("[upgrade53] canal 'Tienda online' creado")

    conn.commit(); conn.close()


APP53_PY = r'''
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

    conn.close()
    return render_template('catalogo/carrito.html', items=items, subtotal=subtotal, mayorista=m)


@catalogo_bp.route('/carrito/agregar/<int:producto_id>', methods=['POST'])
@mayorista_requerido
def carrito_agregar(producto_id):
    m = get_current_mayorista()
    if m['estado'] != 'aprobado':
        return jsonify({'ok': False, 'error': 'Tu cuenta aun no esta aprobada.')}), 403

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

    # Reconstruir items + total
    items = []
    subtotal = 0
    for pid_str, item in carrito_data.items():
        pid = int(pid_str)
        prod = conn.execute("SELECT * FROM productos WHERE id=? AND activo=1", (pid,)).fetchone()
        if not prod:
            continue
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

        if tipo_envio not in ('retira_deposito', 'transporte', 'envio_personal'):
            conn.close()
            flash('Tenes que elegir un tipo de envio.', 'error')
            return redirect(url_for('catalogo.checkout'))

        # Recoger datos de envio
        dest_nombre = request.form.get('destinatario_nombre', '').strip() or m['nombre_completo']
        dest_prov = request.form.get('destinatario_provincia', '').strip()
        dest_loc = request.form.get('destinatario_localidad', '').strip()
        dest_cp = request.form.get('destinatario_cp', '').strip()
        dest_calle = request.form.get('destinatario_calle', '').strip()
        dest_detalles = request.form.get('destinatario_detalles', '').strip()

        if tipo_envio == 'envio_personal' and not (dest_calle and dest_loc and dest_prov):
            conn.close(); flash('Para envio personal: calle, localidad y provincia son obligatorios.', 'error')
            return redirect(url_for('catalogo.checkout'))

        transportista_id = None
        nro_guia = None
        destino_tipo = None
        sucursal_detalle = None

        if tipo_envio == 'transporte':
            transportista_id = request.form.get('transportista_id') or None
            if not transportista_id:
                conn.close(); flash('Elegi un transportista.', 'error')
                return redirect(url_for('catalogo.checkout'))
            destino_tipo = request.form.get('destino_tipo', '').strip()
            if destino_tipo not in ('domicilio', 'sucursal'):
                conn.close(); flash('Elegi domicilio o sucursal.', 'error')
                return redirect(url_for('catalogo.checkout'))
            if destino_tipo == 'sucursal':
                sucursal_detalle = request.form.get('sucursal_detalle', '').strip()
                if not sucursal_detalle:
                    conn.close(); flash('Indica la sucursal.', 'error')
                    return redirect(url_for('catalogo.checkout'))
            if destino_tipo == 'domicilio' and not (dest_calle and dest_loc and dest_prov):
                conn.close(); flash('Para domicilio: calle, localidad y provincia son obligatorios.', 'error')
                return redirect(url_for('catalogo.checkout'))

        # Buscar el canal "Tienda online"
        canal = conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)='tienda online'").fetchone()
        canal_id = canal['id'] if canal else None

        # Vendedor asignado = el admin por defecto (o el vendedor del cliente si tiene)
        cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (m['cliente_id'],)).fetchone()
        vendedor_id = cliente['vendedor_id'] if cliente and cliente['vendedor_id'] else 1

        # Numero de orden
        n = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM ordenes_venta").fetchone()[0]
        numero = f"ORD-{n:06d}"

        # Crear la orden
        cur = conn.execute("""INSERT INTO ordenes_venta
            (numero_interno, cliente_id, usuario_id, canal_id, tipo, fecha, estado,
             estado_facturacion, subtotal, descuento, total, notas,
             tipo_envio, destino_tipo, sucursal_detalle, transportista_id, nro_guia,
             destinatario_nombre, destinatario_provincia, destinatario_localidad,
             destinatario_cp, destinatario_calle, destinatario_detalles)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, m['cliente_id'], vendedor_id, canal_id, 'mayorista',
             date.today().isoformat(), 'pendiente_pago', 'no_requiere',
             subtotal, 0, subtotal, notas,
             tipo_envio, destino_tipo, sucursal_detalle,
             int(transportista_id) if transportista_id else None, nro_guia,
             dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles))
        orden_id = cur.lastrowid

        # Guardar items + descontar stock (aunque quede negativo)
        for it in items:
            conn.execute("""INSERT INTO orden_items
                (orden_id, producto_id, cantidad, precio_unitario, subtotal)
                VALUES (?,?,?,?,?)""",
                (orden_id, it['producto']['id'], it['cantidad'], it['precio'], it['subtotal']))
            # El descuento de stock se hace cuando pasa a pagado, pero aca como es "pendiente_pago"
            # igual queda reservado. No descontamos aun (sigue el flujo del sistema interno).

        conn.commit()
        conn.close()

        # Vaciar carrito
        session.pop('carrito', None)

        # Emails de notificacion
        _notificar_pedido(orden_id, numero, m, items, subtotal, tipo_envio)

        flash(f'Pedido {numero} recibido. Te enviamos un email con el resumen y los datos para transferir.', 'success')
        return redirect(url_for('catalogo.mis_pedidos'))

    conn.close()
    return render_template('catalogo/checkout.html',
                           items=items, subtotal=subtotal, mayorista=m,
                           transportistas=transportistas)


def _notificar_pedido(orden_id, numero, mayorista, items, total, tipo_envio):
    try:
        from app4 import enviar_email, get_config
        firma = get_config('firma_email')
        detalle = '\n'.join([f"  - {it['producto']['nombre']} x {it['cantidad']:g} = ${it['subtotal']:.2f}" for it in items])
        envio_txt = {'retira_deposito': 'Retira en deposito',
                     'envio_personal': 'Envio personal',
                     'transporte': 'Envio por transporte'}.get(tipo_envio, tipo_envio)

        # Al mayorista
        cuerpo = f"""Hola {mayorista['nombre_completo']},

Recibimos tu pedido {numero}.

Detalle:
{detalle}

Total: ${total:.2f}

Tipo de envio: {envio_txt}

Para confirmar el pedido, transferi el total a:
- ALIAS: (configurar)
- CBU: (configurar)
- Titular: Familia Zaragoza

Cuando recibamos el pago te avisamos por email y despachamos.

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
    conn.close()
    return render_template('catalogo/mi_pedido_detalle.html', orden=orden, items=items, mayorista=m)
'''


CATALOGO_CARRITO = r'''{% extends "catalogo/base.html" %}
{% block title %}Carrito — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <h1 style="font-weight:300;font-size:2rem;margin-bottom:2rem;">Mi pedido</h1>

  {% if items %}
  <div class="row g-4">
    <div class="col-md-8">
      <div class="cat-form-card" style="max-width:100%;padding:0;">
        <table class="table" style="color:var(--cat-text);margin:0;">
          <thead>
            <tr style="border-bottom:1px solid var(--cat-border);">
              <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;">Producto</th>
              <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;text-align:center;">Cantidad</th>
              <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;text-align:right;">Subtotal</th>
              <th style="width:50px;padding:1rem;"></th>
            </tr>
          </thead>
          <tbody>
            {% for item in items %}
            <tr style="border-bottom:1px solid var(--cat-border);">
              <td style="padding:1rem;">
                <div style="display:flex;align-items:center;gap:1rem;">
                  <div style="width:60px;height:60px;background:var(--cat-surface-2);border-radius:8px;overflow:hidden;flex-shrink:0;">
                    {% if item.producto.foto %}
                    <img src="{{ url_for('productos_ver_foto', nombre=item.producto.foto) }}" style="width:100%;height:100%;object-fit:cover;">
                    {% else %}
                    <i class="bi bi-image" style="display:flex;align-items:center;justify-content:center;height:100%;color:#555;font-size:1.5rem;"></i>
                    {% endif %}
                  </div>
                  <div>
                    <div style="font-weight:500;">{{ item.producto.nombre }}</div>
                    <div style="color:var(--cat-text-muted);font-size:.8rem;">${{ '%.2f'|format(item.precio) }} c/u</div>
                  </div>
                </div>
              </td>
              <td style="padding:1rem;text-align:center;vertical-align:middle;">
                <form method="post" action="{{ url_for('catalogo.carrito_actualizar', producto_id=item.producto.id) }}" style="display:inline-flex;align-items:center;gap:.25rem;">
                  <input type="number" name="cantidad" value="{{ item.cantidad|int }}" min="0" step="1" style="width:70px;background:var(--cat-surface-2);border:1px solid var(--cat-border);color:var(--cat-text);padding:.35rem .5rem;border-radius:6px;text-align:center;">
                  <button type="submit" style="background:none;border:none;color:var(--cat-accent);cursor:pointer;padding:.3rem;" title="Actualizar"><i class="bi bi-arrow-clockwise"></i></button>
                </form>
              </td>
              <td style="padding:1rem;text-align:right;color:var(--cat-accent);font-weight:600;vertical-align:middle;">${{ '%.2f'|format(item.subtotal) }}</td>
              <td style="padding:1rem;text-align:center;vertical-align:middle;">
                <form method="post" action="{{ url_for('catalogo.carrito_quitar', producto_id=item.producto.id) }}" style="display:inline;">
                  <button type="submit" style="background:none;border:none;color:#f87171;cursor:pointer;padding:.3rem;" onclick="return confirm('Quitar este producto?')" title="Quitar"><i class="bi bi-x-lg"></i></button>
                </form>
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <div class="mt-3">
        <form method="post" action="{{ url_for('catalogo.carrito_vaciar') }}" style="display:inline;">
          <button type="submit" class="cat-btn cat-btn-outline" style="padding:.5rem 1.2rem;font-size:.8rem;" onclick="return confirm('Vaciar todo el carrito?')">Vaciar carrito</button>
        </form>
        <a href="{{ url_for('catalogo.index') }}" class="cat-btn cat-btn-outline" style="padding:.5rem 1.2rem;font-size:.8rem;">Seguir comprando</a>
      </div>
    </div>

    <div class="col-md-4">
      <div class="cat-form-card" style="padding:1.5rem;">
        <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Resumen</h6>
        <div class="d-flex justify-content-between mb-2">
          <span style="color:var(--cat-text-muted);">Subtotal</span>
          <span>${{ '%.2f'|format(subtotal) }}</span>
        </div>
        <hr style="border-color:var(--cat-border);">
        <div class="d-flex justify-content-between mb-3">
          <span style="font-weight:600;">Total</span>
          <span style="color:var(--cat-accent);font-weight:600;font-size:1.2rem;">${{ '%.2f'|format(subtotal) }}</span>
        </div>
        {% if mayorista.estado == 'aprobado' %}
        <a href="{{ url_for('catalogo.checkout') }}" class="cat-btn w-100 text-center">Iniciar pedido</a>
        {% else %}
        <div class="cat-alert cat-alert-warning" style="font-size:.85rem;">
          <i class="bi bi-hourglass-split"></i> Tu cuenta esta pendiente de aprobacion.
        </div>
        {% endif %}
      </div>
    </div>
  </div>
  {% else %}
  <div class="text-center py-5">
    <i class="bi bi-cart-x" style="font-size:4rem;color:var(--cat-border);"></i>
    <h3 style="font-weight:300;margin-top:1.5rem;color:var(--cat-text-muted);">Tu carrito esta vacio</h3>
    <a href="{{ url_for('catalogo.index') }}" class="cat-btn mt-3" style="display:inline-block;">Ver catalogo</a>
  </div>
  {% endif %}
</div>
{% endblock %}
'''


CATALOGO_CHECKOUT = r'''{% extends "catalogo/base.html" %}
{% block title %}Checkout — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <h1 style="font-weight:300;font-size:2rem;margin-bottom:2rem;">Finalizar pedido</h1>

  <form method="post">
    <div class="row g-4">
      <div class="col-md-8">

        <!-- Tipo de envio -->
        <div class="cat-form-card" style="max-width:100%;padding:1.5rem;">
          <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Tipo de envio *</h6>

          <div class="row g-2 mb-3">
            <div class="col-md-4">
              <label class="tipo-envio-card" data-tipo="retira_deposito" style="cursor:pointer;display:block;">
                <input type="radio" name="tipo_envio" value="retira_deposito" style="display:none;" required>
                <div style="border:1px solid var(--cat-border);border-radius:10px;padding:1rem;text-align:center;">
                  <i class="bi bi-shop" style="font-size:1.5rem;display:block;margin-bottom:.5rem;"></i>
                  <div style="font-weight:500;font-size:.85rem;">Retira en deposito</div>
                </div>
              </label>
            </div>
            <div class="col-md-4">
              <label class="tipo-envio-card" data-tipo="transporte" style="cursor:pointer;display:block;">
                <input type="radio" name="tipo_envio" value="transporte" style="display:none;">
                <div style="border:1px solid var(--cat-border);border-radius:10px;padding:1rem;text-align:center;">
                  <i class="bi bi-truck" style="font-size:1.5rem;display:block;margin-bottom:.5rem;"></i>
                  <div style="font-weight:500;font-size:.85rem;">Envio por transporte</div>
                </div>
              </label>
            </div>
            <div class="col-md-4">
              <label class="tipo-envio-card" data-tipo="envio_personal" style="cursor:pointer;display:block;">
                <input type="radio" name="tipo_envio" value="envio_personal" style="display:none;">
                <div style="border:1px solid var(--cat-border);border-radius:10px;padding:1rem;text-align:center;">
                  <i class="bi bi-car-front" style="font-size:1.5rem;display:block;margin-bottom:.5rem;"></i>
                  <div style="font-weight:500;font-size:.85rem;">Envio personal</div>
                </div>
              </label>
            </div>
          </div>

          <!-- Bloque: retira -->
          <div class="bloque-envio" data-bloque="retira_deposito" style="display:none;">
            <div class="cat-alert cat-alert-info" style="font-size:.85rem;">Retiras personalmente en el deposito. Te avisamos cuando este listo.</div>
          </div>

          <!-- Bloque: transporte -->
          <div class="bloque-envio" data-bloque="transporte" style="display:none;">
            <div class="mb-3">
              <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Transportista *</label>
              <select name="transportista_id" class="form-control">
                <option value="">-- Elegir --</option>
                {% for t in transportistas %}
                <option value="{{ t.id }}">{{ t.nombre }}</option>
                {% endfor %}
              </select>
            </div>
            <div class="mb-3">
              <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Destino *</label>
              <div class="row g-2">
                <div class="col-md-6">
                  <label class="destino-card" data-destino="domicilio" style="cursor:pointer;display:block;">
                    <input type="radio" name="destino_tipo" value="domicilio" style="display:none;">
                    <div style="border:1px solid var(--cat-border);border-radius:10px;padding:.75rem;text-align:center;font-size:.85rem;">
                      <i class="bi bi-house"></i> Domicilio
                    </div>
                  </label>
                </div>
                <div class="col-md-6">
                  <label class="destino-card" data-destino="sucursal" style="cursor:pointer;display:block;">
                    <input type="radio" name="destino_tipo" value="sucursal" style="display:none;">
                    <div style="border:1px solid var(--cat-border);border-radius:10px;padding:.75rem;text-align:center;font-size:.85rem;">
                      <i class="bi bi-building"></i> Sucursal
                    </div>
                  </label>
                </div>
              </div>
            </div>

            <div class="bloque-destino" data-destino-tipo="domicilio" style="display:none;">
              {% include 'catalogo/_form_direccion.html' %}
            </div>
            <div class="bloque-destino" data-destino-tipo="sucursal" style="display:none;">
              <div class="mb-3">
                <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Sucursal donde retiras *</label>
                <input name="sucursal_detalle" class="form-control" placeholder="Ej: Sucursal Andreani Cordoba Centro">
              </div>
              <div class="row g-2">
                <div class="col-md-6">
                  <label style="color:var(--cat-text-muted);font-size:.8rem;">Localidad</label>
                  <input name="destinatario_localidad" class="form-control">
                </div>
                <div class="col-md-6">
                  <label style="color:var(--cat-text-muted);font-size:.8rem;">Provincia</label>
                  <input name="destinatario_provincia" class="form-control">
                </div>
              </div>
            </div>
          </div>

          <!-- Bloque: envio personal -->
          <div class="bloque-envio" data-bloque="envio_personal" style="display:none;">
            <div class="cat-alert cat-alert-info" style="font-size:.85rem;margin-bottom:1rem;">Entrega personal dentro de la ciudad.</div>
            {% include 'catalogo/_form_direccion.html' %}
          </div>
        </div>

        <!-- Notas -->
        <div class="cat-form-card mt-3" style="max-width:100%;padding:1.5rem;">
          <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Notas (opcional)</h6>
          <textarea name="notas" class="form-control" rows="3" placeholder="Ej: entregar despues de las 18hs, es para regalo, etc."></textarea>
        </div>

      </div>

      <!-- Resumen -->
      <div class="col-md-4">
        <div class="cat-form-card" style="padding:1.5rem;">
          <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Tu pedido</h6>
          {% for item in items %}
          <div class="d-flex justify-content-between mb-2" style="font-size:.85rem;">
            <span>{{ item.producto.nombre }} <span style="color:var(--cat-text-muted);">x{{ item.cantidad|int }}</span></span>
            <span>${{ '%.2f'|format(item.subtotal) }}</span>
          </div>
          {% endfor %}
          <hr style="border-color:var(--cat-border);">
          <div class="d-flex justify-content-between">
            <span style="font-weight:600;">Total</span>
            <span style="color:var(--cat-accent);font-weight:600;font-size:1.2rem;">${{ '%.2f'|format(subtotal) }}</span>
          </div>
          <button type="submit" class="cat-btn w-100 text-center mt-3">Confirmar pedido</button>
          <a href="{{ url_for('catalogo.carrito') }}" style="display:block;text-align:center;margin-top:.75rem;color:var(--cat-text-muted);font-size:.85rem;text-decoration:none;">Volver al carrito</a>
        </div>
      </div>
    </div>
  </form>
</div>

<style>
.tipo-envio-card input:checked + div,
.destino-card input:checked + div {
  border-color: var(--cat-accent) !important;
  background: rgba(201,169,110,.08);
}
.tipo-envio-card:hover > div,
.destino-card:hover > div {
  border-color: var(--cat-text-muted);
}
</style>

<script>
function updateCheckoutForm() {
  const tipo = document.querySelector('input[name="tipo_envio"]:checked')?.value || '';
  const destino = document.querySelector('input[name="destino_tipo"]:checked')?.value || '';
  document.querySelectorAll('.bloque-envio').forEach(el => {
    el.style.display = el.dataset.bloque === tipo ? 'block' : 'none';
  });
  document.querySelectorAll('.bloque-destino').forEach(el => {
    el.style.display = (tipo === 'transporte' && el.dataset.destinoTipo === destino) ? 'block' : 'none';
  });
}
document.querySelectorAll('.tipo-envio-card').forEach(el => {
  el.addEventListener('click', () => {
    const radio = el.querySelector('input[type="radio"]');
    if (radio) { radio.checked = true; updateCheckoutForm(); }
  });
});
document.querySelectorAll('.destino-card').forEach(el => {
  el.addEventListener('click', () => {
    const radio = el.querySelector('input[type="radio"]');
    if (radio) { radio.checked = true; updateCheckoutForm(); }
  });
});
document.addEventListener('DOMContentLoaded', updateCheckoutForm);
</script>
{% endblock %}
'''


FORM_DIRECCION = r'''<div class="row g-2">
  <div class="col-md-12">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Destinatario</label>
    <input name="destinatario_nombre" class="form-control" placeholder="Nombre y apellido">
  </div>
  <div class="col-md-8">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Calle y altura *</label>
    <input name="destinatario_calle" class="form-control" placeholder="Ej: Av. Colon 123">
  </div>
  <div class="col-md-4">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">CP</label>
    <input name="destinatario_cp" class="form-control">
  </div>
  <div class="col-md-6">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Localidad *</label>
    <input name="destinatario_localidad" class="form-control">
  </div>
  <div class="col-md-6">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Provincia *</label>
    <input name="destinatario_provincia" class="form-control">
  </div>
  <div class="col-12">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Detalles adicionales</label>
    <input name="destinatario_detalles" class="form-control" placeholder="Piso, depto, referencias">
  </div>
</div>
'''


MIS_PEDIDOS_HTML = r'''{% extends "catalogo/base.html" %}
{% block title %}Mis pedidos — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <h1 style="font-weight:300;font-size:2rem;margin-bottom:2rem;">Mis pedidos</h1>

  {% if pedidos %}
  <div class="cat-form-card" style="max-width:100%;padding:0;">
    <table class="table" style="color:var(--cat-text);margin:0;">
      <thead>
        <tr style="border-bottom:1px solid var(--cat-border);">
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;">Pedido</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;">Fecha</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;">Estado</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;text-align:right;">Total</th>
          <th style="padding:1rem;width:50px;"></th>
        </tr>
      </thead>
      <tbody>
        {% for p in pedidos %}
        <tr style="border-bottom:1px solid var(--cat-border);">
          <td style="padding:1rem;font-weight:500;">{{ p.numero_interno }}</td>
          <td style="padding:1rem;color:var(--cat-text-muted);font-size:.85rem;">{{ p.fecha }}</td>
          <td style="padding:1rem;">
            {% if p.estado == 'pendiente_pago' %}<span class="badge-cat badge-pendiente">Pendiente pago</span>
            {% elif p.estado == 'pagado_sin_enviar' %}<span class="badge-cat" style="background:rgba(6,182,212,.15);color:#22d3ee;">Pagado - En preparacion</span>
            {% elif p.estado == 'pagado_enviado' %}<span class="badge-cat badge-aprobado">Enviado</span>
            {% else %}<span class="badge-cat badge-rechazado">Cancelado</span>{% endif %}
          </td>
          <td style="padding:1rem;text-align:right;color:var(--cat-accent);font-weight:600;">${{ '%.2f'|format(p.total) }}</td>
          <td style="padding:1rem;text-align:center;">
            <a href="{{ url_for('catalogo.mi_pedido_detalle', id=p.id) }}" style="color:var(--cat-accent);"><i class="bi bi-eye"></i></a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="text-center py-5">
    <i class="bi bi-receipt" style="font-size:4rem;color:var(--cat-border);"></i>
    <h3 style="font-weight:300;margin-top:1.5rem;color:var(--cat-text-muted);">No tenes pedidos aun</h3>
    <a href="{{ url_for('catalogo.index') }}" class="cat-btn mt-3" style="display:inline-block;">Ver catalogo</a>
  </div>
  {% endif %}
</div>
{% endblock %}
'''


MI_PEDIDO_DETALLE = r'''{% extends "catalogo/base.html" %}
{% block title %}Pedido {{ orden.numero_interno }} — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <div class="d-flex justify-content-between align-items-start mb-4">
    <div>
      <h1 style="font-weight:300;font-size:2rem;margin-bottom:.5rem;">Pedido {{ orden.numero_interno }}</h1>
      <p style="color:var(--cat-text-muted);">{{ orden.fecha }}</p>
    </div>
    <a href="{{ url_for('catalogo.mis_pedidos') }}" style="color:var(--cat-text-muted);text-decoration:none;"><i class="bi bi-arrow-left"></i> Volver</a>
  </div>

  <div class="cat-form-card" style="max-width:100%;padding:2rem;">
    <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Productos</h6>
    <table class="table" style="color:var(--cat-text);">
      <thead>
        <tr style="border-bottom:1px solid var(--cat-border);">
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:.75rem 0;">Producto</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:.75rem 0;text-align:center;">Cant.</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:.75rem 0;text-align:right;">Precio</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:.75rem 0;text-align:right;">Subtotal</th>
        </tr>
      </thead>
      <tbody>
        {% for it in items %}
        <tr style="border-bottom:1px solid var(--cat-border);">
          <td style="padding:.75rem 0;">{{ it.producto_nombre }}</td>
          <td style="padding:.75rem 0;text-align:center;">{{ '%g'|format(it.cantidad) }}</td>
          <td style="padding:.75rem 0;text-align:right;">${{ '%.2f'|format(it.precio_unitario) }}</td>
          <td style="padding:.75rem 0;text-align:right;">${{ '%.2f'|format(it.subtotal) }}</td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr>
          <td colspan="3" style="text-align:right;font-weight:600;padding-top:1rem;">Total</td>
          <td style="text-align:right;font-weight:600;color:var(--cat-accent);padding-top:1rem;font-size:1.1rem;">${{ '%.2f'|format(orden.total) }}</td>
        </tr>
      </tfoot>
    </table>

    {% if orden.notas %}
    <hr style="border-color:var(--cat-border);margin:1.5rem 0;">
    <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:.5rem;">Notas</h6>
    <p style="color:var(--cat-text);">{{ orden.notas }}</p>
    {% endif %}
  </div>
</div>
{% endblock %}
'''


def patch_catalogo_base():
    """Agrega el icono de carrito con contador al header del catalogo."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade53] no existe catalogo/base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'carrito_count' in contenido and 'catalogo.carrito' in contenido:
        print("[upgrade53] header ya tiene carrito")
        return

    # Reemplazar el bloque de boton login/logueado por uno con carrito
    buscar = '''    <div class="d-flex align-items-center gap-3">
      {% if current_mayorista %}
      <a href="{{ url_for('catalogo.mi_cuenta') }}" class="text-decoration-none text-muted-cat small">
        <i class="bi bi-person-circle"></i> {{ current_mayorista.nombre_completo.split()[0] }}
      </a>
      <a href="{{ url_for('catalogo.logout') }}" class="text-decoration-none text-muted-cat" title="Salir"><i class="bi bi-box-arrow-right"></i></a>
      {% else %}
      <a href="{{ url_for('catalogo.login') }}" class="cat-btn cat-btn-outline" style="padding:.4rem 1rem;font-size:.8rem;">Ingresar</a>
      {% endif %}
    </div>'''

    nuevo = '''    <div class="d-flex align-items-center gap-3">
      {% if current_mayorista %}
      <a href="{{ url_for('catalogo.carrito') }}" class="text-decoration-none text-muted-cat position-relative" title="Mi pedido">
        <i class="bi bi-bag fs-5"></i>
        {% if carrito_count and carrito_count > 0 %}
        <span style="position:absolute;top:-6px;right:-8px;background:var(--cat-accent);color:#0a0a0a;font-size:.65rem;font-weight:700;border-radius:10px;padding:1px 6px;">{{ carrito_count|int }}</span>
        {% endif %}
      </a>
      <a href="{{ url_for('catalogo.mis_pedidos') }}" class="text-decoration-none text-muted-cat small" title="Mis pedidos">
        <i class="bi bi-receipt"></i>
      </a>
      <a href="{{ url_for('catalogo.mi_cuenta') }}" class="text-decoration-none text-muted-cat small">
        <i class="bi bi-person-circle"></i> {{ current_mayorista.nombre_completo.split()[0] }}
      </a>
      <a href="{{ url_for('catalogo.logout') }}" class="text-decoration-none text-muted-cat" title="Salir"><i class="bi bi-box-arrow-right"></i></a>
      {% else %}
      <a href="{{ url_for('catalogo.login') }}" class="cat-btn cat-btn-outline" style="padding:.4rem 1rem;font-size:.8rem;">Ingresar</a>
      {% endif %}
    </div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade53] header del catalogo con carrito")
    else:
        print("[upgrade53] ADVERTENCIA: no se encontro el bloque del header")


def patch_producto_detalle():
    """Reemplaza el boton 'Agregar al pedido' por un form que agrega al carrito."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'producto.html')
    if not os.path.exists(ruta):
        print("[upgrade53] no existe catalogo/producto.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'catalogo.carrito_agregar' in contenido:
        print("[upgrade53] producto.html ya tiene carrito")
        return

    buscar = '''          <div class="d-flex gap-3 flex-wrap">
            <a href="#" class="cat-btn"><i class="bi bi-bag-plus"></i> Agregar al pedido</a>
            <a href="{{ url_for('catalogo.index') }}" class="cat-btn cat-btn-outline"><i class="bi bi-arrow-left"></i> Seguir comprando</a>
          </div>'''

    nuevo = '''          {% if current_mayorista %}
          <form method="post" action="{{ url_for('catalogo.carrito_agregar', producto_id=producto.id) }}" class="d-flex gap-2 flex-wrap align-items-center mb-3">
            <div style="display:flex;align-items:center;gap:.5rem;background:var(--cat-surface-2);border:1px solid var(--cat-border);border-radius:8px;padding:.4rem;">
              <button type="button" onclick="cambiarCant(-1)" style="background:none;border:none;color:var(--cat-text);font-size:1.2rem;cursor:pointer;padding:0 .5rem;">−</button>
              <input type="number" name="cantidad" id="cant-input" value="1" min="1" step="1" style="width:60px;text-align:center;background:none;border:none;color:var(--cat-text);font-weight:500;">
              <button type="button" onclick="cambiarCant(1)" style="background:none;border:none;color:var(--cat-text);font-size:1.2rem;cursor:pointer;padding:0 .5rem;">+</button>
            </div>
            <button type="submit" class="cat-btn"><i class="bi bi-bag-plus"></i> Agregar al pedido</button>
          </form>
          <script>
          function cambiarCant(delta) {
            const input = document.getElementById('cant-input');
            let v = parseInt(input.value) || 1;
            v = Math.max(1, v + delta);
            input.value = v;
          }
          </script>
          {% else %}
          <div class="cat-alert cat-alert-info" style="font-size:.85rem;">
            <a href="{{ url_for('catalogo.login') }}">Ingresa a tu cuenta</a> para agregar productos al pedido.
          </div>
          {% endif %}
          <div class="d-flex gap-3 flex-wrap">
            <a href="{{ url_for('catalogo.index') }}" class="cat-btn cat-btn-outline"><i class="bi bi-arrow-left"></i> Seguir comprando</a>
          </div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade53] producto.html con boton agregar al carrito")
    else:
        print("[upgrade53] ADVERTENCIA: no se encontro el bloque del boton en producto.html")


def patch_catalogo_index():
    """Agrega un boton rapido 'agregar' en las cards del catalogo."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'index.html')
    if not os.path.exists(ruta):
        print("[upgrade53] no existe catalogo/index.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'carrito_agregar' in contenido:
        print("[upgrade53] index ya tiene boton agregar")
        return

    buscar = '''      <div class="cat-card-body">
        {% if p.categoria_nombre %}
        <div class="cat-card-cat">{{ p.categoria_nombre }}</div>
        {% endif %}
        <div class="cat-card-title">{{ p.nombre }}</div>
        <div class="cat-card-price">${{ '%.2f'|format(p.precio) }}</div>
      </div>
    </a>'''

    nuevo = '''      <div class="cat-card-body">
        {% if p.categoria_nombre %}
        <div class="cat-card-cat">{{ p.categoria_nombre }}</div>
        {% endif %}
        <div class="cat-card-title">{{ p.nombre }}</div>
        <div class="cat-card-price">${{ '%.2f'|format(p.precio) }}</div>
      </div>
    </a>'''

    # No agregamos boton rapido en cards por ahora (mejor que el cliente entre al detalle)
    print("[upgrade53] catalogo/index.html sin cambios (agregar desde detalle)")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 53: Carrito + Checkout + Orden automatica (F6.3) ===")
    migrar()
    escribir('app53.py', APP53_PY)
    escribir('templates/catalogo/carrito.html', CATALOGO_CARRITO)
    escribir('templates/catalogo/checkout.html', CATALOGO_CHECKOUT)
    escribir('templates/catalogo/_form_direccion.html', FORM_DIRECCION)
    escribir('templates/catalogo/mis_pedidos.html', MIS_PEDIDOS_HTML)
    escribir('templates/catalogo/mi_pedido_detalle.html', MI_PEDIDO_DETALLE)
    patch_catalogo_base()
    patch_producto_detalle()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()