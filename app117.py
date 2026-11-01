
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app115 import app
from app import permiso_required
from database import get_db
from app34 import _guardar_foto, _categorias_arbol
from datetime import date
import os

def _guardar_relacionados(conn, producto_id, relacionados_ids):
    conn.execute("DELETE FROM productos_relacionados WHERE producto_id=?", (producto_id,))
    for rid in relacionados_ids:
        try:
            rid_int = int(rid)
            if rid_int != producto_id:
                conn.execute("INSERT OR IGNORE INTO productos_relacionados (producto_id, relacionado_id) VALUES (?, ?)", (producto_id, rid_int))
        except ValueError:
            pass

def productos_nuevo_v9():
    conn = get_db()
    padres, hijos = _categorias_arbol(conn)
    todos_productos = conn.execute("SELECT id, nombre FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    
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
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
            tiene_cv = 1 if request.form.get('tiene_costo_variable') else 0
            cv_unit = float(request.form.get('costo_variable_unitario') or 0) if tiene_cv else 0
            mostrar_cat = 1 if request.form.get('mostrar_en_catalogo') else 0
            mostrar_carrusel = 1 if request.form.get('mostrar_carrusel_recomendados') else 0
            relacionados = request.form.getlist('relacionados')
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos, todos_productos=todos_productos, relacionados_actuales=[])
            
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos, todos_productos=todos_productos, relacionados_actuales=[])

        foto_nombre, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos, todos_productos=todos_productos, relacionados_actuales=[])

        cur = conn.execute("""INSERT INTO productos
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto, actualizado, tiene_costo_variable, costo_variable_unitario, mostrar_en_catalogo, mostrar_carrusel_recomendados)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'), ?, ?, ?, ?)""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit, mostrar_cat, mostrar_carrusel))
        
        pid = cur.lastrowid
        if stock_actual > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (pid, 'ajuste_inicial', stock_actual, 'Carga inicial', current_user.id))
                         
        _guardar_relacionados(conn, pid, relacionados)
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))
        
    conn.close()
    return render_template('productos/form.html', producto=None, valores={}, padres=padres, hijos=hijos, todos_productos=todos_productos, relacionados_actuales=[])

def productos_editar_v9(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))
    producto = dict(row)
    padres, hijos = _categorias_arbol(conn)
    todos_productos = conn.execute("SELECT id, nombre FROM productos WHERE activo=1 AND id!=? ORDER BY nombre", (id,)).fetchall()
    
    rel_rows = conn.execute("SELECT relacionado_id FROM productos_relacionados WHERE producto_id=?", (id,)).fetchall()
    relacionados_actuales = [r['relacionado_id'] for r in rel_rows]

    if request.method == 'POST':
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
            mostrar_carrusel = 1 if request.form.get('mostrar_carrusel_recomendados') else 0
            relacionados = request.form.getlist('relacionados')
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos, todos_productos=todos_productos, relacionados_actuales=relacionados_actuales)

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
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos, todos_productos=todos_productos, relacionados_actuales=relacionados_actuales)
            
        if nueva_foto:
            if foto_nombre:
                try: os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'productos', foto_nombre))
                except Exception: pass
            foto_nombre = nueva_foto

        conn.execute("""UPDATE productos SET sku=?, nombre=?, costo=?, precio=?,
            stock_minimo=?, peso_valor=?, peso_unidad=?, categoria_id=?, foto=?,
            actualizado=datetime('now'), tiene_costo_variable=?, costo_variable_unitario=?, mostrar_en_catalogo=?, mostrar_carrusel_recomendados=?
            WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit, mostrar_cat, mostrar_carrusel, id))
            
        _guardar_relacionados(conn, id, relacionados)
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
        
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={}, padres=padres, hijos=hijos, todos_productos=todos_productos, relacionados_actuales=relacionados_actuales)

app.view_functions['productos_nuevo'] = productos_nuevo_v9
app.view_functions['productos_editar'] = productos_editar_v9
