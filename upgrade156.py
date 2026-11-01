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
    print(f"[upgrade156] escrito: {relpath}")

def actualizar_plantillas():
    """Actualiza el correo de confirmacion para que avise de las 24hs."""
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db): return
    conn = sqlite3.connect(db)
    
    asunto = "Recibimos tu pedido {{numero_orden}} - Familia Zaragoza"
    cuerpo = """Hola {{cliente_nombre}},

¡Gracias por tu compra! Recibimos tu pedido {{numero_orden}} con fecha {{fecha}}.

Detalle:
{{detalle_productos}}

Total: ${{total}}

{{datos_envio}}

IMPORTANTE: Recordá que tenés 24 horas para realizar el pago. Pasado ese tiempo, el pedido se cancelará automáticamente y te avisaremos 1 hora antes. Esto se debe a la desregulación en el precio de la yerba mate y a los costos logísticos.

Una vez que realices la transferencia, subí el comprobante en el sistema para que podamos despacharlo.

{{firma}}"""

    conn.execute("UPDATE configuracion SET valor=? WHERE clave='plantilla_confirmacion_asunto'", (asunto,))
    conn.execute("UPDATE configuracion SET valor=? WHERE clave='plantilla_confirmacion_cuerpo'", (cuerpo,))
    conn.commit(); conn.close()
    print("[upgrade156] Plantilla de confirmacion actualizada con el aviso de 24hs.")

APP156_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required, aplicar_descuento_stock, revertir_stock
from database import get_db
from datetime import date
from app4 import _cargar_orden, get_config, construir_contexto, render_plantilla
from app39 import _remitentes_disponibles, _enviar_con_remitente, _remitente_por_email

def _registrar_pago_automatico(conn, orden_id, total, usuario_id):
    pagos_totales = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE orden_id=?", (orden_id,)).fetchone()[0]
    if pagos_totales < total:
        falta = total - pagos_totales
        medio = conn.execute("SELECT id FROM medios_pago LIMIT 1").fetchone()
        medio_id = medio['id'] if medio else None
        conn.execute("""INSERT INTO pagos 
            (orden_id, fecha, medio_pago_id, monto, comision, monto_neto, usuario_id, notas)
            VALUES (?, ?, ?, ?, 0, ?, ?, 'Pago automatico (cuadre)')""",
            (orden_id, date.today().isoformat(), medio_id, falta, falta, usuario_id))

# ===== LOGICA DE EMAIL ESTRICTA =====
@app.route('/ventas/<int:id>/email/<tipo>', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_email_enviar_v5(id, tipo):
    TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'factura', 'entrega'}
    if tipo not in TIPOS_VALIDOS:
        from flask import abort
        abort(404)
        
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))

    # VALIDACIONES ESTRICTAS POR ESTADO
    if tipo == 'pago' and orden['estado'] != 'pendiente_pago':
        conn.close(); flash('La orden ya está pagada o cancelada. No podés notificar un pago.', 'error')
        return redirect(url_for('ventas_detalle', id=id))
        
    if tipo == 'envio' and orden['estado'] != 'pagado_sin_enviar':
        conn.close(); flash('Primero tenés que acreditar el pago antes de notificar el envío.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    destino = request.form.get('destinatario') or orden['cliente_email']
    if not destino or '@' not in destino:
        conn.close(); flash('El cliente no tiene email o es invalido.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

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
    
    # AUTOMATIZACION DE ESTADOS AL ENVIAR CORREO
    if ok:
        if tipo == 'pago':
            if not orden['stock_descontado']:
                aplicar_descuento_stock(conn, id, current_user.id)
            _registrar_pago_automatico(conn, id, orden['total'], current_user.id)
            conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
            flash('Pago notificado. Orden actualizada a Pagado / Sin enviar.', 'success')
            
        elif tipo == 'envio':
            conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado' WHERE id=?", (id,))
            flash('Envío notificado. Orden actualizada a Pagado / Enviado.', 'success')
        else:
            flash('Notificación enviada.', 'success')
    else:
        flash(msg, 'error')
        
    conn.commit(); conn.close()
    return redirect(url_for('ventas_detalle', id=id))

app.view_functions['ventas_email_enviar'] = ventas_email_enviar_v5


# ===== LOGICA DE ESTADO ESTRICTA =====
@app.route('/ventas/<int:id>/estado', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_estado_v6(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden: conn.close(); return redirect(url_for('ventas_lista'))
    
    nuevo = request.form['estado']
    actual = orden['estado']
    
    if actual == nuevo:
        conn.close(); flash('La orden ya está en ese estado.', 'info'); return redirect(url_for('ventas_detalle', id=id))

    trans = {
        'pendiente_pago': ['pagado_sin_enviar', 'cancelado'],
        'pagado_sin_enviar': ['pagado_enviado', 'cancelado', 'pendiente_pago'],
        'pagado_enviado': ['cancelado', 'pagado_sin_enviar'],
        'cancelado': ['pendiente_pago']
    }
    
    if nuevo not in trans.get(actual, []):
        conn.close(); flash('Transición de estado no permitida.', 'error'); return redirect(url_for('ventas_detalle', id=id))

    if nuevo == 'cancelado':
        if orden['stock_descontado']: revertir_stock(conn, id, current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='cancelado' WHERE id=?", (id,))
    elif nuevo == 'pagado_sin_enviar':
        if not orden['stock_descontado']: aplicar_descuento_stock(conn, id, current_user.id)
        _registrar_pago_automatico(conn, id, orden['total'], current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
    elif nuevo == 'pagado_enviado':
        conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado' WHERE id=?", (id,))
    elif nuevo == 'pendiente_pago':
        if orden['stock_descontado']: revertir_stock(conn, id, current_user.id)
        conn.execute("DELETE FROM pagos WHERE orden_id=? AND notas='Pago automatico (cuadre)'", (id,))
        conn.execute("UPDATE ordenes_venta SET estado='pendiente_pago' WHERE id=?", (id,))

    conn.commit(); conn.close()
    flash(f'Estado actualizado a {nuevo}.', 'success')
    return redirect(url_for('ventas_detalle', id=id))

app.view_functions['ventas_estado'] = ventas_estado_v6
'''

# El HTML corregido, quitando el modal feo y usando botones de estado fijos
VENTAS_DETALLE_HTML = r'''{% extends "base.html" %}
{% block title %}{{ orden.numero_interno }}{% endblock %}
{% block content %}
<style>
  .ticket-card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
  .ticket-title { font-size: 1rem; font-weight: 600; color: #4b5563; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; }
  .info-label { font-size: 0.8rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.2rem; }
  .info-value { font-size: 1rem; font-weight: 500; color: #111827; }
</style>

<div class="d-flex justify-content-between align-items-center mb-4">
    <div>
        <h3 class="mb-1" style="font-weight:700; letter-spacing:-.02em;">Orden {{ orden.numero_interno }}
            {% if orden.estado == 'pendiente_pago' %}<span class="badge bg-warning text-dark ms-2 fs-6">Pendiente pago</span>
            {% elif orden.estado == 'pagado_sin_enviar' %}<span class="badge bg-info text-dark ms-2 fs-6">Pagado / Sin enviar</span>
            {% elif orden.estado == 'pagado_enviado' %}<span class="badge bg-success ms-2 fs-6">Pagado / Enviado</span>
            {% else %}<span class="badge bg-secondary ms-2 fs-6">Cancelado</span>{% endif %}
        </h3>
        <div class="text-muted">{{ orden.fecha }} · {{ orden.vendedor_nombre }} · {{ orden.canal_nombre or 'Sin canal' }}</div>
    </div>
    <div class="d-flex gap-2">
        <a href="{{ url_for('ventas_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
        <a href="{{ url_for('ventas_imprimir', id=orden.id) }}" target="_blank" class="btn btn-outline-dark"><i class="bi bi-printer"></i> Imprimir / PDF</a>
    </div>
</div>

<div class="row g-4">
    <div class="col-md-8">
        <!-- INFO CLIENTE -->
        <div class="ticket-card">
            <div class="ticket-title"><span>Información del comprador</span></div>
            <div class="row g-3">
                <div class="col-md-6"><div class="info-label">Nombre</div><div class="info-value">{{ orden.cliente_nombre }}</div></div>
                <div class="col-md-6"><div class="info-label">Email</div><div class="info-value">{{ orden.cliente_email or '—' }}</div></div>
                <div class="col-md-6"><div class="info-label">Teléfono</div><div class="info-value">{{ orden.cliente_telefono or '—' }}</div></div>
            </div>
        </div>

        <!-- PRODUCTOS -->
        <div class="ticket-card">
            <div class="ticket-title">Productos</div>
            <table class="table table-sm mb-0">
                <thead><tr><th>Producto</th><th class="text-end">Cant.</th><th class="text-end">Precio</th><th class="text-end">Subtotal</th><th></th></tr></thead>
                <tbody>
                    {% for it in items %}
                    <tr>
                        <td>{{ it.producto_nombre }}</td>
                        <td class="text-end">{{ '%g'|format(it.cantidad) }}</td>
                        <td class="text-end">{{ it.precio_unitario|pesos }}</td>
                        <td class="text-end">{{ it.subtotal|pesos }}</td>
                        <td class="text-end">
                            {% if orden.estado != 'cancelado' %}
                            <form method="post" action="{{ url_for('ventas_eliminar_item', id=orden.id, item_id=it.id) }}" class="d-inline" onsubmit="return confirm('Eliminar?')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
                <tfoot><tr><td colspan="3" class="text-end text-muted small pt-3">Kilos totales:</td><td class="text-end fw-bold pt-3">{{ '%.2f'|format(kilos_total) }} kg</td><td></td></tr></tfoot>
            </table>

            {% if orden.estado != 'cancelado' %}
            <div class="mt-3 p-3 bg-light rounded border">
                <form method="post" action="{{ url_for('ventas_agregar_item', id=orden.id) }}" class="row g-2 align-items-end">
                    <div class="col-md-6"><select name="producto_id" class="form-select form-select-sm" required><option value="">Añadir producto...</option>{% for p in todos_productos %}<option value="{{ p.id }}" data-precio="{{ p.precio }}">{{ p.nombre }}</option>{% endfor %}</select></div>
                    <div class="col-md-2"><input type="number" step="0.01" name="cantidad" class="form-control form-control-sm" value="1" required></div>
                    <div class="col-md-2"><input type="number" step="0.01" name="precio" class="form-control form-control-sm" required></div>
                    <div class="col-md-2"><button type="submit" class="btn btn-sm btn-dark w-100">Sumar</button></div>
                </form>
            </div>
            {% endif %}
        </div>

        <!-- NOTIFICACIONES (SIN MODAL, BOTONES DIRECTOS) -->
        <div class="ticket-card">
            <div class="ticket-title">Enviar email al cliente</div>
            <div class="d-flex flex-wrap gap-2">
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
            </div>
        </div>
    </div>

    <div class="col-md-4">
        <!-- RESUMEN -->
        <div class="ticket-card" style="background:#fafbfd;">
            <div class="ticket-title">Resumen comercial</div>
            <div class="d-flex justify-content-between mb-2"><span class="text-muted">Subtotal</span><span>{{ orden.subtotal|pesos }}</span></div>
            <div class="d-flex justify-content-between mb-2"><span class="text-muted">Envío</span><span>{{ orden.costo_envio|pesos }}</span></div>
            <hr>
            <div class="d-flex justify-content-between align-items-center"><span class="fw-bold">Total</span><span class="fw-bold fs-4 text-success">{{ orden.total|pesos }}</span></div>
        </div>

        <!-- ESTADO ESTRICTO CON BOTONES -->
        <div class="ticket-card">
            <div class="ticket-title">Avanzar Estado</div>
            <div class="d-grid gap-2">
                {% if orden.estado == 'pendiente_pago' %}
                <form method="post" action="{{ url_for('ventas_estado', id=orden.id) }}">
                    <input type="hidden" name="estado" value="pagado_sin_enviar">
                    <button class="btn btn-success w-100" onclick="return confirm('¿Confirmás que el pago fue recibido? Se descontará stock.')">Marcar como PAGADO</button>
                </form>
                {% elif orden.estado == 'pagado_sin_enviar' %}
                <form method="post" action="{{ url_for('ventas_estado', id=orden.id) }}">
                    <input type="hidden" name="estado" value="pagado_enviado">
                    <button class="btn btn-info text-white w-100" onclick="return confirm('¿Confirmás que el pedido fue enviado?')">Marcar como ENVIADO</button>
                </form>
                {% endif %}
                
                {% if orden.estado != 'cancelado' %}
                <form method="post" action="{{ url_for('ventas_estado', id=orden.id) }}">
                    <input type="hidden" name="estado" value="cancelado">
                    <button class="btn btn-outline-danger w-100" onclick="return confirm('¿Cancelar la orden?')">Cancelar Orden</button>
                </form>
                {% endif %}
            </div>
        </div>

        <!-- ENVIO -->
        <div class="ticket-card">
            <div class="ticket-title">Envío</div>
            <form method="post" action="{{ url_for('ventas_envio', id=orden.id) }}">
                <div class="mb-2"><input name="destinatario_nombre" class="form-control form-control-sm" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}" placeholder="Destinatario"></div>
                <div class="mb-2"><input name="destinatario_calle" class="form-control form-control-sm" value="{{ orden.destinatario_calle or '' }}" placeholder="Dirección"></div>
                <div class="row g-2 mb-2">
                    <div class="col-6"><input name="destinatario_localidad" class="form-control form-control-sm" value="{{ orden.destinatario_localidad or '' }}" placeholder="Localidad"></div>
                    <div class="col-6"><input name="destinatario_provincia" class="form-control form-control-sm" value="{{ orden.destinatario_provincia or '' }}" placeholder="Provincia"></div>
                </div>
                <div class="mb-2"><select name="transportista_id" class="form-select form-select-sm"><option value="">Transportista...</option>{% for t in transportistas %}<option value="{{ t.id }}" {% if orden.transportista_id==t.id %}selected{% endif %}>{{ t.nombre }}</option>{% endfor %}</select></div>
                <div class="mb-2"><input name="nro_guia" class="form-control form-control-sm" value="{{ orden.nro_guia or '' }}" placeholder="Nro Guía"></div>
                <button class="btn btn-dark btn-sm w-100">Guardar Envío</button>
            </form>
        </div>
    </div>
</div>
<script>
document.addEventListener('DOMContentLoaded', () => {
    const selectProd = document.querySelector('select[name="producto_id"]');
    if (selectProd) {
        selectProd.addEventListener('change', function() {
            const opt = this.options[this.selectedIndex];
            if (opt.dataset.precio) this.closest('form').querySelector('input[name="precio"]').value = opt.dataset.precio;
        });
    }
});
</script>
{% endblock %}
'''

def patch_run_bat():
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; import app152; import app155; import app156; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat)
    print("[upgrade156] run.bat actualizado")

def main():
    print("=== Upgrade 156: Flujo estricto de estados y limpieza de emails ===")
    actualizar_plantillas()
    escribir('app156.py', APP156_PY)
    escribir('templates/ventas/detalle.html', VENTAS_DETALLE_HTML)
    patch_run_bat()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()