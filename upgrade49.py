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
    print(f"[upgrade49] escrito: {relpath}")


APP49_PY = r'''
from flask import Blueprint, render_template, abort
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
        # Verificar que exista
        cat = conn.execute("SELECT * FROM categorias_productos WHERE id=? AND activo=1", (categoria_id,)).fetchone()
        if not cat:
            conn.close()
            abort(404)
        # Obtener productos de la categoria y sus hijas
        ids = [categoria_id] + [h['id'] for h in hijos.get(categoria_id, [])]
        placeholders = ','.join(['?'] * len(ids))
        productos = conn.execute(f"""
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.categoria_id IN ({placeholders})
            ORDER BY p.nombre
        """, ids).fetchall()
    else:
        productos = conn.execute("""
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1
            ORDER BY p.nombre
        """).fetchall()

    conn.close()
    return render_template('catalogo/index.html',
                           productos=productos,
                           padres=padres,
                           hijos=hijos,
                           categoria_actual=categoria_id)


@catalogo_bp.route('/producto/<int:id>')
def producto_detalle(id):
    conn = get_db()
    producto = conn.execute("""
        SELECT p.*, c.nombre as categoria_nombre
        FROM productos p
        LEFT JOIN categorias_productos c ON c.id = p.categoria_id
        WHERE p.id=? AND p.activo=1
    """, (id,)).fetchone()
    if not producto:
        conn.close()
        abort(404)
    conn.close()
    return render_template('catalogo/producto.html', producto=producto)
'''


CATALOGO_BASE = r'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{% block title %}Familia Zaragoza ® - Catálogo{% endblock %}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --cat-bg: #0a0a0a;
  --cat-surface: #141414;
  --cat-surface-2: #1c1c1c;
  --cat-border: #262626;
  --cat-text: #f0f0f0;
  --cat-text-muted: #8a8a8a;
  --cat-accent: #c9a96e; /* Dorado sutil inspirado en la yerba */
  --cat-accent-hover: #dfc08a;
}
* { -webkit-font-smoothing: antialiased; }
body {
  background: var(--cat-bg);
  color: var(--cat-text);
  font-family: 'Inter', system-ui, sans-serif;
  font-weight: 400;
  line-height: 1.6;
  min-height: 100vh;
}
/* Header */
.cat-header {
  padding: 2rem 0;
  border-bottom: 1px solid var(--cat-border);
  position: sticky;
  top: 0;
  background: rgba(10,10,10,.85);
  backdrop-filter: blur(12px);
  z-index: 100;
}
.cat-brand {
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: .15em;
  text-transform: uppercase;
  color: var(--cat-text);
  text-decoration: none;
}
.cat-brand:hover { color: var(--cat-accent); }
.cat-nav a {
  color: var(--cat-text-muted);
  text-decoration: none;
  font-size: .85rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: .08em;
  margin-left: 2rem;
  transition: color .2s;
}
.cat-nav a:hover, .cat-nav a.active { color: var(--cat-text); }
/* Hero */
.cat-hero {
  padding: 5rem 0 3rem;
  text-align: center;
}
.cat-hero h1 {
  font-size: 3rem;
  font-weight: 300;
  letter-spacing: -.02em;
  margin-bottom: 1rem;
}
.cat-hero p {
  color: var(--cat-text-muted);
  max-width: 500px;
  margin: 0 auto;
  font-size: 1rem;
}
/* Subcategorías */
.cat-subcats {
  display: flex;
  gap: .75rem;
  justify-content: center;
  flex-wrap: wrap;
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--cat-border);
}
.cat-subcats a {
  color: var(--cat-text-muted);
  text-decoration: none;
  font-size: .85rem;
  padding: .4rem 1rem;
  border: 1px solid var(--cat-border);
  border-radius: 20px;
  transition: all .2s;
}
.cat-subcats a:hover, .cat-subcats a.active {
  background: var(--cat-accent);
  border-color: var(--cat-accent);
  color: #0a0a0a;
}
/* Grid de productos */
.cat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 2rem;
  padding: 3rem 0;
}
.cat-card {
  background: var(--cat-surface);
  border: 1px solid var(--cat-border);
  border-radius: 12px;
  overflow: hidden;
  transition: transform .25s ease, border-color .25s ease;
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
}
.cat-card:hover {
  transform: translateY(-4px);
  border-color: var(--cat-accent);
  color: inherit;
}
.cat-card-img {
  aspect-ratio: 1;
  background: var(--cat-surface-2);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.cat-card-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform .4s ease;
}
.cat-card:hover .cat-card-img img { transform: scale(1.04); }
.cat-card-img .placeholder-icon {
  font-size: 3rem;
  color: var(--cat-border);
}
.cat-card-body {
  padding: 1.25rem 1.5rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.cat-card-cat {
  font-size: .7rem;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--cat-text-muted);
  margin-bottom: .4rem;
}
.cat-card-title {
  font-size: 1.05rem;
  font-weight: 500;
  margin-bottom: .75rem;
  line-height: 1.3;
}
.cat-card-price {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--cat-accent);
  margin-top: auto;
}
/* Detalle producto */
.cat-detail {
  padding: 4rem 0;
}
.cat-detail-img {
  aspect-ratio: 1;
  background: var(--cat-surface);
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cat-detail-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cat-detail-info h1 {
  font-size: 2rem;
  font-weight: 300;
  margin-bottom: .5rem;
}
.cat-detail-price {
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--cat-accent);
  margin: 1.5rem 0;
}
.cat-btn {
  background: var(--cat-accent);
  color: #0a0a0a;
  border: none;
  padding: .8rem 2rem;
  font-weight: 600;
  font-size: .9rem;
  text-transform: uppercase;
  letter-spacing: .05em;
  border-radius: 6px;
  transition: background .2s, transform .2s;
  text-decoration: none;
  display: inline-block;
}
.cat-btn:hover {
  background: var(--cat-accent-hover);
  color: #0a0a0a;
  transform: translateY(-2px);
}
.cat-btn-outline {
  background: transparent;
  border: 1px solid var(--cat-border);
  color: var(--cat-text);
}
.cat-btn-outline:hover {
  border-color: var(--cat-text);
  background: transparent;
}
/* Footer */
.cat-footer {
  padding: 3rem 0;
  border-top: 1px solid var(--cat-border);
  text-align: center;
  color: var(--cat-text-muted);
  font-size: .8rem;
  margin-top: 4rem;
}
/* Utilidades */
.text-muted-cat { color: var(--cat-text-muted) !important; }
</style>
{% block extra_head %}{% endblock %}
</head>
<body>

<!-- HEADER -->
<header class="cat-header">
  <div class="container d-flex justify-content-between align-items-center">
    <a href="{{ url_for('catalogo.index') }}" class="cat-brand">Familia Zaragoza ®</a>
    <nav class="cat-nav d-none d-md-flex">
      <a href="{{ url_for('catalogo.index') }}" class="{% if not categoria_actual %}active{% endif %}">Catálogo</a>
      {% for p in padres %}
      <a href="{{ url_for('catalogo.index', categoria=p.id) }}" class="{% if categoria_actual == p.id %}active{% endif %}">{{ p.nombre }}</a>
      {% endfor %}
    </nav>
    <div class="d-flex align-items-center gap-3">
      <a href="#" class="text-decoration-none text-muted-cat" title="Carrito (próximamente)"><i class="bi bi-bag fs-5"></i></a>
      <a href="#" class="cat-btn-outline cat-btn" style="padding:.4rem 1rem;font-size:.8rem;">Ingresar</a>
    </div>
  </div>
</header>

<!-- MAIN -->
<main>
  {% block content %}{% endblock %}
</main>

<!-- FOOTER -->
<footer class="cat-footer">
  <div class="container">
    <p class="mb-1">Familia Zaragoza ® — Yerba Mate Barbacuá</p>
    <p class="mb-0">© {{ now().year if now is defined else 2026 }} Todos los derechos reservados.</p>
  </div>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''


CATALOGO_INDEX = r'''{% extends "catalogo/base.html" %}

{% block title %}Catálogo — Familia Zaragoza ®{% endblock %}

{% block content %}
<!-- Hero -->
<section class="cat-hero">
  <div class="container">
    <h1>Catálogo</h1>
    <p>Yerba mate elaborada con paciencia, siguiendo el tradicional método Barbacuá.</p>
  </div>
</section>

<!-- Subcategorías (si estamos en una categoría padre) -->
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

<!-- Grid de productos -->
<div class="container">
  {% if productos %}
  <div class="cat-grid">
    {% for p in productos %}
    <a href="{{ url_for('catalogo.producto_detalle', id=p.id) }}" class="cat-card">
      <div class="cat-card-img">
        {% if p.foto %}
        <img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" alt="{{ p.nombre }}">
        {% else %}
        <i class="bi bi-image placeholder-icon"></i>
        {% endif %}
      </div>
      <div class="cat-card-body">
        {% if p.categoria_nombre %}
        <div class="cat-card-cat">{{ p.categoria_nombre }}</div>
        {% endif %}
        <div class="cat-card-title">{{ p.nombre }}</div>
        <div class="cat-card-price">${{ '%.2f'|format(p.precio) }}</div>
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
          {% if producto.foto %}
          <img src="{{ url_for('productos_ver_foto', nombre=producto.foto) }}" alt="{{ producto.nombre }}">
          {% else %}
          <i class="bi bi-image placeholder-icon" style="font-size:4rem;"></i>
          {% endif %}
        </div>
      </div>
      <div class="col-md-6">
        <div class="cat-detail-info">
          {% if producto.categoria_nombre %}
          <div class="cat-card-cat">{{ producto.categoria_nombre }}</div>
          {% endif %}
          <h1>{{ producto.nombre }}</h1>
          {% if producto.peso_valor %}
          <p class="text-muted-cat">{{ producto.peso_valor }}{{ producto.peso_unidad }}</p>
          {% endif %}
          <div class="cat-detail-price">${{ '%.2f'|format(producto.precio) }}</div>
          <p class="text-muted-cat mb-4">IVA no incluido. Precio sujeto a cambios sin previo aviso.</p>
          <div class="d-flex gap-3 flex-wrap">
            <a href="#" class="cat-btn"><i class="bi bi-bag-plus"></i> Agregar al pedido</a>
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


def main():
    print("=== Upgrade 49: Catálogo público minimalista (F6.1) ===")
    # Escribir el blueprint
    escribir('app49.py', APP49_PY)
    # Escribir templates
    escribir('templates/catalogo/base.html', CATALOGO_BASE)
    escribir('templates/catalogo/index.html', CATALOGO_INDEX)
    escribir('templates/catalogo/producto.html', CATALOGO_PRODUCTO)

    # Actualizar run.bat para importar app49 y registrar el blueprint
    run_bat_content = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat_content)

    print("\n=== LISTO ===")
    print("Ejecuta: run.bat")
    print("Luego abrí: http://127.0.0.1:5000/catalogo")


if __name__ == '__main__':
    main()