# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade97] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade97] sin DB."); return
    conn = sqlite3.connect(db)

    # Agregar columna tipo_destino a la tabla de escalas
    cols = [r[1] for r in conn.execute("PRAGMA table_info(escalas_envio_b2b)").fetchall()]
    if 'tipo_destino' not in cols:
        conn.execute("ALTER TABLE escalas_envio_b2b ADD COLUMN tipo_destino TEXT DEFAULT 'sucursal'")
        print("[upgrade97] + escalas_envio_b2b.tipo_destino")
        
        # Actualizar los registros existentes
        conn.execute("UPDATE escalas_envio_b2b SET tipo_destino='sucursal'")
        
    conn.commit(); conn.close()


APP97_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app95 import app
from app import admin_required
from database import get_db

@app.route('/b2b/envios', methods=['GET', 'POST'])
@login_required
@admin_required
def b2b_envios_v2():
    conn = get_db()
    if request.method == 'POST':
        try:
            peso_desde = float(request.form['peso_desde'])
            peso_hasta = float(request.form['peso_hasta'])
            precio = float(request.form['precio'])
            tipo_destino = request.form.get('tipo_destino', 'sucursal')
        except ValueError:
            flash('Los valores deben ser numéricos.', 'error')
            return redirect(url_for('b2b_envios'))
            
        if peso_desde >= peso_hasta:
            flash('El peso "desde" debe ser menor que el "hasta".', 'error')
            return redirect(url_for('b2b_envios'))
            
        conn.execute("""INSERT INTO escalas_envio_b2b 
            (peso_desde, peso_hasta, precio, tipo_destino) 
            VALUES (?, ?, ?, ?)""",
            (peso_desde, peso_hasta, precio, tipo_destino))
        conn.commit()
        flash('Escala de envío agregada.', 'success')
        return redirect(url_for('b2b_envios'))

    escalas = conn.execute("SELECT * FROM escalas_envio_b2b ORDER BY peso_desde ASC").fetchall()
    conn.close()
    return render_template('b2b/envios.html', escalas=escalas)

# Reemplazar la función original
app.view_functions['b2b_envios'] = b2b_envios_v2


def calcular_envio_carrito(conn, carrito_data, subtotal=0, destino_tipo='sucursal'):
    """Calcula el peso total en kg y busca el precio según el rango y el destino."""
    peso_total_kg = 0.0
    for pid_str, item in carrito_data.items():
        pid = int(pid_str)
        prod = conn.execute("SELECT peso_valor, peso_unidad FROM productos WHERE id=?", (pid,)).fetchone()
        if prod and prod['peso_valor']:
            pv = prod['peso_valor']
            if prod['peso_unidad'] == 'g':
                pv = pv / 1000.0
            peso_total_kg += (pv * item.get('cantidad', 0))
            
    # Bultos estimados (20kg por bulto) solo para mostrar
    bultos = 0
    if peso_total_kg > 0:
        bultos = int(peso_total_kg // 20)
        if peso_total_kg % 20 > 0:
            bultos += 1
            
    # Si el pedido supera los 300k, es PALET
    if subtotal >= 300000:
        return {
            'peso_total': round(peso_total_kg, 1),
            'bultos': 0,
            'costo_envio': 0,
            'requiere_cotizacion': True,
            'mensaje_extra': "Tu pedido supera los $300.000. El envío se realiza por palet (logística especial). Generá tu orden y a la brevedad te enviaremos la cotización del flete para que puedas completar el pago."
        }

    # Buscar el costo según la escala y el tipo de destino
    escala = conn.execute("""
        SELECT * FROM escalas_envio_b2b 
        WHERE peso_desde <= ? AND peso_hasta >= ? AND tipo_destino = ? AND activo=1
        LIMIT 1
    """, (peso_total_kg, peso_total_kg, destino_tipo)).fetchone()
    
    costo_envio = escala['precio'] if escala else 0.0
    
    # Si no hay escala que coincida exacta, buscar la más cercana
    if not escala and peso_total_kg > 0:
        escala = conn.execute("SELECT * FROM escalas_envio_b2b WHERE tipo_destino = ? AND activo=1 ORDER BY peso_hasta DESC LIMIT 1", (destino_tipo,)).fetchone()
        if escala:
            costo_envio = escala['precio']

    mensaje_extra = None
    if escala and peso_total_kg < escala['peso_hasta']:
        falta = escala['peso_hasta'] - peso_total_kg
        if falta > 0:
            mensaje_extra = f"Estás a {falta:.1f}kg de completar el rango de {escala['peso_hasta']}kg. ¡Podés agregar más productos por el mismo costo de envío!"

    return {
        'peso_total': round(peso_total_kg, 1),
        'bultos': bultos,
        'costo_envio': costo_envio,
        'requiere_cotizacion': False,
        'mensaje_extra': mensaje_extra
    }

# Sobrescribir la función en app95
import app95
app95.calcular_envio_carrito = calcular_envio_carrito

if __name__ == '__main__':
    pass
'''


ENVIOS_HTML = r'''{% extends "base.html" %}
{% block title %}Escala de Envíos B2B{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Escala de Envíos</h4>
<div class="text-muted small">Configurá los costos de envío manualmente según el peso y el destino.</div>
</div>
<a href="{{ url_for('b2b_index', tab='cuentas') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver a B2B</a>
</div>

<div class="row g-3">
<div class="col-md-4">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-plus-circle"></i> Nueva escala</h6>
<form method="post">
<div class="row g-2 mb-2">
<div class="col-md-6">
<label class="form-label small">Peso Desde (kg)</label>
<input type="number" step="1" name="peso_desde" class="form-control" required placeholder="20">
</div>
<div class="col-md-6">
<label class="form-label small">Peso Hasta (kg)</label>
<input type="number" step="1" name="peso_hasta" class="form-control" required placeholder="30">
</div>
</div>
<div class="mb-2">
<label class="form-label small">Tipo de Destino</label>
<select name="tipo_destino" class="form-select" required>
<option value="sucursal">Sucursal (Retiro en agencia)</option>
<option value="domicilio">Domicilio (Envío a casa)</option>
</select>
</div>
<div class="mb-3">
<label class="form-label small">Precio del Envío ($)</label>
<input type="number" step="0.01" name="precio" class="form-control" required placeholder="36000">
</div>
<button class="btn btn-dark w-100">Agregar Escala</button>
</form>
</div></div>
</div>

<div class="col-md-8">
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light">
<tr>
<th>Rango de Peso</th>
<th>Destino</th>
<th class="text-end">Costo de Envío</th>
<th class="text-end">Acciones</th>
</tr>
</thead>
<tbody>
{% for e in escalas %}
<tr>
<td class="fw-semibold">{{ '%g'|format(e.peso_desde) }}kg a {{ '%g'|format(e.peso_hasta) }}kg</td>
<td>
{% if e.tipo_destino == 'domicilio' %}
<span class="badge bg-primary">Domicilio</span>
{% else %}
<span class="badge bg-secondary">Sucursal</span>
{% endif %}
</td>
<td class="text-end fw-bold text-success">${{ '%.2f'|format(e.precio) }}</td>
<td class="text-end">
<form method="post" action="{{ url_for('b2b_envios_eliminar', id=e.id) }}" class="d-inline" onsubmit="return confirm('Eliminar esta escala?')">
<button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button>
</form>
</td>
</tr>
{% else %}
<tr><td colspan="4" class="text-center text-muted py-4">No hay escalas cargadas.</td></tr>
{% endfor %}
</tbody></table></div></div>
</div>
</div>
{% endblock %}
'''

def patch_carrito():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Modificar la ruta del carrito (usa sucursal por defecto porque todavía no eligió)
    viejo_carrito = "info_envio = calcular_envio_carrito(conn, carrito_data, subtotal)"
    nuevo_carrito = "info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, 'sucursal')"
    contenido = contenido.replace(viejo_carrito, nuevo_carrito)

    # 2. Modificar la ruta del checkout para usar el destino seleccionado
    viejo_checkout = "info_envio = calcular_envio_carrito(conn, carrito_data, subtotal)"
    nuevo_checkout = """        destino_calc = request.form.get('destino_tipo') or request.args.get('destino') or 'sucursal'
        info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, destino_calc)"""
    
    # En el GET inicial, el destino por defecto será sucursal
    if 'if request.method == \'POST\':' in contenido:
        # Buscamos el bloque del POST del checkout
        contenido = contenido.replace(viejo_checkout, nuevo_checkout, 1)
    else:
        contenido = contenido.replace(viejo_checkout, "info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, 'sucursal')", 1)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade97] app53.py actualizado para usar el destino en el cálculo")


def patch_checkout_html():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'checkout.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Si el usuario cambia de Domicilio a Sucursal, que se recargue para recalcular el envío
    buscar = '''<script>
function updateCheckoutForm() {
  const tipo = document.querySelector('input[name="tipo_envio"]:checked')?.value || '';
  const destino = document.querySelector('input[name="destino_tipo"]:checked')?.value || '';'''

    nuevo = '''<script>
function updateCheckoutForm() {
  const tipo = document.querySelector('input[name="tipo_envio"]:checked')?.value || '';
  const destino = document.querySelector('input[name="destino_tipo"]:checked')?.value || '';
  
  // Si es transporte y cambia el destino (domicilio/sucursal), recargamos para calcular el envío
  if (tipo === 'transporte' && destino && destino !== '{{ request.args.get("destino") }}') {
      window.location.href = "?destino=" + destino;
      return;
  }
'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade97] checkout.html actualizado para recargar al cambiar de destino")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app96; import app97; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 97: Escala de envíos manual (Domicilio/Sucursal) ===")
    migrar()
    escribir('app97.py', APP97_PY)
    escribir('templates/b2b/envios.html', ENVIOS_HTML)
    patch_carrito()
    patch_checkout_html()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")

if __name__ == '__main__':
    main()