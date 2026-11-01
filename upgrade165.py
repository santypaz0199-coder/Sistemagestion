# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade165] escrito: {relpath}")

APP165_PY = r'''
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required, generar_numero_orden
from database import get_db
from datetime import date

@app.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
@permiso_required('ventas')
def ventas_nueva_v3():
    conn = get_db()
    if request.method == 'POST':
        try:
            cliente_id = int(request.form['cliente_id'])
            tipo = request.form['tipo']
            canal_id = int(request.form['canal_id']) if request.form.get('canal_id') else None
            fecha = request.form.get('fecha') or date.today().isoformat()
            descuento = float(request.form.get('descuento') or 0)
            costo_envio = float(request.form.get('costo_envio') or 0)
            tipo_envio = request.form.get('tipo_envio', 'transporte')
            
            transportista_id = int(request.form['transportista_id']) if request.form.get('transportista_id') else None
            destino_tipo = request.form.get('destino_tipo')
            notas = request.form.get('notas', '').strip()
            
            # Datos de envio
            dest_nombre = request.form.get('dest_nombre', '').strip()
            dest_doc = request.form.get('dest_doc', '').strip()
            dest_tel = request.form.get('dest_tel', '').strip()
            dest_email = request.form.get('dest_email', '').strip()
            dest_prov = request.form.get('dest_prov', '').strip()
            dest_loc = request.form.get('dest_loc', '').strip()
            dest_calle = request.form.get('dest_calle', '').strip()
            dest_piso = request.form.get('dest_piso', '').strip()
            dest_depto = request.form.get('dest_depto', '').strip()
            dest_detalles = request.form.get('dest_detalles', '').strip()
            
            pids = request.form.getlist('producto_id')
            cants = request.form.getlist('cantidad')
            precios = request.form.getlist('precio')
        except (ValueError, KeyError):
            conn.close(); flash('Revisa los datos.', 'error'); return redirect(url_for('ventas_nueva'))

        items = []
        for pid, cant, prec in zip(pids, cants, precios):
            if not pid or not cant: continue
            try:
                cant_f = float(cant); prec_f = float(prec)
            except ValueError: continue
            if cant_f <= 0: continue
            items.append({'producto_id': int(pid), 'cantidad': cant_f, 'precio': prec_f, 'subtotal': cant_f * prec_f})
            
        if not items:
            conn.close(); flash('Agrega productos.', 'error'); return redirect(url_for('ventas_nueva'))

        subtotal = sum(i['subtotal'] for i in items)
        total = max(0, subtotal - descuento) + costo_envio
        numero = generar_numero_orden(conn)

        cur = conn.execute("""INSERT INTO ordenes_venta
            (numero_interno, cliente_id, usuario_id, canal_id, tipo, fecha, estado,
             estado_facturacion, subtotal, descuento, total, notas, tipo_envio,
             transportista_id, destino_tipo, costo_envio,
             destinatario_nombre, destinatario_documento, destinatario_telefono, destinatario_email,
             destinatario_provincia, destinatario_localidad, destinatario_calle, 
             destinatario_piso, destinatario_depto, destinatario_detalles)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, cliente_id, current_user.id, canal_id, tipo, fecha, 'pendiente_pago',
             'no_requiere', subtotal, descuento, total, notas, tipo_envio,
             transportista_id, destino_tipo, costo_envio,
             dest_nombre, dest_doc, dest_tel, dest_email,
             dest_prov, dest_loc, dest_calle, dest_piso, dest_depto, dest_detalles))
        oid = cur.lastrowid

        for it in items:
            conn.execute("""INSERT INTO orden_items (orden_id, producto_id, cantidad, precio_unitario, subtotal)
                VALUES (?,?,?,?,?)""", (oid, it['producto_id'], it['cantidad'], it['precio'], it['subtotal']))

        conn.commit(); conn.close()
        flash(f'Orden {numero} creada.', 'success')
        return redirect(url_for('ventas_detalle', id=oid))

    # GET
    if current_user.es_admin:
        clientes = conn.execute("SELECT * FROM clientes WHERE activo=1 ORDER BY nombre_completo").fetchall()
    else:
        clientes = conn.execute("SELECT * FROM clientes WHERE activo=1 AND vendedor_id=? ORDER BY nombre_completo", (current_user.id,)).fetchall()
        
    productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    canales = conn.execute("SELECT * FROM canales_venta WHERE activo=1 AND lower(nombre) != 'tienda online' ORDER BY nombre").fetchall()
    transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1 ORDER BY nombre").fetchall()
    
    provincias = [dict(r) for r in conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()]
    locs_rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    localidades_por_provincia = {}
    for r in locs_rows:
        localidades_por_provincia.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})

    conn.close()
    return render_template('ventas/form.html', clientes=clientes, productos=productos, canales=canales,
                           transportistas=transportistas, provincias=provincias, 
                           localidades_por_provincia=localidades_por_provincia, hoy=date.today().isoformat())

app.view_functions['ventas_nueva'] = ventas_nueva_v3
'''

VENTAS_FORM = r'''{% extends "base.html" %}
{% block title %}Nueva orden{% endblock %}

{% block content %}
<style>
  .paso-card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 1.5rem; margin-bottom: 1.5rem; }
  .paso-num { background: #3b5bdb; color: white; width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; font-size: 0.9rem; margin-right: 10px; }
  .paso-title { font-size: 1.1rem; font-weight: 600; color: #1f2937; display: flex; align-items: center; }
  .metodo-btn { border: 2px solid #e5e7eb; border-radius: 8px; padding: 15px; cursor: pointer; text-align: center; transition: all 0.2s; background: #fff; }
  .metodo-btn.active { border-color: #3b5bdb; background: #eef2ff; }
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
        <label class="form-label">Tipo de compra</label>
        <select name="tipo" id="tipo-compra" class="form-select" required>
          <option value="minorista">Minorista (Consumidor Final)</option>
          <option value="mayorista">Mayorista</option>
        </select>
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
        <tr><th>Producto</th><th width="100">Cant.</th><th width="130">Precio</th><th width="110" class="text-end">Subtotal</th><th width="40"></th></tr>
      </thead>
      <tbody id="items-body"></tbody>
    </table>
    <button type="button" class="btn btn-sm btn-outline-secondary mt-3" onclick="addItem()"><i class="bi bi-plus-lg"></i> Agregar producto</button>
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
            <tr><td>Subtotal productos:</td><td class="text-end" id="subtotal-view">$0,00</td></tr>
            <tr>
              <td>Valor de envío:</td>
              <td class="text-end">
                <input type="number" step="0.01" min="0" name="costo_envio" id="costo_envio" value="0" class="form-control form-control-sm text-end" onchange="updateTotals()" readonly>
              </td>
            </tr>
            <tr><td>Descuento:</td><td class="text-end"><input type="number" step="0.01" min="0" name="descuento" id="descuento" value="0" class="form-control form-control-sm text-end" onchange="updateTotals()"></td></tr>
            <tr class="fw-bold fs-5"><td>Total:</td><td class="text-end" id="total-view">$0,00</td></tr>
          </table>
        </div>
      </div>
    </div>
  </div>

  <button class="btn btn-dark btn-lg w-100">Crear Orden</button>
</form>

<!-- Template Item -->
<template id="item-template">
  <tr class="item-row">
    <td>
      <select name="producto_id" class="form-select form-select-sm" onchange="onProductChange(this)" required>
        <option value="">-- Elegir --</option>
        {% for p in productos %}
        <option value="{{ p.id }}" data-precio="{{ p.precio }}" data-peso="{{ p.peso_valor }}" data-unidad="{{ p.peso_unidad }}">{{ p.nombre }} (stock: {{ '%g'|format(p.stock_actual) }})</option>
        {% endfor %}
      </select>
    </td>
    <td><input type="number" step="0.01" min="0.01" name="cantidad" class="form-control form-control-sm" value="1" onchange="updateTotals()" required></td>
    <td><input type="number" step="0.01" min="0" name="precio" class="form-control form-control-sm" value="0" onchange="updateTotals()" required></td>
    <td class="text-end subtotal">$0,00</td>
    <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="removeItem(this)"><i class="bi bi-trash"></i></button></td>
  </tr>
</template>

<script>
const LOCALIDADES = {{ localidades_por_provincia|tojson }};
const PROVINCIAS = {{ provincias|tojson }};

// FORMATEADOR DE MONEDA ARGENTINA
const fmt = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' });

let metodoActual = 'retiro';

function setMetodo(metodo) {
    metodoActual = metodo;
    document.getElementById('input-tipo-envio').value = metodo;
    
    // UI Active
    document.querySelectorAll('.metodo-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-' + metodo).classList.add('active');
    
    // Panels
    document.getElementById('panel-retiro').style.display = metodo === 'retiro' ? 'block' : 'none';
    document.getElementById('panel-transporte').style.display = metodo === 'transporte' ? 'block' : 'none';
    document.getElementById('panel-coordinar').style.display = metodo === 'coordinar' ? 'block' : 'none';
    
    // Si es transporte, calculamos. Si no, envio a 0.
    if (metodo === 'transporte') {
        calcularEnvio();
    } else {
        document.getElementById('costo_envio').value = 0;
        updateTotals();
    }
}

function addItem() {
  const tmpl = document.getElementById('item-template');
  document.getElementById('items-body').appendChild(tmpl.content.cloneNode(true));
}

function removeItem(btn) {
  btn.closest('tr').remove();
  updateTotals();
}

function onProductChange(sel) {
  const opt = sel.options[sel.selectedIndex];
  const precio = opt.dataset.precio || 0;
  const row = sel.closest('tr');
  row.querySelector('[name="precio"]').value = precio;
  updateTotals();
}

function updateTotals() {
  let subtotal = 0;
  document.querySelectorAll('.item-row').forEach(row => {
    const cant = parseFloat(row.querySelector('[name="cantidad"]').value) || 0;
    const precio = parseFloat(row.querySelector('[name="precio"]').value) || 0;
    const sub = cant * precio;
    row.querySelector('.subtotal').textContent = fmt.format(sub);
    subtotal += sub;
  });
  const desc = parseFloat(document.getElementById('descuento').value) || 0;
  const envio = parseFloat(document.getElementById('costo_envio').value) || 0;
  
  document.getElementById('subtotal-view').textContent = fmt.format(subtotal);
  document.getElementById('total-view').textContent = fmt.format(Math.max(0, subtotal - desc + envio));
}

// --- CARGA DE CLIENTE ---
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
    
    const chkModificar = document.getElementById('chk-modificar-datos');
    if (!data.calle || !data.provincia || !data.tel || !data.email) {
      chkModificar.checked = true;
      toggleDatosEnvio();
      document.getElementById('aviso-faltan-datos').style.display = 'block';
    } else {
      chkModificar.checked = false;
      toggleDatosEnvio();
      document.getElementById('aviso-faltan-datos').style.display = 'none';
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

function toggleDatosEnvio() {
  const chk = document.getElementById('chk-modificar-datos');
  const campos = document.getElementById('form-envio-campos');
  const inputs = campos.querySelectorAll('input, select');
  
  if (chk.checked) {
    campos.classList.remove('opacity-50');
    campos.style.pointerEvents = 'auto';
    inputs.forEach(i => i.removeAttribute('readonly'));
    inputs.forEach(i => i.removeAttribute('disabled'));
  } else {
    campos.classList.add('opacity-50');
    campos.style.pointerEvents = 'none';
    inputs.forEach(i => i.setAttribute('readonly', true));
    inputs.forEach(i => i.setAttribute('disabled', true));
  }
}

async function calcularEnvio() {
  if (metodoActual !== 'transporte') return;
  const t_id = document.getElementById('transp-select').value;
  const destino = document.getElementById('destino-select').value;
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
    const res = await fetch(`/api/calcular-envio?transportista_id=${t_id}&peso=${peso}&destino=${destino}`);
    const data = await res.json();
    if (data.ok) {
      document.getElementById('costo_envio').value = data.precio;
      updateTotals();
    }
  } catch(e) { console.error(e); }
}

document.getElementById('form-venta').addEventListener('submit', function(e) {
  const campos = document.getElementById('form-envio-campos');
  if (campos) {
      const inputs = campos.querySelectorAll('input, select');
      inputs.forEach(i => i.removeAttribute('disabled'));
  }
});

document.addEventListener('DOMContentLoaded', () => {
  addItem();
  setMetodo('retiro'); 
});
</script>
{% endblock %}
'''

def patch_run_bat():
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; import app152; import app155; import app156; import app157; import app158; import app159; import app160; import app163; import app165; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat)
    print("[upgrade165] run.bat actualizado")

def main():
    print("=== Upgrade 165: Metodos de envio y formato de moneda ===")
    escribir('app165.py', APP165_PY)
    escribir('templates/ventas/form.html', VENTAS_FORM)
    patch_run_bat()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()