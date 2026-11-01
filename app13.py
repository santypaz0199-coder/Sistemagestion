
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app12 import app
from app4 import _cargar_orden
from app import permiso_required
from database import get_db


def _config(clave, default=''):
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return (row['valor'] if row and row['valor'] else default)


@app.route('/ventas/<int:id>/imprimir')
@login_required
@permiso_required('ventas')
def ventas_imprimir(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))

    items = conn.execute("""SELECT oi.*, p.nombre as producto_nombre, p.sku,
        p.peso_valor, p.peso_unidad FROM orden_items oi
        JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?""", (id,)).fetchall()
    pagos = conn.execute("""SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg
        LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id WHERE pg.orden_id=?""", (id,)).fetchall()
    total_pagado = sum(p['monto'] for p in pagos)
    conn.close()

    kilos_total = 0.0
    for it in items:
        pv = it['peso_valor'] or 0
        if it['peso_unidad'] == 'g':
            kilos_total += (it['cantidad'] * pv) / 1000.0
        else:
            kilos_total += it['cantidad'] * pv

    empresa = {
        'nombre': _config('empresa_nombre', 'Familia Zaragoza'),
        'telefono': _config('empresa_telefono', ''),
        'web': _config('empresa_web', ''),
        'email': _config('smtp_remitente_email', ''),
    }
    return render_template('ventas/imprimir.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, kilos_total=kilos_total, empresa=empresa)


@app.route('/ventas/<int:id>/compartir', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_compartir(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); return jsonify({'ok': False, 'error': 'No encontrada'}), 404
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); return jsonify({'ok': False, 'error': 'Sin permiso'}), 403
    items = conn.execute("""SELECT oi.*, p.nombre as producto_nombre FROM orden_items oi
        JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?""", (id,)).fetchall()
    conn.close()

    estado = {'pendiente_pago': 'Pendiente de pago', 'pagado_sin_enviar': 'Pagado / Sin enviar',
              'pagado_enviado': 'Pagado / Enviado', 'cancelado': 'Cancelado'}.get(orden['estado'], orden['estado'])
    lineas = [f"*Pedido {orden['numero_interno']}*",
              f"Fecha: {orden['fecha']}",
              f"Cliente: {orden['cliente_nombre']}",
              f"Estado: {estado}",
              ""]
    for it in items:
        lineas.append(f"- {it['producto_nombre']} x {it['cantidad']:g} = ${it['subtotal']:.2f}")
    lineas.append("")
    lineas.append(f"*Total: ${orden['total']:.2f}*")
    if orden['nro_guia']:
        lineas.append(f"Guia: {orden['nro_guia']}")
    texto = "\n".join(lineas)
    link = url_for('ventas_detalle', id=id, _external=False)
    return jsonify({'ok': True, 'texto': texto, 'link': link, 'numero': orden['numero_interno']})


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
