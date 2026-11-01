
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required, aplicar_descuento_stock, revertir_stock
from database import get_db
from app4 import enviar_email, get_config, render_plantilla, construir_contexto, _cargar_orden
import os

# --- NUEVO: NOTIFICAR EMAIL Y CAMBIAR ESTADO ---
# Monkey-patch: eliminamos el decorador de ruta para forzar el reemplazo
@login_required
@permiso_required('ventas')
def ventas_email_enviar_v3(id, tipo):
    TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'factura', 'entrega'}
    if tipo not in TIPOS_VALIDOS:
        from flask import abort
        abort(404)
        
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))

    destino = request.form.get('destinatario') or orden['cliente_email']
    if not destino or '@' not in destino:
        conn.close(); flash('El cliente no tiene email o es invalido.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    remitente_email = request.form.get('remitente_email', '').strip()
    remitente_override = None
    if remitente_email and current_user.es_admin:
        from app39 import _remitente_por_email
        remitente_override = _remitente_por_email(conn, remitente_email)
    elif not current_user.es_admin:
        row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if row and row['email_remitente']:
            remitente_override = {'email': row['email_remitente'], 'nombre': row['nombre_remitente'] or row['nombre']}

    ctx = construir_contexto(orden, conn, tipo)
    asunto = render_plantilla(get_config(f'plantilla_{tipo}_asunto'), ctx)
    cuerpo = render_plantilla(get_config(f'plantilla_{tipo}_cuerpo'), ctx)

    adjuntos = []
    adj_ids = request.form.getlist('adjunto_id')
    if adj_ids:
        for aid in adj_ids:
            a = conn.execute("SELECT * FROM archivos WHERE id=? AND orden_id=?", (int(aid), id)).fetchone()
            if a:
                ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', a['ruta_local'])
                if os.path.exists(ruta):
                    adjuntos.append((ruta, a['nombre_original']))

    from app39 import _enviar_con_remitente
    ok, msg = _enviar_con_remitente(destino, asunto, cuerpo, remitente_override=remitente_override, adjuntos=adjuntos)

    remitente_usado = remitente_override['email'] if remitente_override else get_config('smtp_remitente_email')
    conn.execute("INSERT INTO emails_enviados (destinatario, asunto, tipo, orden_id, estado, remitente) VALUES (?,?,?,?,?,?)",
                 (destino, asunto, tipo, id, 'ok' if ok else 'error', remitente_usado))
    
    # --- LOGICA DE NEGOCIO: CAMBIAR ESTADO AUTOMATICAMENTE ---
    if ok:
        if tipo == 'pago' and orden['estado'] == 'pendiente_pago':
            if not orden['stock_descontado']:
                aplicar_descuento_stock(conn, id, current_user.id)
            conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
            flash('Pago notificado. La orden cambió a Pagado / Sin enviar.', 'success')
        elif tipo == 'envio' and orden['estado'] == 'pagado_sin_enviar':
            conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado' WHERE id=?", (id,))
            flash('Envío notificado. La orden cambió a Pagado / Enviado.', 'success')
        else:
            flash('Notificación enviada.', 'success')
    else:
        flash(msg, 'error')
        
    conn.commit(); conn.close()
    return redirect(url_for('ventas_detalle', id=id))


# --- NUEVO: EDITAR PRODUCTOS DE LA ORDEN ---
@app.route('/ventas/<int:id>/items/agregar', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_agregar_item(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
        
    prod_id = request.form.get('producto_id')
    cant = float(request.form.get('cantidad', 0))
    precio = float(request.form.get('precio', 0))
    
    if not prod_id or cant <= 0:
        conn.close(); flash('Selecciona un producto y cantidad válida.', 'error'); return redirect(url_for('ventas_detalle', id=id))
        
    prod = conn.execute("SELECT * FROM productos WHERE id=?", (prod_id,)).fetchone()
    if not prod:
        conn.close(); flash('Producto no encontrado.', 'error'); return redirect(url_for('ventas_detalle', id=id))
        
    # Insertar item
    conn.execute("INSERT INTO orden_items (orden_id, producto_id, cantidad, precio_unitario, subtotal) VALUES (?,?,?,?,?)",
                 (id, prod_id, cant, precio, cant * precio))
                 
    # Actualizar totales de la orden
    nuevo_subtotal = orden['subtotal'] + (cant * precio)
    nuevo_total = nuevo_subtotal - orden['descuento']
    conn.execute("UPDATE ordenes_venta SET subtotal=?, total=? WHERE id=?", (nuevo_subtotal, nuevo_total, id))
    
    # Actualizar stock si ya estaba pagada
    if orden['stock_descontado']:
        conn.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id=?", (cant, prod_id))
        conn.execute("INSERT INTO movimientos_stock (producto_id, tipo, cantidad, referencia, usuario_id) VALUES (?, 'salida', ?, ?, ?)",
                     (prod_id, cant, f'Modificación Orden #{id}', current_user.id))
                     
    conn.commit(); conn.close()
    flash('Producto agregado a la orden.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


@app.route('/ventas/<int:id>/items/<int:item_id>/eliminar', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_eliminar_item(id, item_id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    item = conn.execute("SELECT * FROM orden_items WHERE id=? AND orden_id=?", (item_id, id)).fetchone()
    
    if not orden or not item:
        conn.close(); flash('Item no encontrado.', 'error'); return redirect(url_for('ventas_detalle', id=id))
        
    # Eliminar item
    conn.execute("DELETE FROM orden_items WHERE id=?", (item_id,))
    
    # Actualizar totales
    nuevo_subtotal = orden['subtotal'] - item['subtotal']
    nuevo_total = nuevo_subtotal - orden['descuento']
    conn.execute("UPDATE ordenes_venta SET subtotal=?, total=? WHERE id=?", (nuevo_subtotal, nuevo_total, id))
    
    # Devolver stock si ya estaba pagada
    if orden['stock_descontado']:
        conn.execute("UPDATE productos SET stock_actual = stock_actual + ? WHERE id=?", (item['cantidad'], item['producto_id']))
        conn.execute("INSERT INTO movimientos_stock (producto_id, tipo, cantidad, referencia, usuario_id) VALUES (?, 'entrada', ?, ?, ?)",
                     (item['producto_id'], item['cantidad'], f'Modificación Orden #{id}', current_user.id))
                     
    conn.commit(); conn.close()
    flash('Producto eliminado de la orden.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


# Forzar a Flask a usar esta funcion para la ruta de emails
app.view_functions['ventas_email_enviar'] = ventas_email_enviar_v3
