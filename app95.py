
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
        WHERE peso_desde <= ? AND peso_hasta >= ? AND (tipo_destino = ? OR tipo_destino = 'ambos') AND activo=1
        LIMIT 1
    """, (peso_total_kg, peso_total_kg, destino_tipo)).fetchone()
    
    costo_envio = escala['precio'] if escala else 0.0
    
    if not escala and peso_total_kg > 0:
        escala = conn.execute("SELECT * FROM escalas_envio_b2b WHERE (tipo_destino = ? OR tipo_destino = 'ambos') AND activo=1 ORDER BY peso_hasta DESC LIMIT 1", (destino_tipo,)).fetchone()
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
