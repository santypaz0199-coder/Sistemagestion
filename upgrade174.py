import os

def aplicar_actualizacion():
    print("Iniciando actualizacion: Fix submit, validacion de filas y precio...")
    
    ruta_archivo = os.path.join('templates', 'ventas', 'form.html')
    
    if not os.path.exists(os.path.dirname(ruta_archivo)):
        print(f"Error: No se encontró la carpeta {os.path.dirname(ruta_archivo)}")
        return

    html_content = """{% extends "base.html" %}
{% block title %}Nueva orden{% endblock %}

{% block content %}
<style>
  .paso-card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 1.5rem; margin-bottom: 1.5rem; }
  .paso-num { background: #3b5bdb; color: white; width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; font-size: 0.9rem; margin-right: 10px; }
  .paso-title { font-size: 1.1rem; font-weight: 600; color: #1f2937; display: flex; align-items: center; }
  .metodo-btn { border: 2px solid #e5e7eb; border-radius: 8px; padding: 15px; cursor: pointer; text-align: center; transition: all 0.2s; background: #fff; }
  .metodo-btn.active { border-color: #3b5bdb; background: #eef2ff; }
  
  /* Ocultar las flechitas del input type number en Chrome, Safari, Edge y Firefox */
  input[type=number]::-webkit-inner-spin-button, 
  input[type=number]::-webkit-outer-spin-button { 
      -webkit-appearance: none; 
      margin: 0; 
  }
  input[type=number] {
      -moz-appearance: textfield;
  }
</style>

<div class="d-flex justify-content-between align-items-center mb-4">
  <h4 class="mb-0">Nueva orden de venta</h4>
  <a href="{{ url_for('ventas_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<form method="post" id="form-venta">
  
  <!-- PASO 1: CLIENTE -->
  <div class="paso-card">
    <div class="paso-title mb-3"><span class="paso-num">1</span> Seleccionar Cliente</div>
    <div class="row g-3">
      <div class="col-md-8">
        <select name="cliente_id" id="cliente-select" class="form-select" required onchange="cargarCliente()">
          <option value="">-- Buscar cliente --</option>
          {% for c in clientes %}
          <option value="{{ c.id }}">{{ c.nombre_completo }} ({{ c.nro_doc or 'Sin doc' }})</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-4">
        <label class="form-label">Tipo de compra (Automático)</label>
        <input type="text" id="tipo-compra-display" class="form-control bg-light fw-bold text-center" readonly value="Esperando cliente...">
        <input type="hidden" name="tipo" id="tipo-compra-value" value="minorista">
      </div>
    </div>
  </div>

  <!-- PASO 2: ORIGEN Y FECHA -->
  <div class="paso-card">
    <div class="paso-title mb-3"><span class="paso-num">2</span> Canal de Venta</div>
    <div class="row g-3">
      <div class="col-md-4">
        <label class="form-label">Canal *</label>
        <select name="canal_id" class="form-select" required>
          <option value="">-- Elegir --</option>
          {% for ch in canales %}
          <option value="{{ ch.id }}">{{ ch.nombre }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-4">
        <label class="form-label">Fecha</label>
        <input type="date" name="fecha" class="form-control" value="{{ hoy }}">
      </div>
      <div class="col-md-4">
        <label class="form-label">Notas internas</label>
        <input name="notas" class="form-control" placeholder="Opcional">
      </div>
    </div>
  </div>

  <!-- PASO 3: PRODUCTOS -->
  <div class="paso-card">
    <div class="paso-title mb-3"><span class="paso-num">3</span> Productos</div>
    <table class="table table-sm align-middle mb-0">
      <thead>
        <tr><th>Producto</th><th width="90">Cant.</th><th width="120">Precio</th><th width="110" class="text-end">Subtotal</th><th width="90" class="text-center">Acción</th><th width="40"></th></tr>
      </thead>
      <tbody id="items-body"></tbody>
    </table>
    <button type="button" class="btn btn-sm btn-outline-secondary mt-3" onclick="addItem()"><i class="bi bi-plus-lg"></i> Agregar otra fila</button>
  </div>

  <!-- PASO 4: ENVIO -->
  <div class="paso-card">
    <div class="paso-title mb-3"><span class="paso-num">4</span> Método de Entrega</div>
    
    <!-- 3 BOTONES DE SELECCION -->
    <div class="row g-3 mb-4">
        <div class="col-md-4">
            <div class="metodo-btn active" id="btn-retiro" onclick="setMetodo('retiro')">
                <i class="bi bi-shop fs-3 d-block mb-2"></i>
                <div class="fw-bold">Retiro en depósito</div>
                <div class="small text-muted">El cliente retira</div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="metodo-btn" id="btn-transporte" onclick="setMetodo('transporte')">
                <i class="bi bi-truck fs-3 d-block mb-2"></i>
                <div class="fw-bold">Empresa de transporte</div>
                <div class="small text-muted">Vía Cargo, etc.</div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="metodo-btn" id="btn-coordinar" onclick="setMetodo('coordinar')">
                <i class="bi bi-chat-dots fs-3 d-block mb-2"></i>
                <div class="fw-bold">Coordinar entrega</div>
                <div class="small text-muted">Personalizado</div>
            </div>
        </div>
    </div>

    <!-- PANEL RETIRO -->
    <div id="panel-retiro" class="p-3 bg-light rounded border">
        <p class="mb-0 text-muted small"><i class="bi bi-info-circle"></i> El cliente pasa a retirar por el depósito. No se cobra envío.</p>
        <input type="hidden" name="tipo_envio" id="input-tipo-envio" value="retiro">
    </div>

    <!-- PANEL TRANSPORTE -->
    <div id="panel-transporte" class="p-3 bg-light rounded border" style="display:none;">
        
        <!-- PASO A: Empresa -->
        <div id="bloque-empresa" class="mb-3">
            <label class="form-label fw-bold">1. Seleccionar Empresa de transporte *</label>
            <select name="transportista_id" id="transp-select" class="form-select" onchange="onEmpresaChange()">
                <option value="">-- Elegir --</option>
                {% for t in transportistas %}
                <option value="{{ t.id }}">{{ t.nombre }}</option>
                {% endfor %}
            </select>
        </div>

        <!-- PASO B: Destino (Oculto hasta elegir empresa) -->
        <div id="bloque-destino" class="mb-3" style="display:none;">
            <label class="form-label fw-bold">2. Tipo de entrega *</label>
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
                <div class="col-md-6"><label class="form-label">Nombre completo *</label><input name="dest_nombre" id="dest_nombre" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">DNI/CUIT *</label><input name="dest_doc" id="dest_doc" class="form-control" required></div>
                <div class="col-md-3"><label class="form-label">Teléfono *</label><input name="dest_tel" id="dest_tel" class="form-control" required></div>
                <div class="col-md-6"><label class="form-label">Email *</label><input type="email" name="dest_email" id="dest_email" class="form-control" required></div>
                
                <div class="col-md-4"><label class="form-label">Provincia *</label>
                    <select name="dest_prov" id="dest_prov" class="form-select" required onchange="actualizarCiudades()"><option value="">Seleccione</option>{% for p in provincias %}<option value="{{ p.nombre }}">{{ p.nombre }}</option>{% endfor %}</select>
                </div>
                <div class="col-md-4"><label class="form-label">Localidad *</label>
                    <select name="dest_loc" id="dest_loc" class="form-select" required><option value="">Seleccione</option></select>
                </div>
                <div class="col-md-4"><label class="form-label">Código Postal *</label><input name="dest_cp" id="dest_cp" class="form-control" required></div>

                <!-- Campos exclusivos de Domicilio -->
                <div class="col-md-6 campo-domicilio"><label class="form-label">Calle y altura *</label><input name="dest_calle" id="dest_calle" class="form-control"></div>
                <div class="col-md-3 campo-domicilio"><label class="form-label">Piso</label><input name="dest_piso" id="dest_piso" class="form-control"></div>
                <div class="col-md-3 campo-domicilio"><label class="form-label">Depto</label><input name="dest_depto" id="dest_depto" class="form-control"></div>
                
                <!-- Campo para ambos -->
                <div class="col-12"><label class="form-label">Datos adicionales (Opcional)</label><input name="dest_detalles" id="dest_detalles" class="form-control" placeholder="Referencias de la casa, horarios, etc."></div>
            </div>

            <!-- TILDE MODIFICAR DATOS (Al fondo de todo, destildado) -->
            <div class="form-check mt-4 pt-3 border-top">
                <input class="form-check-input" type="checkbox" id="chk-modificar-datos" onchange="toggleEdicion()">
                <label class="form-check-label fw-semibold text-primary" for="chk-modificar-datos" style="cursor:pointer;">
                    <i class="bi bi-pencil-square"></i> Modificar datos de entrega / Enviar a otra persona
                </label>
            </div>
        </div>
    </div>

    <!-- PANEL COORDINAR -->
    <div id="panel-coordinar" class="p-3 bg-light rounded border" style="display:none;">
        <p class="mb-2 text-muted small"><i class="bi bi-info-circle"></i> Se coordina por fuera. No se cobra envío automático.</p>
        <textarea name="dest_detalles" class="form-control" rows="2" placeholder="Aclaraciones para coordinar la entrega (Ej: Envío con mi transporte, etc.)"></textarea>
    </div>

  </div>

  <!-- TOTALES Y GUARDAR -->
  <div class="row g-3 mb-4">
    <div class="col-md-6 offset-md-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <table class="table table-sm mb-0">
            <tr><td class="align-middle">Subtotal productos:</td><td class="text-end fw-semibold" id="subtotal-view">$ 0,00</td></tr>
            <tr>
              <td class="align-middle">Valor de envío:</td>
              <td class="text-end">
                <div class="input-group input-group-sm">
                    <span class="input-group-text bg-light text-muted fw-bold">$</span>
                    <input type="text" id="costo_envio_display" class="form-control text-end bg-light fw-semibold" readonly value="0,00">
                    <input type="hidden" name="costo_envio" id="costo_envio" value="0">
                </div>
              </td>
            </tr>
            <tr><td class="align-middle">Descuento:</td><td class="text-end"><input type="number" step="0.01" min="0" name="descuento" id="descuento" value="0" class="form-control form-control-sm text-end" onchange="updateTotals()"></td></tr>
            <tr class="fw-bold fs-5"><td>Total:</td><td class="text-end" id="total-view">$ 0,00</td></tr>
          </table>
        </div>
      </div>
    </div>
  </div>

  <button type="submit" id="btn-crear-orden" class="btn btn-dark btn-lg w-100">Crear Orden</button>
</form>

<!-- Template Item -->
<template id="item-template">
  <tr class="item-row">
    <td>
      <!-- Ya no es required para que no bloquee el envio si esta vacia -->
      <select name="producto_id" class="form-select form-select-sm" onchange="onProductChange(this)">
        <option value="">-- Elegir --</option>
        {% for p in productos %}
        <option value="{{ p.id }}" data-precio="{{ p.precio }}" data-peso="{{ p.peso_valor }}" data-unidad="{{ p.peso_unidad }}">{{ p.nombre }} (stock: {{ '%g'|format(p.stock_actual) }})</option>
        {% endfor %}
      </select>
    </td>
    <!-- Cantidad Entera (Sin required) -->
    <td><input type="number" step="1" min="1" name="cantidad" class="form-control form-control-sm text-center" value="1"></td>
    <!-- PRECIO FIJO (Sin required) -->
    <td><input type="number" step="0.01" name="precio" class="form-control form-control-sm bg-light fw-bold" readonly></td>
    
    <td class="text-end subtotal fw-semibold">$ 0,00</td>
    
    <td class="text-center">
        <!-- Boton Añadir -->
        <button type="button" class="btn btn-sm btn-outline-success w-100" onclick="confirmItem(this)"><i class="bi bi-plus-lg"></i> Añadir</button>
    </td>
    <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="removeItem(this)"><i class="bi bi-trash"></i></button></td>
  </tr>
</template>

<script>
const LOCALIDADES = {{ localidades_por_provincia|default({})|tojson }};
const PROVINCIAS = {{ provincias|default([])|tojson }};
const fmt = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' });

let metodoActual = 'retiro';
let destinoActual = 'sucursal';

function formatMoneda(val) {
    return fmt.format(val).replace('$', '').trim();
}

// --- 1. FUNCIONES DE PRODUCTOS ---
function addItem() {
    const tmpl = document.getElementById('item-template');
    if(tmpl) {
        document.getElementById('items-body').appendChild(tmpl.content.cloneNode(true));
    }
}

function removeItem(btn) {
    btn.closest('tr').remove();
    updateTotalsAndShipping();
}

function onProductChange(sel) {
    const opt = sel.options[sel.selectedIndex];
    const precio = opt.dataset.precio || 0;
    const row = sel.closest('tr');
    row.querySelector('[name="precio"]').value = precio;
}

function confirmItem(btn) {
    const row = btn.closest('tr');
    const sel = row.querySelector('[name="producto_id"]');
    
    if (!sel.value) {
        alert("Por favor, selecciona un producto antes de añadir.");
        return;
    }
    
    const cantInput = row.querySelector('[name="cantidad"]');
    const precioInput = row.querySelector('[name="precio"]');
    
    const cant = parseInt(cantInput.value) || 0;
    const precio = parseFloat(precioInput.value) || 0;
    
    if (cant <= 0) {
        alert("La cantidad debe ser mayor a 0.");
        return;
    }

    const sub = cant * precio;
    row.querySelector('.subtotal').textContent = fmt.format(sub);

    sel.disabled = true;
    cantInput.disabled = true;
    precioInput.disabled = true;
    
    btn.className = "btn btn-sm btn-success w-100";
    btn.innerHTML = '<i class="bi bi-check-lg"></i> Añadido';
    btn.disabled = true;

    updateTotalsAndShipping();
}

function updateTotalsAndShipping() {
    updateTotals();
    if (metodoActual === 'transporte') {
        calcularEnvio();
    }
}

function updateTotals() {
    let subtotal = 0;
    document.querySelectorAll('.item-row').forEach(row => {
        const cantInput = row.querySelector('[name="cantidad"]');
        if (!cantInput.disabled) return; 
        
        const cant = parseInt(cantInput.value) || 0;
        const precio = parseFloat(row.querySelector('[name="precio"]').value) || 0;
        subtotal += (cant * precio);
    });
    
    const desc = parseFloat(document.getElementById('descuento').value) || 0;
    const envio = parseFloat(document.getElementById('costo_envio').value) || 0;
    
    document.getElementById('subtotal-view').textContent = fmt.format(subtotal);
    document.getElementById('total-view').textContent = fmt.format(Math.max(0, subtotal - desc + envio));
}


// --- 2. FUNCIONES DE ENVÍO ---
function setMetodo(metodo) {
    metodoActual = metodo;
    document.getElementById('input-tipo-envio').value = metodo;
    
    document.querySelectorAll('.metodo-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-' + metodo).classList.add('active');
    
    document.getElementById('panel-retiro').style.display = (metodo === 'retiro') ? 'block' : 'none';
    document.getElementById('panel-transporte').style.display = (metodo === 'transporte') ? 'block' : 'none';
    document.getElementById('panel-coordinar').style.display = (metodo === 'coordinar') ? 'block' : 'none';
    
    if (metodo !== 'transporte') {
        document.getElementById('bloque-destino').style.display = 'none';
        document.getElementById('form-envio-campos').style.display = 'none';
        document.getElementById('costo_envio').value = 0;
        document.getElementById('costo_envio_display').value = "0,00";
        updateTotals();
    } else {
        calcularEnvio();
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
    
    document.getElementById('form-envio-campos').style.display = 'block';
    
    const camposCalle = document.querySelectorAll('.campo-domicilio');
    if (destino === 'domicilio') {
        camposCalle.forEach(c => c.style.display = 'block');
        document.getElementById('dest_calle').required = true;
    } else {
        camposCalle.forEach(c => c.style.display = 'none');
        document.getElementById('dest_calle').required = false;
        document.getElementById('dest_calle').value = '';
        document.getElementById('dest_piso').value = '';
        document.getElementById('dest_depto').value = '';
    }

    document.getElementById('chk-modificar-datos').checked = false;
    toggleEdicion();
    cargarCliente(); 
    calcularEnvio();
}

function toggleEdicion() {
    const chk = document.getElementById('chk-modificar-datos').checked;
    const camposFijos = ['dest_nombre', 'dest_doc', 'dest_tel', 'dest_email', 'dest_prov', 'dest_loc', 'dest_cp'];
    
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

    if (destinoActual === 'domicilio') {
        ['dest_calle', 'dest_piso', 'dest_depto', 'dest_detalles'].forEach(id => {
            document.getElementById(id).removeAttribute('readonly');
        });
    } else {
        document.getElementById('dest_detalles').removeAttribute('readonly');
    }
}


// --- 3. CARGA DE CLIENTE Y TAG ---
async function cargarCliente() {
  const cid = document.getElementById('cliente-select').value;
  const displayTipo = document.getElementById('tipo-compra-display');
  const hiddenTipo = document.getElementById('tipo-compra-value');
  
  if (!cid) {
      displayTipo.value = "Esperando cliente...";
      displayTipo.style.color = '#6b7280'; 
      hiddenTipo.value = "minorista";
      return;
  }
  
  try {
    const res = await fetch('/api/cliente/' + cid);
    const data = await res.json();
    
    const tipoLower = (data.tipo || '').toLowerCase();
    if (tipoLower.includes('mayor')) {
        hiddenTipo.value = 'mayorista';
        displayTipo.value = 'Mayorista';
        displayTipo.style.color = '#d97706'; 
    } else {
        hiddenTipo.value = 'minorista';
        displayTipo.value = 'Minorista (Consumidor Final)';
        displayTipo.style.color = '#0284c7'; 
    }

    document.getElementById('dest_nombre').value = data.nombre || '';
    document.getElementById('dest_doc').value = data.doc ? data.doc.replace(/[^0-9]/g, '') : '';
    document.getElementById('dest_tel').value = data.tel || data.telefono || '';
    document.getElementById('dest_email').value = data.email || '';
    document.getElementById('dest_cp').value = data.cp || data.codigo_postal || '';
    
    if (data.provincia) {
      document.getElementById('dest_prov').value = data.provincia;
      actualizarCiudades();
      if (data.localidad) document.getElementById('dest_loc').value = data.localidad;
    }

    if (destinoActual === 'domicilio') {
        document.getElementById('dest_calle').value = data.calle || '';
    }
  } catch(e) { console.error("Error al cargar cliente:", e); }
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
    const cantInput = row.querySelector('[name="cantidad"]');
    if (!cantInput.disabled) return; 

    const sel = row.querySelector('[name="producto_id"]');
    const opt = sel.options[sel.selectedIndex];
    const cant = parseInt(cantInput.value) || 0;
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
      document.getElementById('costo_envio_display').value = formatMoneda(data.precio);
    } else {
      document.getElementById('costo_envio').value = 0;
      document.getElementById('costo_envio_display').value = "0,00";
    }
    updateTotals(); 
  } catch(e) { 
    console.error("Error al calcular envío:", e); 
    updateTotals();
  }
}

// Inicializar la página cuando carga
document.addEventListener('DOMContentLoaded', () => {
  addItem(); 
  setMetodo('retiro'); 
});

// EVENTO DE ENVIO DEL FORMULARIO
document.getElementById('form-venta').addEventListener('submit', function(e) {
  // 1. Quitamos las filas de productos que se agregaron pero NO se les dio a "Añadir"
  document.querySelectorAll('.item-row').forEach(row => {
      const sel = row.querySelector('[name="producto_id"]');
      if (!sel.disabled) { // Si no esta deshabilitado, es porque no se confirmo
          row.remove(); // Lo borramos del formulario para que no moleste
      }
  });

  // 2. Habilitamos todos los inputs deshabilitados (como los del cliente y el boton añadir) 
  // para que los datos viajen al servidor de Python.
  document.querySelectorAll('input, select').forEach(i => i.removeAttribute('disabled'));
  
  // 3. Efecto visual en el boton para saber que se esta cargando
  const btn = document.getElementById('btn-crear-orden');
  btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creando...';
  btn.disabled = true;
});
</script>
{% endblock %}"""

    try:
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("¡Formulario actualizado con exito!")
        print("Se solucionó el bloqueo de envío, se agregó efecto de carga y se limpiaron las flechitas.")
    except Exception as e:
        print(f"Hubo un error al guardar el archivo: {e}")

if __name__ == '__main__':
    aplicar_actualizacion()