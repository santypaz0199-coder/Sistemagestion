# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade145] escrito: {relpath}")

# 1. CREAR LAS RUTAS PARA SUMAR/RESTAR PRODUCTOS Y NOTIFICACIONES INTELIGENTES
APP145_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app142 import app
from app import permiso_required, aplicar_descuento_stock, revertir_stock
from database import get_db
from app4 import enviar_email, get_config, render_plantilla, construir_contexto, _cargar_orden
import os

# --- NUEVO: NOTIFICAR EMAIL Y CAMBIAR ESTADO ---
@app.route('/ventas/<int:id>/email/<tipo>', methods=['POST'])
@login_required
@permiso_requerido('ventas')
def ventas_email_enviar_v3(id, tipo):
    TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'entrega', 'factura'}
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
@permiso_requerido('ventas')
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
@permiso_requerido('ventas')
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
'''

def patch_run_bat():
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat)
    print("[upgrade145] run.bat actualizado")

def patch_detalle_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Modificar la tabla de productos para agregar el botón de eliminar
    buscar_tabla = r'''<table class="table table-sm mb-0"><thead><tr><th>Producto</th><th class="text-end">Cant.</th><th class="text-end">Precio</th><th class="text-end">Subtotal</th></tr></thead><tbody>
{% for it in items %}<tr><td>{{ it.producto_nombre }} {% if it.sku %}<small class="text-muted">({{ it.sku }})</small>{% endif %}</td><td class="text-end">{{ '%g'|format(it.cantidad) }}</td><td class="text-end">${{ '%.2f'|format(it.precio_unitario) }}</td><td class="text-end">${{ '%.2f'|format(it.subtotal) }}</td></tr>{% endfor %}
</tbody></table>'''

    nueva_tabla = r'''<table class="table table-sm mb-0"><thead><tr><th>Producto</th><th class="text-end">Cant.</th><th class="text-end">Precio</th><th class="text-end">Subtotal</th><th></th></tr></thead><tbody>
{% for it in items %}
<tr>
    <td>{{ it.producto_nombre }} {% if it.sku %}<small class="text-muted">({{ it.sku }})</small>{% endif %}</td>
    <td class="text-end">{{ '%g'|format(it.cantidad) }}</td>
    <td class="text-end">{{ it.precio_unitario|pesos }}</td>
    <td class="text-end">{{ it.subtotal|pesos }}</td>
    <td class="text-end">
        {% if orden.estado != 'cancelado' %}
        <form method="post" action="{{ url_for('ventas_eliminar_item', id=orden.id, item_id=it.id) }}" class="d-inline" onsubmit="return confirm('Eliminar este producto de la orden?')">
            <button class="btn btn-sm btn-outline-danger py-0 px-1"><i class="bi bi-x-lg"></i></button>
        </form>
        {% endif %}
    </td>
</tr>
{% endfor %}
</tbody></table>

{% if orden.estado != 'cancelado' %}
<div class="mt-3 p-3 bg-light rounded border">
    <h6 class="mb-2 text-muted small">Agregar más productos a esta orden</h6>
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
            <input type="number" step="0.01" min="0.01" name="cantidad" class="form-control form-control-sm" value="1" required placeholder="Cant">
        </div>
        <div class="col-md-2">
            <input type="number" step="0.01" min="0" name="precio" class="form-control form-control-sm" required placeholder="Precio">
        </div>
        <div class="col-md-2">
            <button type="submit" class="btn btn-sm btn-dark w-100"><i class="bi bi-plus-lg"></i> Sumar</button>
        </div>
    </form>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {
    const select = document.querySelector('select[name="producto_id"]');
    if (select) {
        select.addEventListener('change', function() {
            const opt = this.options[this.selectedIndex];
            if (opt.dataset.precio) {
                this.closest('form').querySelector('input[name="precio"]').value = opt.dataset.precio;
            }
        });
    }
});
</script>
{% endif %}'''

    if buscar_tabla in contenido:
        contenido = contenido.replace(buscar_tabla, nueva_tabla)
        print("[upgrade145] Tabla de productos modificada para editar items")

    # 2. Actualizar los botones de notificacion para que sean estrictos
    buscar_botones = r'''<div class="d-flex flex-wrap gap-2">
<button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-confirmacion"><i class="bi bi-file-text"></i> Enviar orden</button>
<button class="btn btn-outline-success btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-pago"><i class="bi bi-cash-coin"></i> Notificar pago</button>
<button class="btn btn-outline-info btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-envio"><i class="bi bi-truck"></i> Notificar envio</button>
<button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-entrega"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button class="btn btn-outline-dark btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-factura"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>'''

    nuevo_botones = r'''<div class="d-flex flex-wrap gap-2">
<button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-confirmacion"><i class="bi bi-file-text"></i> Enviar orden</button>

{% if orden.estado == 'pendiente_pago' %}
<button class="btn btn-outline-success btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-pago"><i class="bi bi-cash-coin"></i> Notificar pago</button>
<button class="btn btn-outline-info btn-sm" disabled title="Primero tenés que cobrar la orden"><i class="bi bi-truck"></i> Notificar envio</button>
{% elif orden.estado == 'pagado_sin_enviar' %}
<button class="btn btn-outline-success btn-sm" disabled title="La orden ya está pagada"><i class="bi bi-check-circle"></i> Pago acreditado</button>
<button class="btn btn-outline-info btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-envio"><i class="bi bi-truck"></i> Notificar envio</button>
{% elif orden.estado == 'pagado_enviado' %}
<button class="btn btn-outline-success btn-sm" disabled><i class="bi bi-check-circle"></i> Pago acreditado</button>
<button class="btn btn-outline-info btn-sm" disabled><i class="bi bi-truck"></i> Envio notificado</button>
{% endif %}

<button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-entrega"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button class="btn btn-outline-dark btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-factura"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>'''

    if buscar_botones in contenido:
        contenido = contenido.replace(buscar_botones, nuevo_botones)
        print("[upgrade145] Botones de notificación actualizados con reglas estrictas")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_app39_route():
    """Inyecta la lista de todos los productos al detalle de la orden para el select."""
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # En ventas_detalle_v3, agregar todos_productos
    buscar = "transportista_url_actual = transportista_url_actual)"
    nuevo = "transportista_url_actual = transportista_url_actual, todos_productos=conn.execute(\"SELECT id, nombre, precio, stock_actual FROM productos WHERE activo=1 ORDER BY nombre\").fetchall())"
    
    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        print("[upgrade145] Lista de productos inyectada en ventas_detalle_v3")
    
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 145: Edicion de productos en orden y logica de notificaciones ===")
    escribir('app145.py', APP145_PY)
    patch_run_bat()
    patch_detalle_html()
    patch_app39_route()
    
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()