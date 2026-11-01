
import re, urllib.parse
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app8 import app
from app import permiso_required
from database import get_db


def _estado_humano(e):
    return {'pendiente_pago': 'Pendiente de pago', 'pagado_sin_enviar': 'Pagado / Sin enviar',
            'pagado_enviado': 'Pagado / Enviado', 'cancelado': 'Cancelado'}.get(e, e)


def _limpiar_tel(t):
    if not t: return ''
    n = re.sub(r'\D', '', t)
    if n and not n.startswith('54'): n = '54' + n
    return n


# ==== Ventas (lista nueva) ====
@app.route('/ventas')
@login_required
@permiso_required('ventas')
def ventas_lista_v2():
    conn = get_db()
    q = request.args.get('q', '').strip()
    estado = request.args.get('estado', '')
    canal = request.args.get('canal', '')
    tipo = request.args.get('tipo', '')
    vendedor = request.args.get('vendedor', '')
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')

    sql = """SELECT o.*, c.nombre_completo as cliente_nombre, c.telefono as cliente_telefono,
             u.nombre as vendedor_nombre, cv.nombre as canal_nombre,
             (SELECT COALESCE(SUM(
                CASE WHEN p.peso_unidad = 'g' THEN (oi.cantidad * p.peso_valor) / 1000.0
                     ELSE oi.cantidad * COALESCE(p.peso_valor, 0) END
             ), 0)
              FROM orden_items oi
              LEFT JOIN productos p ON p.id = oi.producto_id
              WHERE oi.orden_id = o.id) as kilos
             FROM ordenes_venta o
             JOIN clientes c ON c.id = o.cliente_id
             JOIN usuarios u ON u.id = o.usuario_id
             LEFT JOIN canales_venta cv ON cv.id = o.canal_id
             WHERE 1=1"""
    params = []
    if not current_user.es_admin:
        sql += " AND o.usuario_id=?"; params.append(current_user.id)
    elif vendedor:
        sql += " AND o.usuario_id=?"; params.append(int(vendedor))
    if q:
        sql += " AND (o.numero_interno LIKE ? OR c.nombre_completo LIKE ?)"
        params += [f'%{q}%', f'%{q}%']
    if estado:
        sql += " AND o.estado=?"; params.append(estado)
    if canal:
        sql += " AND o.canal_id=?"; params.append(int(canal))
    if tipo:
        sql += " AND o.tipo=?"; params.append(tipo)
    if desde:
        sql += " AND date(o.fecha)>=?"; params.append(desde)
    if hasta:
        sql += " AND date(o.fecha)<=?"; params.append(hasta)
    sql += " ORDER BY o.id DESC"
    rows = conn.execute(sql, params).fetchall()

    ventas = []
    for r in rows:
        d = dict(r)
        tel = _limpiar_tel(r['cliente_telefono'])
        if tel:
            msg = (f"Hola {r['cliente_nombre']}!\n"
                   f"Te paso el resumen de tu pedido {r['numero_interno']}:\n"
                   f"Total: ${r['total']:.2f}\n"
                   f"Estado: {_estado_humano(r['estado'])}")
            d['wa_url'] = f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"
        else:
            d['wa_url'] = None
        ventas.append(d)

    canales = conn.execute("SELECT * FROM canales_venta WHERE activo=1 ORDER BY nombre").fetchall()
    vendedores = conn.execute("SELECT * FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall() if current_user.es_admin else []
    conn.close()
    return render_template('ventas/lista.html', ventas=ventas, q=q, estado=estado, canal=canal,
                           tipo=tipo, vendedor=vendedor, desde=desde, hasta=hasta,
                           canales=canales, vendedores=vendedores)


app.view_functions['ventas_lista'] = ventas_lista_v2


# ==== Productos (con peso) ====
@app.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def productos_nuevo_v2():
    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_actual = float(request.form.get('stock_actual') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
        except ValueError:
            flash('Revisa los numeros.', 'error')
            return render_template('productos/form.html', producto=None, valores=request.form)
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            return render_template('productos/form.html', producto=None, valores=request.form)
        conn = get_db()
        if sku and conn.execute("SELECT id FROM productos WHERE sku=?", (sku,)).fetchone():
            conn.close(); flash('SKU ya existe.', 'error')
            return render_template('productos/form.html', producto=None, valores=request.form)
        cur = conn.execute("""INSERT INTO productos (sku,nombre,costo,precio,stock_actual,stock_minimo,peso_valor,peso_unidad)
            VALUES (?,?,?,?,?,?,?,?)""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad))
        if stock_actual > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (cur.lastrowid, 'ajuste_inicial', stock_actual, 'Carga inicial', current_user.id))
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))
    return render_template('productos/form.html', producto=None, valores={})


@app.route('/productos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def productos_editar_v2(id):
    conn = get_db()
    producto = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not producto:
        conn.close(); return redirect(url_for('productos_lista'))
    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
        except ValueError:
            flash('Revisa los numeros.', 'error')
            return render_template('productos/form.html', producto=producto, valores=request.form)
        conn.execute("""UPDATE productos SET sku=?,nombre=?,costo=?,precio=?,stock_minimo=?,peso_valor=?,peso_unidad=?
            WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={})


app.view_functions['productos_nuevo'] = productos_nuevo_v2
app.view_functions['productos_editar'] = productos_editar_v2


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
