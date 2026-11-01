# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_base_css():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Bloquear el scroll horizontal en todo el sitio
    if 'html { overflow-x: hidden; }' not in contenido:
        contenido = contenido.replace('<style>', '<style>\nhtml { overflow-x: hidden; }\nbody { overflow-x: hidden; }')
        print("[upgrade127] Scroll horizontal bloqueado en base.html")

    # 2. Quitar el padding-top del body para que la foto suba al techo
    # (y pasarlo al contenedor de contenido general para que no tape otras páginas)
    buscar_body = "body {\n  padding-top: 80px; /* Espacio para que el header fijo no tape el contenido */\n}"
    if buscar_body in contenido:
        contenido = contenido.replace(buscar_body, "body {\n  padding-top: 0;\n}")
        print("[upgrade127] padding-top eliminado del body")

    # Darle padding al .content para que las paginas internas no queden tapadas por el header
    buscar_content = ".content { margin-left: 245px; padding: 1.75rem 2.25rem; }"
    if buscar_content in contenido:
        contenido = contenido.replace(buscar_content, ".content { margin-left: 245px; padding: 80px 2.25rem 1.75rem 2.25rem; }")
    
    # Ojo: en el catalogo, la clase .container ya maneja sus margenes. 
    # Pero asegurémonos de que el main-content del catalogo no quede pegado.

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_index_html():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'index.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Ajustar el contenedor de la imagen para que llegue hasta el techo
    buscar_img = '''{% if portada_imagen %}
<div id="hero-image-container" style="width: 100%; transition: opacity 0.5s ease-out, transform 0.5s ease-out; overflow: hidden; margin-bottom: 2rem;">
  <img src="{{ url_for('ver_portada', nombre=portada_imagen) }}" style="width: 100%; height: auto; display: block;" alt="Portada">
</div>
{% endif %}'''

    nuevo_img = '''{% if portada_imagen %}
<div id="hero-image-container" style="width: 100%; max-width: 100vw; transition: opacity 0.5s ease-out; overflow: hidden; margin-bottom: 2rem;">
  <img src="{{ url_for('ver_portada', nombre=portada_imagen) }}" style="width: 100%; height: auto; display: block; object-fit: cover;" alt="Portada">
</div>
{% else %}
<div style="height: 80px;"></div> <!-- Espacio en blanco si no hay portada para que no tape el header -->
{% endif %}'''

    if buscar_img in contenido:
        contenido = contenido.replace(buscar_img, nuevo_img)
        print("[upgrade127] Contenedor de imagen ajustado (Full width real)")
    else:
        print("[upgrade127] ADVERTENCIA: no se encontró el bloque de la imagen")

    # 2. Arreglar el JS para que no haga Zoom (que causaba el scroll horizontal)
    buscar_js = '''            heroImg.style.opacity = opacity;
            // Efecto de zoom suave mientras se difumina
            heroImg.style.transform = `scale(${1 + (1 - opacity) * 0.05})`;'''
            
    nuevo_js = '''            heroImg.style.opacity = opacity;
            // Se eliminó el efecto zoom para evitar el scroll horizontal'''
            
    if buscar_js in contenido:
        contenido = contenido.replace(buscar_js, nuevo_js)
        print("[upgrade127] Efecto Zoom eliminado del JS (causaba scroll horizontal)")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 127: Fix Header sobre foto y Scroll Horizontal ===")
    patch_base_css()
    patch_index_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()