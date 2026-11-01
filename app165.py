
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required, generar_numero_orden
from database import get_db
from datetime import date

@app.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
@permiso_required('ventas')
def ventas_nueva_v3():
    conn = get_db()
    if request.method == 'POST':
        try:
            cliente_id = int(request.form['cliente_id'])
            tipo = request.form['tipo']
            canal_id = int(request.form['canal_id']) if request.form.get('canal_id') else None
            fecha = request.form.get('fecha') or date.today().isoformat()
            descuento = float(request.form.get('descuento') or 0)
            costo_envio = float(request.form.get('costo_envio') or 0)
            tipo_envio = request.form.get('tipo_envio', 'transporte')
            
            transportista_id = int(request.form['transportista_id']) if request.form.get('transportista_id') else None
            destino_tipo = request.form.get('destino_tipo')
            notas = request.form.get('notas', '').strip()
            
            # Datos de envio
            dest_nombre = request.form.get('dest_nombre', '').strip()
            dest_doc = request.form.get('dest_doc', '').strip()
            dest_tel = request.form.get('dest_tel', '').strip()
            dest_email = request.form.get('dest_email', '').strip()
            dest_prov = request.form.get('dest_prov', '').strip()
            dest_loc = request.form.get('dest_loc', '').strip()
            dest_calle = request.form.get('dest_calle', '').strip()
            dest_piso = request.form.get('dest_piso', '').strip()
            dest_depto = request.form.get('dest_depto', '').strip()
            dest_detalles = request.form.get('dest_detalles', '').strip()
            
            pids = request.form.getlist('producto_id')
            cants = request.form.getlist('cantidad')
            precios = request.form.getlist('precio')
        except (ValueError, KeyError):
            conn.close(); flash('Revisa los datos.', 'error'); return redirect(url_for('ventas_nueva'))

        items = []
        for pid, cant, prec in zip(pids, cants, precios):
            if not pid or not cant: continue
            try:
                cant_f = float(cant); prec_f = float(prec)
            except ValueError: continue
            if cant_f <= 0: continue
            items.append({'producto_id': int(pid), 'cantidad': cant_f, 'precio': prec_f, 'subtotal': cant_f * prec_f})
            
        if not items:
            conn.close(); flash('Agrega productos.', 'error'); return redirect(url_for('ventas_nueva'))

        subtotal = sum(i['subtotal'] for i in items)
        total = max(0, subtotal - descuento) + costo_envio
        numero = generar_numero_orden(conn)

        cur = conn.execute("""INSERT INTO ordenes_venta
            (numero_interno, cliente_id, usuario_id, canal_id, tipo, fecha, estado,
             estado_facturacion, subtotal, descuento, total, notas, tipo_envio,
             transportista_id, destino_tipo, costo_envio,
             destinatario_nombre, destinatario_documento, destinatario_telefono, destinatario_email,
             destinatario_provincia, destinatario_localidad, destinatario_calle, 
             destinatario_piso, destinatario_depto, destinatario_detalles)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, cliente_id, current_user.id, canal_id, tipo, fecha, 'pendiente_pago',
             'no_requiere', subtotal, descuento, total, notas, tipo_envio,
             transportista_id, destino_tipo, costo_envio,
             dest_nombre, dest_doc, dest_tel, dest_email,
             dest_prov, dest_loc, dest_calle, dest_piso, dest_depto, dest_detalles))
        oid = cur.lastrowid

        for it in items:
            conn.execute("""INSERT INTO orden_items (orden_id, producto_id, cantidad, precio_unitario, subtotal)
                VALUES (?,?,?,?,?)""", (oid, it['producto_id'], it['cantidad'], it['precio'], it['subtotal']))

        conn.commit(); conn.close()
        flash(f'Orden {numero} creada.', 'success')
        return redirect(url_for('ventas_detalle', id=oid))

    # GET
    if current_user.es_admin:
        clientes = conn.execute("SELECT * FROM clientes WHERE activo=1 ORDER BY nombre_completo").fetchall()
    else:
        clientes = conn.execute("SELECT * FROM clientes WHERE activo=1 AND vendedor_id=? ORDER BY nombre_completo", (current_user.id,)).fetchall()
        
    productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    canales = conn.execute("SELECT * FROM canales_venta WHERE activo=1 AND lower(nombre) != 'tienda online' ORDER BY nombre").fetchall()
    transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1 ORDER BY nombre").fetchall()
    
    provincias = [dict(r) for r in conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()]
    locs_rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    localidades_por_provincia = {}
    for r in locs_rows:
        localidades_por_provincia.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})

    conn.close()
    return render_template('ventas/form.html', clientes=clientes, productos=productos, canales=canales,
                           transportistas=transportistas, provincias=provincias, 
                           localidades_por_provincia=localidades_por_provincia, hoy=date.today().isoformat())

app.view_functions['ventas_nueva'] = ventas_nueva_v3
