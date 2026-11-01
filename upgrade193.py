import os
import textwrap
import sqlite3

def arreglar_run_bat():
    print("Asegurando que run.bat cargue app182.py...")
    ruta = 'run.bat'
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Limpiamos rastros de app181 o intentos viejos
        contenido = contenido.replace('; import app181', '').replace('import app181; ', '')
        
        # Si no está app182, lo agregamos antes del run
        if 'import app182' not in contenido:
            if 'app48.app.run' in contenido:
                contenido = contenido.replace('app48.app.run', 'import app182; app48.app.run')
                print(" -> Agregado a run.bat.")
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)

def crear_app182():
    print("Creando el cerebro de pagos y facturas (app182.py)...")
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
                        flash('Datos de facturación guardados.', 'success')
                        return redirect(url_for('ventas_detalle', id=id))

                    elif accion == 'enviar_factura':
                        orden = conn.execute("SELECT c.email FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id WHERE o.id=?", (id,)).fetchone()
                        if orden and orden['email']:
                            flash(f'[SIMULACIÓN] Factura enviada por correo a {orden["email"]}', 'success')
                        else:
                            flash('El cliente no tiene correo registrado.', 'error')
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

                    elif accion == 'notificar_pago':
                        orden = conn.execute("SELECT c.email FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id WHERE o.id=?", (id,)).fetchone()
                        if orden and orden['email']:
                            flash(f'[SIMULACIÓN] Correo de "Pago Recibido" enviado a {orden["email"]}', 'success')
                        else:
                            flash('El cliente no tiene correo registrado.', 'error')
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
    print(" -> app182.py creado.")

def actualizar_html():
    print("Actualizando la pantalla de detalle (sin tocar el Remito)...")
    ruta = os.path.join('templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return

    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    # --- BLOQUE DE FACTURACIÓN ---
    inicio_fact = html.find('<!-- COMENTARIOS Y FACTURACION -->')
    fin_fact = html.find('<!-- PAGOS Y COMPROBANTES -->')
    
    if inicio_fact != -1 and fin_fact != -1:
        nuevo_bloque_fact = '''<!-- FACTURACION -->
        <div class="ticket-card">
            <div class="ticket-title">Facturación</div>
            
            <div class="mb-3">
                <label class="form-label small fw-bold text-muted">Requiere Factura</label>
                <select id="select-requiere-factura" class="form-select form-select-sm" onchange="toggleFacturaForm()">
                    <option value="0" {% if not orden.requiere_factura or orden.requiere_factura == '0' %}selected{% endif %}>No requiere</option>
                    <option value="1" {% if orden.requiere_factura == '1' %}selected{% endif %}>Sí requiere</option>
                </select>
            </div>

            <div id="div-factura-form" style="display: none;">
                <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}" enctype="multipart/form-data">
                    <input type="hidden" name="accion" value="actualizar_factura">
                    <input type="hidden" name="requiere_factura" value="1">
                    
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
                            <div class="small text-success mt-1"><i class="bi bi-check-circle-fill"></i> Ya hay una factura cargada. <a href="/uploads/{{ orden.archivo_factura }}" target="_blank">Ver</a></div>
                            {% endif %}
                        </div>
                        <button type="submit" class="btn btn-sm btn-primary w-100">Guardar Cambios</button>
                    </div>
                </form>
                
                <div id="div-enviar-factura" style="display: none; margin-top: 10px;">
                    <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}">
                        <input type="hidden" name="accion" value="enviar_factura">
                        <button type="submit" class="btn btn-sm btn-outline-primary w-100">Enviar Factura por Correo</button>
                    </form>
                </div>
            </div>
        </div>

        '''
        html = html[:inicio_fact] + nuevo_bloque_fact + html[fin_fact:]

    # --- BLOQUE DE PAGOS ---
    inicio_pago = html.find('<!-- PAGOS Y COMPROBANTES -->')
    fin_pago = html.find('<!-- ESTADO ESTRICTO CON BOTONES -->')

    if inicio_pago != -1 and fin_pago != -1:
        nuevo_bloque_pago = '''<!-- PAGOS Y COMPROBANTES -->
        <div class="ticket-card">
            <div class="ticket-title">Pagos <span class="badge bg-danger ms-2">Saldo: ${{ '{:,.2f}'.format(saldo_pendiente) }}</span></div>
            
            <div class="form-check mb-3">
                <input class="form-check-input" type="checkbox" id="chk-pago-parcial" onchange="togglePagoForm()">
                <label class="form-check-label fw-bold" for="chk-pago-parcial">
                    Hizo pago parcial / total
                </label>
            </div>

            <div id="div-pago-form" style="display: none;">
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
                        <label class="form-label small fw-bold text-muted">Comprobante (Opcional)</label>
                        <input type="file" name="archivo_comprobante" class="form-control form-control-sm">
                    </div>
                    
                    <button type="submit" class="btn btn-sm btn-success w-100">Guardar Pago</button>
                </form>
            </div>

            {% if pagos %}
            <div class="mt-3 pt-3 border-top">
                <p class="small text-muted mb-2">Pagos registrados:</p>
                <ul class="list-unstyled mb-3">
                    {% for p in pagos %}
                    <li class="small mb-1">
                        <i class="bi bi-check2-circle text-success"></i> {{ p.fecha }} - ${{ '{:,.2f}'.format(p.monto) }} ({{ p.medio_nombre }})
                    </li>
                    {% endfor %}
                </ul>
                <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}">
                    <input type="hidden" name="accion" value="notificar_pago">
                    <button type="submit" class="btn btn-sm btn-outline-success w-100">Notificar Pago al Cliente</button>
                </form>
            </div>
            {% endif %}
        </div>

        '''
        html = html[:inicio_pago] + nuevo_bloque_pago + html[fin_pago:]

    # --- BOTÓN DE ENVIADO CONDICIONAL ---
    # Buscamos el botón de enviado y lo envolvemos en un if
    boton_enviado_viejo = '<button class="btn btn-info text-white w-100" onclick="return confirm(\'¿Confirmás que el pedido fue enviado?\')">Marcar como ENVIADO</button>'
    boton_enviado_nuevo = '''{% if total_pagado > 0 %}
    <button class="btn btn-info text-white w-100" onclick="return confirm('¿Confirmás que el pedido fue enviado?')">Marcar como ENVIADO</button>
    {% else %}
    <button class="btn btn-secondary w-100" disabled>Debe registrar un pago para enviar</button>
    {% endif %}'''
    
    html = html.replace(boton_enviado_viejo, boton_enviado_nuevo)

    # --- JAVASCRIPT PARA MOSTRAR/OCULTAR ---
    js_script = """
    <script>
    function toggleFacturaForm() {
        const val = document.getElementById('select-requiere-factura').value;
        const divForm = document.getElementById('div-factura-form');
        if (val === '1') {
            divForm.style.display = 'block';
            toggleSubirFactura();
        } else {
            divForm.style.display = 'none';
        }
    }

    function toggleSubirFactura() {
        const val = document.getElementById('select-estado-factura').value;
        const divSubir = document.getElementById('div-subir-factura');
        const divEnviar = document.getElementById('div-enviar-factura');
        const tieneArchivo = "{{ orden.archivo_factura }}" !== "None" && "{{ orden.archivo_factura }}" !== "";

        if (val === 'facturada') {
            divSubir.style.display = 'block';
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

    function togglePagoForm() {
        const isChecked = document.getElementById('chk-pago-parcial').checked;
        const divForm = document.getElementById('div-pago-form');
        if (isChecked) {
            divForm.style.display = 'block';
        } else {
            divForm.style.display = 'none';
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        toggleFacturaForm();
        togglePagoForm();
    });
    </script>
    """
    
    # Limpiamos scripts viejos si los hay
    if '<script>\n    function toggleFacturaForm()' not in html:
        html = html.replace('{% endblock %}', js_script + '\n{% endblock %}')

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print(" -> detalle.html actualizado.")

if __name__ == '__main__':
    arreglar_run_bat()
    crear_app182()
    actualizar_html()
    print("\n¡TODO LISTO! Arrancá run.bat, refrescá con Ctrl+F5 y probá las tres cosas que me pediste.")