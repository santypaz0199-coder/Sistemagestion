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
    print(f"[upgrade158] escrito: {relpath}")

APP158_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required, aplicar_descuento_stock, revertir_stock
from database import get_db
from datetime import date
from app4 import _cargar_orden, get_config, construir_contexto, render_plantilla
from app39 import _remitentes_disponibles, _enviar_con_remitente, _remitente_por_email

@app.route('/ventas/<int:id>/email/<tipo>', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_email_enviar_v7(id, tipo):
    TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'factura', 'entrega'}
    if tipo not in TIPOS_VALIDOS:
        from flask import abort
        abort(404)
        
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))

    # ===== MAQUINA DE ESTADOS ESTRICTA =====
    # Regla 1: No notificar pago si no está pendiente de pago.
    if tipo == 'pago' and orden['estado'] != 'pendiente_pago':
        conn.close(); flash('Error: La orden no está pendiente de pago.', 'error'); return redirect(url_for('ventas_detalle', id=id))
        
    # Regla 2: No notificar envío si no está pagada.
    if tipo == 'envio' and orden['estado'] != 'pagado_sin_enviar':
        conn.close(); flash('Error: Primero tenés que acreditar el pago para notificar el envío.', 'error'); return redirect(url_for('ventas_detalle', id=id))
        
    # Regla 3: No notificar entrega si no fue despachada.
    if tipo == 'entrega' and orden['estado'] != 'pagado_enviado':
        conn.close(); flash('Error: No podés notificar una entrega si el pedido aún no fue despachado.', 'error'); return redirect(url_for('ventas_detalle', id=id))

    destino = request.form.get('destinatario') or orden['cliente_email']
    if not destino or '@' not in destino:
        conn.close(); flash('El cliente no tiene email válido.', 'error'); return redirect(url_for('ventas_detalle', id=id))

    remitente_email = request.form.get('remitente_email', '').strip()
    remitente_override = None
    if remitente_email and current_user.es_admin:
        remitente_override = _remitente_por_email(conn, remitente_email)
    elif not current_user.es_admin:
        row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if row and row['email_remitente']:
            remitente_override = {'email': row['email_remitente'], 'nombre': row['nombre_remitente'] or row['nombre']}

    ctx = construir_contexto(orden, conn, tipo)
    asunto = render_plantilla(get_config(f'plantilla_{tipo}_asunto'), ctx)
    cuerpo = render_plantilla(get_config(f'plantilla_{tipo}_cuerpo'), ctx)
    
    ok, msg = _enviar_con_remitente(destino, asunto, cuerpo, remitente_override=remitente_override)
    remitente_usado = remitente_override['email'] if remitente_override else get_config('smtp_remitente_email')
    
    conn.execute("INSERT INTO emails_enviados (destinatario, asunto, tipo, orden_id, estado, remitente) VALUES (?,?,?,?,?,?)",
                 (destino, asunto, tipo, id, 'ok' if ok else 'error', remitente_usado))
    
    if ok:
        if tipo == 'pago':
            if not orden['stock_descontado']: aplicar_descuento_stock(conn, id, current_user.id)
            # Registro de pago automatico para cuadrar caja
            pagos_totales = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE orden_id=?", (id,)).fetchone()[0]
            if pagos_totales < orden['total']:
                falta = orden['total'] - pagos_totales
                medio = conn.execute("SELECT id FROM medios_pago LIMIT 1").fetchone()
                medio_id = medio['id'] if medio else None
                conn.execute("INSERT INTO pagos (orden_id, fecha, medio_pago_id, monto, comision, monto_neto, usuario_id, notas) VALUES (?, ?, ?, ?, 0, ?, ?, 'Pago automatico (cuadre)')",
                             (id, date.today().isoformat(), medio_id, falta, falta, current_user.id))
            conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
            flash('Pago notificado. Orden actualizada a Pagado / Sin enviar.', 'success')
            
        elif tipo == 'envio':
            conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado' WHERE id=?", (id,))
            flash('Envío notificado. Orden actualizada a Pagado / Enviado.', 'success')
            
        elif tipo == 'entrega':
            flash('Entrega notificada con éxito.', 'success')
            
        else:
            flash('Notificación enviada.', 'success')
    else:
        flash(msg, 'error')
        
    conn.commit(); conn.close()
    return redirect(url_for('ventas_detalle', id=id))

app.view_functions['ventas_email_enviar'] = ventas_email_enviar_v7
'''

def patch_detalle_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar el bloque de botones de email y actualizarlo
    buscar = r'''<div class="d-flex flex-wrap gap-2">
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='confirmacion') }}" class="d-inline">
                    <button type="submit" class="btn btn-outline-primary btn-sm">Enviar orden</button>
                </form>
                
                {% if orden.estado == 'pendiente_pago' %}
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='pago') }}" class="d-inline" onsubmit="return confirm('Al notificar el pago, la orden pasará a Pagado/Sin enviar. ¿Continuar?')">
                    <button type="submit" class="btn btn-outline-success btn-sm">Notificar pago</button>
                </form>
                {% endif %}

                {% if orden.estado == 'pagado_sin_enviar' %}
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='envio') }}" class="d-inline" onsubmit="return confirm('Al notificar el envío, la orden pasará a Pagado/Enviado. ¿Continuar?')">
                    <button type="submit" class="btn btn-outline-info btn-sm">Notificar envío</button>
                </form>
                {% endif %}
                
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='factura') }}" class="d-inline">
                    <button type="submit" class="btn btn-outline-dark btn-sm">Enviar factura</button>
                </form>
            </div>'''

    nuevo = r'''<div class="d-flex flex-wrap gap-2">
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='confirmacion') }}" class="d-inline">
                    <button type="submit" class="btn btn-outline-primary btn-sm">Enviar orden</button>
                </form>
                
                {% if orden.estado == 'pendiente_pago' %}
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='pago') }}" class="d-inline" onsubmit="return confirm('Al notificar el pago, la orden pasará a Pagado/Sin enviar. ¿Continuar?')">
                    <button type="submit" class="btn btn-outline-success btn-sm">Notificar pago</button>
                </form>
                {% elif orden.estado == 'pagado_sin_enviar' %}
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='envio') }}" class="d-inline" onsubmit="return confirm('Al notificar el envío, la orden pasará a Pagado/Enviado. ¿Continuar?')">
                    <button type="submit" class="btn btn-outline-info btn-sm">Notificar envío</button>
                </form>
                {% elif orden.estado == 'pagado_enviado' %}
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='entrega') }}" class="d-inline">
                    <button type="submit" class="btn btn-outline-secondary btn-sm">Notificar entrega</button>
                </form>
                {% endif %}
                
                <form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='factura') }}" class="d-inline">
                    <button type="submit" class="btn btn-outline-dark btn-sm">Enviar factura</button>
                </form>
            </div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        print("[upgrade158] Botones de email actualizados con el flujo lógico.")
    else:
        print("[upgrade158] ADVERTENCIA: no se encontró el bloque de botones exacto.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def patch_run_bat():
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; import app152; import app155; import app156; import app157; import app158; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat)
    print("[upgrade158] run.bat actualizado")

def main():
    print("=== Upgrade 158: Flujo lógico de notificaciones ===")
    escribir('app158.py', APP158_PY)
    patch_detalle_html()
    patch_run_bat()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()