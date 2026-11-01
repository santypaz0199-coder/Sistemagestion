# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_form_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'form.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Reemplazar todo el bloque del panel de transporte
    buscar_panel = r'''<!-- PANEL TRANSPORTE -->
    <div id="panel-transporte" class="p-3 bg-light rounded border" style="display:none;">
        <div class="row g-3 mb-3">
            <div class="col-md-6">
                <label class="form-label">Empresa de transporte *</label>
                <select name="transportista_id" id="transp-select" class="form-select" onchange="calcularEnvio()">
                    <option value="">-- Elegir --</option>
                    {% for t in transportistas %}
                    <option value="{{ t.id }}">{{ t.nombre }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-6">
                <label class="form-label">Destino *</label>
                <select name="destino_tipo" id="destino-select" class="form-select" onchange="calcularEnvio()">
                    <option value="sucursal">Retiro en Sucursal</option>
                    <option value="domicilio">Entrega a Domicilio</option>
                </select>
            </div>
        </div>

        <div class="form-check mb-3">
            <input class="form-check-input" type="checkbox" id="chk-modificar-datos" onchange="toggleDatosEnvio()">
            <label class="form-check-label fw-semibold text-danger" for="chk-modificar-datos">
                Modificar datos de entrega / Enviar a otra persona
            </label>
        </div>
        
        <div id="aviso-faltan-datos" class="alert alert-warning py-2 small mb-3" style="display:none;">
            <i class="bi bi-exclamation-triangle"></i> El cliente no tiene la dirección completa. Completala abajo.
        </div>

        <div id="form-envio-campos" class="opacity-50" style="pointer-events:none;">
            <div class="row g-3">
                <div class="col-md-6"><label class="form-label">Nombre *</label><input name="dest_nombre" id="dest_nombre" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">DNI/CUIT *</label><input name="dest_doc" id="dest_doc" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">Teléfono *</label><input name="dest_tel" id="dest_tel" class="form-control" required></div>
                <div class="col-md-6"><label class="form-label">Email *</label><input type="email" name="dest_email" id="dest_email" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">Provincia *</label>
                    <select name="dest_prov" id="dest_prov" class="form-select" required onchange="actualizarCiudades()"><option value="">Seleccione</option>{% for p in provincias %}<option value="{{ p.nombre }}">{{ p.nombre }}</option>{% endfor %}</select>
                </div>
                <div class="col-md-3"><label class="form-label">Localidad *</label>
                    <select name="dest_loc" id="dest_loc" class="form-select" required><option value="">Seleccione</option></select>
                </div>
                <div class="col-md-6"><label class="form-label">Calle y altura *</label><input name="dest_calle" id="dest_calle" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">Piso</label><input name="dest_piso" id="dest_piso" class="form-control"></div>
                <div class="col-md-3"><label class="form-label">Depto</label><input name="dest_depto" id="dest_depto" class="form-control"></div>
                <div class="col-12"><label class="form-label">Detalles</label><input name="dest_detalles" id="dest_detalles" class="form-control" placeholder="Ej: Casa con rejas negras..."></div>
            </div>
        </div>
    </div>'''

    nuevo_panel = r'''<!-- PANEL TRANSPORTE -->
    <div id="panel-transporte" class="p-3 bg-light rounded border" style="display:none;">
        
        <!-- PASO A: Empresa -->
        <div id="bloque-empresa" class="mb-3">
            <label class="form-label">1. Seleccionar Empresa de transporte *</label>
            <select name="transportista_id" id="transp-select" class="form-select" onchange="onEmpresaChange()">
                <option value="">-- Elegir --</option>
                {% for t in transportistas %}
                <option value="{{ t.id }}">{{ t.nombre }}</option>
                {% endfor %}
            </select>
        </div>

        <!-- PASO B: Destino (Oculto hasta elegir empresa) -->
        <div id="bloque-destino" class="mb-3" style="display:none;">
            <label class="form-label">2. Tipo de entrega *</label>
            <div class="row g-2">
                <div class="col-md-6">
                    <div class="metodo-btn" id="btn-sucursal" onclick="setDestino('sucursal')" style="padding:10px; font-size:.9rem;">
                        <i class="bi bi-building mb-1"></i> Sucursal
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="metodo-btn" id="btn-domicilio" onclick="setDestino('domicilio')" style="padding:10px; font-size:.9rem;">
                        <i class="bi bi-house mb-1"></i> Domicilio
                    </div>
                </div>
            </div>
            <input type="hidden" name="destino_tipo" id="destino-select" value="sucursal">
        </div>
        
        <!-- PASO C: Datos (Oculto hasta elegir destino) -->
        <div id="form-envio-campos" style="display:none;">
            <hr class="my-3">
            <div class="row g-3">
                <div class="col-md-6"><label class="form-label">Nombre *</label><input name="dest_nombre" id="dest_nombre" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">DNI/CUIT *</label><input name="dest_doc" id="dest_doc" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">Teléfono *</label><input name="dest_tel" id="dest_tel" class="form-control" required></div>
                <div class="col-md-6"><label class="form-label">Email *</label><input type="email" name="dest_email" id="dest_email" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">Provincia *</label>
                    <select name="dest_prov" id="dest_prov" class="form-select" required onchange="actualizarCiudades()"><option value="">Seleccione</option>{% for p in provincias %}<option value="{{ p.nombre }}">{{ p.nombre }}</option>{% endfor %}</select>
                </div>
                <div class="col-md-3"><label class="form-label">Localidad *</label>
                    <select name="dest_loc" id="dest_loc" class="form-select" required><option value="">Seleccione</option></select>
                </div>

                <!-- Campos exclusivos de Domicilio -->
                <div class="col-md-6 campo-domicilio"><label class="form-label">Calle y altura *</label><input name="dest_calle" id="dest_calle" class="form-control"></div>
                <div class="col-md-3 campo-domicilio"><label class="form-label">Piso</label><input name="dest_piso" id="dest_piso" class="form-control"></div>
                <div class="col-md-3 campo-domicilio"><label class="form-label">Depto</label><input name="dest_depto" id="dest_depto" class="form-control"></div>
                
                <!-- Campo para ambos -->
                <div class="col-12"><label class="form-label">Datos adicionales</label><input name="dest_detalles" id="dest_detalles" class="form-control" placeholder="Referencias de la casa, horarios..."></div>
            </div>

            <!-- TILDE MODIFICAR DATOS -->
            <div class="form-check mt-4 pt-3 border-top">
                <input class="form-check-input" type="checkbox" id="chk-modificar-datos" onchange="toggleEdicion()">
                <label class="form-check-label fw-semibold" for="chk-modificar-datos">
                    Modificar datos (Enviar a otra persona / Regalo)
                </label>
            </div>
        </div>
    </div>'''

    if buscar_panel in contenido:
        contenido = contenido.replace(buscar_panel, nuevo_panel)
        print("[upgrade166] Panel de transporte actualizado al modo asistente.")
    else:
        print("[upgrade166] ADVERTENCIA: no se encontró el panel de transporte exacto.")

    # 2. Reemplazar el bloque de Javascript de cliente y calcular envio
    buscar_js = r'''// --- CARGA DE CLIENTE ---
async function cargarCliente() {'''

    # Buscamos desde cargarCliente hasta el final del script para reescribirlo
    patron_js = re.compile(r"// --- CARGA DE CLIENTE ---.*?document\.addEventListener\('DOMContentLoaded', \(\) => \{.*?\}\);", re.DOTALL)
    
    nuevo_js = r'''// --- LOGICA DEL ASISTENTE DE ENVIO ---
let metodoActual = 'retiro';
let destinoActual = 'sucursal';

function setMetodo(metodo) {
    metodoActual = metodo;
    document.getElementById('input-tipo-envio').value = metodo;
    
    document.querySelectorAll('.metodo-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-' + metodo).classList.add('active');
    
    document.getElementById('panel-retiro').style.display = metodo === 'retiro' ? 'block' : 'none';
    document.getElementById('panel-transporte').style.display = metodo === 'transporte' ? 'block' : 'none';
    document.getElementById('panel-coordinar').style.display = metodo === 'coordinar' ? 'block' : 'none';
    
    // Resetear el asistente si cambia de metodo
    if (metodo !== 'transporte') {
        document.getElementById('bloque-destino').style.display = 'none';
        document.getElementById('form-envio-campos').style.display = 'none';
        document.getElementById('costo_envio').value = 0;
        updateTotals();
    }
}

function onEmpresaChange() {
    const t_id = document.getElementById('transp-select').value;
    if (t_id) {
        document.getElementById('bloque-destino').style.display = 'block';
    } else {
        document.getElementById('bloque-destino').style.display = 'none';
        document.getElementById('form-envio-campos').style.display = 'none';
    }
    calcularEnvio();
}

function setDestino(destino) {
    destinoActual = destino;
    document.getElementById('destino-select').value = destino;
    
    document.querySelectorAll('#bloque-destino .metodo-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-' + destino).classList.add('active');
    
    // Mostrar campos
    document.getElementById('form-envio-campos').style.display = 'block';
    
    // Mostrar u ocultar calle/piso/depto
    const camposCalle = document.querySelectorAll('.campo-domicilio');
    if (destino === 'domicilio') {
        camposCalle.forEach(c => c.style.display = 'block');
        document.getElementById('dest_calle').required = true;
    } else {
        camposCalle.forEach(c => c.style.display = 'none');
        document.getElementById('dest_calle').required = false;
        document.getElementById('dest_calle').value = ''; // Limpiar si cambia a sucursal
    }

    // Forzar que se llene con los datos del cliente (destilda el check)
    document.getElementById('chk-modificar-datos').checked = false;
    toggleEdicion();
    cargarCliente(); // Refrescar datos
    calcularEnvio();
}

function toggleEdicion() {
    const chk = document.getElementById('chk-modificar-datos').checked;
    
    // Campos que SIEMPRE se bloquean si no estamos modificando
    const camposFijos = ['dest_nombre', 'dest_doc', 'dest_tel', 'dest_email', 'dest_prov', 'dest_loc'];
    camposFijos.forEach(id => {
        const el = document.getElementById(id);
        if (chk) {
            el.removeAttribute('readonly');
            el.removeAttribute('disabled');
        } else {
            if(el.tagName === 'SELECT') el.setAttribute('disabled', true);
            else el.setAttribute('readonly', true);
        }
    });

    // Campos de calle/piso/depto/detalles (dependen de si es domicilio)
    if (destinoActual === 'domicilio') {
        const camposEditables = ['dest_calle', 'dest_piso', 'dest_depto', 'dest_detalles'];
        camposEditables.forEach(id => {
            const el = document.getElementById(id);
            if (chk) el.removeAttribute('readonly');
            else el.setAttribute('readonly', true);
        });
    } else {
        // Si es sucursal, solo detalles es editable
        const el = document.getElementById('dest_detalles');
        if (chk) el.removeAttribute('readonly');
        else el.setAttribute('readonly', true);
    }
}

async function cargarCliente() {
  const cid = document.getElementById('cliente-select').value;
  if (!cid) return;
  
  try {
    const res = await fetch('/api/cliente/' + cid);
    const data = await res.json();
    
    document.getElementById('tipo-compra').value = data.tipo;
    document.getElementById('dest_nombre').value = data.nombre;
    document.getElementById('dest_doc').value = data.doc.replace(/[^0-9]/g, '');
    document.getElementById('dest_tel').value = data.tel;
    document.getElementById('dest_email').value = data.email;
    
    if (data.provincia) {
      document.getElementById('dest_prov').value = data.provincia;
      actualizarCiudades();
      if (data.localidad) document.getElementById('dest_loc').value = data.localidad;
    }

    if (data.calle) {
        document.getElementById('dest_calle').value = data.calle;
    } else {
        document.getElementById('dest_calle').value = '';
    }
  } catch(e) { console.error(e); }
}

function actualizarCiudades() {
  const provNombre = document.getElementById('dest_prov').value;
  const locSelect = document.getElementById('dest_loc');
  locSelect.innerHTML = '<option value="">Seleccione</option>';
  if(!provNombre) return;
  const prov = PROVINCIAS.find(p => p.nombre === provNombre);
  if (prov && LOCALIDADES[prov.id]) {
    LOCALIDADES[prov.id].forEach(l => {
      const opt = document.createElement('option');
      opt.value = l.nombre; opt.textContent = l.nombre;
      locSelect.appendChild(opt);
    });
  }
}

async function calcularEnvio() {
  if (metodoActual !== 'transporte') return;
  const t_id = document.getElementById('transp-select').value;
  if (!t_id) return;
  
  let peso = 0;
  document.querySelectorAll('.item-row').forEach(row => {
    const sel = row.querySelector('[name="producto_id"]');
    const opt = sel.options[sel.selectedIndex];
    const cant = parseFloat(row.querySelector('[name="cantidad"]').value) || 0;
    if (opt.dataset.peso) {
      let pv = parseFloat(opt.dataset.peso);
      if (opt.dataset.unidad === 'g') pv = pv / 1000;
      peso += (pv * cant);
    }
  });

  try {
    const res = await fetch(`/api/calcular-envio?transportista_id=${t_id}&peso=${peso}&destino=${destinoActual}`);
    const data = await res.json();
    if (data.ok) {
      document.getElementById('costo_envio').value = data.precio;
      updateTotals();
    }
  } catch(e) { console.error(e); }
}

// Inicializar
document.addEventListener('DOMContentLoaded', () => {
  addItem();
  setMetodo('retiro'); 
});

// Antes de enviar, quitar disabled de todos los inputs para que viajen en el POST
document.getElementById('form-venta').addEventListener('submit', function(e) {
  document.querySelectorAll('input, select').forEach(i => i.removeAttribute('disabled'));
});'''

    # Reemplazar el bloque de JS
    contenido, n = patron_js.subn(nuevo_js, contenido)
    
    if n > 0:
        print("[upgrade166] JavaScript del formulario reescrito (Lógica de Asistente).")
    else:
        # Si falló, buscamos las funciones viejas por nombre
        contenido = contenido.replace("// --- CARGA DE CLIENTE ---", nuevo_js)
        print("[upgrade166] JavaScript reemplazado por coincidencia de texto.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 166: Formulario de Envio estilo Asistente ===")
    patch_form_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()