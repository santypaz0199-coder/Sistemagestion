# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app152():
    ruta = os.path.join(BASE, 'app152.py')
    if not os.path.exists(ruta):
        print("[upgrade153] no existe app152.py")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Arreglar la importación de app
    viejo_import = "from app148 import app"
    nuevo_import = "from app48 import app"
    
    if viejo_import in contenido:
        contenido = contenido.replace(viejo_import, nuevo_import)
        print("[upgrade153] Importación de 'app' corregida en app152.py")
    else:
        print("[upgrade153] ADVERTENCIA: no se encontró el import de app148")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 153: Fix import app en app152 ===")
    patch_app152()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()