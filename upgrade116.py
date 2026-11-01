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
    print(f"[upgrade116] escrito: {relpath}")


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
    <div class="cat-card">
      <!-- Zona clickeable para entrar al detalle -->
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
      
      <!-- Botón de añadir al carrito -->
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
    <p class="mt-3 text-muted-cat">No hay productos disponibles en este momento.</p>
  </div>
  {% endif %}
</div>
{% endblock %}
'''

def main():
    print("=== Upgrade 116: Devolver botón de Añadir al carrito en la portada ===")
    escribir('templates/catalogo/index.html', CATALOGO_INDEX)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")


if __name__ == '__main__':
    main()