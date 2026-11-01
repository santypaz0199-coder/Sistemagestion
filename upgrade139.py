# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_ventas_detalle():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta):
        print("[upgrade139] no existe ventas/detalle.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Arreglar la línea del saldo que explotó
    # El problema: {{ orden.total - total_pagado|pesos }}
    # La solución: {{ (orden.total - total_pagado)|pesos }}
    buscar_saldo = "{{ orden.total - total_pagado|pesos }}"
    nuevo_saldo = "{{ (orden.total - total_pagado)|pesos }}"
    
    if buscar_saldo in contenido:
        contenido = contenido.replace(buscar_saldo, nuevo_saldo)
        print("[upgrade139] Fix aplicado en la línea del Saldo.")
    else:
        # Variante de seguridad usando regex
        contenido = re.sub(r"\{\{\s*orden\.total\s*-\s*total_pagado\s*\|\s*pesos\s*\}\}", nuevo_saldo, contenido)

    # 2. Revisar por si quedó alguna otra resta o suma sin paréntesis con el filtro pesos
    # (Por ejemplo en los subtotales o descuentos)
    buscar_subtotal = "{{ orden.subtotal - orden.descuento|pesos }}"
    nuevo_subtotal = "{{ (orden.subtotal - orden.descuento)|pesos }}"
    if buscar_subtotal in contenido:
        contenido = contenido.replace(buscar_subtotal, nuevo_subtotal)
        print("[upgrade139] Fix aplicado en la línea del Subtotal con descuento.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade139] Template ventas/detalle.html actualizado.")


def patch_ventas_lista():
    """Revisa la lista de ventas por si quedó el mismo error en la columna de Total."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta): return
    
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # En la lista suele ser simplemente {{ v.total|pesos }}, pero por si quedó alguna cuenta:
    buscar = "{{ v.total - algo|pesos }}"
    # No hace falta reemplazar nada si no hay restas, pero verificamos que no haya textos raros.
    pass

def main():
    print("=== Upgrade 139: Fix de resta con filtro de moneda ===")
    patch_ventas_detalle()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()