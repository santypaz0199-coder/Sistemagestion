
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
