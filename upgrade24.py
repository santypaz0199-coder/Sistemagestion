# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade24] escrito: {relpath}")


APP23_PY = r'''
import os
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app22 import app
from app import permiso_required, admin_required
from database import get_db


def _mes_ant(hoy):
    if hoy.month == 1:
        return date(hoy.year-1, 12, 1), date(hoy.year-1, 12, 31)
    ini = date(hoy.year, hoy.month-1, 1)
    ult = date(hoy.year, hoy.month, 1) - timedelta(days=1)
    return ini, ult


def _var(curr, prev):
    if prev == 0:
        return None if curr == 0 else 100.0
    return ((curr - prev) / prev) * 100


def gastos_unificado():
    tab = request.args.get('tab', 'gastos')
    conn = get_db()
    hoy = date.today()
    ini_mes = hoy.replace(day=1).isoformat()
    ini_ant, fin_ant = _mes_ant(hoy)
    ini_ant_s, fin_ant_s = ini_ant.isoformat(), fin_ant.isoformat()

    gastos_mes = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha)>=?", (ini_mes,)).fetchone()[0]
    gastos_ant = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha) BETWEEN ? AND ?", (ini_ant_s, fin_ant_s)).fetchone()[0]
    compras_mes = conn.execute("SELECT COALESCE(SUM(total),0) FROM compras WHERE date(fecha)>=?", (ini_mes,)).fetchone()[0]
    compras_ant = conn.execute("SELECT COALESCE(SUM(total),0) FROM compras WHERE date(fecha) BETWEEN ? AND ?", (ini_ant_s, fin_ant_s)).fetchone()[0]

    stats = {
        'gastos_mes': gastos_mes, 'gastos_ant': gastos_ant,
        'compras_mes': compras_mes, 'compras_ant': compras_ant,
        'total_mes': gastos_mes + compras_mes,
        'total_ant': gastos_ant + compras_ant,
        'var_gastos': _var(gastos_mes, gastos_ant),
        'var_compras': _var(compras_mes, compras_ant),
        'var_total': _var(gastos_mes + compras_mes, gastos_ant + compras_ant),
    }

    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    proveedores_lista = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()

    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    cat_filtro = request.args.get('categoria', '')
    prov_filtro = request.args.get('proveedor', '')

    gastos = compras = proveedores = []
    if tab == 'gastos':
        sql = """SELECT g.*, cg.nombre as categoria_nombre, u.nombre as usuario_nombre
                 FROM gastos g LEFT JOIN categorias_gastos cg ON cg.id=g.categoria_id
                 LEFT JOIN usuarios u ON u.id=g.usuario_id WHERE 1=1"""
        params = []
        if desde: sql += " AND date(g.fecha)>=?"; params.append(desde)
        if hasta: sql += " AND date(g.fecha)<=?"; params.append(hasta)
        if cat_filtro: sql += " AND g.categoria_id=?"; params.append(int(cat_filtro))
        sql += " ORDER BY g.fecha DESC, g.id DESC"
        gastos = conn.execute(sql, params).fetchall()
    elif tab == 'compras':
        sql = """SELECT c.*, p.nombre as proveedor_nombre, u.nombre as usuario_nombre
                 FROM compras c LEFT JOIN proveedores p ON p.id=c.proveedor_id
                 LEFT JOIN usuarios u ON u.id=c.usuario_id WHERE 1=1"""
        params = []
        if desde: sql += " AND date(c.fecha)>=?"; params.append(desde)
        if hasta: sql += " AND date(c.fecha)<=?"; params.append(hasta)
        if prov_filtro: sql += " AND c.proveedor_id=?"; params.append(int(prov_filtro))
        sql += " ORDER BY c.id DESC"
        compras = conn.execute(sql, params).fetchall()
    else:
        proveedores = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()

    conn.close()
    return render_template('gastos/lista.html',
        tab=tab, stats=stats, gastos=gastos, compras=compras, proveedores=proveedores,
        categorias=categorias, proveedores_lista=proveedores_lista,
        desde=desde, hasta=hasta, cat_filtro=cat_filtro, prov_filtro=prov_filtro)


def compras_redirect():
    return redirect(url_for('gastos_lista', tab='compras'))


def proveedores_redirect():
    return redirect(url_for('gastos_lista', tab='proveedores'))


# Reemplazo de view_functions existentes
app.view_functions['gastos_lista'] = gastos_unificado
app.view_functions['compras_lista'] = compras_redirect
app.view_functions['proveedores_lista'] = proveedores_redirect


@app.route('/api/productos-por-proveedor/<int:pid>')
@login_required
def api_productos_por_proveedor(pid):
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id, p.nombre, p.sku, p.costo, p.stock_actual
        FROM productos p
        JOIN productos_proveedores pp ON pp.producto_id = p.id
        WHERE pp.proveedor_id = ? AND p.activo = 1
        ORDER BY p.nombre
    """, (pid,)).fetchall()
    conn.close()
    return jsonify([{'id': r['id'], 'nombre': r['nombre'], 'sku': r['sku'],
                     'costo': r['costo'], 'stock_actual': r['stock_actual']} for r in rows])


# === Proveedores (endpoints _v2 para evitar conflicto) ===
def proveedores_nuevo_v2():
    conn = get_db()
    productos_lista = conn.execute("SELECT id, nombre, sku FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('proveedores/form.html', proveedor=None, valores=request.form,
                                   productos_lista=productos_lista, productos_seleccionados=[])
        cur = conn.execute("INSERT INTO proveedores (nombre,cuit,contacto,telefono,email) VALUES (?,?,?,?,?)",
                     (nombre, request.form.get('cuit','').strip(), request.form.get('contacto','').strip(),
                      request.form.get('telefono','').strip(), request.form.get('email','').strip()))
        pid = cur.lastrowid
        for prod_id in request.form.getlist('productos'):
            try:
                conn.execute("INSERT OR IGNORE INTO productos_proveedores (producto_id, proveedor_id) VALUES (?, ?)",
                             (int(prod_id), pid))
            except: pass
        conn.commit(); conn.close()
        flash('Proveedor creado.', 'success')
        return redirect(url_for('gastos_lista', tab='proveedores'))
    conn.close()
    return render_template('proveedores/form.html', proveedor=None, valores={},
                           productos_lista=productos_lista, productos_seleccionados=[])


def proveedores_editar_v2(id):
    conn = get_db()
    prov = conn.execute("SELECT * FROM proveedores WHERE id=?", (id,)).fetchone()
    if not prov:
        conn.close(); return redirect(url_for('gastos_lista', tab='proveedores'))
    productos_lista = conn.execute("SELECT id, nombre, sku FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    prod_sel = [r[0] for r in conn.execute("SELECT producto_id FROM productos_proveedores WHERE proveedor_id=?", (id,)).fetchall()]

    if request.method == 'POST':
        conn.execute("UPDATE proveedores SET nombre=?,cuit=?,contacto=?,telefono=?,email=? WHERE id=?",
                     (request.form['nombre'].strip(), request.form.get('cuit','').strip(),
                      request.form.get('contacto','').strip(), request.form.get('telefono','').strip(),
                      request.form.get('email','').strip(), id))
        conn.execute("DELETE FROM productos_proveedores WHERE proveedor_id=?", (id,))
        for prod_id in request.form.getlist('productos'):
            try:
                conn.execute("INSERT OR IGNORE INTO productos_proveedores (producto_id, proveedor_id) VALUES (?, ?)",
                             (int(prod_id), id))
            except: pass
        conn.commit(); conn.close()
        flash('Proveedor actualizado.', 'success')
        return redirect(url_for('gastos_lista', tab='proveedores'))

    conn.close()
    return render_template('proveedores/form.html', proveedor=dict(prov), valores={},
                           productos_lista=productos_lista, productos_seleccionados=prod_sel)


def proveedores_eliminar_v2(id):
    conn = get_db()
    conn.execute("UPDATE proveedores SET activo=0 WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Proveedor desactivado.', 'success')
    return redirect(url_for('gastos_lista', tab='proveedores'))


# Registrar rutas con endpoints _v2 y SOBRESCRIBIR los originales
app.add_url_rule('/proveedores/nuevo', endpoint='proveedores_nuevo',
                 view_func=proveedores_nuevo_v2, methods=['GET', 'POST'])
app.add_url_rule('/proveedores/<int:id>/editar', endpoint='proveedores_editar',
                 view_func=proveedores_editar_v2, methods=['GET', 'POST'])
app.add_url_rule('/proveedores/<int:id>/eliminar', endpoint='proveedores_eliminar',
                 view_func=proveedores_eliminar_v2, methods=['POST'])


# === Compras ===
def compras_nueva_v2():
    conn = get_db()
    if request.method == 'POST':
        tipo = request.form.get('tipo', 'stock')
        prov_id = int(request.form['proveedor_id']) if request.form.get('proveedor_id') else None
        fecha = request.form.get('fecha') or date.today().isoformat()
        notas = request.form.get('notas', '').strip()
        cat_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None

        if tipo == 'stock':
            pids = request.form.getlist('producto_id')
            cants = request.form.getlist('cantidad')
            costos = request.form.getlist('costo')
            items = []
            for pid, c, co in zip(pids, cants, costos):
                if not pid or not c: continue
                try:
                    cf = float(c); cof = float(co)
                except ValueError: continue
                if cf <= 0: continue
                items.append({'pid': int(pid), 'cantidad': cf, 'costo': cof, 'sub': cf*cof})
            if not items:
                conn.close(); flash('Agrega productos de stock.', 'error')
                return redirect(url_for('compras_nueva'))
            total = sum(i['sub'] for i in items)
            cur = conn.execute("INSERT INTO compras (proveedor_id,fecha,total,usuario_id,notas,tipo,categoria_id) VALUES (?,?,?,?,?,?,?)",
                               (prov_id, fecha, total, current_user.id, notas, 'stock', cat_id))
            cid = cur.lastrowid
            for it in items:
                conn.execute("INSERT INTO compra_items (compra_id,producto_id,cantidad,costo_unitario) VALUES (?,?,?,?)",
                             (cid, it['pid'], it['cantidad'], it['costo']))
                conn.execute("UPDATE productos SET stock_actual=stock_actual+?, costo=? WHERE id=?",
                             (it['cantidad'], it['costo'], it['pid']))
                conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                             (it['pid'], 'entrada', it['cantidad'], f'Compra #{cid}', current_user.id))
            conn.commit(); conn.close()
            flash(f'Compra de stock #{cid} registrada. Stock actualizado.', 'success')
            return redirect(url_for('gastos_lista', tab='compras'))
        else:
            desc = request.form.get('descripcion', '').strip()
            try:
                monto = float(request.form.get('monto_insumo') or 0)
            except ValueError:
                monto = 0
            if not desc or monto <= 0:
                conn.close(); flash('Descripcion y monto obligatorios para insumo.', 'error')
                return redirect(url_for('compras_nueva'))
            cur = conn.execute("INSERT INTO compras (proveedor_id,fecha,total,usuario_id,notas,tipo,categoria_id) VALUES (?,?,?,?,?,?,?)",
                               (prov_id, fecha, monto, current_user.id, notas, 'insumo', cat_id))
            cid = cur.lastrowid
            conn.execute("INSERT INTO compra_items (compra_id,producto_id,descripcion,cantidad,costo_unitario) VALUES (?,?,?,?,?)",
                         (cid, None, desc, 1, monto))
            conn.commit(); conn.close()
            flash(f'Insumo #{cid} registrado.', 'success')
            return redirect(url_for('gastos_lista', tab='compras'))

    proveedores_lista = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()
    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    productos_todos = conn.execute("SELECT id, nombre, sku, costo FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('compras/nueva.html', proveedores=proveedores_lista,
                           categorias=categorias, hoy=date.today().isoformat(),
                           productos_todos=productos_todos)


app.view_functions['compras_nueva'] = compras_nueva_v2


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app23; app23.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 24: Fix endpoints duplicados de proveedores ===")
    escribir('app23.py', APP23_PY)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()