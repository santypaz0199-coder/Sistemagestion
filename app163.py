
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
