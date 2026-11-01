
import os
from datetime import date
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app15 import app
from app import permiso_required, admin_required
from database import get_db

BASE = os.path.dirname(os.path.abspath(__file__))
FOTOS_DIR = os.path.join(BASE, 'uploads', 'productos')
os.makedirs(FOTOS_DIR, exist_ok=True)

EXT_VALIDAS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def _categorias_arbol(conn):
    cats = conn.execute("SELECT * FROM categorias_productos WHERE activo=1 ORDER BY nombre").fetchall()
    padres = [c for c in cats if not c['parent_id']]
    hijos = {}
    for c in cats:
        if c['parent_id']:
            hijos.setdefault(c['parent_id'], []).append(c)
    return padres, hijos


def _stats_productos(conn):
    total = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1").fetchone()[0]
    sin_foto = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1 AND (foto IS NULL OR foto='')").fetchone()[0]
    sin_precio = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1 AND (precio IS NULL OR precio=0)").fetchone()[0]
    agotados = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1 AND stock_actual <= 0").fetchone()[0]
    bajo_stock = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1 AND stock_minimo>0 AND stock_actual<=stock_minimo AND stock_actual>0").fetchone()[0]
    return {'total': total, 'sin_foto': sin_foto, 'sin_precio': sin_precio,
            'agotados': agotados, 'bajo_stock': bajo_stock}


def _guardar_foto(file):
    if not file or not file.filename:
        return None, None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in EXT_VALIDAS:
        return None, f'Formato no permitido. Usa: {", ".join(EXT_VALIDAS)}'
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE:
        return None, 'La imagen supera 5 MB.'
    nombre = f"{date.today().isoformat()}_{secure_filename(file.filename)}"
    # Asegurar nombre unico
    contador = 1
    base, extension = os.path.splitext(nombre)
    while os.path.exists(os.path.join(FOTOS_DIR, nombre)):
        nombre = f"{base}_{contador}{extension}"
        contador += 1
    file.save(os.path.join(FOTOS_DIR, nombre))
    return nombre, None


@app.route('/productos/categorias')
@login_required
@permiso_required('productos')
def productos_categorias():
    conn = get_db()
    padres, hijos = _categorias_arbol(conn)
    conn.close()
    return render_template('productos/categorias.html', padres=padres, hijos=hijos)


@app.route('/productos/categorias/nueva', methods=['POST'])
@login_required
@permiso_required('productos')
def productos_categorias_nueva():
    nombre = request.form.get('nombre', '').strip()
    parent_id = request.form.get('parent_id', '').strip()
    if not nombre:
        flash('El nombre es obligatorio.', 'error')
        return redirect(url_for('productos_categorias'))
    conn = get_db()
    conn.execute("INSERT INTO categorias_productos (nombre, parent_id) VALUES (?, ?)",
                 (nombre, int(parent_id) if parent_id else None))
    conn.commit(); conn.close()
    flash('Categoria creada.', 'success')
    return redirect(url_for('productos_categorias'))


@app.route('/productos/categorias/<int:id>/eliminar', methods=['POST'])
@login_required
@permiso_required('productos')
def productos_categorias_eliminar(id):
    conn = get_db()
    # Desactivar categoria y sus hijas
    conn.execute("UPDATE categorias_productos SET activo=0 WHERE id=? OR parent_id=?", (id, id))
    # Desvincular productos
    conn.execute("UPDATE productos SET categoria_id=NULL WHERE categoria_id=?", (id,))
    conn.commit(); conn.close()
    flash('Categoria desactivada. Los productos quedaron sin categoria.', 'success')
    return redirect(url_for('productos_categorias'))


@app.route('/productos/foto/<path:nombre>')
@login_required
def productos_ver_foto(nombre):
    ruta = os.path.join(FOTOS_DIR, secure_filename(nombre))
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta)


@app.route('/productos')
@login_required
@permiso_required('productos')
def productos_lista_v2():
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
    sql += " ORDER BY p.nombre"
    productos = conn.execute(sql, params).fetchall()

    stats = _stats_productos(conn)
    padres, hijos = _categorias_arbol(conn)
    conn.close()
    return render_template('productos/lista.html',
                           productos=productos, q=q, categoria_id=categoria_id,
                           alerta=alerta, stats=stats, padres=padres, hijos=hijos)


@app.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def productos_nuevo_v3():
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
             peso_valor, peso_unidad, categoria_id, foto, actualizado)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo,
             peso_valor, peso_unidad, categoria_id, foto_nombre))
        if stock_actual > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (cur.lastrowid, 'ajuste_inicial', stock_actual, 'Carga inicial', current_user.id))
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))

    conn.close()
    return render_template('productos/form.html', producto=None, valores={},
                           padres=padres, hijos=hijos)


@app.route('/productos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def productos_editar_v4(id):
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
        # Eliminar foto si lo piden
        if request.form.get('eliminar_foto') == '1':
            if foto_nombre:
                try:
                    os.remove(os.path.join(FOTOS_DIR, foto_nombre))
                except Exception:
                    pass
            foto_nombre = None
        # Subir nueva foto si la hay
        nueva_foto, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)
        if nueva_foto:
            # Eliminar foto vieja
            if foto_nombre:
                try:
                    os.remove(os.path.join(FOTOS_DIR, foto_nombre))
                except Exception:
                    pass
            foto_nombre = nueva_foto

        conn.execute("""UPDATE productos SET sku=?, nombre=?, costo=?, precio=?,
            stock_minimo=?, peso_valor=?, peso_unidad=?, categoria_id=?, foto=?,
            actualizado=datetime('now') WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad,
             categoria_id, foto_nombre, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))

    conn.close()
    return render_template('productos/form.html', producto=producto, valores={},
                           padres=padres, hijos=hijos)


app.view_functions['productos_lista'] = productos_lista_v2
app.view_functions['productos_nuevo'] = productos_nuevo_v3
app.view_functions['productos_editar'] = productos_editar_v4


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
