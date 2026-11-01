import os

def arreglar_envio_visual():
    print("Arreglando la sección de Envío (Con botón Editar y columnas correctas)...")
    ruta = os.path.join('templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return

    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    inicio_envio = html.find('<!-- ENVIO -->')
    fin_envio = html.find('<!-- NOTAS Y TERMINOS -->')

    if inicio_envio != -1 and fin_envio != -1:
        nuevo_bloque_envio = '''<!-- ENVIO -->
        <div class="ticket-card">
            <div class="ticket-title d-flex justify-content-between align-items-center">
                <span>Envío</span>
                <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-2" id="btn-edit-envio" onclick="toggleEditEnvio()">
                    <i class="bi bi-pencil"></i> Editar
                </button>
            </div>
            
            <form method="post" action="{{ url_for('ventas_envio', id=orden.id) }}">
                <div class="row g-2">
                    <div class="col-6">
                        <label class="form-label small text-muted mb-0">Destinatario</label>
                        <input name="destinatario_nombre" class="form-control form-control-sm envio-field" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}" readonly>
                    </div>
                    <div class="col-6">
                        <label class="form-label small text-muted mb-0">Transportista</label>
                        <select name="transportista_id" class="form-select form-select-sm envio-field" disabled>
                            <option value="">Sin transportista</option>
                            {% for t in transportistas %}<option value="{{ t.id }}" {% if orden.transportista_id==t.id %}selected{% endif %}>{{ t.nombre }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="col-6">
                        <label class="form-label small text-muted mb-0">Dirección</label>
                        <input name="destinatario_calle" class="form-control form-control-sm envio-field" value="{{ orden.destinatario_calle or '' }}" readonly>
                    </div>
                    <div class="col-6">
                        <label class="form-label small text-muted mb-0">Localidad</label>
                        <input name="destinatario_localidad" class="form-control form-control-sm envio-field" value="{{ orden.destinatario_localidad or '' }}" readonly>
                    </div>
                    <div class="col-6">
                        <label class="form-label small text-muted mb-0">Provincia</label>
                        <input name="destinatario_provincia" class="form-control form-control-sm envio-field" value="{{ orden.destinatario_provincia or '' }}" readonly>
                    </div>
                    <div class="col-6">
                        <label class="form-label small text-muted mb-0">Nro Guía</label>
                        <input name="nro_guia" class="form-control form-control-sm envio-field" value="{{ orden.nro_guia or '' }}" readonly>
                    </div>
                </div>
                
                <div class="mt-2 d-none" id="btn-save-envio">
                    <button class="btn btn-dark btn-sm w-100">Guardar Cambios de Envío</button>
                </div>
            </form>

            <!-- Link de seguimiento -->
            {% if orden.nro_guia and orden.transportista_id %}
                {% for t in transportistas %}
                    {% if t.id == orden.transportista_id and t.url_seguimiento %}
                        <div class="mt-2 text-center">
                            <a href="{{ t.url_seguimiento.replace('{guia}', orden.nro_guia) }}" target="_blank" class="btn btn-sm btn-outline-primary w-100">
                                <i class="bi bi-box-arrow-up-right"></i> Seguir Envío
                            </a>
                        </div>
                    {% endif %}
                {% endfor %}
            {% endif %}
        </div>

        '''
        html = html[:inicio_envio] + nuevo_bloque_envio + html[fin_envio:]

    # Arreglar el JavaScript para que el botón funcione de verdad
    js_viejo_inicio = html.find('function toggleEditarEnvio()')
    js_viejo_fin = html.find('}', html.find('btnEditar.innerHTML = \'<i class="bi bi-pencil"></i> Editar\';')) + 1
    
    if js_viejo_inicio != -1 and js_viejo_fin != -1:
        js_nuevo = '''function toggleEditEnvio() {
        const fields = document.querySelectorAll('.envio-field');
        const btnSave = document.getElementById('btn-save-envio');
        const btnEdit = document.getElementById('btn-edit-envio');
        
        let isReadonly = fields[0].hasAttribute('readonly');
        
        if (isReadonly) {
            fields.forEach(f => { f.removeAttribute('readonly'); f.removeAttribute('disabled'); });
            btnSave.classList.remove('d-none');
            btnEdit.innerHTML = '<i class="bi bi-x"></i> Cancelar';
        } else {
            fields.forEach(f => { 
                if(f.tagName === 'SELECT') f.setAttribute('disabled', 'true');
                else f.setAttribute('readonly', 'true'); 
            });
            btnSave.classList.add('d-none');
            btnEdit.innerHTML = '<i class="bi bi-pencil"></i> Editar';
        }
    }'''
        html = html[:js_viejo_inicio] + js_nuevo + html[js_viejo_fin:]

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print(" -> Sección de Envío actualizada con Botón de Editar y 2 columnas.")

if __name__ == '__main__':
    arreglar_envio_visual()
    print("\n¡LISTO! Ahora sí, refrescá con Ctrl+F5.")