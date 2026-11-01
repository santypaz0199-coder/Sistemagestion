
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app32 import app
from app import permiso_required
from database import get_db
from app16 import _guardar_foto, _categorias_arbol


def _peso_data(form):
    try:
        pv = float(form.get('peso_valor') or 0)
    except ValueError:
        pv = 0
    return pv, form.get('peso_unidad', 'kg')


def _costo_variable(form):
    tiene = 1 if form.get('tiene_costo_variable') else 0
    try:
        cv = float(form.get('costo_variable_unitario') or 0)
    except ValueError:
        cv = 0
    if not tiene:
        cv = 0
    return tiene, cv


def productos_nuevo_v5():
    conn = get_db()
    padres, hijos = _categorias_arbol(conn)
    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_actual = float(request.form.get('stock_actual') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor, peso_unidad = _peso_data(request.form)
            tiene_cv, cv_unit = _costo_variable(request.form)
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form,
                                   padres=padres, hijos=hijos)
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form,
                                   padres=padres, hijos=hijos)
        if sku and conn.execute("SELECT id FROM productos WHERE sku=?", (sku,)).fetchone():
            flash('SKU ya existe.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form,
                                   padres=padres, hijos=hijos)

        foto_nombre, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form,
                                   padres=padres, hijos=hijos)

        cur = conn.execute("""INSERT INTO productos
            (sku, nombre, costo, precio, stock_actual, stock_minimo,
             peso_valor, peso_unidad, categoria_id, foto, actualizado,
             tiene_costo_variable, costo_variable_unitario)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'), ?, ?)""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo,
             peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit))
        if stock_actual > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (cur.lastrowid, 'ajuste_inicial', stock_actual, 'Carga inicial', current_user.id))
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=None, valores={},
                           padres=padres, hijos=hijos)


def productos_editar_v5(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))
    producto = dict(row)
    padres, hijos = _categorias_arbol(conn)

    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor, peso_unidad = _peso_data(request.form)
            tiene_cv, cv_unit = _costo_variable(request.form)
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)
        if sku and conn.execute("SELECT id FROM productos WHERE sku=? AND id!=?", (sku, id)).fetchone():
            flash('SKU ya existe en otro producto.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)

        foto_nombre = producto.get('foto')
        if request.form.get('eliminar_foto') == '1':
            if foto_nombre:
                try: os.remove(os.path.join(BASE_UPLOADS, foto_nombre))
                except Exception: pass
            foto_nombre = None
        nueva_foto, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)
        if nueva_foto:
            if foto_nombre:
                try: os.remove(os.path.join(BASE_UPLOADS, foto_nombre))
                except Exception: pass
            foto_nombre = nueva_foto

        conn.execute("""UPDATE productos SET sku=?, nombre=?, costo=?, precio=?,
            stock_minimo=?, peso_valor=?, peso_unidad=?, categoria_id=?, foto=?,
            actualizado=datetime('now'), tiene_costo_variable=?, costo_variable_unitario=?
            WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad,
             categoria_id, foto_nombre, tiene_cv, cv_unit, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={},
                           padres=padres, hijos=hijos)


import os
BASE_UPLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'productos')

app.view_functions['productos_nuevo'] = productos_nuevo_v5
app.view_functions['productos_editar'] = productos_editar_v5


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
