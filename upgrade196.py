import os
import textwrap

def crear_app182_definitivo():
    print("1. Limpiando el cerebro de Python (app182.py)...")
    codigo = textwrap.dedent('''
        from flask import render_template, request, redirect, url_for, flash, send_from_directory
        from flask_login import login_required, current_user
        from app48 import app
        from app import permiso_required
        from database import get_db
        from datetime import date
        import os, uuid

        UPLOAD_FOLDER = 'uploads'
        if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

        @app.route('/uploads/<filename>')
        def uploaded_file(filename):
            return send_from_directory(UPLOAD_FOLDER, filename)

        @app.route('/ventas/<int:id>/remito')
        @login_required
        def ventas_remito(id):
            conn = get_db()
            orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
            items = conn.execute("SELECT oi.*, p.nombre as producto_nombre FROM orden_items oi JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?", (id,)).fetchall()
            conn.close()
            return render_template('ventas/remito.html', orden=orden, items=items)

        def ventas_detalle_v4(id):
            conn = get_db()
            try:
                if request.method == 'POST':
                    accion = request.form.get('accion')
                    
                    if accion == 'actualizar_factura':
                        requiere_factura = request.form.get('requiere_factura', '0')
                        estado_facturacion = request.form.get('estado_facturacion', 'pendiente')
                        
                        archivo_factura = None
                        if 'archivo_factura' in request.files:
                            file = request.files['archivo_factura']
                            if file and file.filename != '':
                                filename = str(uuid.uuid4()) + "_" + file.filename
                                file.save(os.path.join(UPLOAD_FOLDER, filename))
                                archivo_factura = filename
                        
                        if archivo_factura:
                            conn.execute("UPDATE ordenes_venta SET requiere_factura=?, estado_facturacion=?, archivo_factura=? WHERE id=?", (requiere_factura, estado_facturacion, archivo_factura, id))
                        else:
                            conn.execute("UPDATE ordenes_venta SET requiere_factura=?, estado_facturacion=? WHERE id=?", (requiere_factura, estado_facturacion, id))
                        conn.commit()
                        flash('Facturación guardada correctamente.', 'success')
                        return redirect(url_for('ventas_detalle', id=id))

                    elif accion == 'registrar_pago':
                        monto = float(request.form.get('monto_pago') or 0)
                        medio_id = request.form.get('medio_pago') 
                        archivo_comprobante = None
                        
                        if 'archivo_comprobante' in request.files:
                            file = request.files['archivo_comprobante']
                            if file and file.filename != '':
                                filename = str(uuid.uuid4()) + "_" + file.filename
                                file.save(os.path.join(UPLOAD_FOLDER, filename))
                                archivo_comprobante = filename

                        conn.execute("INSERT INTO pagos (orden_id, fecha, medio_pago_id, monto, monto_neto, usuario_id, notas) VALUES (?, ?, ?, ?, ?, ?, ?)", (id, date.today().isoformat(), medio_id, monto, monto, current_user.id, archivo_comprobante))
                        conn.commit()
                        flash('Pago registrado correctamente.', 'success')
                        return redirect(url_for('ventas_detalle', id=id))

                # GET (Cargar la pantalla)
                orden = conn.execute("SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email, c.telefono as cliente_telefono, u.nombre as vendedor_nombre, cv.nombre as canal_nombre, t.nombre as transportista_nombre FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id JOIN usuarios u ON u.id=o.usuario_id LEFT JOIN canales_venta cv ON cv.id=o.canal_id LEFT JOIN transportistas t ON t.id=o.transportista_id WHERE o.id=?", (id,)).fetchone()
                if not orden: return redirect(url_for('ventas_lista'))
                
                items = conn.execute("SELECT oi.*, p.nombre as producto_nombre, p.peso_valor, p.peso_unidad FROM orden_items oi JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?", (id,)).fetchall()
                todos_productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
                
                pagos = conn.execute("SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id WHERE pg.orden_id=? ORDER BY pg.id", (id,)).fetchall()
                total_pagado = sum(p['monto'] for p in pagos)
                saldo_pendiente = orden['total'] - total_pagado

                kilos_total = 0.0
                for it in items:
                    peso = it['peso_valor'] if it['peso_valor'] else 0
                    if it['peso_unidad'] == 'g': peso = peso / 1000.0
                    kilos_total += (it['cantidad'] * peso)

                medios = conn.execute("SELECT * FROM medios_pago WHERE activo=1").fetchall()
                
                return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                                       total_pagado=total_pagado, saldo_pendiente=saldo_pendiente, 
                                       kilos_total=kilos_total, todos_productos=todos_productos, medios=medios)
            finally:
                conn.close()

        if 'ventas_detalle_v4_endpoint' not in app.view_functions:
            app.add_url_rule('/ventas/<int:id>', 'ventas_detalle_v4_endpoint', ventas_detalle_v4, methods=['GET', 'POST'])
            app.view_functions['ventas_detalle'] = ventas_detalle_v4
    ''')
    with open('app182.py', 'w', encoding='utf-8') as f:
        f.write(codigo)

def actualizar_html():
    print("2. Ajustando la pantalla para que guarde y envíe correos reales...")
    ruta = os.path.join('templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return

    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Arreglar el bloque de Facturación
    inicio_fact = html.find('<!-- FACTURACIÓN -->')
    fin_fact = html.find('<!-- PAGOS -->')
    
    if inicio_fact != -1 and fin_fact != -1:
        nuevo_bloque_fact = '''<!-- FACTURACIÓN -->
        <div class="ticket-card">
            <div class="ticket-title">Facturación</div>
            
            <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}" enctype="multipart/form-data">
                <input type="hidden" name="accion" value="actualizar_factura">
                
                <div class="mb-3">
                    <label class="form-label small fw-bold text-muted">Requiere Factura</label>
                    <select name="requiere_factura" id="select-requiere-factura" class="form-select form-select-sm" onchange="toggleFacturaForm()">
                        <option value="0" {% if not orden.requiere_factura or orden.requiere_factura == 0 or orden.requiere_factura == '0' %}selected{% endif %}>No requiere</option>
                        <option value="1" {% if orden.requiere_factura == 1 or orden.requiere_factura == '1' %}selected{% endif %}>Sí requiere</option>
                    </select>
                </div>

                <div id="div-factura-form" style="display: none;">
                    <div class="mb-3">
                        <label class="form-label small fw-bold text-muted">Estado</label>
                        <select name="estado_facturacion" id="select-estado-factura" class="form-select form-select-sm" onchange="toggleSubirFactura()">
                            <option value="pendiente" {% if orden.estado_facturacion == 'pendiente' or not orden.estado_facturacion %}selected{% endif %}>Facturar (Pendiente)</option>
                            <option value="facturada" {% if orden.estado_facturacion == 'facturada' %}selected{% endif %}>Facturado</option>
                        </select>
                    </div>

                    <div id="div-subir-factura" style="display: none;">
                        <div class="mb-3">
                            <label class="form-label small fw-bold text-muted">Subir Factura (PDF/Foto)</label>
                            <input type="file" name="archivo_factura" class="form-control form-control-sm">
                            {% if orden.archivo_factura %}
                            <div class="small text-success mt-1"><i class="bi bi-check-circle-fill"></i> <a href="/uploads/{{ orden.archivo_factura }}" target="_blank">Ver Factura Cargada</a></div>
                            {% endif %}
                        </div>
                    </div>
                </div>
                
                <button type="submit" class="btn btn-sm btn-primary w-100 mt-2">Guardar Facturación</button>
            </form>
            
            <!-- FORMULARIO DE CORREO REAL (POST a tu sistema) -->
            <div id="div-enviar-factura" style="display: none; margin-top: 10px;">
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='factura') }}">
                    <button type="submit" class="btn btn-sm btn-outline-primary w-100">Enviar Factura por Correo</button>
                </form>
            </div>
        </div>

        '''
        html = html[:inicio_fact] + nuevo_bloque_fact + html[fin_fact:]

    # 2. Arreglar el bloque de Pagos para notificar por correo real
    viejo_notificar = '''<form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}">
                    <input type="hidden" name="accion" value="notificar_pago">
                    <button type="submit" class="btn btn-sm btn-outline-success w-100">Notificar Pago Parcial al Cliente</button>
                </form>'''
    
    # FORMULARIO DE CORREO REAL (POST a tu sistema)
    nuevo_notificar = '''<form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='pago') }}">
                    <button type="submit" class="btn btn-sm btn-outline-success w-100">Notificar Pago al Cliente por Correo</button>
                </form>'''
    
    html = html.replace(viejo_notificar, nuevo_notificar)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print(" -> HTML ajustado para usar correos reales.")

if __name__ == '__main__':
    crear_app182_definitivo()
    actualizar_html()
    print("\n¡LISTO! Ya quité el código de más. Ahora los correos se envían de verdad y la factura se guarda bien.")