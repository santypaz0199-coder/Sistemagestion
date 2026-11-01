
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app7 import app
from app import revertir_stock, permiso_required
from database import get_db


@app.route('/ventas/masivo', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_masivo():
    accion = request.form.get('accion')
    ids = request.form.getlist('ordenes_ids')
    if not ids:
        flash('No seleccionaste ordenes.', 'error')
        return redirect(url_for('ventas_lista'))
    ids_int = []
    for i in ids:
        try: ids_int.append(int(i))
        except: pass

    if accion == 'notificar':
        from app4 import enviar_email, get_config, construir_contexto, render_plantilla, _cargar_orden

    ok = 0
    sin_email = 0
    sin_cambio = 0
    conn = get_db()
    nro_arca = request.form.get('nro_arca', '').strip() or None
    hoy_s = date.today().isoformat()

    for oid in ids_int:
        orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (oid,)).fetchone()
        if not orden: continue
        if not current_user.es_admin and orden['usuario_id'] != current_user.id:
            continue

        if accion == 'cancelar':
            if orden['estado'] == 'cancelado':
                sin_cambio += 1; continue
            if orden['stock_descontado']:
                revertir_stock(conn, oid, current_user.id)
            conn.execute("UPDATE ordenes_venta SET estado='cancelado' WHERE id=?", (oid,))
            ok += 1

        elif accion == 'enviado':
            if orden['estado'] != 'pagado_sin_enviar':
                sin_cambio += 1; continue
            conn.execute("UPDATE ordenes_venta SET estado='pagado_enviado' WHERE id=?", (oid,))
            ok += 1

        elif accion == 'facturar':
            conn.execute("""UPDATE ordenes_venta SET estado_facturacion='facturada',
                nro_factura_arca=?, fecha_factura=? WHERE id=?""", (nro_arca, hoy_s, oid))
            ok += 1

        elif accion == 'notificar':
            oc = _cargar_orden(conn, oid)
            if not oc or not oc['cliente_email']:
                sin_email += 1; continue
            try:
                ctx = construir_contexto(oc, conn, 'envio')
                asunto = render_plantilla(get_config('plantilla_envio_asunto'), ctx)
                cuerpo = render_plantilla(get_config('plantilla_envio_cuerpo'), ctx)
                success, msg = enviar_email(oc['cliente_email'], asunto, cuerpo)
                conn.execute("""INSERT INTO emails_enviados
                    (destinatario, asunto, tipo, orden_id, estado) VALUES (?,?,?,?,?)""",
                    (oc['cliente_email'], asunto, 'envio', oid, 'ok' if success else 'error'))
                if success: ok += 1
            except Exception as e:
                print(f"[masivo notificar] {oid}: {e}")

    conn.commit(); conn.close()

    partes = [f'{ok} orden(es) procesadas']
    if sin_cambio > 0: partes.append(f'{sin_cambio} sin cambios (ya en ese estado)')
    if sin_email > 0: partes.append(f'{sin_email} sin email de cliente')
    flash('. '.join(partes) + '.', 'success' if ok > 0 else 'error')
    return redirect(url_for('ventas_lista'))


@app.route('/ventas/<int:id>/facturacion', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_facturacion_individual(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))
    est = request.form.get('estado_facturacion', 'no_requiere')
    if est == 'facturada':
        nro = request.form.get('nro_factura_arca', '').strip() or None
        conn.execute("""UPDATE ordenes_venta SET estado_facturacion='facturada',
            nro_factura_arca=?, fecha_factura=? WHERE id=?""",
            (nro, date.today().isoformat(), id))
    else:
        conn.execute("""UPDATE ordenes_venta SET estado_facturacion=?,
            nro_factura_arca=NULL, fecha_factura=NULL WHERE id=?""", (est, id))
    conn.commit(); conn.close()
    flash('Facturacion actualizada.', 'success')
    return redirect(url_for('ventas_lista'))


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
