# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade16] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade16] sin DB."); return
    conn = sqlite3.connect(db)

    # Tabla categorias_productos (con parent_id para subcategorias)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categorias_productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            parent_id INTEGER,
            activo INTEGER DEFAULT 1,
            creado TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES categorias_productos(id) ON DELETE CASCADE
        )
    """)
    print("[upgrade16] tabla categorias_productos OK")

    # Columnas nuevas en productos
    cols = [r[1] for r in conn.execute("PRAGMA table_info(productos)").fetchall()]
    if 'categoria_id' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN categoria_id INTEGER")
        print("[upgrade16] + productos.categoria_id")
    if 'foto' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN foto TEXT")
        print("[upgrade16] + productos.foto")
    if 'actualizado' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN actualizado TEXT")
        print("[upgrade16] + productos.actualizado")

    conn.commit(); conn.close()


APP16_PY = r'''
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
'''


PRODUCTOS_LISTA = r'''{% extends "base.html" %}
{% block title %}Productos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Productos</h4>
<div>
<a href="{{ url_for('productos_categorias') }}" class="btn btn-outline-secondary"><i class="bi bi-tags"></i> Categorias</a>
<a href="{{ url_for('productos_nuevo') }}" class="btn btn-dark"><i class="bi bi-plus-lg"></i> Nuevo producto</a>
</div>
</div>

<!-- Contadores -->
<div class="row g-2 mb-3">
<div class="col-md-3"><div class="card-kpi"><div class="kpi-label">Total productos</div><div class="kpi-value">{{ stats.total }}</div></div></div>
<div class="col-md-3"><a href="{{ url_for('productos_lista', alerta='sin_foto') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #f59e0b;"><div class="kpi-label">Sin foto</div><div class="kpi-value">{{ stats.sin_foto }}</div></div></a></div>
<div class="col-md-3"><a href="{{ url_for('productos_lista', alerta='sin_precio') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #ef4444;"><div class="kpi-label">Sin precio</div><div class="kpi-value">{{ stats.sin_precio }}</div></div></a></div>
<div class="col-md-3"><a href="{{ url_for('productos_lista', alerta='agotado') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #6b7280;"><div class="kpi-label">Agotados</div><div class="kpi-value">{{ stats.agotados }}</div></div></a></div>
</div>

<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-4"><label class="form-label small text-muted">Buscar</label><input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="SKU o nombre"></div>
<div class="col-md-3"><label class="form-label small text-muted">Categoria</label>
<select name="categoria" class="form-select form-select-sm">
<option value="">Todas</option>
{% for p in padres %}
<option value="{{ p.id }}" {% if categoria_id==p.id|string %}selected{% endif %}>{{ p.nombre }}</option>
{% for h in hijos.get(p.id, []) %}
<option value="{{ h.id }}" {% if categoria_id==h.id|string %}selected{% endif %}>&nbsp;&nbsp;— {{ h.nombre }}</option>
{% endfor %}
{% endfor %}
</select></div>
<div class="col-md-3"><label class="form-label small text-muted">Alerta</label>
<select name="alerta" class="form-select form-select-sm">
<option value="">Todas</option>
<option value="sin_foto" {% if alerta=='sin_foto' %}selected{% endif %}>Sin foto</option>
<option value="sin_precio" {% if alerta=='sin_precio' %}selected{% endif %}>Sin precio</option>
<option value="agotado" {% if alerta=='agotado' %}selected{% endif %}>Agotados</option>
<option value="bajo_stock" {% if alerta=='bajo_stock' %}selected{% endif %}>Bajo stock</option>
</select></div>
<div class="col-md-2"><button class="btn btn-outline-secondary btn-sm w-100"><i class="bi bi-search"></i> Filtrar</button></div>
</div></form>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th width="60">Foto</th><th>SKU</th><th>Nombre</th><th>Categoria</th>
<th class="text-end">Precio</th><th class="text-end">Stock</th><th>Estado</th>
<th class="text-muted small">Creado</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for p in productos %}
<tr>
<td>
{% if p.foto %}
<img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" style="width:44px;height:44px;object-fit:cover;border-radius:8px;">
{% else %}
<div style="width:44px;height:44px;border-radius:8px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;color:#9ca3af;"><i class="bi bi-image"></i></div>
{% endif %}
</td>
<td class="text-muted small">{{ p.sku or '' }}</td>
<td class="fw-semibold">{{ p.nombre }}</td>
<td class="small">{% if p.parent_nombre %}{{ p.parent_nombre }} › {% endif %}{{ p.categoria_nombre or '—' }}</td>
<td class="text-end">{% if p.precio and p.precio > 0 %}${{ '%.2f'|format(p.precio) }}{% else %}<span class="text-danger small">Sin precio</span>{% endif %}</td>
<td class="text-end">
{% if p.stock_actual <= 0 %}<span class="badge bg-secondary">Agotado</span>
{% elif p.stock_minimo > 0 and p.stock_actual <= p.stock_minimo %}<span class="badge bg-danger">{{ '%g'|format(p.stock_actual) }}</span>
{% else %}<span class="badge bg-success">{{ '%g'|format(p.stock_actual) }}</span>{% endif %}
</td>
<td class="small text-muted">
{% if not p.foto %}<span class="badge bg-warning text-dark">Sin foto</span>{% endif %}
{% if not p.precio or p.precio == 0 %}<span class="badge bg-danger">Sin precio</span>{% endif %}
</td>
<td class="small text-muted">{{ p.creado[:10] if p.creado else '' }}</td>
<td class="text-end text-nowrap">
<a href="{{ url_for('productos_editar', id=p.id) }}" class="btn btn-sm btn-outline-secondary" title="Editar"><i class="bi bi-pencil"></i></a>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrarProducto({{ p.id }}, '{{ p.nombre }}')" title="Borrar"><i class="bi bi-trash"></i></button>
</td>
</tr>
{% else %}
<tr><td colspan="9" class="text-center text-muted py-4">Sin productos.</td></tr>
{% endfor %}
</tbody></table></div></div>

<div class="modal fade" id="borrarProductoModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="borrar-producto-form" method="post">
<div class="modal-header"><h6 class="modal-title">Borrar producto <span id="borrar-producto-nombre"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
{% if current_user.es_admin %}
<div class="alert alert-warning py-2 small mb-3"><i class="bi bi-exclamation-triangle"></i> Como admin, el producto se desactiva inmediatamente.</div>
{% else %}
<div class="alert alert-info py-2 small mb-3"><i class="bi bi-info-circle"></i> Se enviara una <strong>solicitud al admin</strong>.</div>
{% endif %}
<div class="mb-2"><label class="form-label">Motivo (opcional)</label><textarea name="motivo" class="form-control" rows="2"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">{% if current_user.es_admin %}Borrar{% else %}Enviar solicitud{% endif %}</button>
</div>
</form></div></div></div>

<script>
function openBorrarProducto(id, nombre) {
  document.getElementById('borrar-producto-form').action = '/productos/' + id + '/borrar';
  document.getElementById('borrar-producto-nombre').textContent = nombre;
  new bootstrap.Modal(document.getElementById('borrarProductoModal')).show();
}
</script>
{% endblock %}
'''


PRODUCTOS_FORM = r'''{% extends "base.html" %}
{% block title %}Producto{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if producto else 'Nuevo' }} producto</h4>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
{% set v = valores if valores else (producto if producto else {}) %}
<div class="card shadow-sm"><div class="card-body">
<form method="post" enctype="multipart/form-data">
<div class="row g-3">

<div class="col-md-4">
<label class="form-label">SKU</label>
<input name="sku" class="form-control" value="{{ v.get('sku') or '' }}">
</div>
<div class="col-md-8">
<label class="form-label">Nombre *</label>
<input name="nombre" class="form-control" required value="{{ v.get('nombre') or '' }}">
</div>

<div class="col-md-4">
<label class="form-label">Costo</label>
<input type="number" step="0.01" name="costo" class="form-control" value="{{ v.get('costo', 0) or 0 }}">
</div>
<div class="col-md-4">
<label class="form-label">Precio</label>
<input type="number" step="0.01" name="precio" class="form-control" value="{{ v.get('precio', 0) or 0 }}">
</div>
<div class="col-md-4">
<label class="form-label">Stock minimo</label>
<input type="number" step="0.01" name="stock_minimo" class="form-control" value="{{ v.get('stock_minimo', 0) or 0 }}">
</div>

{% if not producto %}
<div class="col-md-4">
<label class="form-label">Stock inicial</label>
<input type="number" step="0.01" name="stock_actual" class="form-control" value="0">
<div class="form-text">Solo al crear. Despues se ajusta por ventas/compras.</div>
</div>
{% endif %}

<div class="col-md-4">
<label class="form-label">Peso del producto</label>
<div class="input-group">
<input type="number" step="0.01" min="0" name="peso_valor" class="form-control" value="{{ v.get('peso_valor', 0) or 0 }}">
<select name="peso_unidad" class="form-select" style="max-width:80px;">
<option value="kg" {% if (v.get('peso_unidad') or 'kg') == 'kg' %}selected{% endif %}>kg</option>
<option value="g" {% if v.get('peso_unidad') == 'g' %}selected{% endif %}>g</option>
</select>
</div>
</div>

<div class="col-md-8">
<label class="form-label">Categoria</label>
<select name="categoria_id" class="form-select">
<option value="">— Sin categoria —</option>
{% for p in padres %}
<option value="{{ p.id }}" {% if v.get('categoria_id') == p.id %}selected{% endif %}>{{ p.nombre }}</option>
{% for h in hijos.get(p.id, []) %}
<option value="{{ h.id }}" {% if v.get('categoria_id') == h.id %}selected{% endif %}>&nbsp;&nbsp;— {{ h.nombre }}</option>
{% endfor %}
{% endfor %}
</select>
<a href="{{ url_for('productos_categorias') }}" class="small text-decoration-none">Gestionar categorias</a>
</div>

<div class="col-12">
<label class="form-label">Foto del producto</label>
<div class="d-flex align-items-start gap-3">
{% if producto and producto.get('foto') %}
<div>
<img src="{{ url_for('productos_ver_foto', nombre=producto.foto) }}" style="width:120px;height:120px;object-fit:cover;border-radius:12px;border:1px solid #e5e7eb;">
<div class="form-check mt-2">
<input class="form-check-input" type="checkbox" name="eliminar_foto" value="1" id="eliminar_foto">
<label class="form-check-label small text-danger" for="eliminar_foto">Eliminar foto actual</label>
</div>
</div>
{% endif %}
<div class="flex-grow-1">
<input type="file" name="foto" class="form-control" accept="image/png,image/jpeg,image/webp,image/gif">
<div class="form-text">JPG, PNG, WEBP o GIF. Max 5 MB.</div>
</div>
</div>
</div>

</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>
{% endblock %}
'''


CATEGORIAS_HTML = r'''{% extends "base.html" %}
{% block title %}Categorias{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Categorias de productos</h4>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">
<div class="col-md-5">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3">Nueva categoria</h6>
<form method="post" action="{{ url_for('productos_categorias_nueva') }}">
<div class="mb-2">
<label class="form-label small">Nombre *</label>
<input name="nombre" class="form-control" required placeholder="Ej: Yerbas">
</div>
<div class="mb-3">
<label class="form-label small">Padre (opcional)</label>
<select name="parent_id" class="form-select">
<option value="">— Sin padre (categoria principal) —</option>
{% for p in padres %}
<option value="{{ p.id }}">{{ p.nombre }}</option>
{% endfor %}
</select>
<div class="form-text">Deja vacio si es una categoria principal.</div>
</div>
<button class="btn btn-dark">Crear categoria</button>
</form>
</div></div>
</div>

<div class="col-md-7">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3">Estructura</h6>
{% if padres %}
{% for p in padres %}
<div class="border-bottom pb-2 mb-2">
<div class="d-flex justify-content-between align-items-center">
<div class="fw-semibold"><i class="bi bi-folder-fill text-warning"></i> {{ p.nombre }}</div>
<form method="post" action="{{ url_for('productos_categorias_eliminar', id=p.id) }}" onsubmit="return confirm('Eliminar {{ p.nombre }}? Las subcategorias y vinculos se perderan.')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
</div>
{% for h in hijos.get(p.id, []) %}
<div class="d-flex justify-content-between align-items-center ms-4 mt-1">
<div class="small"><i class="bi bi-folder text-secondary"></i> {{ h.nombre }}</div>
<form method="post" action="{{ url_for('productos_categorias_eliminar', id=h.id) }}" onsubmit="return confirm('Eliminar {{ h.nombre }}?')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
</div>
{% endfor %}
</div>
{% endfor %}
{% else %}
<p class="text-muted small mb-0">No hay categorias. Crea la primera a la izquierda.</p>
{% endif %}
</div></div>
</div>
</div>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app16; app16.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 16: Productos + Categorias + Fotos (F3.1) ===")
    migrar()
    escribir('app16.py', APP16_PY)
    escribir('templates/productos/lista.html', PRODUCTOS_LISTA)
    escribir('templates/productos/form.html', PRODUCTOS_FORM)
    escribir('templates/productos/categorias.html', CATEGORIAS_HTML)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app16.py)")


if __name__ == '__main__':
    main()