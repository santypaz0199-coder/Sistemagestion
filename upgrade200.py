import os

def arreglar_envio_html():
    print("Arreglando el diseño de la sección Envío (2 columnas y Nro Guía)...")
    ruta = os.path.join('templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return

    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    inicio_envio = html.find('<!-- ENVIO -->')
    fin_envio = html.find('<!-- NOTAS Y TERMINOS -->')

    if inicio_envio != -1 and fin_envio != -1:
        nuevo_bloque_envio = '''<!-- ENVIO -->
        <div class="ticket-card">
            <div class="ticket-title d-flex justify-content-between">
                <span>Envío</span>
                <button type="button" class="btn btn-sm btn-outline-secondary" id="btn-editar-envio" onclick="toggleEditarEnvio()">
                    <i class="bi bi-pencil"></i> Editar
                </button>
            </div>
            <form method="post" action="{{ url_for('ventas_envio', id=orden.id) }}">
                <div class="row g-2">
                    <div class="col-md-6">
                        <label class="form-label small text-muted mb-1">Destinatario</label>
                        <input name="destinatario_nombre" class="form-control form-control-sm envio-input" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}" readonly>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small text-muted mb-1">Transportista</label>
                        <select name="transportista_id" class="form-select form-select-sm envio-input" disabled>
                            <option value="">Retira / Sin transportista</option>
                            {% for t in transportistas %}<option value="{{ t.id }}" {% if orden.transportista_id==t.id %}selected{% endif %}>{{ t.nombre }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small text-muted mb-1">Dirección</label>
                        <input name="destinatario_calle" class="form-control form-control-sm envio-input" value="{{ orden.destinatario_calle or '' }}" readonly placeholder="Retira en depósito">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small text-muted mb-1">Localidad</label>
                        <input name="destinatario_localidad" class="form-control form-control-sm envio-input" value="{{ orden.destinatario_localidad or '' }}" readonly>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small text-muted mb-1">Provincia</label>
                        <input name="destinatario_provincia" class="form-control form-control-sm envio-input" value="{{ orden.destinatario_provincia or '' }}" readonly>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small text-muted mb-1">Nro Guía (Editable)</label>
                        <!-- El Nro Guía NO tiene readonly para que siempre puedas cargarlo -->
                        <input name="nro_guia" class="form-control form-control-sm" value="{{ orden.nro_guia or '' }}" placeholder="Ingrese Nro de Guía">
                    </div>
                </div>
                <div class="mt-3">
                    <!-- El botón de guardar siempre visible -->
                    <button class="btn btn-dark btn-sm w-100">Guardar Envío y Guía</button>
                </div>
            </form>
        </div>

        '''
        html = html[:inicio_envio] + nuevo_bloque_envio + html[fin_envio:]

    # Arreglar el JavaScript del botón Editar
    js_viejo = '''function toggleEditarEnvio() {
        const inputs = document.querySelectorAll('.envio-input');
        const btnGuardar = document.getElementById('btn-guardar-envio-container');
        const btnEditar = document.getElementById('btn-editar-envio');
        
        let isReadonly = inputs[0].hasAttribute('readonly') || inputs[0].hasAttribute('disabled');
        
        if (isReadonly) {
            inputs.forEach(i => { i.removeAttribute('readonly'); i.removeAttribute('disabled'); });
            btnGuardar.classList.remove('d-none');
            btnEditar.innerHTML = '<i class="bi bi-x"></i> Cancelar';
        } else {
            inputs.forEach(i => { 
                if(i.tagName === 'SELECT') i.setAttribute('disabled', 'true');
                else i.setAttribute('readonly', 'true'); 
            });
            btnGuardar.classList.add('d-none');
            btnEditar.innerHTML = '<i class="bi bi-pencil"></i> Editar';
        }
    }'''

    js_nuevo = '''function toggleEditarEnvio() {
        const inputs = document.querySelectorAll('.envio-input');
        const btnEditar = document.getElementById('btn-editar-envio');
        
        let isReadonly = inputs[0].hasAttribute('readonly') || inputs[0].hasAttribute('disabled');
        
        if (isReadonly) {
            inputs.forEach(i => { i.removeAttribute('readonly'); i.removeAttribute('disabled'); });
            btnEditar.innerHTML = '<i class="bi bi-x"></i> Bloquear';
        } else {
            inputs.forEach(i => { 
                if(i.tagName === 'SELECT') i.setAttribute('disabled', 'true');
                else i.setAttribute('readonly', 'true'); 
            });
            btnEditar.innerHTML = '<i class="bi bi-pencil"></i> Editar';
        }
    }'''

    html = html.replace(js_viejo, js_nuevo)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print(" -> Sección de Envío rediseñada correctamente.")

if __name__ == '__main__':
    arreglar_envio_html()
    print("\n¡LISTO! Las columnas ahora están una al lado de la otra y podés cargar el Nro de Guía cuando quieras.")