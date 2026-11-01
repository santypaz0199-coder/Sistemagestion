# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_catalogo_index():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'index.html')
    if not os.path.exists(ruta):
        print("[upgrade124] no existe catalogo/index.html")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # El bloque actual que tiene el texto sobre la imagen
    patron = re.compile(r'<!-- PORTADA DINÁMICA -->.*?{% endif %}', re.DOTALL)
    
    nueva_portada = '''<!-- PORTADA DINÁMICA -->
  {% if portada_imagen %}
  <!-- Imagen limpia, sin texto encima -->
  <div style="width: 100%; border-radius: 16px; overflow: hidden; margin-top: 1rem; margin-bottom: 2rem; box-shadow: 0 8px 32px rgba(0,0,0,0.4);">
    <img src="{{ url_for('ver_portada', nombre=portada_imagen) }}" style="width: 100%; height: auto; display: block; object-fit: cover;" alt="Portada">
  </div>
  {% endif %}

  <!-- Textos debajo de la portada -->
  <div class="hero-title" style="padding: 0 0 2rem 0; text-align: center;">
    <h1 style="font-size: 2.5rem; font-weight: 300; letter-spacing: -0.02em; margin: 0; color: var(--cat-text);">{{ portada_titulo }}</h1>
    {% if portada_subtitulo %}
    <p style="color: var(--cat-text-muted); font-size: 1.1rem; margin-top: .5rem; max-width: 700px; margin-left: auto; margin-right: auto; line-height: 1.5;">{{ portada_subtitulo }}</p>
    {% endif %}
  </div>'''

    contenido, n = patron.subn(nueva_portada, contenido)
    
    if n > 0:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade124] Home actualizada: Imagen limpia y texto debajo.")
    else:
        print("[upgrade124] ADVERTENCIA: No se encontró el bloque de portada anterior.")

def main():
    print("=== Upgrade 124: Portada limpia y texto reubicado ===")
    patch_catalogo_index()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()