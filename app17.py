
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app16 import app, _categorias_arbol, _stats_productos
from app import permiso_required, admin_required
from database import get_db


def _stats_reservados(conn):
    return conn.execute("""
        SELECT COUNT(DISTINCT oi.producto_id) FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        WHERE o.estado = 'pendiente_pago'
    """).fetchone()[0]


@app.route('/productos')
@login_required
@permiso_required('productos')
def productos_lista_v3():
    conn = get_db()
    q = request.args.get('q', '').strip()
    categoria_id = request.args.get('categoria', '').strip()
    alerta = request.args.get('alerta', '').strip()

    sql = """SELECT p.*, c.nombre as categoria_nombre, cp.nombre as parent_nombre
             FROM productos p
             LEFT JOIN categorias_productos c ON c.id = p.categoria_id
             LEFT JOIN categorias_productos cp ON cp.id = c.parent_id
             WHERE p.activo=1"""
    params = []
    if q:
        sql += " AND (p.nombre LIKE ? OR p.sku LIKE ?)"
        params += [f'%{q}%', f'%{q}%']
    if categoria_id:
        sql += " AND (p.categoria_id=? OR c.parent_id=?)"
        params += [int(categoria_id), int(categoria_id)]
    if alerta == 'sin_foto':
        sql += " AND (p.foto IS NULL OR p.foto='')"
    elif alerta == 'sin_precio':
        sql += " AND (p.precio IS NULL OR p.precio=0)"
    elif alerta == 'agotado':
        sql += " AND p.stock_actual <= 0"
    elif alerta == 'bajo_stock':
        sql += " AND p.stock_minimo > 0 AND p.stock_actual <= p.stock_minimo AND p.stock_actual > 0"
    elif alerta == 'reservado':
        sql += " AND p.id IN (SELECT oi.producto_id FROM orden_items oi JOIN ordenes_venta o ON o.id=oi.orden_id WHERE o.estado='pendiente_pago')"
    sql += " ORDER BY p.nombre"
    productos = conn.execute(sql, params).fetchall()

    stats = _stats_productos(conn)
    stats['reservados'] = _stats_reservados(conn)
    padres, hijos = _categorias_arbol(conn)
    conn.close()
    return render_template('productos/lista.html',
                           productos=productos, q=q, categoria_id=categoria_id,
                           alerta=alerta, stats=stats, padres=padres, hijos=hijos)


@app.route('/productos/reservados')
@login_required
@permiso_required('productos')
def productos_reservados():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id as producto_id, p.nombre as producto_nombre, p.sku as producto_sku,
               p.foto as producto_foto, p.stock_actual,
               SUM(oi.cantidad) as cantidad_reservada,
               COUNT(DISTINCT o.id) as num_ordenes
        FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        JOIN productos p ON p.id = oi.producto_id
        WHERE o.estado = 'pendiente_pago'
        GROUP BY p.id
        ORDER BY cantidad_reservada DESC
    """).fetchall()

    reservas = []
    for r in rows:
        d = dict(r)
        d['ordenes'] = conn.execute("""
            SELECT o.id as orden_id, o.numero_interno, o.fecha, oi.cantidad, oi.subtotal,
                   c.nombre_completo as cliente_nombre, c.id as cliente_id,
                   u.nombre as vendedor_nombre
            FROM orden_items oi
            JOIN ordenes_venta o ON o.id = oi.orden_id
            JOIN clientes c ON c.id = o.cliente_id
            JOIN usuarios u ON u.id = o.usuario_id
            WHERE oi.producto_id = ? AND o.estado = 'pendiente_pago'
            ORDER BY o.fecha ASC
        """, (r['producto_id'],)).fetchall()
        reservas.append(d)
    conn.close()
    return render_template('productos/reservados.html', reservas=reservas)


@app.route('/productos/ranking')
@login_required
@permiso_required('productos')
def productos_ranking():
    conn = get_db()
    periodo = request.args.get('periodo', 'mes')
    hoy = date.today()
    if periodo == 'mes':
        ini = hoy.replace(day=1)
    elif periodo == 'trimestre':
        ini = hoy - timedelta(days=90)
    elif periodo == 'anio':
        ini = hoy.replace(month=1, day=1)
    else:
        ini = date(2000, 1, 1)

    ranking = conn.execute("""
        SELECT p.id, p.nombre, p.sku, p.foto,
               SUM(oi.cantidad) as cant_vendida,
               SUM(oi.subtotal) as total_vendido,
               COUNT(DISTINCT o.id) as num_ordenes
        FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        JOIN productos p ON p.id = oi.producto_id
        WHERE o.estado IN ('pagado_sin_enviar','pagado_enviado')
          AND date(o.fecha) BETWEEN ? AND ?
        GROUP BY p.id
        ORDER BY cant_vendida DESC
        LIMIT 50
    """, (ini.isoformat(), hoy.isoformat())).fetchall()
    conn.close()
    return render_template('productos/ranking.html', ranking=ranking, periodo=periodo,
                           ini=ini, fin=hoy)


@app.route('/productos/<int:id>/ajuste', methods=['GET', 'POST'])
@login_required
@admin_required
def productos_ajuste(id):
    conn = get_db()
    producto = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not producto:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))

    if request.method == 'POST':
        try:
            nuevo = float(request.form['nuevo_stock'])
        except (ValueError, KeyError):
            flash('Numero invalido.', 'error')
            conn.close()
            return redirect(url_for('productos_ajuste', id=id))
        motivo = request.form.get('motivo', '').strip()
        if not motivo:
            flash('El motivo es obligatorio.', 'error')
            conn.close()
            return redirect(url_for('productos_ajuste', id=id))
        anterior = producto['stock_actual']
        diferencia = nuevo - anterior
        conn.execute("UPDATE productos SET stock_actual=?, actualizado=datetime('now') WHERE id=?",
                     (nuevo, id))
        conn.execute("""INSERT INTO movimientos_stock (producto_id, tipo, cantidad, referencia, usuario_id)
            VALUES (?, 'ajuste', ?, ?, ?)""",
            (id, diferencia,
             f'Ajuste manual: {motivo} (antes: {anterior:g}, ahora: {nuevo:g})',
             current_user.id))
        conn.commit(); conn.close()
        flash(f'Stock ajustado: {anterior:g} → {nuevo:g}. Motivo registrado.', 'success')
        return redirect(url_for('productos_lista'))

    movimientos = conn.execute("""SELECT m.*, u.nombre as usuario_nombre FROM movimientos_stock m
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        WHERE m.producto_id = ? ORDER BY m.fecha DESC, m.id DESC LIMIT 30""", (id,)).fetchall()
    conn.close()
    return render_template('productos/ajuste.html', producto=producto, movimientos=movimientos)


app.view_functions['productos_lista'] = productos_lista_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
