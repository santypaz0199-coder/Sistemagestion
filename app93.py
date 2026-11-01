
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required
from database import get_db
from app34 import _guardar_foto, _categorias_arbol
from datetime import date
import os

# Reemplazamos las funciones de crear y editar producto para incluir el check de catalogo
def productos_nuevo_v6():
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
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
            tiene_cv = 1 if request.form.get('tiene_costo_variable') else 0
            cv_unit = float(request.form.get('costo_variable_unitario') or 0) if tiene_cv else 0
            mostrar_cat = 1 if request.form.get('mostrar_en_catalogo') else 0
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)
        
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)
            
        if sku and conn.execute("SELECT id FROM productos WHERE sku=?", (sku,)).fetchone():
            flash('SKU ya existe.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)

        foto_nombre, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)

        cur = conn.execute("""INSERT INTO productos
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto, actualizado, tiene_costo_variable, costo_variable_unitario, mostrar_en_catalogo)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'), ?, ?, ?)""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit, mostrar_cat))
        
        if stock_actual > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (cur.lastrowid, 'ajuste_inicial', stock_actual, 'Carga inicial', current_user.id))
        
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=None, valores={}, padres=padres, hijos=hijos)


def productos_editar_v6(id):
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
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
            tiene_cv = 1 if request.form.get('tiene_costo_variable') else 0
            cv_unit = float(request.form.get('costo_variable_unitario') or 0) if tiene_cv else 0
            mostrar_cat = 1 if request.form.get('mostrar_en_catalogo') else 0
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)
        
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)
            
        if sku and conn.execute("SELECT id FROM productos WHERE sku=? AND id!=?", (sku, id)).fetchone():
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
            actualizado=datetime('now'), tiene_costo_variable=?, costo_variable_unitario=?, mostrar_en_catalogo=?
            WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit, mostrar_cat, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={}, padres=padres, hijos=hijos)


app.view_functions['productos_nuevo'] = productos_nuevo_v6
app.view_functions['productos_editar'] = productos_editar_v6

# ===== CATALOGO PDF =====
@app.route('/productos/catalogo-pdf', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def catalogo_pdf_seleccionar():
    conn = get_db()
    if request.method == 'POST':
        ids = request.form.getlist('productos')
        if not ids:
            flash('Seleccioná al menos un producto.', 'error')
            return redirect(url_for('catalogo_pdf_seleccionar'))
        
        placeholders = ','.join(['?'] * len(ids))
        productos = conn.execute(f"SELECT * FROM productos WHERE id IN ({placeholders})", ids).fetchall()
        
        # Datos de la empresa
        empresa = {}
        for k in ['empresa_nombre', 'empresa_telefono', 'empresa_email', 'empresa_web', 'empresa_logo']:
            row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
            empresa[k] = row['valor'] if row and row['valor'] else ''
        if not empresa['empresa_nombre']: empresa['empresa_nombre'] = 'Familia Zaragoza ®'
        
        conn.close()
        return render_template('productos/catalogo_pdf_print.html', productos=productos, empresa=empresa, generado=date.today())

    # GET
    productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('productos/catalogo_pdf_form.html', productos=productos)

if __name__ == '__main__':
    pass
