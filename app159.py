
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
