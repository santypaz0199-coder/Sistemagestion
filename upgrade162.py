# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_base_html():
    """Elimina el enlace de Catalogos del menu lateral."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar cualquier enlace que apunte a catalogos_index en el sidebar y borrarlo
    patron = re.compile(r'<a href="\{\{ url_for\(\'catalogos_index\'\) \}\}".*?</a>\n?', re.DOTALL)
    contenido, n = patron.subn('', contenido)
    
    if n > 0:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f"[upgrade162] Enlaces de Catálogos eliminados del menú lateral ({n} encontrados).")
    else:
        print("[upgrade162] No se encontró el enlace en el menú lateral (quizás ya estaba eliminado).")

def patch_configuracion_index():
    """Agrega la tarjeta de Catalogos en la pantalla de Configuracion."""
    ruta = os.path.join(BASE, 'templates', 'configuracion', 'index.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'catalogos_index' in contenido:
        print("[upgrade162] La tarjeta de Catálogos ya estaba en Configuración.")
        return

    # Tarjeta HTML para Catalogos
    tarjeta_catalogos = '''<div class="col-md-4"><a href="{{ url_for('catalogos_index') }}" class="text-decoration-none"><div class="card shadow-sm h-100" style="border-left:3px solid #8b5cf6;"><div class="card-body">
<i class="bi bi-tags fs-2" style="color:#8b5cf6;"></i>
<h6 class="mt-2">Catálogos</h6>
<p class="text-muted small mb-0">Canales de venta, medios de pago y transportistas.</p>
</div></div></a></div>
'''

    # Insertar justo antes de la tarjeta de "Remitentes y SMTP" o la primera que encontremos
    buscar = '<div class="col-md-4"><a href="{{ url_for(\'configuracion_remitentes\') }}"'
    if buscar in contenido:
        contenido = contenido.replace(buscar, tarjeta_catalogos + buscar)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade162] Tarjeta de Catálogos agregada a Configuración.")
    else:
        print("[upgrade162] ADVERTENCIA: No se encontró dónde insertar la tarjeta en Configuración.")

def main():
    print("=== Upgrade 162: Mover Catalogos a Configuracion ===")
    patch_base_html()
    patch_configuracion_index()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()