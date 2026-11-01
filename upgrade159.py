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
    print(f"[upgrade159] escrito: {relpath}")

def migrar_db():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db): return
    conn = sqlite3.connect(db)
    
    # 1. Agregar columnas a transportistas
    cols = [r[1] for r in conn.execute("PRAGMA table_info(transportistas)").fetchall()]
    if 'tipo_tarifa' not in cols:
        conn.execute("ALTER TABLE transportistas ADD COLUMN tipo_tarifa TEXT DEFAULT 'manual'")
        print("[upgrade159] + transportistas.tipo_tarifa")
    if 'precio_manual' not in cols:
        conn.execute("ALTER TABLE transportistas ADD COLUMN precio_manual REAL DEFAULT 0")
        print("[upgrade159] + transportistas.precio_manual")

    # 2. Crear tabla de tarifas por escala
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tarifas_transporte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transportista_id INTEGER NOT NULL,
            peso_desde REAL NOT NULL,
            peso_hasta REAL NOT NULL,
            precio_domicilio REAL DEFAULT 0,
            precio_sucursal REAL DEFAULT 0,
            FOREIGN KEY (transportista_id) REFERENCES transportistas(id) ON DELETE CASCADE
        )
    """)
    print("[upgrade159] tabla tarifas_transporte OK")
    
    # 3. Migrar las escalas viejas (escalas_envio_b2b) a la nueva tabla
    try:
        viejas = conn.execute("SELECT * FROM escalas_envio_b2b").fetchall()
        if viejas:
            # Crear un transportista virtual para las viejas reglas o asignarlo al primero
            t_id = conn.execute("SELECT id FROM transportistas LIMIT 1").fetchone()
            if not t_id:
                conn.execute("INSERT INTO transportistas (nombre, tipo_tarifa) VALUES ('Transporte General', 'escala')")
                t_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            else:
                t_id = t_id[0]
                conn.execute("UPDATE transportistas SET tipo_tarifa='escala' WHERE id=?", (t_id,))
            
            for v in viejas:
                p_dom = v['precio']
                p_suc = v['precio']
                if v['tipo_destino'] == 'sucursal': p_suc = v['precio']; p_dom = 0
                elif v['tipo_destino'] == 'domicilio': p_dom = v['precio']; p_suc = 0
                
                conn.execute("""INSERT INTO tarifas_transporte 
                    (transportista_id, peso_desde, peso_hasta, precio_domicilio, precio_sucursal) 
                    VALUES (?, ?, ?, ?, ?)""", (t_id, v['peso_desde'], v['peso_hasta'], p_dom, p_suc))
            print("[upgrade159] Escalas viejas migradas a tarifas_transporte")
    except Exception as e:
        print(f"[upgrade159] No se pudieron migrar escalas viejas: {e}")

    conn.commit(); conn.close()

APP159_PY = r'''
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app48 import app
from app import admin_required
from database import get_db

# ===== CONFIGURACION: MEDIOS DE ENVIO =====
@app.route('/configuracion/medios-envio')
@login_required
@admin_required
def configuracion_medios_envio():
    conn = get_db()
    transportistas = conn.execute("""
        SELECT t.*, 
        (SELECT COUNT(*) FROM ordenes_venta WHERE transportista_id = t.id) as total_envios
        FROM transportistas t ORDER BY t.activo DESC, t.nombre
    """).fetchall()
    
    # Cargar las tarifas de cada transportista
    tarifas = {}
    for t in transportistas:
        tarifas[t['id']] = conn.execute("SELECT * FROM tarifas_transporte WHERE transportista_id=? ORDER BY peso_desde ASC", (t['id'],)).fetchall()
        
    conn.close()
    return render_template('configuracion/medios_envio.html', transportistas=transportistas, tarifas=tarifas)


@app.route('/configuracion/medios-envio/nuevo', methods=['POST'])
@login_required
@admin_required
def medios_envio_nuevo():
    nombre = request.form.get('nombre', '').strip()
    tipo = request.form.get('tipo_tarifa', 'manual')
    try:
        precio_manual = float(request.form.get('precio_manual', 0))
    except ValueError:
        precio_manual = 0
        
    if not nombre:
        flash('Nombre obligatorio.', 'error'); return redirect(url_for('configuracion_medios_envio'))
        
    conn = get_db()
    conn.execute("INSERT INTO transportistas (nombre, tipo_tarifa, precio_manual, activo) VALUES (?, ?, ?, 1)",
                 (nombre, tipo, precio_manual))
    conn.commit(); conn.close()
    flash('Medio de envío creado.', 'success')
    return redirect(url_for('configuracion_medios_envio'))


@app.route('/configuracion/medios-envio/<int:id>/tarifa', methods=['POST'])
@login_required
@admin_required
def medios_envio_agregar_tarifa(id):
    try:
        peso_desde = float(request.form['peso_desde'])
        peso_hasta = float(request.form['peso_hasta'])
        p_dom = float(request.form.get('precio_domicilio') or 0)
        p_suc = float(request.form.get('precio_sucursal') or 0)
    except ValueError:
        flash('Valores inválidos.', 'error'); return redirect(url_for('configuracion_medios_envio'))

    conn = get_db()
    conn.execute("""INSERT INTO tarifas_transporte 
        (transportista_id, peso_desde, peso_hasta, precio_domicilio, precio_sucursal) 
        VALUES (?, ?, ?, ?, ?)""", (id, peso_desde, peso_hasta, p_dom, p_suc))
    conn.execute("UPDATE transportistas SET tipo_tarifa='escala' WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Tarifa agregada.', 'success')
    return redirect(url_for('configuracion_medios_envio'))


@app.route('/configuracion/medios-envio/tarifa/<int:tid>/eliminar', methods=['POST'])
@login_required
@admin_required
def medios_envio_eliminar_tarifa(tid):
    conn = get_db()
    conn.execute("DELETE FROM tarifas_transporte WHERE id=?", (tid,))
    conn.commit(); conn.close()
    return redirect(url_for('configuracion_medios_envio'))


@app.route('/configuracion/medios-envio/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def medios_envio_eliminar(id):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE transportista_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE transportistas SET activo=0 WHERE id=?", (id,))
        flash('Transporte desactivado (tiene envíos asociados).', 'success')
    else:
        conn.execute("DELETE FROM transportistas WHERE id=?", (id,))
        flash('Transporte eliminado.', 'success')
    conn.commit(); conn.close()
    return redirect(url_for('configuracion_medios_envio'))


# ===== API PARA CALCULAR PRECIO DE ENVIO =====
@app.route('/api/calcular-envio')
@login_required
def api_calcular_envio():
    t_id = request.args.get('transportista_id', type=int)
    peso = request.args.get('peso', type=float, default=0)
    destino = request.args.get('destino', 'sucursal') # 'domicilio' o 'sucursal'

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
        # Buscar en la escala
        tarifa = conn.execute("""
            SELECT * FROM tarifas_transporte 
            WHERE transportista_id=? AND peso_desde <= ? AND peso_hasta >= ?
            LIMIT 1
        """, (t_id, peso, peso)).fetchone()
        
        if tarifa:
            if destino == 'domicilio':
                precio = tarifa['precio_domicilio']
            else:
                precio = tarifa['precio_sucursal']
        else:
            # Si se pasa del peso maximo, agarramos la tarifa mas alta
            tarifa_max = conn.execute("SELECT * FROM tarifas_transporte WHERE transportista_id=? ORDER BY peso_hasta DESC LIMIT 1", (t_id,)).fetchone()
            if tarifa_max:
                if destino == 'domicilio': precio = tarifa_max['precio_domicilio']
                else: precio = tarifa_max['precio_sucursal']

    conn.close()
    return jsonify({'ok': True, 'precio': precio})
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
<div class="col-md-4">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-plus-circle"></i> Nuevo Transporte</h6>
<form method="post" action="{{ url_for('medios_envio_nuevo') }}">
<div class="mb-2">
<label class="form-label small">Nombre *</label>
<input name="nombre" class="form-control" required placeholder="Ej: Vía Cargo">
</div>
<div class="mb-2">
<label class="form-label small">Tipo de Tarifa</label>
<select name="tipo_tarifa" class="form-select">
<option value="manual">Precio Manual (por orden)</option>
<option value="escala">Escala por Kilos</option>
</select>
</div>
<div class="mb-3">
<label class="form-label small">Precio Manual ($)</label>
<input type="number" step="0.01" name="precio_manual" class="form-control" placeholder="0.00">
<div class="form-text">Solo se usa si elegís "Precio Manual".</div>
</div>
<button class="btn btn-dark w-100">Crear Transporte</button>
</form>
</div></div>
</div>

<div class="col-md-8">
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
<table class="table table-sm mb-3">
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
{% else %}
<tr><td colspan="4" class="text-center text-muted small">No hay tarifas cargadas.</td></tr>
{% endfor %}
</tbody>
</table>

<form method="post" action="{{ url_for('medios_envio_agregar_tarifa', id=t.id) }}" class="bg-light p-2 rounded border">
<div class="row g-2 align-items-end">
<div class="col-md-2"><label class="form-label small mb-0">Desde (kg)</label><input type="number" step="0.1" name="peso_desde" class="form-control form-control-sm" required></div>
<div class="col-md-2"><label class="form-label small mb-0">Hasta (kg)</label><input type="number" step="0.1" name="peso_hasta" class="form-control form-control-sm" required></div>
<div class="col-md-2"><label class="form-label small mb-0">$ Domicilio</label><input type="number" step="0.01" name="precio_domicilio" class="form-control form-control-sm" value="0"></div>
<div class="col-md-2"><label class="form-label small mb-0">$ Sucursal</label><input type="number" step="0.01" name="precio_sucursal" class="form-control form-control-sm" value="0"></div>
<div class="col-md-2"><button class="btn btn-sm btn-dark w-100">Añadir</button></div>
</div>
</form>
{% endif %}
</div>
</div>
{% endfor %}
</div>
</div>
{% endblock %}
'''

def patch_menu():
    ruta = os.path.join(BASE, 'templates', 'configuracion', 'index.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    if 'configuracion_medios_envio' not in contenido:
        buscar = '<div class="col-md-4"><a href="{{ url_for(\'configuracion_datos_pago\') }}"'
        nuevo = '''<div class="col-md-4"><a href="{{ url_for('configuracion_medios_envio') }}" class="text-decoration-none"><div class="card shadow-sm h-100" style="border-left:3px solid #f59e0b;"><div class="card-body">
<i class="bi bi-truck fs-2 text-warning"></i>
<h6 class="mt-2">Medios de Envío</h6>
<p class="text-muted small mb-0">Transportistas y tarifas por kilo o manuales.</p>
</div></div></a></div>
''' + buscar
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade159] Tarjeta 'Medios de Envío' agregada a Configuración")

def patch_app95():
    """Actualiza la lógica del catalogo B2B para usar las nuevas tarifas de transporte."""
    ruta = os.path.join(BASE, 'app95.py')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    buscar_funcion = "def calcular_envio_carrito(conn, carrito_data, subtotal=0, destino_tipo='sucursal'):"
    if buscar_funcion not in contenido: return

    # Reemplazar la funcion completa
    import re
    patron = re.compile(r"def calcular_envio_carrito\(conn, carrito_data, subtotal=0, destino_tipo='sucursal'\):.*?(?=#|\Z)", re.DOTALL)
    
    nueva_funcion = '''def calcular_envio_carrito(conn, carrito_data, subtotal=0, destino_tipo='sucursal'):
    peso_total_kg = 0.0
    for pid_str, item in carrito_data.items():
        pid = int(pid_str)
        prod = conn.execute("SELECT peso_valor, peso_unidad FROM productos WHERE id=?", (pid,)).fetchone()
        if prod and prod['peso_valor']:
            pv = prod['peso_valor']
            if prod['peso_unidad'] == 'g': pv = pv / 1000.0
            peso_total_kg += (pv * item.get('cantidad', 0))
            
    bultos = 0
    if peso_total_kg > 0:
        bultos = int(peso_total_kg // 20)
        if peso_total_kg % 20 > 0: bultos += 1
            
    # Regla de PALET (>$300.000)
    if subtotal >= 300000:
        return {
            'peso_total': round(peso_total_kg, 1),
            'bultos': 0, 'costo_envio': 0, 'requiere_cotizacion': True,
            'mensaje_extra': "Tu pedido supera los $300.000. El envío se realiza por palet (logística especial). Generá tu orden y a la brevedad te enviaremos la cotización del flete para que puedas completar el pago."
        }

    # Buscar el transportista activo
    t = conn.execute("SELECT * FROM transportistas WHERE activo=1 LIMIT 1").fetchone()
    costo_envio = 0.0
    mensaje_extra = None
    
    if t:
        if t['tipo_tarifa'] == 'manual':
            costo_envio = t['precio_manual']
        else:
            tarifa = conn.execute("""
                SELECT * FROM tarifas_transporte 
                WHERE transportista_id=? AND peso_desde <= ? AND peso_hasta >= ?
                LIMIT 1
            """, (t['id'], peso_total_kg, peso_total_kg)).fetchone()
            
            if tarifa:
                if destino_tipo == 'domicilio': costo_envio = tarifa['precio_domicilio']
                else: costo_envio = tarifa['precio_sucursal']
                
                # Mensaje para llegar al tope
                if peso_total_kg < tarifa['peso_hasta']:
                    falta = tarifa['peso_hasta'] - peso_total_kg
                    if falta > 0:
                        mensaje_extra = f"Estás a {falta:.1f}kg de completar el rango de {tarifa['peso_hasta']}kg. ¡Podés agregar más productos por el mismo valor de envío!"
            else:
                tarifa_max = conn.execute("SELECT * FROM tarifas_transporte WHERE transportista_id=? ORDER BY peso_hasta DESC LIMIT 1", (t['id'],)).fetchone()
                if tarifa_max:
                    if destino_tipo == 'domicilio': costo_envio = tarifa_max['precio_domicilio']
                    else: costo_envio = tarifa_max['precio_sucursal']

    return {
        'peso_total': round(peso_total_kg, 1),
        'bultos': bultos,
        'costo_envio': costo_envio,
        'requiere_cotizacion': False,
        'mensaje_extra': mensaje_extra
    }
'''
    contenido, n = patron.subn(nueva_funcion, contenido)
    if n > 0:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade159] Lógica de envío actualizada en app95.py")

def patch_run_bat():
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; import app152; import app155; import app156; import app157; import app158; import app159; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat)
    print("[upgrade159] run.bat actualizado")

def main():
    print("=== Upgrade 159: Motor de Medios de Envio ===")
    migrar_db()
    escribir('app159.py', APP159_PY)
    escribir('templates/configuracion/medios_envio.html', CONFIG_MEDIOS_ENVIO)
    patch_menu()
    patch_app95()
    patch_run_bat()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()