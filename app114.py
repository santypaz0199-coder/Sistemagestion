
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app110 import app
from app import permiso_required
from database import get_db
from app34 import _guardar_foto, _categorias_arbol
from datetime import date
import os

def _procesar_form_producto(producto_existente=None):
    try:
        sku = request.form.get('sku', '').strip() or None
        nombre = request.form['nombre'].strip()
        costo = float(request.form.get('costo') or 0)
        precio = float(request.form.get('precio') or 0)
        stock_minimo = float(request.form.get('stock_minimo') or 0)
        peso_valor = float(request.form.get('peso_valor') or 0)
        peso_unidad = request.form.get('peso_unidad', 'kg')
        categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        tiene_cv = 1 if request.form.get('tiene_costo_variable') else 0
        cv_unit = float(request.form.get('costo_variable_unitario') or 0) if tiene_cv else 0
        mostrar_cat = 1 if request.form.get('mostrar_en_catalogo') else 0
        compra_rapida = 1 if request.form.get('compra_rapida') else 0
        
        stock_actual = 0
        if not producto_existente:
            stock_actual = float(request.form.get('stock_actual') or 0)
            
        return {
            'sku': sku, 'nombre': nombre, 'costo': costo, 'precio': precio,
            'stock_minimo': stock_minimo, 'peso_valor': peso_valor, 'peso_unidad': peso_unidad,
            'categoria_id': categoria_id, 'tiene_cv': tiene_cv, 'cv_unit': cv_unit,
            'mostrar_cat': mostrar_cat, 'compra_rapida': compra_rapida,
            'stock_actual': stock_actual
        }, None
    except ValueError:
        return None, 'Revisa los numeros ingresados.'

def productos_nuevo_v7():
    conn = get_db()
    padres, hijos = _categorias_arbol(conn)
    if request.method == 'POST':
        d, err = _procesar_form_producto()
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)
        
        if not d['nombre']:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)
            
        if d['sku'] and conn.execute("SELECT id FROM productos WHERE sku=?", (d['sku'],)).fetchone():
            flash('SKU ya existe.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)

        foto_nombre, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)

        cur = conn.execute("""INSERT INTO productos
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto, actualizado, tiene_costo_variable, costo_variable_unitario, mostrar_en_catalogo, compra_rapida)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'), ?, ?, ?, ?)""",
            (d['sku'], d['nombre'], d['costo'], d['precio'], d['stock_actual'], d['stock_minimo'], d['peso_valor'], d['peso_unidad'], d['categoria_id'], foto_nombre, d['tiene_cv'], d['cv_unit'], d['mostrar_cat'], d['compra_rapida']))
        
        if d['stock_actual'] > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (cur.lastrowid, 'ajuste_inicial', d['stock_actual'], 'Carga inicial', current_user.id))
        
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=None, valores={}, padres=padres, hijos=hijos)


def productos_editar_v7(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))
    producto = dict(row)
    padres, hijos = _categorias_arbol(conn)

    if request.method == 'POST':
        d, err = _procesar_form_producto(producto_existente=producto)
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)
        
        if not d['nombre']:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)
            
        if d['sku'] and conn.execute("SELECT id FROM productos WHERE sku=? AND id!=?", (d['sku'], id)).fetchone():
            flash('SKU ya existe en otro producto.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)

        foto_nombre = producto.get('foto')
        if request.form.get('eliminar_foto') == '1':
            if foto_nombre:
                try: os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'productos', foto_nombre))
                except Exception: pass
            foto_nombre = None
            
        nueva_foto, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)
            
        if nueva_foto:
            if foto_nombre:
                try: os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'productos', foto_nombre))
                except Exception: pass
            foto_nombre = nueva_foto

        conn.execute("""UPDATE productos SET sku=?, nombre=?, costo=?, precio=?,
            stock_minimo=?, peso_valor=?, peso_unidad=?, categoria_id=?, foto=?,
            actualizado=datetime('now'), tiene_costo_variable=?, costo_variable_unitario=?, mostrar_en_catalogo=?, compra_rapida=?
            WHERE id=?""",
            (d['sku'], d['nombre'], d['costo'], d['precio'], d['stock_minimo'], d['peso_valor'], d['peso_unidad'], d['categoria_id'], foto_nombre, d['tiene_cv'], d['cv_unit'], d['mostrar_cat'], d['compra_rapida'], id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={}, padres=padres, hijos=hijos)


app.view_functions['productos_nuevo'] = productos_nuevo_v7
app.view_functions['productos_editar'] = productos_editar_v7
