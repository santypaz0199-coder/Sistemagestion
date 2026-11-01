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

        if 'b2b_portada' in contenido:
            print(f"[upgrade123] El botón ya existe en {os.path.basename(ruta)}")
            continue

        # Buscamos el div que contiene los botones superiores
        # Nos enfocamos en el botón de Escala de Envíos que vimos en tu foto
        patron = re.compile(r'(<a[^>]*href="[^"]*b2b_envios[^"]*"[^>]*>.*?Escala de Envíos.*?</a>)', re.DOTALL)
        
        def reemplazar(match):
            boton_envio = match.group(1)
            boton_portada = '\n<a href="{{ url_for(\'b2b_portada\') }}" class="btn btn-outline-dark btn-sm"><i class="bi bi-image"></i> Portada del Catálogo</a>'
            return boton_envio + boton_portada

        contenido_nuevo, n = patron.subn(reemplazar, contenido, count=1)
        
        if n > 0:
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido_nuevo)
            print(f"[upgrade123] Botón 'Portada del Catálogo' agregado a {os.path.basename(ruta)}")
        else:
            # Si no encontramos el link, intentamos buscar el botón por texto
            buscar_texto = 'Escala de Envíos'
            if buscar_texto in contenido:
                # Inyectamos el botón justo antes de "Abrir catálogo"
                buscar_abrir = '<a href="/catalogo" target="_blank" class="btn btn-outline-secondary btn-sm">'
                if buscar_abrir in contenido:
                    nuevo_boton = '<a href="{{ url_for(\'b2b_portada\') }}" class="btn btn-outline-dark btn-sm" style="margin-right:8px;"><i class="bi bi-image"></i> Portada del Catálogo</a>\n' + buscar_abrir
                    contenido = contenido.replace(buscar_abrir, nuevo_boton)
                    with open(ruta, 'w', encoding='utf-8') as f:
                        f.write(contenido)
                    print(f"[upgrade123] Botón inyectado por posición en {os.path.basename(ruta)}")
                else:
                    print(f"[upgrade123] ADVERTENCIA: No se encontró el lugar exacto en {os.path.basename(ruta)}")

def main():
    print("=== Upgrade 123: Forzar botón de Portada en B2B ===")
    patch_botones()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()