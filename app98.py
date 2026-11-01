
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

app.view_functions['b2b_envios'] = b2b_envios_v2


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
            
    if subtotal >= 300000:
        return {
            'peso_total': round(peso_total_kg, 1),
            'bultos': 0,
            'costo_envio': 0,
            'requiere_cotizacion': True,
            'mensaje_extra': "Tu pedido supera los $300.000. El envío se realiza por palet (logística especial). Generá tu orden y a la brevedad te enviaremos la cotización del flete para que puedas completar el pago."
        }

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

import app95
app95.calcular_envio_carrito = calcular_envio_carrito

if __name__ == '__main__':
    pass
