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
    print(f"[upgrade163] escrito: {relpath}")

APP163_PY = r'''
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app48 import app
from app import admin_required
from database import get_db

@app.route('/configuracion/medios-envio/nuevo', methods=['POST'])
@login_required
@admin_required
def medios_envio_nuevo_v2():
    nombre = request.form.get('nombre', '').strip()
    tipo = request.form.get('tipo_tarifa', 'manual')
    
    if not nombre:
        flash('El nombre del transporte es obligatorio.', 'error')
        return redirect(url_for('configuracion_medios_envio'))
        
    conn = get_db()
    
    # 1. Crear el transportista
    if tipo == 'manual':
        precio_manual = float(request.form.get('precio_manual', 0))
        cur = conn.execute("INSERT INTO transportistas (nombre, tipo_tarifa, precio_manual, activo) VALUES (?, 'manual', ?, 1)", (nombre, precio_manual))
        t_id = cur.lastrowid
        flash('Transporte con precio manual creado.', 'success')
    else:
        cur = conn.execute("INSERT INTO transportistas (nombre, tipo_tarifa, precio_manual, activo) VALUES (?, 'escala', 0, 1)", (nombre,))
        t_id = cur.lastrowid
        
        # 2. Procesar las escalas
        pesos_desde = request.form.getlist('peso_desde[]')
        pesos_hasta = request.form.getlist('peso_hasta[]')
        precios_dom = request.form.getlist('precio_domicilio[]')
        precios_suc = request.form.getlist('precio_sucursal[]')
        
        # Validar que al menos haya una escala
        if not pesos_desde:
            conn.rollback()
            conn.close()
            flash('Debes agregar al menos una escala de peso.', 'error')
            return redirect(url_for('configuracion_medios_envio'))
            
        for i in range(len(pesos_desde)):
            try:
                p_desde = float(pesos_desde[i])
                p_hasta = float(pesos_hasta[i])
                p_dom = float(precios_dom[i]) if precios_dom[i] else 0
                p_suc = float(precios_suc[i]) if precios_suc[i] else 0
                
                conn.execute("""INSERT INTO tarifas_transporte 
                    (transportista_id, peso_desde, peso_hasta, precio_domicilio, precio_sucursal) 
                    VALUES (?, ?, ?, ?, ?)""", (t_id, p_desde, p_hasta, p_dom, p_suc))
            except ValueError:
                continue
                
        flash('Transporte con escala por kilos creado.', 'success')

    conn.commit(); conn.close()
    return redirect(url_for('configuracion_medios_envio'))

app.view_functions['medios_envio_nuevo'] = medios_envio_nuevo_v2

# API para calcular envio (Actualizada)
@app.route('/api/calcular-envio')
@login_required
def api_calcular_envio_v2():
    t_id = request.args.get('transportista_id', type=int)
    peso = request.args.get('peso', type=float, default=0)
    destino = request.args.get('destino', 'sucursal')

    if not t_id:
        return jsonify({'ok': False, 'precio': 0})

    conn = get_db()
    t = conn.execute("SELECT * FROM transportistas WHERE id=?", (t_id,)).fetchone()
    if not t:
        conn.close(); return jsonify({'ok': False, 'precio': 0})

    precio = 0
    if t['tipo_tarifa'] == 'manual':
        precio = t['precio_manual']
    else:
        tarifa = conn.execute("""
            SELECT * FROM tarifas_transporte 
            WHERE transportista_id=? AND peso_desde <= ? AND peso_hasta >= ?
            LIMIT 1
        """, (t_id, peso, peso)).fetchone()
        
        if tarifa:
            if destino == 'domicilio': precio = tarifa['precio_domicilio']
            else: precio = tarifa['precio_sucursal']
        else:
            tarifa_max = conn.execute("SELECT * FROM tarifas_transporte WHERE transportista_id=? ORDER BY peso_hasta DESC LIMIT 1", (t_id,)).fetchone()
            if tarifa_max:
                if destino == 'domicilio': precio = tarifa_max['precio_domicilio']
                else: precio = tarifa_max['precio_sucursal']

    conn.close()
    return jsonify({'ok': True, 'precio': precio})

app.view_functions['api_calcular_envio'] = api_calcular_envio_v2
'''

CONFIG_MEDIOS_ENVIO = r'''{% extends "base.html" %}
{% block title %}Medios de Envío{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Medios de Envío</h4>
<div class="text-muted small">Configura los precios de envío por transportista (Manual o por Escala de Kilos).</div>
</div>
<a href="{{ url_for('configuracion') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">
<!-- FORMULARIO DE CREACION -->
<div class="col-md-5">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-plus-circle"></i> Nuevo Transporte</h6>
<form method="post" action="{{ url_for('medios_envio_nuevo') }}">
<div class="mb-3">
<label class="form-label small">Nombre del Transportista *</label>
<input name="nombre" class="form-control" required placeholder="Ej: Vía Cargo">
</div>
<div class="mb-3">
<label class="form-label small">Tipo de Tarifa</label>
<select name="tipo_tarifa" id="tipo_tarifa" class="form-select" onchange="toggleTarifa()">
<option value="manual">Precio Manual (ingreso en la orden)</option>
<option value="escala">Escala de Precios por Kilos</option>
</select>
</div>

<!-- BLOQUE MANUAL -->
<div id="bloque-manual">
<div class="alert alert-info py-2 small">En la orden de venta, se te va a pedir que ingreses el precio del envío a mano.</div>
</div>

<!-- BLOQUE ESCALA -->
<div id="bloque-escala" style="display:none;">
<div class="alert alert-primary py-2 small">Añadí los rangos de peso. El sistema calculará el precio en base al peso de los productos.</div>
<div id="contenedor-escalas">
<!-- Fila de escala 0 -->
<div class="row g-2 mb-2 escala-row align-items-end">
<div class="col-6 col-md-3">
<label class="form-label small mb-0">Desde (kg)</label>
<input type="number" step="0.1" name="peso_desde[]" class="form-control form-control-sm" required>
</div>
<div class="col-6 col-md-3">
<label class="form-label small mb-0">Hasta (kg)</label>
<input type="number" step="0.1" name="peso_hasta[]" class="form-control form-control-sm" required>
</div>
<div class="col-12 col-md-6 text-end">
<button type="button" class="btn btn-sm btn-outline-danger mt-2" onclick="this.closest('.escala-row').remove()" style="display:none;">Eliminar</button>
</div>

<!-- Tildes de precios -->
<div class="col-12 mt-2 mb-1">
<div class="form-check form-check-inline">
<input class="form-check-input chk-dom" type="checkbox" onchange="togglePrecio(this, 'dom')" checked>
<label class="form-check-label small">Cobrar a Domicilio</label>
</div>
<div class="form-check form-check-inline">
<input class="form-check-input chk-suc" type="checkbox" onchange="togglePrecio(this, 'suc')" checked>
<label class="form-check-label small">Cobrar a Sucursal</label>
</div>
</div>
<div class="col-6 col-md-6 precio-dom-wrap">
<label class="form-label small mb-0">$ Precio Domicilio</label>
<input type="number" step="0.01" name="precio_domicilio[]" class="form-control form-control-sm" required>
</div>
<div class="col-6 col-md-6 precio-suc-wrap">
<label class="form-label small mb-0">$ Precio Sucursal</label>
<input type="number" step="0.01" name="precio_sucursal[]" class="form-control form-control-sm" required>
</div>
</div>
</div>

<button type="button" class="btn btn-sm btn-outline-secondary mb-3" onclick="addEscala()"><i class="bi bi-plus-lg"></i> Añadir otra escala</button>
</div>

<button class="btn btn-dark w-100 mt-3">Crear Transporte</button>
</form>
</div></div>
</div>

<!-- LISTA DE TRANSPORTES -->
<div class="col-md-7">
{% for t in transportistas %}
<div class="card shadow-sm mb-3 {% if not t.activo %}opacity-50{% endif %}">
<div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0 fw-bold">{{ t.nombre }} 
{% if t.tipo_tarifa == 'manual' %}
<span class="badge bg-primary ms-2">Precio Manual: {{ t.precio_manual|pesos }}</span>
{% else %}
<span class="badge bg-success ms-2">Escala por Kilos</span>
{% endif %}
</h6>
<form method="post" action="{{ url_for('medios_envio_eliminar', id=t.id) }}" class="d-inline" onsubmit="return confirm('Eliminar/Desactivar?')">
<button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button>
</form>
</div>

{% if t.tipo_tarifa == 'escala' %}
<table class="table table-sm mb-0">
<thead class="table-light"><tr><th>Rango de Peso</th><th class="text-end">Domicilio</th><th class="text-end">Sucursal</th><th></th></tr></thead>
<tbody>
{% for tar in tarifas.get(t.id, []) %}
<tr>
<td class="small">{{ '%g'|format(tar.peso_desde) }}kg a {{ '%g'|format(tar.peso_hasta) }}kg</td>
<td class="text-end">{{ tar.precio_domicilio|pesos }}</td>
<td class="text-end">{{ tar.precio_sucursal|pesos }}</td>
<td class="text-end">
<form method="post" action="{{ url_for('medios_envio_eliminar_tarifa', tid=tar.id) }}" class="d-inline"><button class="btn btn-sm text-danger"><i class="bi bi-x"></i></button></form>
</td>
</tr>
{% endfor %}
</tbody>
</table>
{% endif %}
</div>
</div>
{% endfor %}
</div>
</div>

<script>
function toggleTarifa() {
    const tipo = document.getElementById('tipo_tarifa').value;
    if (tipo === 'manual') {
        document.getElementById('bloque-manual').style.display = 'block';
        document.getElementById('bloque-escala').style.display = 'none';
    } else {
        document.getElementById('bloque-manual').style.display = 'none';
        document.getElementById('bloque-escala').style.display = 'block';
    }
}

function togglePrecio(chk, tipo) {
    const row = chk.closest('.escala-row');
    const wrap = row.querySelector(tipo === 'dom' ? '.precio-dom-wrap' : '.precio-suc-wrap');
    const input = wrap.querySelector('input');
    if (chk.checked) {
        wrap.style.display = 'block';
        input.required = true;
    } else {
        wrap.style.display = 'none';
        input.required = false;
        input.value = 0;
    }
}

function addEscala() {
    const contenedor = document.getElementById('contenedor-escalas');
    const primera = contenedor.querySelector('.escala-row');
    const clon = primera.cloneNode(true);
    
    // Limpiar valores
    clon.querySelectorAll('input').forEach(i => i.value = '');
    
    // Mostrar botón de eliminar
    clon.querySelector('button').style.display = 'inline-block';
    
    contenedor.appendChild(clon);
}

document.addEventListener('DOMContentLoaded', toggleTarifa);
</script>
{% endblock %}
'''

def patch_run_bat():
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; import app152; import app155; import app156; import app157; import app158; import app159; import app160; import app163; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat)
    print("[upgrade163] run.bat actualizado")

def main():
    print("=== Upgrade 163: Rediseño de Medios de Envío ===")
    escribir('app163.py', APP163_PY)
    escribir('templates/configuracion/medios_envio.html', CONFIG_MEDIOS_ENVIO)
    patch_run_bat()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()