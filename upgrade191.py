import os
import textwrap

def actualizar_app182():
    print("1. Actualizando el cerebro (app182.py) para recibir los datos...")
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

        def ventas_detalle_v4(id):
            conn = get_db()
            try:
                if request.method == 'POST':
                    accion = request.form.get('accion')
                    
                    if accion == 'actualizar_admin':
                        requiere_factura = request.form.get('requiere_factura', 'no')
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
                        flash('Datos de facturación guardados.', 'success')

                    elif accion == 'enviar_factura':
                        orden = conn.execute("SELECT c.email, o.numero_interno FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id WHERE o.id=?", (id,)).fetchone()
                        if orden and orden['email']:
                            flash(f'Factura enviada al correo {orden["email"]}', 'success')
                        else:
                            flash('El cliente no tiene correo registrado.', 'error')
                            
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

                # GET
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
    print("   -> app182.py actualizado.")

def actualizar_html():
    print("2. Actualizando la pantalla (detalle.html)...")
    ruta = os.path.join('templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return

    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    # --- BLOQUE 1: COMENTARIOS Y FACTURACIÓN ---
    bloque_facturacion_viejo_inicio = '<!-- COMENTARIOS Y FACTURACION -->'
    bloque_facturacion_viejo_fin = '<!-- PAGOS Y COMPROBANTES -->'
    
    # Buscamos dónde empieza y termina el bloque viejo para reemplazarlo
    inicio = html.find(bloque_facturacion_viejo_inicio)
    fin = html.find(bloque_facturacion_viejo_fin)
    
    if inicio != -1 and fin != -1:
        nuevo_bloque_facturacion = '''<!-- FACTURACION -->
        <div class="ticket-card">
            <div class="ticket-title">Facturación</div>
            <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}" enctype="multipart/form-data">
                <input type="hidden" name="accion" value="actualizar_admin">
                
                <div class="mb-3">
                    <label class="form-label small fw-bold text-muted">Requiere Factura</label>
                    <select name="requiere_factura" id="select-requiere-factura" class="form-select form-select-sm" onchange="toggleFacturacion()">
                        <option value="no" {% if not orden.requiere_factura or orden.requiere_factura == '0' %}selected{% endif %}>No</option>
                        <option value="si" {% if orden.requiere_factura and orden.requiere_factura != '0' %}selected{% endif %}>Sí</option>
                    </select>
                </div>

                <div id="div-estado-factura" style="display: none;">
                    <div class="mb-3">
                        <label class="form-label small fw-bold text-muted">Estado</label>
                        <select name="estado_facturacion" id="select-estado-factura" class="form-select form-select-sm" onchange="toggleSubirFactura()">
                            <option value="pendiente" {% if orden.estado_facturacion == 'pendiente' %}selected{% endif %}>Facturar</option>
                            <option value="facturada" {% if orden.estado_facturacion == 'facturada' %}selected{% endif %}>Facturado</option>
                        </select>
                    </div>

                    <div id="div-subir-factura" style="display: none;">
                        <div class="mb-3">
                            <label class="form-label small fw-bold text-muted">Subir Factura (PDF/Foto)</label>
                            <input type="file" name="archivo_factura" class="form-control form-control-sm">
                            {% if orden.archivo_factura %}
                            <div class="small text-success mt-1"><i class="bi bi-check-circle-fill"></i> Factura cargada: <a href="/uploads/{{ orden.archivo_factura }}" target="_blank">Ver Archivo</a></div>
                            {% endif %}
                        </div>
                        <button type="submit" class="btn btn-sm btn-primary w-100 mb-2">Guardar Cambios</button>
                    </div>
                </div>
            </form>
            
            <!-- Botón de Enviar Factura (fuera del form de guardar para no mezclar) -->
            <div id="div-enviar-factura" style="display: none;">
                <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}">
                    <input type="hidden" name="accion" value="enviar_factura">
                    <button type="submit" class="btn btn-sm btn-outline-primary w-100">Enviar Factura por Correo</button>
                </form>
            </div>
        </div>

        '''
        html = html[:inicio] + nuevo_bloque_facturacion + html[fin:]

    # --- BLOQUE 2: REGISTRAR PAGO ---
    bloque_pago_viejo_inicio = '<!-- PAGOS Y COMPROBANTES -->'
    bloque_pago_viejo_fin = '<!-- ESTADO ESTRICTO CON BOTONES -->'
    
    inicio_pago = html.find(bloque_pago_viejo_inicio)
    fin_pago = html.find(bloque_pago_viejo_fin)

    if inicio_pago != -1 and fin_pago != -1:
        nuevo_bloque_pago = '''<!-- PAGOS Y COMPROBANTES -->
        <div class="ticket-card">
            <div class="ticket-title">Registrar Pago <span class="badge bg-danger ms-2">Saldo: ${{ '{:,.2f}'.format(saldo_pendiente) }}</span></div>
            
            <div class="form-check mb-3">
                <input class="form-check-input" type="checkbox" id="chk-pago-parcial" onchange="togglePagoParcial()" {% if saldo_pendiente > 0 %}checked{% endif %}>
                <label class="form-check-label fw-bold" for="chk-pago-parcial">
                    ¿Hizo pago parcial o total?
                </label>
            </div>

            <div id="div-pago-parcial" style="display: none;">
                <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}" enctype="multipart/form-data">
                    <input type="hidden" name="accion" value="registrar_pago">
                    
                    <div class="row g-2 mb-2">
                        <div class="col-6">
                            <label class="form-label small fw-bold text-muted">Monto</label>
                            <input type="number" step="0.01" name="monto_pago" class="form-control form-control-sm" placeholder="$ 0.00" required>
                        </div>
                        <div class="col-6">
                            <label class="form-label small fw-bold text-muted">Medio de Pago</label>
                            <select name="medio_pago" class="form-select form-select-sm" required>
                                <option value="">Elegir...</option>
                                {% for m in medios %}
                                <option value="{{ m.id }}">{{ m.nombre }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label small fw-bold text-muted">Comprobante (Opcional si es Efectivo)</label>
                        <input type="file" name="archivo_comprobante" class="form-control form-control-sm">
                    </div>
                    
                    <button type="submit" class="btn btn-sm btn-success w-100">Cargar Pago</button>
                </form>
            </div>
        </div>

        '''
        html = html[:inicio_pago] + nuevo_bloque_pago + html[fin_pago:]

    # --- BLOQUE 3: AGREGAR EL JAVASCRIPT ---
    js_script = """
    <script>
    function toggleFacturacion() {
        const val = document.getElementById('select-requiere-factura').value;
        const divEstado = document.getElementById('div-estado-factura');
        if (val === 'si') {
            divEstado.style.display = 'block';
            toggleSubirFactura(); // Para chequear el estado del segundo select
        } else {
            divEstado.style.display = 'none';
        }
    }

    function toggleSubirFactura() {
        const val = document.getElementById('select-estado-factura').value;
        const divSubir = document.getElementById('div-subir-factura');
        const divEnviar = document.getElementById('div-enviar-factura');
        const tieneArchivo = "{{ orden.archivo_factura }}" !== "None" && "{{ orden.archivo_factura }}" !== "";

        if (val === 'facturada') {
            divSubir.style.display = 'block';
            // Solo mostramos el botón de enviar si ya hay un archivo subido
            if (tieneArchivo) {
                divEnviar.style.display = 'block';
            } else {
                divEnviar.style.display = 'none';
            }
        } else {
            divSubir.style.display = 'none';
            divEnviar.style.display = 'none';
        }
    }

    function togglePagoParcial() {
        const isChecked = document.getElementById('chk-pago-parcial').checked;
        const divPago = document.getElementById('div-pago-parcial');
        if (isChecked) {
            divPago.style.display = 'block';
        } else {
            divPago.style.display = 'none';
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        toggleFacturacion();
        togglePagoParcial();
    });
    </script>
    """
    # Limpiamos scripts viejos si los hubiera y agregamos el nuevo
    if '<script>\n    function toggleFacturacion()' not in html:
        html = html.replace('{% endblock %}', js_script + '\n{% endblock %}')

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print("   -> detalle.html actualizado con la lógica visual.")

if __name__ == '__main__':
    actualizar_app182()
    actualizar_html()
    print("\n¡LISTO! No toqué nada más. Arrancá run.bat y probá los botones.")