
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app36 import app
from app import permiso_required
from database import get_db
from app4 import _cargar_orden


@app.route('/ventas/<int:id>/envio', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_envio_v3(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error')
        return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error')
        return redirect(url_for('ventas_lista'))

    tipo_envio = request.form.get('tipo_envio', '').strip()
    if tipo_envio not in ('retira_deposito', 'transporte', 'envio_personal'):
        conn.close(); flash('Tenes que elegir un tipo de envio.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    # Datos comunes
    dest_nombre = request.form.get('destinatario_nombre', '').strip() or None
    dest_prov = request.form.get('destinatario_provincia', '').strip() or None
    dest_loc = request.form.get('destinatario_localidad', '').strip() or None
    dest_cp = request.form.get('destinatario_cp', '').strip() or None
    dest_calle = request.form.get('destinatario_calle', '').strip() or None
    dest_detalles = request.form.get('destinatario_detalles', '').strip() or None

    if tipo_envio == 'retira_deposito':
        # No requiere transportista ni direccion
        conn.execute("""UPDATE ordenes_venta SET
            tipo_envio='retira_deposito', destino_tipo=NULL, sucursal_detalle=NULL,
            transportista_id=NULL, nro_guia=NULL,
            destinatario_nombre=?, destinatario_detalles=?,
            destinatario_provincia=NULL, destinatario_localidad=NULL,
            destinatario_cp=NULL, destinatario_calle=NULL
            WHERE id=?""",
            (dest_nombre, dest_detalles, id))
        conn.commit(); conn.close()
        flash('Datos de envio guardados: retira en deposito.', 'success')
        return redirect(url_for('ventas_detalle', id=id))

    if tipo_envio == 'envio_personal':
        # Requiere direccion, no requiere transportista
        if not (dest_calle and dest_loc and dest_prov):
            conn.close()
            flash('Para envio personal tenes que cargar calle, localidad y provincia del destinatario.', 'error')
            return redirect(url_for('ventas_detalle', id=id))
        conn.execute("""UPDATE ordenes_venta SET
            tipo_envio='envio_personal', destino_tipo='domicilio', sucursal_detalle=NULL,
            transportista_id=NULL, nro_guia=NULL,
            destinatario_nombre=?, destinatario_provincia=?, destinatario_localidad=?,
            destinatario_cp=?, destinatario_calle=?, destinatario_detalles=?
            WHERE id=?""",
            (dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles, id))
        conn.commit(); conn.close()
        flash('Datos de envio guardados: envio personal.', 'success')
        return redirect(url_for('ventas_detalle', id=id))

    # tipo_envio == 'transporte'
    destino_tipo = request.form.get('destino_tipo', '').strip()
    if destino_tipo not in ('domicilio', 'sucursal'):
        conn.close()
        flash('Para envio por transporte tenes que elegir destino: Domicilio o Sucursal.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    transportista_id = request.form.get('transportista_id') or None
    if not transportista_id:
        conn.close()
        flash('Para envio por transporte tenes que elegir un transportista.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    sucursal_detalle = request.form.get('sucursal_detalle', '').strip() or None
    if destino_tipo == 'sucursal' and not sucursal_detalle:
        conn.close()
        flash('Indica a que sucursal se envia.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    if destino_tipo == 'domicilio' and not (dest_calle and dest_loc and dest_prov):
        conn.close()
        flash('Para envio a domicilio tenes que cargar calle, localidad y provincia.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    conn.execute("""UPDATE ordenes_venta SET
        tipo_envio='transporte', destino_tipo=?, sucursal_detalle=?,
        transportista_id=?, nro_guia=?,
        destinatario_nombre=?, destinatario_provincia=?, destinatario_localidad=?,
        destinatario_cp=?, destinatario_calle=?, destinatario_detalles=?
        WHERE id=?""",
        (destino_tipo, sucursal_detalle, int(transportista_id),
         request.form.get('nro_guia', '').strip() or None,
         dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles, id))
    conn.commit(); conn.close()
    flash('Datos de envio guardados: transporte a ' + ('domicilio' if destino_tipo == 'domicilio' else 'sucursal') + '.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


app.view_functions['ventas_envio'] = ventas_envio_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
