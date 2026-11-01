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
    print(f"[upgrade121] escrito: {relpath}")


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
    cursor: pointer;
  }
  .cat-pill:hover, .cat-pill.active {
    background: var(--cat-surface-2);
    border-color: var(--cat-accent);
    color: var(--cat-accent);
  }

  /* Botones dentro del Modal de Subcategorías */
  .subcat-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }
  .subcat-btn {
    background: var(--cat-surface-2);
    border: 1px solid var(--cat-border);
    border-radius: 10px;
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
  /* Ajustes del modal para que se vea oscuro */
  .modal-content {
    background: var(--cat-surface) !important;
    border: 1px solid var(--cat-border) !important;
    border-radius: 16px !important;
  }
  .btn-close {
    filter: invert(1) !important;
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
      {% if hijos.get(p.id) %}
        <!-- Si tiene hijos, abrimos el modal con un botón -->
        <button type="button" class="cat-pill {% if categoria_actual == p.id or (padre_actual and padre_actual.id == p.id) %}active{% endif %}" onclick="abrirModalSubcat('{{ p.id }}', '{{ p.nombre }}')">
          {{ p.nombre }}
          <i class="bi bi-chevron-down" style="font-size:.7rem;"></i>
        </button>
      {% else %}
        <!-- Si NO tiene hijos, es un link normal -->
        <a href="{{ url_for('catalogo.index', categoria=p.id) }}" class="cat-pill {% if categoria_actual == p.id %}active{% endif %}">
          {{ p.nombre }}
        </a>
      {% endif %}
    {% endfor %}
  </div>

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

<!-- MODAL DE SUBCATEGORÍAS (Oculto por defecto) -->
<div class="modal fade" id="modalSubcats" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header border-0 pb-0">
        <div>
          <h4 class="modal-title" id="modalSubcatTitle" style="font-weight:600; color:var(--cat-text);">Categoría</h4>
          <p style="color:var(--cat-text-muted); font-size:.9rem; margin:0;">Elija una subcategoría o vea todo</p>
        </div>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body p-4">
        <div class="subcat-grid" id="modalSubcatList">
          <!-- Los botones se inyectan acá con JS -->
        </div>
      </div>
    </div>
  </div>
</div>

<!-- DATOS DE CATEGORÍAS EN JSON PARA JS -->
<script id="categorias-data" type="application/json">
{
  {% for p in padres %}
  "{{ p.id }}": {
    "nombre": "{{ p.nombre }}",
    "subcats": [
      {% for h in hijos.get(p.id, []) %}
        {"id": "{{ h.id }}", "nombre": "{{ h.nombre }}"} {% if not loop.last %},{% endif %}
      {% endfor %}
    ]
  } {% if not loop.last %},{% endif %}
  {% endfor %}
}
</script>

<script>
  const CATEGORIAS = JSON.parse(document.getElementById('categorias-data').textContent);
  const URL_BASE = "{{ url_for('catalogo.index') }}";

  function abrirModalSubcat(padreId, padreNombre) {
    const modalEl = document.getElementById('modalSubcats');
    const titleEl = document.getElementById('modalSubcatTitle');
    const listEl = document.getElementById('modalSubcatList');
    
    titleEl.textContent = padreNombre;
    listEl.innerHTML = '';

    // Botón "Ver todo"
    const btnTodo = document.createElement('a');
    btnTodo.href = URL_BASE + '?categoria=' + padreId;
    btnTodo.className = 'subcat-btn subcat-btn-ver-todo';
    btnTodo.innerHTML = 'Vea todo de ' + padreNombre + ' <i class="bi bi-arrow-right"></i>';
    listEl.appendChild(btnTodo);

    // Botones de subcategorías
    const subcats = CATEGORIAS[padreId].subcats || [];
    subcats.forEach(sub => {
      const btn = document.createElement('a');
      btn.href = URL_BASE + '?categoria=' + sub.id;
      btn.className = 'subcat-btn';
      btn.textContent = sub.nombre;
      listEl.appendChild(btn);
    });

    new bootstrap.Modal(modalEl).show();
  }
</script>
{% endblock %}
'''

def main():
    print("=== Upgrade 121: Modal Emergente para Subcategorías ===")
    escribir('templates/catalogo/index.html', CATALOGO_INDEX)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()