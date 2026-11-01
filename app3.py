
import os
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import app, admin_required, permiso_required
from database import get_db, init_db


def calcular_periodo(tipo, fecha_ref=None):
    if fecha_ref is None:
        fecha_ref = date.today()
    elif isinstance(fecha_ref, str):
        try:
            fecha_ref = date.fromisoformat(fecha_ref)
        except ValueError:
            fecha_ref = date.today()
    if tipo == 'dia':
        return fecha_ref, fecha_ref
    if tipo == 'semana':
        ini = fecha_ref - timedelta(days=fecha_ref.weekday())
        return ini, ini + timedelta(days=6)
    if tipo == 'mes':
        ini = fecha_ref.replace(day=1)
        sig = ini.replace(year=ini.year + 1, month=1) if ini.month == 12 else ini.replace(month=ini.month + 1)
        return ini, sig - timedelta(days=1)
    if tipo == 'anio':
        return fecha_ref.replace(month=1, day=1), fecha_ref.replace(month=12, day=31)
    return fecha_ref, fecha_ref


def periodo_anterior(tipo, ini, fin):
    if tipo == 'dia':
        d = ini - timedelta(days=1); return d, d
    if tipo == 'semana':
        return ini - timedelta(days=7), fin - timedelta(days=7)
    if tipo == 'mes':
        return calcular_periodo('mes', ini - timedelta(days=1))
    if tipo == 'anio':
        return ini.replace(year=ini.year - 1), fin.replace(year=fin.year - 1)
    return ini, fin


def calcular_caja(conn, hasta):
    hs = hasta.isoformat()
    ingresos = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE date(fecha)<=?", (hs,)).fetchone()[0]
    gastos = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha)<=?", (hs,)).fetchone()[0]
    compras = conn.execute("SELECT COALESCE(SUM(total),0) FROM compras WHERE date(fecha)<=?", (hs,)).fetchone()[0]
    return ingresos - gastos - compras


def calcular_cierre(conn, ini, fin):
    ini_s, fin_s = ini.isoformat(), fin.isoformat()
    stock_actual = conn.execute("SELECT COALESCE(SUM(stock_actual),0) FROM productos WHERE activo=1").fetchone()[0]
    entradas = conn.execute("SELECT COALESCE(SUM(cantidad),0) FROM movimientos_stock WHERE tipo IN ('entrada','ajuste_inicial') AND date(fecha) BETWEEN ? AND ?", (ini_s, fin_s)).fetchone()[0]
    salidas = conn.execute("SELECT COALESCE(SUM(cantidad),0) FROM movimientos_stock WHERE tipo='salida' AND date(fecha) BETWEEN ? AND ?", (ini_s, fin_s)).fetchone()[0]
    v = conn.execute("SELECT COALESCE(SUM(total),0), COUNT(*) FROM ordenes_venta WHERE date(fecha) BETWEEN ? AND ? AND estado IN ('pagado_sin_enviar','pagado_enviado')", (ini_s, fin_s)).fetchone()
    c = conn.execute("SELECT COALESCE(SUM(total),0), COUNT(*) FROM compras WHERE date(fecha) BETWEEN ? AND ?", (ini_s, fin_s)).fetchone()
    g = conn.execute("SELECT COALESCE(SUM(monto),0), COUNT(*) FROM gastos WHERE date(fecha) BETWEEN ? AND ?", (ini_s, fin_s)).fetchone()
    ingresos = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE date(fecha) BETWEEN ? AND ?", (ini_s, fin_s)).fetchone()[0]
    a_cobrar = conn.execute("SELECT COALESCE(SUM(o.total - COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)),0) FROM ordenes_venta o WHERE o.estado != 'cancelado' AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)").fetchone()[0]
    saldo_inicio = calcular_caja(conn, ini - timedelta(days=1))
    saldo_fin = saldo_inicio + ingresos - g[0] - c[0]
    return {
        'stock_inicio': stock_actual - (entradas - salidas),
        'entradas': entradas, 'salidas': salidas, 'stock_fin': stock_actual,
        'ventas': v[0], 'ventas_count': v[1],
        'compras': c[0], 'compras_count': c[1],
        'gastos': g[0], 'gastos_count': g[1],
        'ganancia': v[0] - g[0] - c[0],
        'a_cobrar': a_cobrar,
        'saldo_inicio': saldo_inicio,
        'ingresos': ingresos,
        'egresos': g[0] + c[0],
        'saldo_fin': saldo_fin,
    }


def pct(curr, prev):
    if prev == 0:
        return None if curr == 0 else 100.0
    return ((curr - prev) / prev) * 100


# ===== Proveedores =====
@app.route('/proveedores')
@login_required
@admin_required
def proveedores_lista():
    conn = get_db()
    provs = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('proveedores/lista.html', proveedores=provs)


@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def proveedores_nuevo():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            return render_template('proveedores/form.html', proveedor=None, valores=request.form)
        conn = get_db()
        conn.execute("INSERT INTO proveedores (nombre,cuit,contacto,telefono,email) VALUES (?,?,?,?,?)",
                     (nombre, request.form.get('cuit','').strip(), request.form.get('contacto','').strip(),
                      request.form.get('telefono','').strip(), request.form.get('email','').strip()))
        conn.commit(); conn.close()
        flash('Proveedor creado.', 'success')
        return redirect(url_for('proveedores_lista'))
    return render_template('proveedores/form.html', proveedor=None, valores={})


@app.route('/proveedores/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def proveedores_editar(id):
    conn = get_db()
    prov = conn.execute("SELECT * FROM proveedores WHERE id=?", (id,)).fetchone()
    if not prov:
        conn.close(); return redirect(url_for('proveedores_lista'))
    if request.method == 'POST':
        conn.execute("UPDATE proveedores SET nombre=?,cuit=?,contacto=?,telefono=?,email=? WHERE id=?",
                     (request.form['nombre'].strip(), request.form.get('cuit','').strip(),
                      request.form.get('contacto','').strip(), request.form.get('telefono','').strip(),
                      request.form.get('email','').strip(), id))
        conn.commit(); conn.close()
        flash('Proveedor actualizado.', 'success')
        return redirect(url_for('proveedores_lista'))
    conn.close()
    return render_template('proveedores/form.html', proveedor=prov, valores={})


@app.route('/proveedores/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def proveedores_eliminar(id):
    conn = get_db()
    conn.execute("UPDATE proveedores SET activo=0 WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Proveedor desactivado.', 'success')
    return redirect(url_for('proveedores_lista'))


# ===== Compras =====
@app.route('/compras')
@login_required
@admin_required
def compras_lista():
    conn = get_db()
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    prov = request.args.get('proveedor', '')
    sql = """SELECT c.*, p.nombre as proveedor_nombre, u.nombre as usuario_nombre
             FROM compras c LEFT JOIN proveedores p ON p.id=c.proveedor_id
             LEFT JOIN usuarios u ON u.id=c.usuario_id WHERE 1=1"""
    params = []
    if desde: sql += " AND date(c.fecha)>=?"; params.append(desde)
    if hasta: sql += " AND date(c.fecha)<=?"; params.append(hasta)
    if prov: sql += " AND c.proveedor_id=?"; params.append(int(prov))
    sql += " ORDER BY c.id DESC"
    compras = conn.execute(sql, params).fetchall()
    proveedores = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()
    total = sum(c['total'] for c in compras)
    conn.close()
    return render_template('compras/lista.html', compras=compras, proveedores=proveedores, total=total,
                           desde=desde, hasta=hasta, proveedor=prov)


@app.route('/compras/nueva', methods=['GET', 'POST'])
@login_required
@admin_required
def compras_nueva():
    conn = get_db()
    if request.method == 'POST':
        try:
            prov_id = int(request.form['proveedor_id']) if request.form.get('proveedor_id') else None
            fecha = request.form.get('fecha') or date.today().isoformat()
            notas = request.form.get('notas', '').strip()
            pids = request.form.getlist('producto_id')
            cants = request.form.getlist('cantidad')
            costos = request.form.getlist('costo')
        except (ValueError, KeyError):
            conn.close(); flash('Datos invalidos.', 'error'); return redirect(url_for('compras_nueva'))
        items = []
        for pid, c, co in zip(pids, cants, costos):
            if not pid or not c: continue
            try:
                cf = float(c); cof = float(co)
            except ValueError: continue
            if cf <= 0: continue
            items.append({'pid': int(pid), 'cantidad': cf, 'costo': cof, 'sub': cf * cof})
        if not items:
            conn.close(); flash('Agrega productos.', 'error'); return redirect(url_for('compras_nueva'))
        total = sum(i['sub'] for i in items)
        cur = conn.execute("INSERT INTO compras (proveedor_id,fecha,total,usuario_id,notas) VALUES (?,?,?,?,?)",
                           (prov_id, fecha, total, current_user.id, notas))
        cid = cur.lastrowid
        for it in items:
            conn.execute("INSERT INTO compra_items (compra_id,producto_id,cantidad,costo_unitario) VALUES (?,?,?,?)",
                         (cid, it['pid'], it['cantidad'], it['costo']))
            conn.execute("UPDATE productos SET stock_actual=stock_actual+?, costo=? WHERE id=?",
                         (it['cantidad'], it['costo'], it['pid']))
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (it['pid'], 'entrada', it['cantidad'], f'Compra #{cid}', current_user.id))
        conn.commit(); conn.close()
        flash(f'Compra #{cid} registrada. Stock actualizado.', 'success')
        return redirect(url_for('compras_lista'))
    proveedores = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()
    productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('compras/form.html', proveedores=proveedores, productos=productos, hoy=date.today().isoformat())


# ===== Gastos =====
@app.route('/gastos')
@login_required
@admin_required
def gastos_lista():
    conn = get_db()
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    cat = request.args.get('categoria', '')
    sql = """SELECT g.*, cg.nombre as categoria_nombre, u.nombre as usuario_nombre
             FROM gastos g LEFT JOIN categorias_gastos cg ON cg.id=g.categoria_id
             LEFT JOIN usuarios u ON u.id=g.usuario_id WHERE 1=1"""
    params = []
    if desde: sql += " AND date(g.fecha)>=?"; params.append(desde)
    if hasta: sql += " AND date(g.fecha)<=?"; params.append(hasta)
    if cat: sql += " AND g.categoria_id=?"; params.append(int(cat))
    sql += " ORDER BY g.fecha DESC, g.id DESC"
    gastos = conn.execute(sql, params).fetchall()
    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    total = sum(g['monto'] for g in gastos)
    conn.close()
    return render_template('gastos/lista.html', gastos=gastos, categorias=categorias, total=total,
                           desde=desde, hasta=hasta, categoria=cat)


@app.route('/gastos/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def gastos_nuevo():
    conn = get_db()
    if request.method == 'POST':
        try:
            monto = float(request.form['monto'])
        except (ValueError, KeyError):
            conn.close(); flash('Monto invalido.', 'error'); return redirect(url_for('gastos_nuevo'))
        cat_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        fecha = request.form.get('fecha') or date.today().isoformat()
        conn.execute("INSERT INTO gastos (fecha,categoria_id,descripcion,monto,usuario_id) VALUES (?,?,?,?,?)",
                     (fecha, cat_id, request.form.get('descripcion', '').strip(), monto, current_user.id))
        conn.commit(); conn.close()
        flash('Gasto registrado.', 'success')
        return redirect(url_for('gastos_lista'))
    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('gastos/form.html', gasto=None, categorias=categorias, hoy=date.today().isoformat())


@app.route('/gastos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def gastos_editar(id):
    conn = get_db()
    gasto = conn.execute("SELECT * FROM gastos WHERE id=?", (id,)).fetchone()
    if not gasto:
        conn.close(); return redirect(url_for('gastos_lista'))
    if request.method == 'POST':
        try:
            monto = float(request.form['monto'])
        except (ValueError, KeyError):
            conn.close(); flash('Monto invalido.', 'error'); return redirect(url_for('gastos_editar', id=id))
        cat_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        conn.execute("UPDATE gastos SET fecha=?,categoria_id=?,descripcion=?,monto=? WHERE id=?",
                     (request.form.get('fecha') or date.today().isoformat(), cat_id,
                      request.form.get('descripcion', '').strip(), monto, id))
        conn.commit(); conn.close()
        flash('Gasto actualizado.', 'success')
        return redirect(url_for('gastos_lista'))
    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('gastos/form.html', gasto=gasto, categorias=categorias, hoy=gasto['fecha'])


@app.route('/gastos/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def gastos_eliminar(id):
    conn = get_db()
    conn.execute("DELETE FROM gastos WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Gasto eliminado.', 'success')
    return redirect(url_for('gastos_lista'))


@app.route('/categorias-gastos', methods=['GET', 'POST'])
@login_required
@admin_required
def categorias_gastos():
    conn = get_db()
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        if nombre:
            try:
                conn.execute("INSERT INTO categorias_gastos (nombre) VALUES (?)", (nombre,))
                conn.commit()
                flash('Categoria creada.', 'success')
            except Exception:
                flash('Esa categoria ya existe.', 'error')
        return redirect(url_for('categorias_gastos'))
    cats = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('categorias_gastos/lista.html', categorias=cats)


@app.route('/categorias-gastos/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def categorias_gastos_eliminar(id):
    conn = get_db()
    conn.execute("UPDATE categorias_gastos SET activo=0 WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Categoria desactivada.', 'success')
    return redirect(url_for('categorias_gastos'))


# ===== Reportes =====
@app.route('/reportes')
@login_required
@admin_required
def reportes():
    conn = get_db()
    tipo = request.args.get('tipo', 'mes')
    fecha_ref = request.args.get('fecha', '')
    ini, fin = calcular_periodo(tipo, fecha_ref if fecha_ref else None)
    cierre = calcular_cierre(conn, ini, fin)
    ini_p, fin_p = periodo_anterior(tipo, ini, fin)
    cierre_p = calcular_cierre(conn, ini_p, fin_p)
    conn.close()
    return render_template('reportes/index.html',
                           tipo=tipo, fecha_ref=fecha_ref,
                           ini=ini, fin=fin, cierre=cierre,
                           ini_p=ini_p, fin_p=fin_p, cierre_p=cierre_p,
                           pct=pct)


@app.route('/reportes/cierres')
@login_required
@admin_required
def reportes_cierres():
    conn = get_db()
    cierres = conn.execute("SELECT * FROM cierres ORDER BY fecha_desde DESC, id DESC LIMIT 200").fetchall()
    conn.close()
    return render_template('reportes/cierres.html', cierres=cierres)


@app.route('/reportes/cierres/guardar', methods=['POST'])
@login_required
@admin_required
def reportes_cierres_guardar():
    conn = get_db()
    tipo = request.form.get('tipo', 'mes')
    ini, fin = calcular_periodo(tipo, request.form.get('fecha') or None)
    cierre = calcular_cierre(conn, ini, fin)
    conn.execute("""INSERT INTO cierres
        (tipo, fecha_desde, fecha_hasta, stock_unidades, saldo_inicial, total_vendido,
         total_gastado, saldo_actual, a_cobrar, a_pagar)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (tipo, ini.isoformat(), fin.isoformat(), cierre['stock_fin'], cierre['saldo_inicio'],
         cierre['ventas'], cierre['egresos'], cierre['saldo_fin'], cierre['a_cobrar'], 0))
    conn.commit(); conn.close()
    flash('Cierre guardado.', 'success')
    return redirect(url_for('reportes_cierres'))


if __name__ == '__main__':
    init_db()
    print("=== Sistema Familia Zaragoza (app3) ===")
    print("Abrir: http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)
