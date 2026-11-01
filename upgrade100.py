# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_botones():
    rutas = [
        os.path.join(BASE, 'templates', 'mayoristas', 'lista.html'),
        os.path.join(BASE, 'templates', 'mayoristas', 'lista_pagos.html')
    ]
    
    for ruta in rutas:
        if not os.path.exists(ruta):
            continue
            
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()

        if 'b2b_envios' in contenido:
            print(f"[upgrade100] El botón ya existe en {os.path.basename(ruta)}")
            continue

        # Buscar el bloque de botones (donde está el de compartir o el de abrir catálogo)
        # Usamos regex para encontrarlo sin importar los espacios exactos
        patron = re.compile(r'(<div class="d-flex gap-2">\s*)(<button|<a)')
        
        def reemplazar(match):
            inicio = match.group(1)
            resto = match.group(2)
            boton_envio = '<a href="{{ url_for(\'b2b_envios\') }}" class="btn btn-outline-dark btn-sm" style="margin-right: 8px;"><i class="bi bi-truck"></i> Escala de Envíos</a>\n'
            return inicio + boton_envio + resto

        contenido_nuevo, n = patron.subn(reemplazar, contenido, count=1)
        
        if n > 0:
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido_nuevo)
            print(f"[upgrade100] Botón 'Escala de Envíos' agregado a {os.path.basename(ruta)}")
        else:
            print(f"[upgrade100] ADVERTENCIA: No se encontró el lugar exacto en {os.path.basename(ruta)}")

def main():
    print("=== Upgrade 100: Agregar botón de Escala de Envíos a B2B ===")
    patch_botones()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en la pantalla de B2B")

if __name__ == '__main__':
    main()