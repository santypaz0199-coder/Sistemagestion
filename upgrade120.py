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
    print(f"[upgrade120] escrito: {relpath}")


# 1. ACTUALIZAR BACKEND PARA ACEPTAR BÚSQUEDA
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
    busqueda = request.args.get('q', '').strip()

    # Datos para el encabezado de la tarjeta de subcategorías (si aplica)
    padre_actual = None
    subcats_actuales = []

    if categoria_id:
        cat = conn.execute("SELECT * FROM categorias_productos WHERE id=? AND activo=1", (categoria_id,)).fetchone()
        if not cat:
            conn.close(); abort(404)
            
        if cat['parent_id']:
            # Si tocó una subcategoría, buscamos los datos del padre para el título
            padre_actual = conn.execute("SELECT * FROM categorias_productos WHERE id=?", (cat['parent_id'],)).fetchone()
            subcats_actuales = hijos.get(cat['parent_id'], [])
        else:
            # Si tocó el padre, mostramos sus subcategorías
            padre_actual = cat
            subcats_actuales = hijos.get(cat['id'], [])
            
        ids = [categoria_id] + [h['id'] for h in hijos.get(categoria_id, [])]
        placeholders = ','.join(['?'] * len(ids))
        query = f"""
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.mostrar_en_catalogo=1 AND p.categoria_id IN ({placeholders})
        """
        params = ids
    else:
        query = """
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.mostrar_en_catalogo=1
        """
        params = []

    if busqueda:
        query += " AND (p.nombre LIKE ? OR p.sku LIKE ?)"
        params.extend([f'%{busqueda}%', f'%{busqueda}%'])

    query += " ORDER BY p.nombre"
    productos = conn.execute(query, params).fetchall()

    conn.close()
    return render_template('catalogo/index.html', 
                           productos=productos, 
                           padres=padres, 
                           hijos=hijos, 
                           categoria_actual=categoria_id,
                           padre_actual=padre_actual,
                           subcats_actuales=subcats_actuales,
                           busqueda=busqueda)

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

# 2. REESCRIBIR LA HOME CON EL DISEÑO DE LAS FOTOS
CATALOGO_INDEX = r'''{% extends "catalogo/base.html" %}
{% block title %}Catálogo — Familia Zaragoza ®{% endblock %}

{% block content %}
<style>
  /* Encabezado compacto */
  .hero-title {
    padding: 3rem 0 1.5rem;
    text-align: center;
  }
  .hero-title h1 {
    font-size: 2.5rem;
    font-weight: 300;
    letter-spacing: -0.02em;
    margin: 0;
    color: var(--cat-text);
  }
  .hero-title p {
    color: var(--cat-text-muted);
    font-size: 1rem;
    margin-top: .5rem;
  }

  /* Buscador */
  .search-container {
    max-width: 600px;
    margin: 0 auto 2rem;
    position: relative;
  }
  .search-input {
    width: 100%;
    background: var(--cat-surface);
    border: 1px solid var(--cat-border);
    border-radius: 30px;
    padding: 1rem 1.5rem;
    color: var(--cat-text);
    font-size: 1rem;
    padding-right: 3.5rem;
    outline: none;
    transition: border-color 0.2s;
  }
  .search-input:focus {
    border-color: var(--cat-accent);
  }
  .search-btn {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--cat-text-muted);
    font-size: 1.2rem;
    padding: 10px;
    cursor: pointer;
  }

  /* Píldoras de Categoría (Horizontal Scroll) */
  .pills-container {
    display: flex;
    overflow-x: auto;
    gap: 0.75rem;
    padding-bottom: 1rem;
    margin-bottom: 2rem;
    scrollbar-width: none; /* Ocultar scroll en Firefox */
  }
  .pills-container::-webkit-scrollbar {
    display: none; /* Ocultar scroll en Chrome */
  }
  .cat-pill {
    background: var(--cat-surface);
    border: 1px solid var(--cat-border);
    color: var(--cat-text-muted);
    padding: 0.6rem 1.5rem;
    border-radius: 30px;
    text-decoration: none;
    white-space: nowrap;
    font-size: 0.9rem;
    font-weight: 500;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .cat-pill:hover, .cat-pill.active {
    background: var(--cat-surface-2);
    border-color: var(--cat-accent);
    color: var(--cat-accent);
  }

  /* Tarjeta de Subcategorías (Estilo Foto 2) */
  .subcat-card {
    background: var(--cat-surface);
    border: 1px solid var(--cat-border);
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 2rem;
    position: relative;
  }
  .subcat-header {
    border-bottom: 1px solid var(--cat-border);
    padding-bottom: 1.5rem;
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .subcat-header h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0 0 0.25rem 0;
  }
  .subcat-header p {
    color: var(--cat-text-muted);
    font-size: 0.9rem;
    margin: 0;
  }
  .btn-close-subcat {
    background: var(--cat-surface-2);
    border: none;
    color: var(--cat-text-muted);
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    transition: all 0.2s;
  }
  .btn-close-subcat:hover {
    background: var(--cat-border);
    color: var(--cat-text);
  }
  .subcat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1rem;
  }
  .subcat-btn {
    background: var(--cat-surface-2);
    border: 1px solid var(--cat-border);
    border-radius: 12px;
    padding: 1rem 1.5rem;
    color: var(--cat-text);
    text-decoration: none;
    font-weight: 500;
    transition: all 0.2s;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .subcat-btn:hover {
    border-color: var(--cat-accent);
    color: var(--cat-accent);
  }
  .subcat-btn-ver-todo {
    background: rgba(201, 169, 110, 0.1);
    border-color: var(--cat-accent);
    color: var(--cat-accent);
    font-weight: 600;
  }
</style>

<div class="container">
  <!-- TÍTULO PRINCIPAL -->
  <div class="hero-title">
    <h1>Yerba Mate Premium</h1>
    <p>Elaborada con paciencia, siguiendo el tradicional método Barbacuá.</p>
  </div>

  <!-- BUSCADOR -->
  <div class="search-container">
    <form method="GET" action="{{ url_for('catalogo.index') }}">
      {% if categoria_actual %}<input type="hidden" name="categoria" value="{{ categoria_actual }}">{% endif %}
      <input type="text" name="q" class="search-input" placeholder="Buscar productos..." value="{{ busqueda }}">
      <button type="submit" class="search-btn"><i class="bi bi-search"></i></button>
    </form>
  </div>

  <!-- PÍLDORAS DE CATEGORÍA PADRE -->
  <div class="pills-container">
    <a href="{{ url_for('catalogo.index') }}" class="cat-pill {% if not categoria_actual %}active{% endif %}">
      <i class="bi bi-grid"></i> Todo
    </a>
    {% for p in padres %}
    <a href="{{ url_for('catalogo.index', categoria=p.id) }}" class="cat-pill {% if categoria_actual == p.id or (padre_actual and padre_actual.id == p.id) %}active{% endif %}">
      {{ p.nombre }}
      {% if hijos.get(p.id) %}<i class="bi bi-chevron-down" style="font-size:.7rem;"></i>{% endif %}
    </a>
    {% endfor %}
  </div>

  <!-- TARJETA DE SUBCATEGORÍAS (Si se seleccionó una categoría) -->
  {% if padre_actual and subcats_actuales %}
  <div class="subcat-card">
    <div class="subcat-header">
      <div>
        <h2>{{ padre_actual.nombre }}</h2>
        <p>Elija una subcategoría o vea todo</p>
      </div>
      <a href="{{ url_for('catalogo.index', q=busqueda) if busqueda else url_for('catalogo.index') }}" class="btn-close-subcat">
        <i class="bi bi-x-lg"></i>
      </a>
    </div>
    <div class="subcat-grid">
      <!-- Botón Ver Todo -->
      <a href="{{ url_for('catalogo.index', categoria=padre_actual.id) }}" class="subcat-btn subcat-btn-ver-todo">
        Vea todo de {{ padre_actual.nombre }}
        <i class="bi bi-arrow-right"></i>
      </a>
      <!-- Botones de Subcategorías -->
      {% for sub in subcats_actuales %}
      <a href="{{ url_for('catalogo.index', categoria=sub.id) }}" class="subcat-btn {% if categoria_actual == sub.id %}subcat-btn-ver-todo{% endif %}">
        {{ sub.nombre }}
      </a>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <!-- TÍTULO DE PRODUCTOS -->
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h3 style="font-weight:400; font-size:1.3rem; margin:0;">
      {% if busqueda %}
        Resultados para "{{ busqueda }}"
      {% elif categoria_actual %}
        {{ padre_actual.nombre }} 
        {% if categoria_actual != padre_actual.id %}
          <span style="color:var(--cat-text-muted);">/</span> {{ subcats_actuales|selectattr('id', 'equalto', categoria_actual)|map(attribute='nombre')|first|default('') }}
        {% endif %}
      {% else %}
        Todos los productos
      {% endif %}
    </h3>
  </div>

  <!-- GRILLA DE PRODUCTOS -->
  {% if productos %}
  <div class="cat-grid">
    {% for p in productos %}
    <div class="cat-card">
      <a href="{{ url_for('catalogo.producto_detalle', id=p.id) }}" style="text-decoration:none; color:inherit; display:flex; flex-direction:column; flex-grow:1;">
        <div class="cat-card-img">
          {% if p.foto %}<img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" alt="{{ p.nombre }}">
          {% else %}<i class="bi bi-image placeholder-icon"></i>{% endif %}
        </div>
        <div class="cat-card-body" style="padding-bottom:0;">
          {% if p.categoria_nombre %}<div class="cat-card-cat">{{ p.categoria_nombre }}</div>{% endif %}
          <div class="cat-card-title">{{ p.nombre }}</div>
          <div class="cat-card-price">{{ p.precio|pesos }}</div>
        </div>
      </a>
      <div style="padding: 1rem 1.5rem 1.5rem 1.5rem;">
        {% if current_mayorista %}
        <button class="cat-btn w-100 text-center" style="padding:.6rem; font-size:.9rem;" onclick="addToCartAjax({{ p.id }}, 1)">
          <i class="bi bi-cart-plus"></i> Añadir al carrito
        </button>
        {% else %}
        <a href="{{ url_for('catalogo.login') }}" class="cat-btn cat-btn-outline w-100 text-center" style="padding:.6rem; font-size:.9rem;">
          Ingresar para comprar
        </a>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="text-center py-5">
    <i class="bi bi-search" style="font-size:3rem; color:var(--cat-border);"></i>
    <p class="mt-3 text-muted-cat">No encontramos productos con esos filtros.</p>
    <a href="{{ url_for('catalogo.index') }}" class="cat-btn mt-3" style="padding:.5rem 1rem; font-size:.85rem;">Limpiar filtros</a>
  </div>
  {% endif %}

</div>
{% endblock %}
'''

def main():
    print("=== Upgrade 120: Nueva Home estilo tienda moderna ===")
    escribir('app49.py', APP49_PY)
    escribir('templates/catalogo/index.html', CATALOGO_INDEX)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()