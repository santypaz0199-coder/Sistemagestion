# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_header_nav():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade128] no existe catalogo/base.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar el bloque del menú de categorías en el header
    patron = re.compile(r'<nav class="cat-nav.*?</nav>', re.DOTALL)
    
    if '<nav class="cat-nav' in contenido:
        contenido, n = patron.subn('', contenido)
        if n > 0:
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print("[upgrade128] Menú de categorías eliminado del Header")
        else:
            print("[upgrade128] ADVERTENCIA: no se pudo eliminar el bloque con regex")
    else:
        print("[upgrade128] El menú de categorías ya no estaba en el header")

def main():
    print("=== Upgrade 128: Limpiar menú de categorías del Header ===")
    patch_header_nav()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()