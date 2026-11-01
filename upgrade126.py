# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade126] escrito: {relpath}")


def patch_base_css():
    """Modifica el header para que sea transparente y se vuelva solido al scrollear."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade126] no existe catalogo/base.html")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Cambiar el CSS del header
    viejo_css = """.cat-header {
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--cat-border);
  position: sticky; top: 0;
  background: rgba(10,10,10,.85);
  backdrop-filter: blur(12px);
  z-index: 100;
}"""
    
    nuevo_css = """.cat-header {
  padding: 1.5rem 0;
  position: fixed; top: 0; width: 100%;
  background: transparent;
  border-bottom: 1px solid transparent;
  transition: all 0.4s ease;
  z-index: 1000;
}
.cat-header.scrolled {
  background: rgba(10,10,10,.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--cat-border);
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}
body {
  padding-top: 80px; /* Espacio para que el header fijo no tape el contenido */
}"""

    if viejo_css in contenido:
        contenido = contenido.replace(viejo_css, nuevo_css)
        print("[upgrade126] CSS del header actualizado")
    else:
        # Variante por si cambió un espacio
        patron = re.compile(r"\.cat-header\s*\{.*?\}", re.DOTALL)
        contenido, n = patron.subn(nuevo_css, contenido, count=1)
        if n > 0:
            print("[upgrade126] CSS del header actualizado (regex)")

    # 2. Inyectar el JS al final del body
    if 'header-scroll-js' not in contenido:
        js = '''
<script id="header-scroll-js">
document.addEventListener('DOMContentLoaded', function() {
    const header = document.querySelector('.cat-header');
    window.addEventListener('scroll', function() {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });
});
</script>
'''
        contenido = contenido.replace('</body>', js + '\n</body>')
        print("[upgrade126] JS de scroll inyectado en base.html")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_index_html():
    """Saca la imagen del contenedor para que sea full-width y agrega el efecto de desvanecimiento."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'index.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Mover la portada FUERA del .container para que ocupe todo el ancho
    buscar_portada = '''<div class="container">
  
  <!-- PORTADA DINÁMICA -->
  {% if portada_imagen %}
  <!-- Imagen limpia, sin texto encima -->
  <div style="width: 100%; border-radius: 16px; overflow: hidden; margin-top: 1rem; box-shadow: 0 8px 32px rgba(0,0,0,0.4);">
    <img src="{{ url_for('ver_portada', nombre=portada_imagen) }}" style="width: 100%; height: auto; display: block; object-fit: cover;" alt="Portada">
  </div>
  {% endif %}

  <!-- TEXTO DEBAJO DE LA PORTADA -->
  <div class="hero-title">'''

    nueva_portada = '''<!-- PORTADA DINÁMICA FULL WIDTH -->
{% if portada_imagen %}
<div id="hero-image-container" style="width: 100%; transition: opacity 0.5s ease-out, transform 0.5s ease-out; overflow: hidden; margin-bottom: 2rem;">
  <img src="{{ url_for('ver_portada', nombre=portada_imagen) }}" style="width: 100%; height: auto; display: block;" alt="Portada">
</div>
{% endif %}

<div class="container">
  <!-- TEXTO DEBAJO DE LA PORTADA -->
  <div class="hero-title">'''

    if buscar_portada in contenido:
        contenido = contenido.replace(buscar_portada, nueva_portada)
        print("[upgrade126] Portada movida fuera del contenedor (Full Width)")
    else:
        print("[upgrade126] ADVERTENCIA: No se encontró el bloque de portada exacto.")

    # 2. Inyectar el script de desvanecimiento antes del endblock
    if 'fade-hero-js' not in contenido:
        js_fade = '''
<script id="fade-hero-js">
document.addEventListener('DOMContentLoaded', function() {
    const heroImg = document.getElementById('hero-image-container');
    if (heroImg) {
        window.addEventListener('scroll', function() {
            let scrollY = window.scrollY;
            // La imagen empieza a desvanecerse después de 50px y desaparece a los 400px
            let opacity = 1 - ((scrollY - 50) / 350);
            if (opacity < 0) opacity = 0;
            if (opacity > 1) opacity = 1;
            
            heroImg.style.opacity = opacity;
            // Efecto de zoom suave mientras se difumina
            heroImg.style.transform = `scale(${1 + (1 - opacity) * 0.05})`;
        });
    }
});
</script>
{% endblock %}'''
        contenido = contenido.replace('{% endblock %}', js_fade)
        print("[upgrade126] JS de fade para la portada inyectado")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 126: Portada Full-Width y Header Transparente ===")
    patch_base_css()
    patch_index_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()