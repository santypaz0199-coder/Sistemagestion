# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app145():
    ruta = os.path.join(BASE, 'app145.py')
    if not os.path.exists(ruta):
        print("[upgrade147] no existe app145.py")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Arreglar la importación (cambiar requerido por required)
    viejo_import = "from app import permiso_requerido, aplicar_descuento_stock, revertir_stock"
    nuevo_import = "from app import permiso_required, aplicar_descuento_stock, revertir_stock"
    
    if viejo_import in contenido:
        contenido = contenido.replace(viejo_import, nuevo_import)
        print("[upgrade147] Import de permiso corregido")

    # 2. Reemplazar todos los decoradores mal escritos
    contenido = contenido.replace("@permiso_requerido('ventas')", "@permiso_required('ventas')")
    print("[upgrade147] Decoradores @permiso_requerido reemplazados por @permiso_required")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 147: Fix de tipeo permiso_required ===")
    patch_app145()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()