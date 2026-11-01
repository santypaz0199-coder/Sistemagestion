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
    print(f"[upgrade117] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        return
    conn = sqlite3.connect(db)
    
    # Agregar columna para activar el carrusel de recomendados
    cols = [r[1] for r in conn.execute("PRAGMA table_info(productos)").fetchall()]
    if 'mostrar_carrusel_recomendados' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN mostrar_carrusel_recomendados INTEGER DEFAULT 0")
        print("[upgrade117] + productos.mostrar_carrusel_recomendados")
        
    conn.commit(); conn.close()


APP117_PY = r'''
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
<label class="form-label">Costo del producto</label>
<input type="number" step="0.01" name="costo" id="costo-input" class="form-control" value="{{ v.get('costo', 0) or 0 }}" onchange="updateMargen()">
</div>
<div class="col-md-4">
<label class="form-label">Precio de venta</label>
<input type="number" step="0.01" name="precio" id="precio-input" class="form-control" value="{{ v.get('precio', 0) or 0 }}" onchange="updateMargen()">
</div>
<div class="col-md-4">
<label class="form-label">Stock minimo</label>
<input type="number" step="0.01" name="stock_minimo" class="form-control" value="{{ v.get('stock_minimo', 0) or 0 }}">
</div>

{% if not producto %}
<div class="col-md-4">
<label class="form-label">Stock inicial</label>
<input type="number" step="0.01" name="stock_actual" class="form-control" value="0">
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
</div>

<!-- CONFIGURACION DEL CARRUSEL -->
<div class="col-12 mt-4">
<div class="border rounded p-3" style="background:#f8f9fc; border-left: 4px solid #8b5cf6 !important;">
<div class="form-check form-switch mb-3">
<input class="form-check-input" type="checkbox" name="mostrar_carrusel_recomendados" id="mostrar_carrusel" value="1" {% if v.get('mostrar_carrusel_recomendados') %}checked{% endif %}>
<label class="form-check-label fw-bold text-dark" for="mostrar_carrusel">Mostrar carrusel 'Sumá a tu pedido' (Recomendados)</label>
</div>
<div class="form-text mb-2">Si está activo, los productos seleccionados abajo aparecerán como sugerencia cuando el cliente entre a este producto.</div>
<label class="form-label fw-semibold small text-primary">Seleccioná los productos recomendados:</label>
<select name="relacionados" class="form-select" multiple size="5" style="background:#fff;">
{% for tp in todos_productos %}
<option value="{{ tp.id }}" {% if tp.id in relacionados_actuales %}selected{% endif %}>{{ tp.nombre }}</option>
{% endfor %}
</select>
<div class="form-text text-danger mt-1"><i class="bi bi-info-circle"></i> Importante: Mantené apretada la tecla <strong>Ctrl</strong> (o Cmd en Mac) para elegir varios productos de la lista.</div>
</div>
</div>

<div class="col-12 mt-3">
<div class="form-check form-switch">
<input class="form-check-input" type="checkbox" name="mostrar_en_catalogo" id="mostrar_en_catalogo" value="1" {% if v.get('mostrar_en_catalogo') != 0 %}checked{% endif %}>
<label class="form-check-label fw-semibold" for="mostrar_en_catalogo">Mostrar en el catálogo público (B2B)</label>
</div>
</div>

<div class="col-12 mt-3">
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
</div>
</div>
</div>

<div class="col-12">
<div class="border rounded p-3" style="background:#f8f9fc;">
<div class="form-check mb-2">
<input class="form-check-input" type="checkbox" name="tiene_costo_variable" id="tiene_cv" {% if v.get('tiene_costo_variable') %}checked{% endif %} onchange="toggleCV()">
<label class="form-check-label fw-semibold" for="tiene_cv">
<i class="bi bi-box"></i> Este producto tiene costo variable adicional
</label>
</div>
<div id="bloque-cv" class="row g-2 mt-1" {% if not v.get('tiene_costo_variable') %}style="display:none;"{% endif %}>
<div class="col-md-4">
<label class="form-label">Costo variable por unidad</label>
<input type="number" step="0.01" min="0" name="costo_variable_unitario" id="cv-input" class="form-control" value="{{ v.get('costo_variable_unitario', 0) or 0 }}" onchange="updateMargen()">
</div>
<div class="col-md-8">
<div class="border rounded p-2" style="background:#fff;">
<div class="small text-muted mb-1">Costo total unitario</div>
<div class="fs-5 fw-semibold" id="costo-total-view">$0.00</div>
<div class="small" id="margen-view"></div>
</div>
</div>
</div>
</div>
</div>

</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>

<script>
function toggleCV() {
  const check = document.getElementById('tiene_cv');
  document.getElementById('bloque-cv').style.display = check.checked ? 'flex' : 'none';
  if (!check.checked) { document.getElementById('cv-input').value = 0; }
  updateMargen();
}
function updateMargen() {
  const costo = parseFloat(document.getElementById('costo-input').value) || 0;
  const cv = document.getElementById('tiene_cv').checked ? (parseFloat(document.getElementById('cv-input').value) || 0) : 0;
  const precio = parseFloat(document.getElementById('precio-input').value) || 0;
  const total = costo + cv;
  document.getElementById('costo-total-view').textContent = '$' + total.toFixed(2);
  const margen_view = document.getElementById('margen-view');
  if (precio > 0) {
    const margen = precio - total;
    const pct = (margen / precio * 100);
    const color = margen >= 0 ? 'text-success' : 'text-danger';
    margen_view.className = 'small ' + color;
    margen_view.innerHTML = 'Margen: <strong>$' + margen.toFixed(2) + '</strong> (' + pct.toFixed(1) + '%)';
  } else { margen_view.textContent = ''; }
}
document.addEventListener('DOMContentLoaded', () => { updateMargen(); });
</script>
{% endblock %}
'''

APP49_PY = r'''
from flask import Blueprint, render_template, abort, request
from database import get_db

catalogo_bp = Blueprint('catalogo', __name__, url_prefix='/catalogo',
                         template_folder='templates/catalogo')

def _categorias_arbol(conn):
    cats = conn.execute("SELECT * FROM categorias_productos WHERE activo=1 ORDER BY nombre").fetchall()
    padres = [c for c in cats if not c['parent_id']]
    hijos = {}
    for c in cats:
        if c['parent_id']:
            hijos.setdefault(c['parent_id'], []).append(c)
    return padres, hijos

@catalogo_bp.route('/')
def index():
    conn = get_db()
    padres, hijos = _categorias_arbol(conn)
    categoria_id = request.args.get('categoria', type=int)

    if categoria_id:
        cat = conn.execute("SELECT * FROM categorias_productos WHERE id=? AND activo=1", (categoria_id,)).fetchone()
        if not cat:
            conn.close(); abort(404)
        ids = [categoria_id] + [h['id'] for h in hijos.get(categoria_id, [])]
        placeholders = ','.join(['?'] * len(ids))
        productos = conn.execute(f"""
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.mostrar_en_catalogo=1 AND p.categoria_id IN ({placeholders})
            ORDER BY p.nombre
        """, ids).fetchall()
    else:
        productos = conn.execute("""
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.mostrar_en_catalogo=1
            ORDER BY p.nombre
        """).fetchall()

    conn.close()
    return render_template('catalogo/index.html', productos=productos, padres=padres, hijos=hijos, categoria_actual=categoria_id)

@catalogo_bp.route('/producto/<int:id>')
def producto_detalle(id):
    conn = get_db()
    producto = conn.execute("""
        SELECT p.*, c.nombre as categoria_nombre
        FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
        WHERE p.id=? AND p.activo=1 AND p.mostrar_en_catalogo=1
    """, (id,)).fetchone()
    if not producto:
        conn.close(); abort(404)
        
    relacionados = []
    if producto['mostrar_carrusel_recomendados'] == 1:
        relacionados = conn.execute("""
            SELECT p.* FROM productos p
            JOIN productos_relacionados pr ON pr.relacionado_id = p.id
            WHERE pr.producto_id = ? AND p.activo=1 AND p.mostrar_en_catalogo=1
        """, (id,)).fetchall()
    
    conn.close()
    return render_template('catalogo/producto.html', producto=producto, relacionados=relacionados)

from app51 import registro, login, logout, mi_cuenta
'''

RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 117: Carrusel con interruptor de activación ===")
    migrar()
    escribir('app117.py', APP117_PY)
    escribir('templates/productos/form.html', PRODUCTOS_FORM)
    escribir('app49.py', APP49_PY)
    
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
        
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()