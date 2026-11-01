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
    print(f"[upgrade119] escrito: {relpath}")


CATALOGO_INDEX = r'''{% extends "catalogo/base.html" %}
{% block title %}Catálogo — Familia Zaragoza ®{% endblock %}

{% block content %}
<style>
  /* Banner Estático (Parallax) */
  .hero-parallax {
    background-image: linear-gradient(rgba(10,10,10,0.7), rgba(10,10,10,0.7)), url('https://images.unsplash.com/photo-1588691515915-9356e2001a1f?q=80&w=2000&auto=format&fit=crop');
    background-attachment: fixed;
    background-position: center;
    background-repeat: no-repeat;
    background-size: cover;
    height: 60vh;
    min-height: 400px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    border-bottom: 1px solid var(--cat-border);
  }
  .hero-parallax h1 {
    font-size: 4rem;
    font-weight: 300;
    color: #fff;
    letter-spacing: -0.02em;
    text-shadow: 0 4px 12px rgba(0,0,0,0.5);
    margin: 0;
  }

  /* Lista de Categorías estilo Menú */
  .cat-menu-container {
    background: var(--cat-surface);
    border: 1px solid var(--cat-border);
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 3rem;
  }
  .cat-menu-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.2rem 1.5rem;
    border-bottom: 1px solid var(--cat-border);
    text-decoration: none;
    color: var(--cat-text);
    transition: all 0.2s ease;
  }
  .cat-menu-item:last-child {
    border-bottom: none;
  }
  .cat-menu-item:hover {
    background: var(--cat-surface-2);
    padding-left: 2rem;
    color: var(--cat-accent);
  }
  .cat-menu-title {
    font-size: 1.1rem;
    font-weight: 500;
  }
  .cat-menu-sub {
    color: var(--cat-text-muted);
    font-size: 0.95rem;
  }
  .cat-menu-item:hover .cat-menu-sub {
    color: var(--cat-accent);
  }
</style>

<!-- BANNER PRINCIPAL -->
<section class="hero-parallax">
  <div class="container">
    <h1>Yerba Mate Premium</h1>
  </div>
</section>

<!-- CONTENIDO PRINCIPAL -->
<div style="background: var(--cat-bg); position: relative; z-index: 2; padding-top: 3rem;">
  <div class="container">
    
    <!-- CATEGORIAS Y SUBCATEGORIAS -->
    <div class="row">
      <div class="col-md-8 mx-auto">
        <h3 style="font-weight:300; font-size:1.6rem; margin-bottom:1.5rem; text-align:center;">Explorá nuestras variedades</h3>
        
        <div class="cat-menu-container">
          {% for padre in padres %}
            {% if hijos.get(padre.id) %}
              <!-- Tiene subcategorías: mostramos el padre y cada subcategoría como línea -->
              {% for hijo in hijos[padre.id] %}
              <a href="{{ url_for('catalogo.index', categoria=hijo.id) }}" class="cat-menu-item">
                <div>
                  <span class="cat-menu-title">{{ padre.nombre }}</span> 
                  <span style="color:var(--cat-border); margin: 0 10px;">/</span>
                  <span class="cat-menu-sub">{{ hijo.nombre }}</span>
                </div>
                <i class="bi bi-chevron-right text-muted"></i>
              </a>
              {% endfor %}
            {% else %}
              <!-- No tiene subcategorías: mostramos solo el padre -->
              <a href="{{ url_for('catalogo.index', categoria=padre.id) }}" class="cat-menu-item">
                <div>
                  <span class="cat-menu-title">{{ padre.nombre }}</span>
                </div>
                <i class="bi bi-chevron-right text-muted"></i>
              </a>
            {% endif %}
          {% endfor %}
        </div>
      </div>
    </div>

    <hr style="border-color: var(--cat-border); margin: 3rem 0;">

    <!-- TODOS LOS PRODUCTOS -->
    <div class="row">
      <div class="col-12 mb-4">
        <h3 style="font-weight:300; font-size:1.6rem;">
          {% if categoria_actual %}
            Productos filtrados
          {% else %}
            Todos los productos
          {% endif %}
        </h3>
      </div>
    </div>

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
      <i class="bi bi-box-seam fs-1 text-muted-cat"></i>
      <p class="mt-3 text-muted-cat">No hay productos disponibles en esta categoría.</p>
      <a href="{{ url_for('catalogo.index') }}" class="cat-btn mt-3" style="padding:.5rem 1rem; font-size:.85rem;">Ver todos los productos</a>
    </div>
    {% endif %}

  </div>
</div>
{% endblock %}
'''

def main():
    print("=== Upgrade 119: Nueva Home con Banner Fijo y Lista de Categorías ===")
    escribir('templates/catalogo/index.html', CATALOGO_INDEX)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()