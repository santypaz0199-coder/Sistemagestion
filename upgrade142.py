# -*- coding: utf-8 -*-
import os, re, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade142] escrito: {relpath}")

# 1. MOVER CATALOGOS A CONFIGURACION
def patch_base_html():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Quitar del menú principal (buscamos el enlace de Catálogos y lo eliminamos)
    patron_cat = re.compile(r'<a href="\{\{ url_for\(\'catalogos_index\'\) \}\}".*?</a>\n?', re.DOTALL)
    contenido, n = patron_cat.subn('', contenido)
    
    # Agregar dentro del menú de Configuración (en el sidebar, debajo de Usuarios)
    if n > 0:
        buscar_config = '<a href="{{ url_for(\'configuracion\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'configuracion\') %}active{% endif %}"><i class="bi bi-gear"></i> Configuracion</a>'
        nuevo_config = '<a href="{{ url_for(\'catalogos_index\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'catalogos\') %}active{% endif %}"><i class="bi bi-tags"></i> Catálogos (Canales, Pagos, Transportes)</a>\n' + buscar_config
        contenido = contenido.replace(buscar_config, nuevo_config)
        print("[upgrade142] Catálogos movido al menú de Configuración")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


# 2. ACTUALIZAR EL DETALLE DE LA ORDEN (ENVIO, ADJUNTOS Y BOTON GLOBAL)
def patch_detalle_route():
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Pasamos las provincias y localidades al template de la orden
    buscar_route = """    remitentes_disponibles = _remitentes_disponibles(conn)

    # URL base del transportista actual (para construir el link de seguimiento)"""
    
    nuevo_route = """    remitentes_disponibles = _remitentes_disponibles(conn)

    # Cargar Provincias y Localidades para los selectores de envío
    provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
    locs_rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    localidades_por_provincia = {}
    for r in locs_rows:
        localidades_por_provincia.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})

    # URL base del transportista actual (para construir el link de seguimiento)"""

    if buscar_route in contenido:
        contenido = contenido.replace(buscar_route, nuevo_route)

    # Pasar variables al render_template
    buscar_render = "remitentes_disponibles=remitentes_disponibles,\n                           transportista_url_actual=transportista_url_actual)"
    nuevo_render = "remitentes_disponibles=remitentes_disponibles,\n                           transportista_url_actual=transportista_url_actual,\n                           provincias=provincias, localidades_por_provincia=localidades_por_provincia)"
    
    if buscar_render in contenido:
        contenido = contenido.replace(buscar_render, nuevo_render)
    else:
        # Variante con espacios
        buscar_render_2 = "remitentes_disponibles=remitentes_disponibles, transportista_url_actual=transportista_url_actual)"
        nuevo_render_2 = "remitentes_disponibles=remitentes_disponibles, transportista_url_actual=transportista_url_actual, provincias=provincias, localidades_por_provincia=localidades_por_provincia)"
        contenido = contenido.replace(buscar_render_2, nuevo_render_2)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade142] app39.py actualizado con provincias para el envío")


def patch_detalle_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Actualizar los adjuntos para que tengan los nombres correctos
    buscar_adj = """<select name="tipo" class="form-select form-select-sm">
<option value="factura">Factura</option>
<option value="comprobante">Comprobante</option>
<option value="guia">Guia</option>
<option value="otro">Otro</option>
</select>"""
    nuevo_adj = """<select name="tipo" class="form-select form-select-sm">
<option value="factura">Factura</option>
<option value="comprobante">Comprobante de Pago</option>
<option value="guia">Guía / Remito</option>
</select>"""
    if buscar_adj in contenido:
        contenido = contenido.replace(buscar_adj, nuevo_adj)

    # 2. Reemplazar el bloque de envío por los selects con el checkbox de "Usar datos del cliente"
    buscar_envio = """<div class="row g-2">
<div class="col-md-6"><label class="form-label small">Transportista</label><select name="transportista_id" class="form-select form-select-sm"><option value="">--</option>{% for t in transportistas %}<option value="{{ t.id }}" {% if orden.transportista_id==t.id %}selected{% endif %}>{{ t.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-6"><label class="form-label small">Nro guia</label><input name="nro_guia" class="form-control form-control-sm" value="{{ orden.nro_guia or '' }}" placeholder="Se puede cargar despues">
</div>

{% if orden.nro_guia %}
{% set url_seg = construir_url_seguimiento(transportista_url_actual, orden.nro_guia) %}
{% if url_seg %}
<div class="col-12 link-seguimiento-auto">
<div class="alert alert-light border py-2 px-3 mb-2">
<div class="small mb-1"><strong><i class="bi bi-link-45deg"></i> Link de seguimiento generado:</strong></div>
<a href="{{ url_seg }}" target="_blank" class="small text-decoration-none" style="word-break:break-all;">
{{ url_seg }}
</a>
</div>
<div class="small text-muted" style="font-size:.75rem;">
<i class="bi bi-info-circle"></i>
Si el link no funciona, copia el numero de guia <strong>{{ orden.nro_guia }}</strong> y pegalo manualmente en el sitio del transportista.
</div>
</div>
{% endif %}
{% endif %}

<div class="col-md-6"><label class="form-label small">Destinatario</label><input name="destinatario_nombre" class="form-control form-control-sm" value="{{ orden.destinatario_nombre or '' }}"></div>
<div class="col-md-6"><label class="form-label small">Provincia</label><input name="destinatario_provincia" class="form-control form-control-sm" value="{{ orden.destinatario_provincia or '' }}"></div>
<div class="col-md-4"><label class="form-label small">Localidad</label><input name="destinatario_localidad" class="form-control form-control-sm" value="{{ orden.destinatario_localidad or '' }}"></div>
<div class="col-md-4"><label class="form-label small">CP</label><input name="destinatario_cp" class="form-control form-control-sm" value="{{ orden.destinatario_cp or '' }}"></div>
<div class="col-md-4"><label class="form-label small">Calle y altura</label><input name="destinatario_calle" class="form-control form-control-sm" value="{{ orden.destinatario_calle or '' }}"></div>
<div class="col-12"><label class="form-label small">Detalles adicionales</label><textarea name="destinatario_detalles" class="form-control form-control-sm" rows="2">{{ orden.destinatario_detalles or '' }}</textarea></div>
</div>
<button class="btn btn-dark btn-sm mt-3">Guardar datos de envio</button>"""

    nuevo_envio = """<div class="form-check mb-3">
<input class="form-check-input" type="checkbox" id="check-usar-datos" checked onchange="toggleEdicionEnvio()">
<label class="form-check-label small fw-semibold" for="check-usar-datos">Usar los datos del cliente ({{ orden.cliente_nombre }})</label>
</div>

<div id="bloque-envio-edit" style="display:none;">
<div class="row g-2">
<div class="col-md-6"><label class="form-label small">Transportista</label><select name="transportista_id" class="form-select form-select-sm"><option value="">--</option>{% for t in transportistas %}<option value="{{ t.id }}" {% if orden.transportista_id==t.id %}selected{% endif %}>{{ t.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-6"><label class="form-label small">Nro guia</label><input name="nro_guia" class="form-control form-control-sm" value="{{ orden.nro_guia or '' }}"></div>

{% if orden.nro_guia %}
{% set url_seg = construir_url_seguimiento(transportista_url_actual, orden.nro_guia) %}
{% if url_seg %}
<div class="col-12 link-seguimiento-auto">
<div class="alert alert-light border py-2 px-3 mb-2">
<a href="{{ url_seg }}" target="_blank" class="small text-decoration-none" style="word-break:break-all;">{{ url_seg }}</a>
</div>
</div>
{% endif %}
{% endif %}

<div class="col-md-6"><label class="form-label small">Destinatario</label><input name="destinatario_nombre" class="form-control form-control-sm" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}"></div>
<div class="col-md-6"><label class="form-label small">Provincia</label><select name="destinatario_provincia" id="prov-select" class="form-select form-select-sm" onchange="actualizarLoc()"><option value="">Seleccione</option>{% for p in provincias %}<option value="{{ p.nombre }}" {% if orden.destinatario_provincia==p.nombre %}selected{% endif %}>{{ p.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-4"><label class="form-label small">Localidad</label><select name="destinatario_localidad" id="loc-select" class="form-select form-select-sm"><option value="{{ orden.destinatario_localidad or '' }}">{{ orden.destinatario_localidad or 'Seleccione' }}</option></select></div>
<div class="col-md-4"><label class="form-label small">CP</label><input name="destinatario_cp" class="form-control form-control-sm" value="{{ orden.destinatario_cp or '' }}"></div>
<div class="col-md-4"><label class="form-label small">Calle y altura</label><input name="destinatario_calle" class="form-control form-control-sm" value="{{ orden.destinatario_calle or '' }}"></div>
<div class="col-12"><label class="form-label small">Detalles adicionales</label><textarea name="destinatario_detalles" class="form-control form-control-sm" rows="2">{{ orden.destinatario_detalles or '' }}</textarea></div>
</div>
</div>

<script>
const LOCS = {{ localidades_por_provincia|tojson }};
function toggleEdicionEnvio() {
  const chk = document.getElementById('check-usar-datos');
  document.getElementById('bloque-envio-edit').style.display = chk.checked ? 'none' : 'block';
}
function actualizarLoc() {
  const pNombre = document.getElementById('prov-select').value;
  const locSelect = document.getElementById('loc-select');
  locSelect.innerHTML = '<option value="">Seleccione</option>';
  if(!pNombre) return;
  
  // Buscar las localidades que coincidan con el nombre de la provincia
  const provs = {{ provincias|tojson }};
  const prov = provs.find(p => p.nombre === pNombre);
  if (prov && LOCS[prov.id]) {
    LOCS[prov.id].forEach(l => {
      const opt = document.createElement('option');
      opt.value = l.nombre;
      opt.textContent = l.nombre;
      locSelect.appendChild(opt);
    });
  }
}
document.addEventListener('DOMContentLoaded', () => { toggleEdicionEnvio(); });
</script>

<button class="btn btn-dark btn-sm mt-3">Guardar datos de envio</button>"""

    if buscar_envio in contenido:
        contenido = contenido.replace(buscar_envio, nuevo_envio)
        print("[upgrade142] Datos de envío actualizados con selects en detalle.html")

    # 3. Agregar el botón global de guardar (al final de la página, antes del último </div>)
    buscar_end = "</div>\n{% endblock %}"
    nuevo_end = """<hr>
<div class="d-flex justify-content-between align-items-center mb-4 p-3 bg-light rounded shadow-sm">
<span class="text-muted small"><i class="bi bi-info-circle"></i> Este botón guarda los datos de envío y facturación a la vez.</span>
<button type="button" class="btn btn-dark" onclick="guardarTodo()"><i class="bi bi-save"></i> Guardar Todo</button>
</div>

<script>
function guardarTodo() {
    // Enviamos el form de facturación si existe
    const fFactura = document.getElementById('factura-form');
    if (fFactura) {
        fFactura.submit();
    } else {
        // Si no hay form de factura, enviamos el de envío
        const fEnvio = document.querySelector('form[action*="envio"]');
        if(fEnvio) fEnvio.submit();
    }
}
</script>
</div>
{% endblock %}"""
    if buscar_end in contenido:
        contenido = contenido.replace(buscar_end, nuevo_end)
        print("[upgrade142] Botón 'Guardar Todo' agregado a detalle.html")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 142: Mover Catalogos + Envios con Selects + Boton Global ===")
    patch_base_html()
    patch_detalle_route()
    patch_detalle_html()
    
    # Archivo dummy para que no falle el run.bat
    escribir('app142.py', '# Modulo vacio\npass')
    
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
        
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()