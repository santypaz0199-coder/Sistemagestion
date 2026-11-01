import os

def actualizar_lista():
    print("Actualizando lista de ventas (agregando columna de comentarios)...")
    ruta = os.path.join('templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta): return
    
    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    # Agregamos un icono de comentario en la tabla si la orden tiene notas
    # (Buscamos la columna del cliente para agregar una nueva al lado)
    buscar = '<td><a href="{{ url_for(\'clientes_editar\', id=v.cliente_id) }}" class="text-decoration-none">{{ v.cliente_nombre }}</a></td>'
    reemplazar = '''<td>
    <a href="{{ url_for('clientes_editar', id=v.cliente_id) }}" class="text-decoration-none">{{ v.cliente_nombre }}</a>
    {% if v.notas %}<i class="bi bi-chat-text-fill text-primary ms-1" title="{{ v.notas }}"></i>{% endif %}
    </td>'''
    html = html.replace(buscar, reemplazar)
    
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Lista actualizada.")

def actualizar_detalle():
    print("Actualizando detalle de venta (Comentarios, Facturación y Pagos)...")
    ruta = os.path.join('templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return

    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Agregar Módulo de Comentarios y Facturación en la columna derecha
    buscar_resumen = '<!-- ESTADO ESTRICTO CON BOTONES -->'
    modulo_admin = '''<!-- COMENTARIOS Y FACTURACION -->
        <div class="ticket-card">
            <div class="ticket-title">Comentarios y Facturación</div>
            <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}" enctype="multipart/form-data">
                <input type="hidden" name="accion" value="actualizar_admin">
                
                <div class="mb-3">
                    <label class="form-label small fw-bold text-muted">Comentarios / Notas para el cliente</label>
                    <textarea name="notas" class="form-control form-control-sm" rows="2" placeholder="Ej: Entregar por la tarde, dejar en portería...">{{ orden.notas or '' }}</textarea>
                </div>
                
                <div class="row g-2 mb-3">
                    <div class="col-6">
                        <label class="form-label small fw-bold text-muted">Requiere Factura</label>
                        <select name="requiere_factura" class="form-select form-select-sm">
                            <option value="no" {% if not orden.requiere_factura %}selected{% endif %}>No</option>
                            <option value="si" {% if orden.requiere_factura %}selected{% endif %}>Sí</option>
                        </select>
                    </div>
                    <div class="col-6">
                        <label class="form-label small fw-bold text-muted">Estado Factura</label>
                        <select name="estado_facturacion" class="form-select form-select-sm">
                            <option value="no_requiere" {% if orden.estado_facturacion=='no_requiere' %}selected{% endif %}>No requiere</option>
                            <option value="pendiente" {% if orden.estado_facturacion=='pendiente' %}selected{% endif %}>Falta Facturar</option>
                            <option value="facturada" {% if orden.estado_facturacion=='facturada' %}selected{% endif %}>Facturada</option>
                        </select>
                    </div>
                </div>

                <div class="mb-2">
                    <label class="form-label small fw-bold text-muted">Subir Factura (PDF/Foto)</label>
                    <input type="file" name="archivo_factura" class="form-control form-control-sm">
                    {% if orden.archivo_factura %}
                    <div class="small text-success mt-1"><i class="bi bi-check-circle-fill"></i> Factura cargada</div>
                    {% endif %}
                </div>
                
                <button type="submit" class="btn btn-sm btn-primary w-100 mt-2">Guardar Datos</button>
            </form>
        </div>

        <!-- PAGOS Y COMPROBANTES -->
        <div class="ticket-card">
            <div class="ticket-title">Registrar Pago</div>
            <form method="post" action="{{ url_for('ventas_detalle', id=orden.id) }}" enctype="multipart/form-data">
                <input type="hidden" name="accion" value="registrar_pago">
                
                <div class="row g-2 mb-2">
                    <div class="col-6">
                        <label class="form-label small fw-bold text-muted">Monto del Pago</label>
                        <input type="number" step="0.01" name="monto_pago" class="form-control form-control-sm" placeholder="$ 0.00" required>
                    </div>
                    <div class="col-6">
                        <label class="form-label small fw-bold text-muted">Tipo</label>
                        <select name="tipo_pago" class="form-select form-select-sm">
                            <option value="parcial">Pago Parcial</option>
                            <option value="total">Pago Total</option>
                        </select>
                    </div>
                </div>
                
                <div class="mb-3">
                    <label class="form-label small fw-bold text-muted">Subir Comprobante (Transf, MP, etc)</label>
                    <input type="file" name="archivo_comprobante" class="form-control form-control-sm" required>
                </div>
                
                <button type="submit" class="btn btn-sm btn-success w-100">Cargar Pago</button>
            </form>
        </div>

        <!-- ESTADO ESTRICTO CON BOTONES -->'''
    
    html = html.replace(buscar_resumen, modulo_admin)

    # 2. Hacer que el formulario de "Añadir producto" acepte la cantidad correcta
    buscar_add = '<form method="post" action="{{ url_for(\'ventas_agregar_item\', id=orden.id) }}" class="row g-2 align-items-end">'
    reemplazar_add = '<form method="post" action="{{ url_for(\'ventas_agregar_item\', id=orden.id) }}" class="row g-2 align-items-end" enctype="multipart/form-data">'
    html = html.replace(buscar_add, reemplazar_add)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Detalle actualizado con módulos de gestión.")

if __name__ == '__main__':
    actualizar_lista()
    actualizar_detalle()
    print("\n¡TODO LISTO! Reinicia el servidor y presiona Ctrl+F5 en el navegador.")