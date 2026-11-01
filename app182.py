
from flask import render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required
from database import get_db
from datetime import date, datetime, timedelta
import os, uuid
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from jinja2 import Template

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

def enviar_correo_real(conn, destinatario, asunto, cuerpo, adjunto_path=None):
    try:
        conf_rows = conn.execute("SELECT clave, valor FROM configuracion").fetchall()
        config = {r['clave']: r['valor'] for r in conf_rows}
        host = config.get('smtp_host', '')
        port = int(config.get('smtp_puerto', 587))
        seg = config.get('smtp_seguridad', 'tls')
        user = config.get('smtp_usuario', '')
        pwd = config.get('smtp_password', '')
        rem_email = config.get('smtp_remitente_email', '')
        rem_nombre = config.get('smtp_remitente_nombre', '')

        if not host or not user: return False, "Falta configuración SMTP."

        msg = MIMEMultipart()
        msg['From'] = f"{rem_nombre} <{rem_email}>"
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'html'))

        if adjunto_path and os.path.exists(adjunto_path):
            with open(adjunto_path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(adjunto_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(adjunto_path)}"'
            msg.attach(part)

        if seg == 'ssl': server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            if seg == 'tls': server.starttls()

        server.login(user, pwd)
        server.send_message(msg)
        server.quit()
        return True, "OK"
    except Exception as e:
        return False, str(e)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/ventas/<int:id>/remito')
@login_required
def ventas_remito(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    items = conn.execute("SELECT oi.*, p.nombre as producto_nombre FROM orden_items oi JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?", (id,)).fetchall()
    conn.close()
    return render_template('ventas/remito.html', orden=orden, items=items)

# RUTA SEGURA PARA FORZAR EL DESPACHO CON PAGO PARCIAL (No toca app156)
@app.route('/ventas/<int:id>/forzar_despacho', methods=['POST'])
@login_required
def ventas_forzar_despacho(id):
    conn = get_db()
    try:
        pagos = conn.execute("SELECT SUM(monto) as total FROM pagos WHERE orden_id=?", (id,)).fetchone()
        total_pagado = pagos['total'] or 0
        if total_pagado > 0:
            conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado', fecha_envio=? WHERE id=?", (datetime.now().isoformat(), id))
            conn.commit()
            flash('Orden despachada con pago parcial exitosamente.', 'success')
        else:
            flash('No hay pagos registrados para despachar.', 'error')
    finally:
        conn.close()
    return redirect(url_for('ventas_detalle', id=id))

# RUTA SEGURA PARA ENVIAR LA ORDEN CON EL FORMATO QUE PEDISTE
@app.route('/ventas/<int:id>/enviar_orden_correo', methods=['POST'])
@login_required
def ventas_enviar_orden_correo(id):
    conn = get_db()
    try:
        orden = conn.execute("SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id WHERE o.id=?", (id,)).fetchone()
        if not orden or not orden['cliente_email']:
            flash('El cliente no tiene correo.', 'error')
            return redirect(url_for('ventas_detalle', id=id))

        items = conn.execute("SELECT oi.*, p.nombre as producto_nombre FROM orden_items oi JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?", (id,)).fetchall()

        # Armamos el detalle de productos en HTML
        detalle_prods = "<ul>"
        for it in items:
            detalle_prods += f"<li>{it['cantidad']}x {it['producto_nombre']} - ${it['subtotal']:,.2f}</li>"
        detalle_prods += "</ul>"

        # Armamos los datos de envío
        datos_envio = f"<p><strong>Destinatario:</strong> {orden['destinatario_nombre'] or orden['cliente_nombre']}<br>"
        datos_envio += f"<strong>Dirección:</strong> {orden['destinatario_calle'] or 'Retira en depósito'}<br>"
        datos_envio += f"<strong>Localidad:</strong> {orden['destinatario_localidad'] or '-'}</p>"

        notas_terminos = f"<div style='background:#f8f9fa;padding:15px;border-radius:5px;margin-top:20px;'><strong>Términos y Condiciones:</strong><br>{orden['notas'] or 'Sin notas adicionales.'}</div>"

        cuerpo = f"""
        <h2>¡Hola {orden['cliente_nombre']}!</h2>
        <p>Recibimos tu pedido <strong>{orden['numero_interno']}</strong> con fecha {orden['fecha']}.</p>
        <h3>Detalle de tu compra:</h3>
        {detalle_prods}
        <h3>Total: ${orden['total']:,.2f}</h3>
        <h3>Envío:</h3>
        {datos_envio}
        <p style='color:#d9534f;'><strong>IMPORTANTE:</strong> Recordá que tenés 24 horas para realizar el pago. Pasado ese tiempo, el pedido se cancelará automáticamente.</p>
        {notas_terminos}
        <p>¡Gracias por elegirnos!</p>
        """

        asunto = f"Recibimos tu pedido {orden['numero_interno']} - Familia Zaragoza"
        exito, err = enviar_correo_real(conn, orden['cliente_email'], asunto, cuerpo)

        if exito: flash('Correo de orden enviado con éxito.', 'success')
        else: flash(f'Error al enviar correo: {err}', 'error')
    finally:
        conn.close()
    return redirect(url_for('ventas_detalle', id=id))

# RUTA DEL DETALLE
def ventas_detalle_v4(id):
    conn = get_db()
    try:
        if request.method == 'POST':
            accion = request.form.get('accion')

            if accion == 'actualizar_factura':
                requiere_factura = request.form.get('requiere_factura', '0')
                estado_facturacion = request.form.get('estado_facturacion', 'pendiente')
                archivo_factura = None
                if 'archivo_factura' in request.files:
                    file = request.files['archivo_factura']
                    if file and file.filename != '':
                        filename = str(uuid.uuid4()) + "_" + file.filename
                        file.save(os.path.join(UPLOAD_FOLDER, filename))
                        archivo_factura = filename

                if archivo_factura:
                    conn.execute("UPDATE ordenes_venta SET requiere_factura=?, estado_facturacion=?, archivo_factura=? WHERE id=?", (requiere_factura, estado_facturacion, archivo_factura, id))
                else:
                    conn.execute("UPDATE ordenes_venta SET requiere_factura=?, estado_facturacion=? WHERE id=?", (requiere_factura, estado_facturacion, id))
                conn.commit()
                flash('Facturación guardada.', 'success')
                return redirect(url_for('ventas_detalle', id=id))

            elif accion == 'registrar_pago':
                monto = float(request.form.get('monto_pago') or 0)
                medio_id = request.form.get('medio_pago') 
                archivo_comprobante = None
                if 'archivo_comprobante' in request.files:
                    file = request.files['archivo_comprobante']
                    if file and file.filename != '':
                        filename = str(uuid.uuid4()) + "_" + file.filename
                        file.save(os.path.join(UPLOAD_FOLDER, filename))
                        archivo_comprobante = filename
                conn.execute("INSERT INTO pagos (orden_id, fecha, medio_pago_id, monto, monto_neto, usuario_id, notas) VALUES (?, ?, ?, ?, ?, ?, ?)", (id, date.today().isoformat(), medio_id, monto, monto, current_user.id, archivo_comprobante))
                conn.commit()
                flash('Pago registrado.', 'success')
                return redirect(url_for('ventas_detalle', id=id))

            elif accion == 'actualizar_notas':
                notas = request.form.get('notas', '').strip()
                conn.execute("UPDATE ordenes_venta SET notas=? WHERE id=?", (notas, id))
                conn.commit()
                flash('Términos y condiciones guardados.', 'success')
                return redirect(url_for('ventas_detalle', id=id))

            elif accion == 'enviar_factura':
                # (Misma lógica que ya probamos, no la toco)
                orden = conn.execute("SELECT o.*, c.email FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id WHERE o.id=?", (id,)).fetchone()
                if orden and orden['email'] and orden['archivo_factura']:
                    ruta_factura = os.path.join(UPLOAD_FOLDER, orden['archivo_factura'])
                    exito, err = enviar_correo_real(conn, orden['email'], "Factura de tu pedido", "Adjuntamos tu factura.", ruta_factura)
                    if exito: flash('Factura enviada.', 'success')
                    else: flash(f'Error: {err}', 'error')
                return redirect(url_for('ventas_detalle', id=id))

            elif accion == 'notificar_pago':
                orden = conn.execute("SELECT o.*, c.email FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id WHERE o.id=?", (id,)).fetchone()
                if orden and orden['email']:
                    exito, err = enviar_correo_real(conn, orden['email'], "Pago Recibido", "Recibimos tu pago. Gracias.")
                    if exito: flash('Pago notificado.', 'success')
                    else: flash(f'Error: {err}', 'error')
                return redirect(url_for('ventas_detalle', id=id))

        # GET (Cargar pantalla)
        orden = conn.execute("SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email, c.telefono as cliente_telefono, u.nombre as vendedor_nombre, cv.nombre as canal_nombre, t.nombre as transportista_nombre FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id JOIN usuarios u ON u.id=o.usuario_id LEFT JOIN canales_venta cv ON cv.id=o.canal_id LEFT JOIN transportistas t ON t.id=o.transportista_id WHERE o.id=?", (id,)).fetchone()
        if not orden: return redirect(url_for('ventas_lista'))

        items = conn.execute("SELECT oi.*, p.nombre as producto_nombre, p.peso_valor, p.peso_unidad FROM orden_items oi JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?", (id,)).fetchall()
        todos_productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
        pagos = conn.execute("SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id WHERE pg.orden_id=? ORDER BY pg.id", (id,)).fetchall()
        total_pagado = sum(p['monto'] for p in pagos)
        saldo_pendiente = orden['total'] - total_pagado
        kilos_total = sum((it['cantidad'] * (it['peso_valor'] if it['peso_unidad']=='kg' else it['peso_valor']/1000)) for it in items if it['peso_valor'])
        medios = conn.execute("SELECT * FROM medios_pago WHERE activo=1").fetchall()
        transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1").fetchall()

        return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos, total_pagado=total_pagado, saldo_pendiente=saldo_pendiente, kilos_total=kilos_total, todos_productos=todos_productos, medios=medios, transportistas=transportistas)
    finally:
        conn.close()

if 'ventas_detalle_v4_endpoint' not in app.view_functions:
    app.add_url_rule('/ventas/<int:id>', 'ventas_detalle_v4_endpoint', ventas_detalle_v4, methods=['GET', 'POST'])
    app.view_functions['ventas_detalle'] = ventas_detalle_v4
