# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_ventas_lista():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade71] no existe ventas/lista.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Verificar si ya tiene el fix
    if 'data-bs-strategy="fixed"' in contenido:
        print("[upgrade71] ya estaba arreglado")
        return

    # 2. Reemplazar el boton del dropdown para agregar los atributos magicos
    viejo = '''<button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="dropdown" aria-expanded="false" title="Acciones">
<i class="bi bi-three-dots-vertical"></i>
</button>'''

    nuevo = '''<button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="dropdown" data-bs-strategy="fixed" data-bs-boundary="viewport" aria-expanded="false" title="Acciones">
<i class="bi bi-three-dots-vertical"></i>
</button>'''

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade71] Fix aplicado en ventas/lista.html")
    else:
        # Si por alguna razon tiene otro formato, intentar buscar solo el boton
        buscar_alternativo = '<button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="dropdown"'
        if buscar_alternativo in contenido:
            contenido = contenido.replace(
                buscar_alternativo, 
                '<button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="dropdown" data-bs-strategy="fixed" data-bs-boundary="viewport"', 
                1
            )
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print("[upgrade71] Fix aplicado (patrón alternativo)")
        else:
            print("[upgrade71] ADVERTENCIA: no se encontró el botón de acciones")

def main():
    print("=== Upgrade 71: Fix menú desplegable cortado en la tabla ===")
    patch_ventas_lista()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (y apreta Ctrl+F5 en el navegador)")

if __name__ == '__main__':
    main()