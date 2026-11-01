# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app145():
    ruta = os.path.join(BASE, 'app145.py')
    if not os.path.exists(ruta):
        print("[upgrade146] no existe app145.py")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Arreglar la importación de app
    viejo_import = "from app142 import app"
    nuevo_import = "from app48 import app"
    
    if viejo_import in contenido:
        contenido = contenido.replace(viejo_import, nuevo_import)
        print("[upgrade146] Importación de 'app' corregida en app145.py")
    else:
        print("[upgrade146] ADVERTENCIA: no se encontró el import de app142")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 146: Fix import app en app145 ===")
    patch_app145()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()