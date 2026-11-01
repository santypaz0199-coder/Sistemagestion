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
    print(f"[upgrade152] escrito: {relpath}")


APP152_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app148 import app
from app import permiso_required, aplicar_descuento_stock, revertir_stock
from database import get_db
from datetime import date

def _registrar_pago_automatico(conn, orden_id, total, usuario_id):
    """Si no hay pagos registrados, registra un pago por el 100% para cuadrar la caja."""
    pagos_totales = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE orden_id=?", (orden_id,)).fetchone()[0]
    
    if pagos_totales < total:
        falta = total - pagos_totales
        medio = conn.execute("SELECT id FROM medios_pago WHERE lower(nombre)='efectivo' OR lower(nombre)='transferencia' LIMIT 1").fetchone()
        medio_id = medio['id'] if medio else None
        
        conn.execute("""INSERT INTO pagos 
            (orden_id, fecha, medio_pago_id, monto, comision, monto_neto, usuario_id, notas)
            VALUES (?, ?, ?, ?, 0, ?, ?, 'Pago automatico al cambiar estado')""",
            (orden_id, date.today().isoformat(), medio_id, falta, falta, usuario_id))


@app.route('/ventas/<int:id>/estado', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_estado_v4(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
        
    nuevo = request.form['estado']
    actual = orden['estado']
    
    if actual == nuevo:
        conn.close(); flash('La orden ya está en ese estado.', 'info'); return redirect(url_for('ventas_detalle', id=id))

    # Transiciones permitidas (mas flexibles)
    trans = {
        'pendiente_pago': ['pagado_sin_enviar', 'cancelado'],
        'pagado_sin_enviar': ['pagado_enviado', 'cancelado', 'pendiente_pago'],
        'pagado_enviado': ['cancelado', 'pagado_sin_enviar'],
        'cancelado': ['pendiente_pago']
    }
    
    if nuevo not in trans.get(actual, []):
        conn.close(); flash(f'No podes pasar de "{actual}" a "{nuevo}".', 'error'); return redirect(url_for('ventas_detalle', id=id))

    if nuevo == 'cancelado':
        if orden['stock_descontado']:
            revertir_stock(conn, id, current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='cancelado' WHERE id=?", (id,))
        
    elif nuevo == 'pagado_sin_enviar':
        if not orden['stock_descontado']:
            aplicar_descuento_stock(conn, id, current_user.id)
        _registrar_pago_automatico(conn, id, orden['total'], current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
        
    elif nuevo == 'pagado_enviado':
        if not orden['stock_descontado']:
            aplicar_descuento_stock(conn, id, current_user.id)
        _registrar_pago_automatico(conn, id, orden['total'], current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado' WHERE id=?", (id,))
        
    elif nuevo == 'pendiente_pago':
        # Si vuelve a pendiente, borramos los pagos automaticos para que vuelva a figurar la deuda
        if orden['stock_descontado']:
            revertir_stock(conn, id, current_user.id)
        conn.execute("DELETE FROM pagos WHERE orden_id=? AND notas='Pago automatico al cambiar estado'", (id,))
        conn.execute("UPDATE ordenes_venta SET estado='pendiente_pago' WHERE id=?", (id,))

    conn.commit(); conn.close()
    flash(f'Estado actualizado a {nuevo}.', 'success')
    return redirect(url_for('ventas_detalle', id=id))

# Sobrescribir la ruta original
app.view_functions['ventas_estado'] = ventas_estado_v4


# Tambien arreglar la ruta de notificacion por email (app145)
@app.route('/ventas/<int:id>/email/<tipo>', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_email_enviar_v4(id, tipo):
    TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'factura', 'entrega'}
    if tipo not in TIPOS_VALIDOS:
        from flask import abort
        abort(404)
        
    from app4 import _cargar_orden, get_config, construir_contexto, render_plantilla
    from app39 import _enviar_con_remitente, _remitente_por_email
    
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))

    destino = request.form.get('destinatario') or orden['cliente_email']
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
        if tipo == 'pago' and orden['estado'] == 'pendiente_pago':
            if not orden['stock_descontado']:
                aplicar_descuento_stock(conn, id, current_user.id)
            _registrar_pago_automatico(conn, id, orden['total'], current_user.id)
            conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
            flash('Pago notificado y acreditado.', 'success')
            
        elif tipo == 'envio' and orden['estado'] in ('pagado_sin_enviar', 'pendiente_pago'):
            if not orden['stock_descontado']:
                aplicar_descuento_stock(conn, id, current_user.id)
            _registrar_pago_automatico(conn, id, orden['total'], current_user.id)
            conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado' WHERE id=?", (id,))
            flash('Envio notificado y orden despachada.', 'success')
        else:
            flash('Notificación enviada.', 'success')
    else:
        flash(msg, 'error')
        
    conn.commit(); conn.close()
    return redirect(url_for('ventas_detalle', id=id))

app.view_functions['ventas_email_enviar'] = ventas_email_enviar_v4
'''

def patch_run_bat():
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; import app152; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat)
    print("[upgrade152] run.bat actualizado")


def patch_detalle_js():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Arreglar las transiciones del JS para que coincidan con el backend
    buscar_transiciones = """const transiciones = {
  'pendiente_pago': ['pendiente_pago','pagado_sin_enviar','cancelado'],
  'pagado_sin_enviar': ['pagado_sin_enviar','pagado_enviado','cancelado'],
  'pagado_enviado': ['pagado_enviado','cancelado'],
  'cancelado': ['cancelado']
};"""
    nuevo_transiciones = """const transiciones = {
  'pendiente_pago': ['pendiente_pago', 'pagado_sin_enviar', 'cancelado'],
  'pagado_sin_enviar': ['pagado_sin_enviar', 'pagado_enviado', 'cancelado', 'pendiente_pago'],
  'pagado_enviado': ['pagado_enviado', 'cancelado', 'pagado_sin_enviar'],
  'cancelado': ['cancelado', 'pendiente_pago']
};"""
    
    if buscar_transiciones in contenido:
        contenido = contenido.replace(buscar_transiciones, nuevo_transiciones)
        print("[upgrade152] Transiciones de estado (JS) actualizadas.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 152: Fix de pagos automaticos y maquina de estados ===")
    escribir('app152.py', APP152_PY)
    patch_run_bat()
    patch_detalle_js()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()