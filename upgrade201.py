import os

def arreglar_envio_visual():
    print("Arreglando la sección de Envío (Leyendo datos del checkout)...")
    ruta = os.path.join('templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return

    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    # Buscamos el inicio del bloque de envío y el inicio del bloque de notas
    inicio_envio = html.find('<!-- ENVIO -->')
    fin_envio = html.find('<!-- NOTAS Y TERMINOS -->')

    if inicio_envio != -1 and fin_envio != -1:
        nuevo_bloque_envio = '''<!-- ENVIO -->
        <div class="ticket-card">
            <div class="ticket-title">Envío</div>
            
            <form method="post" action="{{ url_for('ventas_envio', id=orden.id) }}">
                <!-- Campos ocultos para que el sistema no pierda los datos al guardar -->
                <input type="hidden" name="destinatario_nombre" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}">
                <input type="hidden" name="destinatario_calle" value="{{ orden.destinatario_calle or '' }}">
                <input type="hidden" name="destinatario_localidad" value="{{ orden.destinatario_localidad or '' }}">
                <input type="hidden" name="destinatario_provincia" value="{{ orden.destinatario_provincia or '' }}">
                <input type="hidden" name="transportista_id" value="{{ orden.transportista_id or '' }}">

                <div class="row g-3">
                    <!-- Fila 1 -->
                    <div class="col-md-6">
                        <label class="form-label small fw-bold text-muted mb-1">Destinatario</label>
                        <input class="form-control form-control-sm bg-light" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}" readonly>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small fw-bold text-muted mb-1">Modo de Entrega</label>
                        <input class="form-control form-control-sm bg-light" value="{{ orden.tipo_envio|capitalize }} / {{ orden.destino_tipo|capitalize }}" readonly>
                    </div>

                    <!-- Fila 2 -->
                    <div class="col-md-6">
                        <label class="form-label small fw-bold text-muted mb-1">Dirección</label>
                        <input class="form-control form-control-sm bg-light" value="{{ orden.destinatario_calle or 'Retira en depósito' }}" readonly>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small fw-bold text-muted mb-1">Localidad / Provincia</label>
                        <input class="form-control form-control-sm bg-light" value="{{ orden.destinatario_localidad or '' }}, {{ orden.destinatario_provincia or '' }}" readonly>
                    </div>

                    <!-- Fila 3 -->
                    <div class="col-md-6">
                        <label class="form-label small fw-bold text-muted mb-1">Transportista</label>
                        <input class="form-control form-control-sm bg-light" value="{{ orden.transportista_nombre or 'Retira / Sin transportista' }}" readonly>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small fw-bold text-muted mb-1">Nro de Guía</label>
                        <input name="nro_guia" class="form-control form-control-sm border-primary" value="{{ orden.nro_guia or '' }}" placeholder="Ingresar número...">
                    </div>
                </div>
                
                <div class="mt-3">
                    <button class="btn btn-dark btn-sm w-100">Guardar Número de Guía</button>
                </div>
            </form>

            <!-- Botón de seguimiento (aparece solo si hay guía y URL) -->
            {% if orden.nro_guia and orden.transportista_id %}
                {% for t in transportistas %}
                    {% if t.id == orden.transportista_id and t.url_seguimiento %}
                        <div class="mt-2 text-center">
                            <a href="{{ t.url_seguimiento.replace('{guia}', orden.nro_guia) }}" target="_blank" class="btn btn-sm btn-outline-primary w-100">
                                <i class="bi bi-box-arrow-up-right"></i> Seguir Envío en {{ t.nombre }}
                            </a>
                        </div>
                    {% endif %}
                {% endfor %}
            {% endif %}
        </div>

        '''
        html = html[:inicio_envio] + nuevo_bloque_envio + html[fin_envio:]

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print(" -> Sección de Envío actualizada (Datos de solo lectura + Nro Guía editable).")

if __name__ == '__main__':
    arreglar_envio_visual()
    print("\n¡LISTO! Fijate que las columnas ahora sí están lado a lado y los datos son los que cargaste al crear la orden.")