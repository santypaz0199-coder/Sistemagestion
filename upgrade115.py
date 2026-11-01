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
    print(f"[upgrade115] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        return
    conn = sqlite3.connect(db)
    
    # Tabla de relacionados (Muchos a Muchos)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS productos_relacionados (
            producto_id INTEGER NOT NULL,
            relacionado_id INTEGER NOT NULL,
            PRIMARY KEY (producto_id, relacionado_id),
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
            FOREIGN KEY (relacionado_id) REFERENCES productos(id) ON DELETE CASCADE
        )
    """)
    print("[upgrade115] tabla productos_relacionados OK")
    conn.commit(); conn.close()


APP115_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app114 import app
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

def productos_nuevo_v8():
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
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto, actualizado, tiene_costo_variable, costo_variable_unitario, mostrar_en_catalogo)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'), ?, ?, ?)""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit, mostrar_cat))
        
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

def productos_editar_v8(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))
    producto = dict(row)
    padres, hijos = _categorias_arbol(conn)
    todos_productos = conn.execute("SELECT id, nombre FROM productos WHERE activo=1 AND id!=? ORDER BY nombre", (id,)).fetchall()
    
    # Cargar relacionados actuales
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
            actualizado=datetime('now'), tiene_costo_variable=?, costo_variable_unitario=?, mostrar_en_catalogo=?
            WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit, mostrar_cat, id))
            
        _guardar_relacionados(conn, id, relacionados)
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
        
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={}, padres=padres, hijos=hijos, todos_productos=todos_productos, relacionados_actuales=relacionados_actuales)

app.view_functions['productos_nuevo'] = productos_nuevo_v8
app.view_functions['productos_editar'] = productos_editar_v8
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

<div class="col-md-12 mt-4">
<label class="form-label fw-bold text-primary"><i class="bi bi-star-fill"></i> Productos en el carrusel de recomendados</label>
<div class="form-text mb-2">Seleccioná los productos que querés que aparezcan abajo en el detalle de ESTE producto (Mantené apretada la tecla Ctrl para elegir varios).</div>
<select name="relacionados" class="form-select" multiple size="6" style="background:#f8f9fc;">
{% for tp in todos_productos %}
<option value="{{ tp.id }}" {% if tp.id in relacionados_actuales %}selected{% endif %}>{{ tp.nombre }}</option>
{% endfor %}
</select>
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
        
    # Cargar productos relacionados (el carrusel)
    relacionados = conn.execute("""
        SELECT p.* FROM productos p
        JOIN productos_relacionados pr ON pr.relacionado_id = p.id
        WHERE pr.producto_id = ? AND p.activo=1 AND p.mostrar_en_catalogo=1
    """, (id,)).fetchall()
    
    conn.close()
    return render_template('catalogo/producto.html', producto=producto, relacionados=relacionados)

from app51 import registro, login, logout, mi_cuenta
'''

CATALOGO_INDEX = r'''{% extends "catalogo/base.html" %}
{% block title %}Catálogo — Familia Zaragoza ®{% endblock %}

{% block content %}
<section class="cat-hero">
  <div class="container">
    <h1>Catálogo</h1>
    <p>Yerba mate elaborada con paciencia, siguiendo el tradicional método Barbacuá.</p>
  </div>
</section>

{% if categoria_actual and hijos.get(categoria_actual) %}
<div class="container">
  <div class="cat-subcats">
    <a href="{{ url_for('catalogo.index') }}">Todas</a>
    {% for h in hijos[categoria_actual] %}
    <a href="{{ url_for('catalogo.index', categoria=h.id) }}">{{ h.nombre }}</a>
    {% endfor %}
  </div>
</div>
{% endif %}

<!-- TODOS LOS PRODUCTOS -->
<div class="container mt-4">
  {% if productos %}
  <div class="cat-grid">
    {% for p in productos %}
    <a href="{{ url_for('catalogo.producto_detalle', id=p.id) }}" class="cat-card">
      <div class="cat-card-img">
        {% if p.foto %}<img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" alt="{{ p.nombre }}">
        {% else %}<i class="bi bi-image placeholder-icon"></i>{% endif %}
      </div>
      <div class="cat-card-body">
        {% if p.categoria_nombre %}<div class="cat-card-cat">{{ p.categoria_nombre }}</div>{% endif %}
        <div class="cat-card-title">{{ p.nombre }}</div>
        <div class="cat-card-price">{{ p.precio|pesos }}</div>
      </div>
    </a>
    {% endfor %}
  </div>
  {% else %}
  <div class="text-center py-5">
    <i class="bi bi-box-seam fs-1 text-muted-cat"></i>
    <p class="mt-3 text-muted-cat">No hay productos disponibles en este momento.</p>
  </div>
  {% endif %}
</div>
{% endblock %}
'''

CATALOGO_PRODUCTO = r'''{% extends "catalogo/base.html" %}
{% block title %}{{ producto.nombre }} — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="cat-detail" style="padding-bottom: 2rem;">
  <div class="container">
    <div class="row align-items-center g-5">
      <div class="col-md-6">
        <div class="cat-detail-img">
          {% if producto.foto %}<img src="{{ url_for('productos_ver_foto', nombre=producto.foto) }}" alt="{{ producto.nombre }}">
          {% else %}<i class="bi bi-image placeholder-icon" style="font-size:4rem;"></i>{% endif %}
        </div>
      </div>
      <div class="col-md-6">
        <div class="cat-detail-info">
          {% if producto.categoria_nombre %}<div class="cat-card-cat">{{ producto.categoria_nombre }}</div>{% endif %}
          <h1>{{ producto.nombre }}</h1>
          {% if producto.peso_valor %}<p class="text-muted-cat">{{ producto.peso_valor }}{{ producto.peso_unidad }}</p>{% endif %}
          <div class="cat-detail-price">{{ producto.precio|pesos }}</div>
          <p class="text-muted-cat mb-4">IVA no incluido. Precio sujeto a cambios sin previo aviso.</p>
          
          {% if current_mayorista %}
          <div class="d-flex gap-2 flex-wrap align-items-center mb-3">
            <div style="display:flex;align-items:center;gap:.5rem;background:var(--cat-surface-2);border:1px solid var(--cat-border);border-radius:8px;padding:.4rem;">
              <button type="button" onclick="cambiarCant(-1)" style="background:none;border:none;color:var(--cat-text);font-size:1.2rem;cursor:pointer;padding:0 .5rem;">−</button>
              <input type="number" id="cant-input" value="1" min="1" step="1" style="width:60px;text-align:center;background:none;border:none;color:var(--cat-text);font-weight:500;">
              <button type="button" onclick="cambiarCant(1)" style="background:none;border:none;color:var(--cat-text);font-size:1.2rem;cursor:pointer;padding:0 .5rem;">+</button>
            </div>
            <button type="button" class="cat-btn" onclick="addToCartAjax({{ producto.id }}, document.getElementById('cant-input').value)">
              <i class="bi bi-bag-plus"></i> Añadir al carrito
            </button>
          </div>
          <script>
          function cambiarCant(delta) {
            const input = document.getElementById('cant-input');
            let v = parseInt(input.value) || 1;
            v = Math.max(1, v + delta);
            input.value = v;
          }
          </script>
          {% else %}
          <div class="cat-alert cat-alert-info" style="font-size:.85rem;">
            <a href="{{ url_for('catalogo.login') }}">Ingresa a tu cuenta</a> para agregar productos al pedido.
          </div>
          {% endif %}
          
          <div class="d-flex gap-3 flex-wrap mt-3">
            <a href="{{ url_for('catalogo.index') }}" class="cat-btn cat-btn-outline"><i class="bi bi-arrow-left"></i> Seguir comprando</a>
          </div>
          <div class="mt-4 pt-4" style="border-top:1px solid var(--cat-border);">
            <p class="small text-muted-cat mb-1"><i class="bi bi-truck"></i> Envíos a todo el país.</p>
            <p class="small text-muted-cat mb-0"><i class="bi bi-shield-check"></i> Compra protegida.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- CARRUSEL DE RECOMENDADOS -->
{% if relacionados %}
<div style="border-top:1px solid var(--cat-border); padding-top:3rem; margin-top:1rem;">
  <div class="container">
    <h3 style="font-weight:300; font-size:1.6rem; margin-bottom:1.5rem; color:var(--cat-text);">
      <i class="bi bi-stars text-warning"></i> Sumá a tu pedido
    </h3>
    
    <div style="display:flex; overflow-x:auto; gap:1.5rem; padding-bottom:1rem; scroll-snap-type:x mandatory;">
      {% for rel in relacionados %}
      <div style="flex:0 0 240px; scroll-snap-align:start; background:var(--cat-surface); border:1px solid var(--cat-border); border-radius:12px; overflow:hidden; display:flex; flex-direction:column;">
        <a href="{{ url_for('catalogo.producto_detalle', id=rel.id) }}" style="text-decoration:none; color:inherit; display:flex; flex-direction:column; flex-grow:1;">
          <div style="aspect-ratio:1; background:var(--cat-surface-2); display:flex; align-items:center; justify-content:center;">
            {% if rel.foto %}<img src="{{ url_for('productos_ver_foto', nombre=rel.foto) }}" style="width:100%; height:100%; object-fit:cover;">
            {% else %}<i class="bi bi-image" style="font-size:2rem; color:var(--cat-border);"></i>{% endif %}
          </div>
          <div style="padding:1rem 1rem 0.5rem 1rem; flex-grow:1;">
            <div style="font-weight:500; font-size:.95rem; line-height:1.2; margin-bottom:.5rem;">{{ rel.nombre }}</div>
            <div style="color:var(--cat-accent); font-weight:600;">{{ rel.precio|pesos }}</div>
          </div>
        </a>
        <div style="padding:0 1rem 1rem 1rem;">
          <button class="cat-btn w-100 text-center" style="padding:.5rem; font-size:.8rem;" onclick="addToCartAjax({{ rel.id }}, 1)">
            <i class="bi bi-cart-plus"></i> Añadir
          </button>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>
</div>
{% endif %}
{% endblock %}
'''

RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app115; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 115: Carrusel de Productos Recomendados ===")
    migrar()
    escribir('app115.py', APP115_PY)
    escribir('templates/productos/form.html', PRODUCTOS_FORM)
    escribir('app49.py', APP49_PY)
    escribir('templates/catalogo/index.html', CATALOGO_INDEX)
    escribir('templates/catalogo/producto.html', CATALOGO_PRODUCTO)
    
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
        
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()