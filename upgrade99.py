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
    print(f"[upgrade99] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade99] sin DB."); return
    conn = sqlite3.connect(db)

    # 1. Crear la tabla
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalas_envio_b2b (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peso_desde REAL NOT NULL,
            peso_hasta REAL NOT NULL,
            precio REAL NOT NULL,
            activo INTEGER DEFAULT 1,
            tipo_destino TEXT DEFAULT 'sucursal'
        )
    """)
    print("[upgrade99] tabla escalas_envio_b2b asegurada")

    # 2. Agregar costo_envio a ordenes_venta
    cols_o = [r[1] for r in conn.execute("PRAGMA table_info(ordenes_venta)").fetchall()]
    if 'costo_envio' not in cols_o:
        conn.execute("ALTER TABLE ordenes_venta ADD COLUMN costo_envio REAL DEFAULT 0")
        print("[upgrade99] + ordenes_venta.costo_envio")

    conn.commit(); conn.close()


APP95_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import admin_required
from database import get_db
from app4 import enviar_email, get_config
from app39 import _enviar_con_remitente

# ===== GESTION DE ESCALAS DE ENVIO =====
@app.route('/b2b/envios', methods=['GET', 'POST'])
@login_required
@admin_required
def b2b_envios():
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

@app.route('/b2b/envios/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def b2b_envios_eliminar(id):
    conn = get_db()
    conn.execute("DELETE FROM escalas_envio_b2b WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Escala eliminada.', 'success')
    return redirect(url_for('b2b_envios'))


# ===== CALCULO DE ENVIO Y BULTOS =====
def calcular_envio_carrito(conn, carrito_data, subtotal=0, destino_tipo='sucursal'):
    peso_total_kg = 0.0
    for pid_str, item in carrito_data.items():
        pid = int(pid_str)
        prod = conn.execute("SELECT peso_valor, peso_unidad FROM productos WHERE id=?", (pid,)).fetchone()
        if prod and prod['peso_valor']:
            pv = prod['peso_valor']
            if prod['peso_unidad'] == 'g':
                pv = pv / 1000.0
            peso_total_kg += (pv * item.get('cantidad', 0))
            
    bultos = 0
    if peso_total_kg > 0:
        bultos = int(peso_total_kg // 20)
        if peso_total_kg % 20 > 0:
            bultos += 1
            
    # Regla de PALET (>$300.000)
    if subtotal >= 300000:
        return {
            'peso_total': round(peso_total_kg, 1),
            'bultos': 0,
            'costo_envio': 0,
            'requiere_cotizacion': True,
            'mensaje_extra': "Tu pedido supera los $300.000. El envío se realiza por palet (logística especial). Generá tu orden y a la brevedad te enviaremos la cotización del flete para que puedas completar el pago."
        }

    # Regla normal por escala
    escala = conn.execute("""
        SELECT * FROM escalas_envio_b2b 
        WHERE peso_desde <= ? AND peso_hasta >= ? AND tipo_destino = ? AND activo=1
        LIMIT 1
    """, (peso_total_kg, peso_total_kg, destino_tipo)).fetchone()
    
    costo_envio = escala['precio'] if escala else 0.0
    
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


# ===== COTIZAR ENVIO (ADMIN) =====
@app.route('/ventas/<int:id>/cotizar-envio', methods=['POST'])
@login_required
@admin_required
def ventas_cotizar_envio(id):
    try:
        costo = float(request.form.get('costo_envio', 0))
    except ValueError:
        flash('Costo de envío inválido.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error')
        return redirect(url_for('ventas_lista'))

    nuevo_total = orden['subtotal'] - (orden['descuento'] or 0) + costo

    conn.execute("UPDATE ordenes_venta SET costo_envio=?, total=? WHERE id=?", (costo, nuevo_total, id))
    conn.commit()

    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
    conn.close()

    if cliente and cliente['email']:
        try:
            cuerpo = f"""Hola {cliente['nombre_completo']},

Te enviamos la cotización del envío por palet para tu pedido {orden['numero_interno']}.

Costo de envío: ${costo:.2f}
Nuevo total a pagar: ${nuevo_total:.2f}

Ya podés ingresar al catálogo y subir el comprobante de pago con el nuevo monto.

{get_config('firma_email')}"""
            _enviar_con_remitente(cliente['email'], f'Cotización de envío - Pedido {orden["numero_interno"]}', cuerpo, None)
        except Exception as e:
            print(f"[cotizar envio] error email: {e}")

    flash(f'Envío cotizado por ${costo:.2f}. Total actualizado a ${nuevo_total:.2f}.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


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

    viejo_carrito = "info_envio = calcular_envio_carrito(conn, carrito_data, subtotal)"
    nuevo_carrito = "info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, 'sucursal')"
    contenido = contenido.replace(viejo_carrito, nuevo_carrito)

    viejo_checkout = "info_envio = calcular_envio_carrito(conn, carrito_data, subtotal)"
    nuevo_checkout = """        destino_calc = request.form.get('destino_tipo') or request.args.get('destino') or 'sucursal'
        info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, destino_calc)"""
    
    if 'if request.method == \'POST\':' in contenido:
        contenido = contenido.replace(viejo_checkout, nuevo_checkout, 1)
    else:
        contenido = contenido.replace(viejo_checkout, "info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, 'sucursal')", 1)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade99] app53.py actualizado para usar el destino en el cálculo")


def patch_checkout_html():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'checkout.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    buscar = '''<script>
function updateCheckoutForm() {
  const tipo = document.querySelector('input[name="tipo_envio"]:checked')?.value || '';
  const destino = document.querySelector('input[name="destino_tipo"]:checked')?.value || '';'''

    nuevo = '''<script>
function updateCheckoutForm() {
  const tipo = document.querySelector('input[name="tipo_envio"]:checked')?.value || '';
  const destino = document.querySelector('input[name="destino_tipo"]:checked')?.value || '';
  
  if (tipo === 'transporte' && destino && destino !== '{{ request.args.get("destino") }}') {
      window.location.href = "?destino=" + destino;
      return;
  }
'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade99] checkout.html actualizado para recargar al cambiar de destino")


def patch_detalle_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'ventas_cotizar_envio' in contenido:
        return

    buscar = '<div class="card shadow-sm mb-3" style="border-left:4px solid #3b5bdb;">\n<div class="card-body">\n<div class="d-flex justify-content-between align-items-center mb-3">\n<h6 class="mb-0"><i class="bi bi-truck"></i> Datos de envio</h6>'

    nuevo = '''{% if orden.origen == 'catalogo' and orden.estado == 'pendiente_pago' and not orden.costo_envio %}
<div class="alert alert-warning d-flex align-items-center mb-3">
<div class="fs-3 me-3"><i class="bi bi-box-seam"></i></div>
<div class="flex-grow-1">
<h6 class="alert-heading mb-1">Falta cotizar el envío (Palet)</h6>
<p class="mb-2 small">Este pedido del catálogo B2B supera los $300.000. El cliente está esperando que le cotices el costo de envío para poder pagar.</p>
<form method="post" action="{{ url_for('ventas_cotizar_envio', id=orden.id) }}" class="d-flex gap-2">
<div class="input-group" style="max-width:300px;">
<span class="input-group-text">$</span>
<input type="number" step="0.01" name="costo_envio" class="form-control" required placeholder="Costo de envío">
<button class="btn btn-dark">Cotizar y Notificar</button>
</div>
</form>
</div>
</div>
{% endif %}

''' + buscar

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade99] Alerta de cotización agregada al detalle de la orden")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 99: Consolidación de Envíos y Palet ===")
    migrar()
    escribir('app95.py', APP95_PY)
    escribir('templates/b2b/envios.html', ENVIOS_HTML)
    patch_carrito()
    patch_checkout_html()
    patch_detalle_html()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")

if __name__ == '__main__':
    main()