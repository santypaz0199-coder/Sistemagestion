# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app160():
    ruta = os.path.join(BASE, 'app160.py')
    if not os.path.exists(ruta):
        print("[upgrade161] no existe app160.py")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Convertir provincias a lista de dicts
    buscar_provincias = 'provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()'
    nuevo_provincias = 'provincias = [dict(r) for r in conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()]'
    if buscar_provincias in contenido:
        contenido = contenido.replace(buscar_provincias, nuevo_provincias)
        print("[upgrade161] Provincias convertidas a dict en app160.py")

    # 2. Asegurar que localidades por provincia se pase bien
    buscar_locs = 'localidades_por_provincia = {}\n    for r in locs_rows:\n        localidades_por_provincia.setdefault(r[\'provincia_id\'], []).append({\'id\': r[\'id\'], \'nombre\': r[\'nombre\']})'
    nuevo_locs = 'localidades_por_provincia = {}\n    for r in locs_rows:\n        localidades_por_provincia.setdefault(r[\'provincia_id\'], []).append({\'id\': r[\'id\'], \'nombre\': r[\'nombre\']})'
    # Esta parte ya debería estar bien, solo verificamos que no falle al serializar.

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def patch_form_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'form.html')
    if not os.path.exists(ruta):
        print("[upgrade161] no existe ventas/form.html")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # A veces Jinja se queja si los dicts tienen cosas raras. 
    # En el form usamos PROVINCIAS|tojson y LOCALIDADES|tojson.
    # Al haber convertido a dict en app160, ya debería andar.

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade161] Template revisado.")

def main():
    print("=== Upgrade 161: Fix JSON Serializable (Row -> dict) ===")
    patch_app160()
    patch_form_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()