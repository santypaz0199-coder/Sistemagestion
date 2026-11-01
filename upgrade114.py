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
    print(f"[upgrade114] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        return
    conn = sqlite3.connect(db)
    
    # Columna para marcar si es de compra rapida
    cols = [r[1] for r in conn.execute("PRAGMA table_info(productos)").fetchall()]
    if 'compra_rapida' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN compra_rapida INTEGER DEFAULT 0")
        print("[upgrade114] + productos.compra_rapida")
        
    conn.commit(); conn.close()


APP114_PY = r'''
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

<div class="col-12">
<div class="border rounded p-3" style="background:#f8f9fc;">
<div class="form-check mb-2">
<input class="form-check-input" type="checkbox" name="tiene_costo_variable" id="tiene_cv" {% if v.get('tiene_costo_variable') %}checked{% endif %} onchange="toggleCV()">
<label class="form-check-label fw-semibold" for="tiene_cv">
<i class="bi bi-box"></i> Este producto tiene costo variable adicional
</label>
</div>
<div class="form-text mb-2">Ej: packaging, bolsa, flete logistico que pagas solo cuando vendes.</div>
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

<div class="col-12 mt-3">
<div class="form-check form-switch">
<input class="form-check-input" type="checkbox" name="mostrar_en_catalogo" id="mostrar_en_catalogo" value="1" {% if v.get('mostrar_en_catalogo') != 0 %}checked{% endif %}>
<label class="form-check-label fw-semibold" for="mostrar_en_catalogo">Mostrar en el catálogo público (B2B)</label>
</div>
</div>

<div class="col-12">
<div class="form-check form-switch">
<input class="form-check-input" type="checkbox" name="compra_rapida" id="compra_rapida" value="1" {% if v.get('compra_rapida') %}checked{% endif %}>
<label class="form-check-label fw-semibold text-success" for="compra_rapida"><i class="bi bi-lightning-charge-fill"></i> Incluir en "Compra Rápida" (Acceso directo en la portada)</label>
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
    
    # Productos para Compra Rápida
    destacados = []
    if not categoria_id:
        destacados = conn.execute("""
            SELECT p.*, c.nombre as categoria_nombre 
            FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.mostrar_en_catalogo=1 AND p.compra_rapida=1
            ORDER BY p.nombre
        """).fetchall()

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
    return render_template('catalogo/index.html', productos=productos, padres=padres, hijos=hijos, categoria_actual=categoria_id, destacados=destacados)

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
    conn.close()
    return render_template('catalogo/producto.html', producto=producto)

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

<!-- COMPRA RÁPIDA -->
{% if destacados %}
<div class="container mt-4">
  <div class="d-flex align-items-center gap-2 mb-3">
    <i class="bi bi-lightning-charge-fill text-warning fs-4"></i>
    <h3 style="font-weight:400; font-size:1.4rem; margin:0;">Compra Rápida</h3>
  </div>
  <div class="cat-grid" style="grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));">
    {% for p in destacados %}
    <div class="cat-card">
      <a href="{{ url_for('catalogo.producto_detalle', id=p.id) }}" style="text-decoration:none; color:inherit;">
        <div class="cat-card-img">
          {% if p.foto %}<img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" alt="{{ p.nombre }}">
          {% else %}<i class="bi bi-image placeholder-icon"></i>{% endif %}
        </div>
        <div class="cat-card-body" style="padding-bottom:0;">
          <div class="cat-card-title">{{ p.nombre }}</div>
          <div class="cat-card-price">{{ p.precio|pesos }}</div>
        </div>
      </a>
      <div style="padding: 1rem 1.5rem 1.5rem 1.5rem;">
        <button class="cat-btn w-100 text-center" style="padding:.6rem; font-size:.9rem;" onclick="addToCartAjax({{ p.id }}, 1)">
          <i class="bi bi-cart-plus"></i> Añadir al carrito
        </button>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
<div class="container mt-5 mb-2"><hr style="border-color:var(--cat-border);"></div>
{% endif %}

<!-- TODOS LOS PRODUCTOS -->
<div class="container">
  <h3 class="mt-4 mb-3" style="font-weight:300; font-size:1.6rem;">Todos los productos</h3>
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
<div class="cat-detail">
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
{% endblock %}
'''

def patch_catalogo_base_js():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'toast-cart' in contenido:
        return

    # Inyectar el HTML del Toast y el JS antes de cerrar </body>
    inyeccion = '''
<!-- TOAST NOTIFICACION -->
<div id="toast-container" style="position:fixed; top:30px; left:50%; transform:translateX(-50%); z-index:99999; pointer-events:none;">
  <div id="toast-cart" style="background:var(--cat-surface); border:1px solid var(--cat-accent); border-radius:12px; padding:12px 24px; color:var(--cat-text); box-shadow:0 8px 24px rgba(0,0,0,0.8); display:none; opacity:0; transition:all 0.3s ease; text-align:center; min-width:250px;">
    <i class="bi bi-check-circle-fill text-success fs-5 mb-1 d-block"></i>
    <span id="toast-text" style="font-weight:500; font-size:1.05rem;">Agregado al carrito</span>
    <div style="width:100%; height:3px; background:var(--cat-border); margin-top:10px; border-radius:3px; overflow:hidden;">
        <div id="toast-progress" style="width:0%; height:100%; background:var(--cat-accent);"></div>
    </div>
  </div>
</div>

<script>
function addToCartAjax(prodId, cantidad) {
  const formData = new FormData();
  formData.append('cantidad', cantidad);
  
  fetch('/catalogo/carrito/agregar/' + prodId, {
    method: 'POST',
    body: formData,
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
  .then(res => res.json())
  .then(data => {
    if (data.ok) {
      mostrarToast(data.mensaje);
      document.querySelectorAll('.carrito-count').forEach(el => el.textContent = data.count);
    } else {
      alert(data.error || 'Error al agregar');
    }
  })
  .catch(err => alert('Error de conexion al agregar'));
}

function mostrarToast(mensaje) {
  const toast = document.getElementById('toast-cart');
  const txt = document.getElementById('toast-text');
  const progress = document.getElementById('toast-progress');
  
  txt.textContent = mensaje;
  toast.style.display = 'block';
  
  // Reset progress
  progress.style.transition = 'none';
  progress.style.width = '0%';
  
  // Animate
  setTimeout(() => {
    toast.style.opacity = '1';
    progress.style.transition = 'width 1.8s linear';
    progress.style.width = '100%';
  }, 50);
  
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => { toast.style.display = 'none'; }, 300);
  }, 2200);
}
</script>
'''
    contenido = contenido.replace('</body>', inyeccion + '\n</body>')
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade114] Toast y AJAX agregados al catalogo base")

def patch_header_carrito():
    # Asegurarnos de que el contador del carrito use la clase correcta para actualizarse via JS
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
        
    buscar = '<span style="position:absolute;top:-6px;right:-8px;background:var(--cat-accent);color:#0a0a0a;font-size:.65rem;font-weight:700;border-radius:10px;padding:1px 6px;">{{ carrito_count|int }}</span>'
    nuevo = '<span class="carrito-count" style="position:absolute;top:-6px;right:-8px;background:var(--cat-accent);color:#0a0a0a;font-size:.65rem;font-weight:700;border-radius:10px;padding:1px 6px;">{{ carrito_count|int }}</span>'
    
    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade114] Contador de carrito preparado para AJAX")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app114; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 114: AJAX Carrito + Compra Rápida ===")
    migrar()
    escribir('app114.py', APP114_PY)
    escribir('templates/productos/form.html', PRODUCTOS_FORM)
    escribir('app49.py', APP49_PY)
    escribir('templates/catalogo/index.html', CATALOGO_INDEX)
    escribir('templates/catalogo/producto.html', CATALOGO_PRODUCTO)
    patch_catalogo_base_js()
    patch_header_carrito()
    
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
        
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()