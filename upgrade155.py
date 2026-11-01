# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade155] escrito: {relpath}")


APP155_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required, aplicar_descuento_stock, revertir_stock
from database import get_db
from datetime import date
import os
from app4 import _cargar_orden, get_config, construir_contexto, render_plantilla
from app39 import _remitentes_disponibles, _enviar_con_remitente, _remitente_por_email

def _registrar_pago_automatico(conn, orden_id, total, usuario_id):
    pagos_totales = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE orden_id=?", (orden_id,)).fetchone()[0]
    if pagos_totales < total:
        falta = total - pagos_totales
        medio = conn.execute("SELECT id FROM medios_pago LIMIT 1").fetchone()
        medio_id = medio['id'] if medio else None
        conn.execute("""INSERT INTO pagos 
            (orden_id, fecha, medio_pago_id, monto, comision, monto_neto, usuario_id, notas)
            VALUES (?, ?, ?, ?, 0, ?, ?, 'Pago automatico (cuadre)')""",
            (orden_id, date.today().isoformat(), medio_id, falta, falta, usuario_id))

# ===== VISTA PRINCIPAL DE LA ORDEN =====
@app.route('/ventas/<int:id>')
@login_required
@permiso_required('ventas')
def ventas_detalle_v5(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))

    items = conn.execute("""SELECT oi.*, p.nombre as producto_nombre, p.sku, p.peso_valor, p.peso_unidad 
        FROM orden_items oi JOIN productos p ON p.id=oi.producto_id
        WHERE oi.orden_id=?""", (id,)).fetchall()
        
    pagos = conn.execute("""SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg
        LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id
        WHERE pg.orden_id=? ORDER BY pg.id""", (id,)).fetchall()
    total_pagado = sum(p['monto'] for p in pagos)
    
    medios = conn.execute("SELECT * FROM medios_pago WHERE activo=1 ORDER BY nombre").fetchall()
    transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1 ORDER BY nombre").fetchall()
    archivos = conn.execute("SELECT * FROM archivos WHERE orden_id=? ORDER BY id DESC", (id,)).fetchall()
    
    remitentes_disponibles = _remitentes_disponibles(conn)
    
    transportista_url = None
    if orden['transportista_id']:
        t = conn.execute("SELECT url_seguimiento FROM transportistas WHERE id=?", (orden['transportista_id'],)).fetchone()
        if t: transportista_url = t['url_seguimiento']

    # Provincias y Localidades
    provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
    locs_rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    localidades_por_provincia = {}
    for r in locs_rows:
        localidades_por_provincia.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})
        
    todos_productos = conn.execute("SELECT id, nombre, precio, stock_actual FROM productos WHERE activo=1 ORDER BY nombre").fetchall()

    # Kilos totales
    kilos_total = 0
    for it in items:
        pv = it['peso_valor'] or 0
        if it['peso_unidad'] == 'g': kilos_total += (it['cantidad'] * pv) / 1000.0
        else: kilos_total += it['cantidad'] * pv

    conn.close()
    return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, medios=medios, transportistas=transportistas,
                           archivos=archivos, remitentes_disponibles=remitentes_disponibles,
                           transportista_url_actual=transportista_url,
                           provincias=provincias, localidades_por_provincia=localidades_por_provincia,
                           todos_productos=todos_productos, kilos_total=kilos_total)

app.view_functions['ventas_detalle'] = ventas_detalle_v5


# ===== EDITAR ITEMS =====
@app.route('/ventas/<int:id>/items/agregar', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_agregar_item_v2(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden: conn.close(); return redirect(url_for('ventas_lista'))
    
    prod_id = request.form.get('producto_id')
    try:
        cant = float(request.form.get('cantidad', 0))
        precio = float(request.form.get('precio', 0))
    except ValueError:
        flash('Cantidad o precio inválido.', 'error'); return redirect(url_for('ventas_detalle', id=id))
        
    if not prod_id or cant <= 0:
        flash('Selecciona un producto y cantidad válida.', 'error'); return redirect(url_for('ventas_detalle', id=id))
        
    conn.execute("INSERT INTO orden_items (orden_id, producto_id, cantidad, precio_unitario, subtotal) VALUES (?,?,?,?,?)",
                 (id, prod_id, cant, precio, cant * precio))
                 
    nuevo_subtotal = orden['subtotal'] + (cant * precio)
    nuevo_total = nuevo_subtotal - orden['descuento']
    conn.execute("UPDATE ordenes_venta SET subtotal=?, total=? WHERE id=?", (nuevo_subtotal, nuevo_total, id))
    
    if orden['stock_descontado']:
        conn.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id=?", (cant, prod_id))
        conn.execute("INSERT INTO movimientos_stock (producto_id, tipo, cantidad, referencia, usuario_id) VALUES (?, 'salida', ?, ?, ?)",
                     (prod_id, cant, f'Modificación Orden #{id}', current_user.id))
                     
    conn.commit(); conn.close()
    flash('Producto agregado.', 'success')
    return redirect(url_for('ventas_detalle', id=id))

@app.route('/ventas/<int:id>/items/<int:item_id>/eliminar', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_eliminar_item_v2(id, item_id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    item = conn.execute("SELECT * FROM orden_items WHERE id=? AND orden_id=?", (item_id, id)).fetchone()
    
    if not orden or not item: conn.close(); return redirect(url_for('ventas_detalle', id=id))
        
    conn.execute("DELETE FROM orden_items WHERE id=?", (item_id,))
    nuevo_subtotal = orden['subtotal'] - item['subtotal']
    nuevo_total = nuevo_subtotal - orden['descuento']
    conn.execute("UPDATE ordenes_venta SET subtotal=?, total=? WHERE id=?", (nuevo_subtotal, nuevo_total, id))
    
    if orden['stock_descontado']:
        conn.execute("UPDATE productos SET stock_actual = stock_actual + ? WHERE id=?", (item['cantidad'], item['producto_id']))
        conn.execute("INSERT INTO movimientos_stock (producto_id, tipo, cantidad, referencia, usuario_id) VALUES (?, 'entrada', ?, ?, ?)",
                     (item['producto_id'], item['cantidad'], f'Modificación Orden #{id}', current_user.id))
                     
    conn.commit(); conn.close()
    flash('Producto eliminado.', 'success')
    return redirect(url_for('ventas_detalle', id=id))

app.view_functions['ventas_agregar_item'] = ventas_agregar_item_v2
app.view_functions['ventas_eliminar_item'] = ventas_eliminar_item_v2


# ===== CAMBIAR ESTADO =====
@app.route('/ventas/<int:id>/estado', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_estado_v5(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden: conn.close(); return redirect(url_for('ventas_lista'))
    
    nuevo = request.form['estado']
    actual = orden['estado']
    
    if actual == nuevo:
        conn.close(); flash('La orden ya está en ese estado.', 'info'); return redirect(url_for('ventas_detalle', id=id))

    trans = {
        'pendiente_pago': ['pagado_sin_enviar', 'cancelado'],
        'pagado_sin_enviar': ['pagado_enviado', 'cancelado', 'pendiente_pago'],
        'pagado_enviado': ['cancelado', 'pagado_sin_enviar'],
        'cancelado': ['pendiente_pago']
    }
    
    if nuevo not in trans.get(actual, []):
        conn.close(); flash('Transición de estado no permitida.', 'error'); return redirect(url_for('ventas_detalle', id=id))

    if nuevo == 'cancelado':
        if orden['stock_descontado']: revertir_stock(conn, id, current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='cancelado' WHERE id=?", (id,))
    elif nuevo == 'pagado_sin_enviar':
        if not orden['stock_descontado']: aplicar_descuento_stock(conn, id, current_user.id)
        _registrar_pago_automatico(conn, id, orden['total'], current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
    elif nuevo == 'pagado_enviado':
        if not orden['stock_descontado']: aplicar_descuento_stock(conn, id, current_user.id)
        _registrar_pago_automatico(conn, id, orden['total'], current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado' WHERE id=?", (id,))
    elif nuevo == 'pendiente_pago':
        if orden['stock_descontado']: revertir_stock(conn, id, current_user.id)
        conn.execute("DELETE FROM pagos WHERE orden_id=? AND notas='Pago automatico (cuadre)'", (id,))
        conn.execute("UPDATE ordenes_venta SET estado='pendiente_pago' WHERE id=?", (id,))

    conn.commit(); conn.close()
    flash(f'Estado actualizado a {nuevo}.', 'success')
    return redirect(url_for('ventas_detalle', id=id))

app.view_functions['ventas_estado'] = ventas_estado_v5
'''

def patch_run_bat():
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; import app152; import app155; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat)
    print("[upgrade155] run.bat actualizado")

VENTAS_DETALLE_HTML = r'''{% extends "base.html" %}
{% block title %}{{ orden.numero_interno }}{% endblock %}
{% block content %}
<style>
  .ticket-card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
  .ticket-title { font-size: 1rem; font-weight: 600; color: #4b5563; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; }
  .info-label { font-size: 0.8rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.2rem; }
  .info-value { font-size: 1rem; font-weight: 500; color: #111827; }
  .table-productos th { font-size: 0.75rem; text-transform: uppercase; color: #6b7280; border-bottom: 2px solid #e5e7eb; padding: 1rem 0.5rem; }
  .table-productos td { vertical-align: middle; padding: 1rem 0.5rem; border-bottom: 1px solid #f3f4f6; }
</style>

<div class="d-flex justify-content-between align-items-center mb-4">
    <div>
        <h3 class="mb-1" style="font-weight:700; letter-spacing:-.02em;">Orden {{ orden.numero_interno }}
            {% if orden.estado == 'pendiente_pago' %}<span class="badge bg-warning text-dark ms-2 fs-6">Pendiente pago</span>
            {% elif orden.estado == 'pagado_sin_enviar' %}<span class="badge bg-info text-dark ms-2 fs-6">Pagado / Sin enviar</span>
            {% elif orden.estado == 'pagado_enviado' %}<span class="badge bg-success ms-2 fs-6">Pagado / Enviado</span>
            {% else %}<span class="badge bg-secondary ms-2 fs-6">Cancelado</span>{% endif %}
        </h3>
        <div class="text-muted">{{ orden.fecha }} · {{ orden.vendedor_nombre }} · {{ orden.canal_nombre or 'Sin canal' }}</div>
    </div>
    <div class="d-flex gap-2">
        <a href="{{ url_for('ventas_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
        <a href="{{ url_for('ventas_imprimir', id=orden.id) }}" target="_blank" class="btn btn-outline-dark"><i class="bi bi-printer"></i> Imprimir / PDF</a>
    </div>
</div>

<div class="row g-4">
    <!-- COLUMNA IZQUIERDA -->
    <div class="col-md-8">
        
        <!-- INFO CLIENTE -->
        <div class="ticket-card">
            <div class="ticket-title">
                <span>Información del comprador</span>
                <a href="{{ url_for('clientes_editar', id=orden.cliente_id) }}" class="text-decoration-none small">Ver ficha del cliente</a>
            </div>
            <div class="row g-3">
                <div class="col-md-6">
                    <div class="info-label">Nombre en el pedido</div>
                    <div class="info-value">{{ orden.cliente_nombre }}</div>
                </div>
                <div class="col-md-6">
                    <div class="info-label">E-mail en el pedido</div>
                    <div class="info-value">{{ orden.cliente_email or '—' }}</div>
                </div>
                <div class="col-md-6">
                    <div class="info-label">Teléfono en el pedido</div>
                    <div class="info-value">{{ orden.cliente_telefono or '—' }}</div>
                </div>
                <div class="col-md-6">
                    <div class="info-label">Documento</div>
                    <div class="info-value">{{ orden.cliente_tipo_doc or '' }} {{ orden.cliente_doc or '' }}</div>
                </div>
            </div>
        </div>

        <!-- PRODUCTOS -->
        <div class="ticket-card">
            <div class="ticket-title">Productos ({{ items|length }} items)</div>
            <table class="table table-sm table-productos mb-0">
                <thead>
                    <tr>
                        <th>Producto</th>
                        <th class="text-end">Cant.</th>
                        <th class="text-end">Precio</th>
                        <th class="text-end">Subtotal</th>
                        <th class="text-end"></th>
                    </tr>
                </thead>
                <tbody>
                    {% for it in items %}
                    <tr>
                        <td class="fw-semibold">{{ it.producto_nombre }} {% if it.sku %}<div class="small text-muted">{{ it.sku }}</div>{% endif %}</td>
                        <td class="text-end">{{ '%g'|format(it.cantidad) }}</td>
                        <td class="text-end">{{ it.precio_unitario|pesos }}</td>
                        <td class="text-end fw-semibold">{{ it.subtotal|pesos }}</td>
                        <td class="text-end">
                            {% if orden.estado != 'cancelado' %}
                            <form method="post" action="{{ url_for('ventas_eliminar_item', id=orden.id, item_id=it.id) }}" class="d-inline" onsubmit="return confirm('Eliminar este producto?')">
                                <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button>
                            </form>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
                <tfoot>
                    <tr>
                        <td colspan="3" class="text-end text-muted small text-uppercase fw-semibold pt-3">Kilos totales:</td>
                        <td class="text-end fw-bold pt-3">{{ '%.2f'|format(kilos_total) }} kg</td>
                        <td></td>
                    </tr>
                </tfoot>
            </table>

            {% if orden.estado != 'cancelado' %}
            <div class="mt-4 p-3 bg-light rounded border">
                <h6 class="mb-2 text-muted small">Añadir producto a esta orden</h6>
                <form method="post" action="{{ url_for('ventas_agregar_item', id=orden.id) }}" class="row g-2 align-items-end">
                    <div class="col-md-6">
                        <select name="producto_id" class="form-select form-select-sm" required>
                            <option value="">Seleccionar producto...</option>
                            {% for p in todos_productos %}
                            <option value="{{ p.id }}" data-precio="{{ p.precio }}">{{ p.nombre }} (Stock: {{ p.stock_actual|int }})</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-md-2">
                        <input type="number" step="0.01" min="0.01" name="cantidad" class="form-control form-control-sm" value="1" required>
                    </div>
                    <div class="col-md-2">
                        <input type="number" step="0.01" min="0" name="precio" class="form-control form-control-sm" required>
                    </div>
                    <div class="col-md-2">
                        <button type="submit" class="btn btn-sm btn-dark w-100">Sumar</button>
                    </div>
                </form>
            </div>
            {% endif %}
        </div>

        <!-- NOTIFICACIONES -->
        <div class="ticket-card">
            <div class="ticket-title">Notificaciones por email</div>
            <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-confirmacion">Enviar orden</button>
                
                {% if orden.estado == 'pendiente_pago' %}
                <button class="btn btn-outline-success btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-pago">Notificar pago</button>
                <button class="btn btn-outline-info btn-sm" disabled>Notificar envío</button>
                {% elif orden.estado == 'pagado_sin_enviar' %}
                <button class="btn btn-outline-success btn-sm" disabled>Pago acreditado</button>
                <button class="btn btn-outline-info btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-envio">Notificar envío</button>
                {% else %}
                <button class="btn btn-outline-success btn-sm" disabled>Pago acreditado</button>
                <button class="btn btn-outline-info btn-sm" disabled>Envío notificado</button>
                {% endif %}
                
                <button class="btn btn-outline-dark btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-factura">Enviar factura</button>
            </div>
            
            {% set tipos = [('confirmacion','mail-confirmacion','Enviar orden'),('pago','mail-pago','Notificar pago'),('envio','mail-envio','Notificar envío'),('factura','mail-factura','Enviar factura')] %}
            {% for t, col, tit in tipos %}
            <div class="collapse mt-3" id="{{ col }}">
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo=t) }}" class="border rounded p-3 bg-light">
                    <div class="mb-2">
                        <label class="form-label small">Destinatario</label>
                        <input name="destinatario" type="email" class="form-control form-control-sm" value="{{ orden.cliente_email or '' }}" required>
                    </div>
                    <button class="btn btn-primary btn-sm">Enviar correo</button>
                </form>
            </div>
            {% endfor %}
        </div>

        <!-- COMENTARIOS / NOTAS -->
        <div class="ticket-card">
            <div class="ticket-title">Comentarios para el cliente</div>
            <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}"> <!-- Temporal -->
            <textarea class="form-control" rows="4" placeholder="Términos y condiciones, notas del pedido...">{{ orden.notas or '' }}</textarea>
            </form>
        </div>

    </div>

    <!-- COLUMNA DERECHA -->
    <div class="col-md-4">
        
        <!-- RESUMEN FINANCIERO -->
        <div class="ticket-card" style="background:#fafbfd;">
            <div class="ticket-title">Resumen comercial</div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Subtotal</span>
                <span>{{ orden.subtotal|pesos }}</span>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Descuento</span>
                <span class="text-danger">-{{ orden.descuento|pesos }}</span>
            </div>
            <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Costo de envío</span>
                <span>{{ orden.costo_envio|pesos }}</span>
            </div>
            <hr>
            <div class="d-flex justify-content-between align-items-center">
                <span class="fw-bold fs-6">Total</span>
                <span class="fw-bold fs-4 text-success">{{ orden.total|pesos }}</span>
            </div>
        </div>

        <!-- PAGOS -->
        <div class="ticket-card">
            <div class="ticket-title">Pagos</div>
            <div class="d-flex justify-content-between mb-3">
                <span class="text-muted">Total pagado</span>
                <span class="fw-bold text-success">{{ total_pagado|pesos }}</span>
            </div>
            {% if pagos %}
            <ul class="list-unstyled small mb-3">
                {% for p in pagos %}
                <li class="d-flex justify-content-between border-bottom py-1">
                    <span>{{ p.fecha }} - {{ p.medio_nombre or '—' }}</span>
                    <strong>{{ p.monto|pesos }}</strong>
                </li>
                {% endfor %}
            </ul>
            {% endif %}
            
            {% if orden.estado != 'cancelado' and total_pagado < orden.total %}
            <button class="btn btn-outline-primary btn-sm w-100" data-bs-toggle="collapse" data-bs-target="#pago-form">Registrar Pago</button>
            <div class="collapse mt-2" id="pago-form">
                <form method="post" action="{{ url_for('ventas_pago', id=orden.id) }}" class="border rounded p-2 bg-light">
                    <div class="mb-2">
                        <input type="number" step="0.01" name="monto" class="form-control form-control-sm" value="{{ '%.2f'|format(orden.total - total_pagado) }}" required>
                    </div>
                    <div class="mb-2">
                        <select name="medio_pago_id" class="form-select form-select-sm">
                            {% for m in medios %}<option value="{{ m.id }}">{{ m.nombre }}</option>{% endfor %}
                        </select>
                    </div>
                    <button class="btn btn-primary btn-sm w-100">Registrar</button>
                </form>
            </div>
            {% endif %}
        </div>

        <!-- ESTADO DE LA ORDEN -->
        <div class="ticket-card">
            <div class="ticket-title">Estado de la orden</div>
            <form method="post" action="{{ url_for('ventas_estado', id=orden.id) }}">
                <select name="estado" class="form-select mb-2">
                    <option value="pendiente_pago" {% if orden.estado=='pendiente_pago' %}selected{% endif %}>Pendiente de pago</option>
                    <option value="pagado_sin_enviar" {% if orden.estado=='pagado_sin_enviar' %}selected{% endif %}>Pagado / Sin enviar</option>
                    <option value="pagado_enviado" {% if orden.estado=='pagado_enviado' %}selected{% endif %}>Pagado / Enviado</option>
                    <option value="cancelado" {% if orden.estado=='cancelado' %}selected{% endif %}>Cancelado</option>
                </select>
                <button class="btn btn-dark w-100">Actualizar Estado</button>
            </form>
        </div>

        <!-- DATOS DE ENVIO -->
        <div class="ticket-card">
            <div class="ticket-title">Detalles de la entrega</div>
            
            <form method="post" action="{{ url_for('ventas_envio', id=orden.id) }}">
                <div class="form-check mb-3">
                    <input class="form-check-input" type="checkbox" id="chk-usar-datos" onchange="toggleEnvio()">
                    <label class="form-check-label small" for="chk-usar-datos">Modificar dirección de envío</label>
                </div>
                
                <div id="bloque-envio" style="display:none;">
                    <div class="mb-2">
                        <label class="form-label small">Transportista</label>
                        <select name="transportista_id" class="form-select form-select-sm">
                            <option value="">--</option>
                            {% for t in transportistas %}
                            <option value="{{ t.id }}" {% if orden.transportista_id==t.id %}selected{% endif %}>{{ t.nombre }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small">Nro Guía</label>
                        <input name="nro_guia" class="form-control form-control-sm" value="{{ orden.nro_guia or '' }}">
                    </div>
                    <div class="mb-2">
                        <label class="form-label small">Destinatario</label>
                        <input name="destinatario_nombre" class="form-control form-control-sm" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}">
                    </div>
                    <div class="mb-2">
                        <label class="form-label small">Dirección</label>
                        <input name="destinatario_calle" class="form-control form-control-sm" value="{{ orden.destinatario_calle or '' }}">
                    </div>
                    <button class="btn btn-primary btn-sm w-100">Guardar Envío</button>
                </div>
                
                {% if orden.nro_guia %}
                <div class="alert alert-info py-2 px-3 mt-3 mb-0 small">
                    <i class="bi bi-truck"></i> Guía: <strong>{{ orden.nro_guia }}</strong>
                    {% if transportista_url_actual %}
                    <br><a href="{{ construir_url_seguimiento(transportista_url_actual, orden.nro_guia) }}" target="_blank" class="text-decoration-none">Ver seguimiento</a>
                    {% endif %}
                </div>
                {% endif %}
            </form>
        </div>

    </div>
</div>

<script>
function toggleEnvio() {
    const chk = document.getElementById('chk-usar-datos');
    document.getElementById('bloque-envio').style.display = chk.checked ? 'block' : 'none';
}
document.addEventListener('DOMContentLoaded', () => {
    // Auto-completar precio al elegir producto
    const selectProd = document.querySelector('select[name="producto_id"]');
    if (selectProd) {
        selectProd.addEventListener('change', function() {
            const opt = this.options[this.selectedIndex];
            if (opt.dataset.precio) {
                this.closest('form').querySelector('input[name="precio"]').value = opt.dataset.precio;
            }
        });
    }
});
</script>
{% endblock %}
'''

def main():
    print("=== Upgrade 155: Rediseño total del Detalle de Orden ===")
    escribir('app155.py', APP155_PY)
    patch_run_bat()
    escribir('templates/ventas/detalle.html', VENTAS_DETALLE_HTML)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()