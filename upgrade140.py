# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_ventas_lista():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade140] no existe ventas/lista.html")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar donde se muestra el kilo con el filtro pesos
    buscar = "{{ v.kilos|pesos }} kg"
    # Reemplazarlo por un formato de número sin el $
    nuevo = "{{ '{:,.2f}'.format(v.kilos).replace(',', 'X').replace('.', ',').replace('X', '.') }} kg"
    
    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        print("[upgrade140] Formato de kilos corregido en ventas/lista.html")
    else:
        # Buscar variante por si quedó sin la palabra kg al lado
        buscar2 = "<td class=\"text-end text-nowrap\">{{ v.kilos|pesos }}</td>"
        nuevo2 = "<td class=\"text-end text-nowrap\">{{ '{:,.2f}'.format(v.kilos).replace(',', 'X').replace('.', ',').replace('X', '.') }} kg</td>"
        if buscar2 in contenido:
            contenido = contenido.replace(buscar2, nuevo2)
            print("[upgrade140] Formato de kilos corregido (variante)")
        else:
            print("[upgrade140] ADVERTENCIA: no se encontró el campo kilos exacto.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def patch_ventas_detalle():
    """Revisa si en el detalle también se aplicó el filtro a los kilos."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # En el detalle suele estar como "{{ v.kilos|pesos }}" o similar
    if "|pesos" in contenido and "kilos" in contenido:
        # Si tiene algo como {{ orden.kilos|pesos }} o {{ kilos_total|pesos }}
        contenido = re.sub(r"\{\{\s*([a-zA-Z0-9_\.]+kilos[a-zA-Z0-9_\.]*)\|pesos\s*\}\}", r"{{ '{:,.2f}'.format(\1).replace(',', 'X').replace('.', ',').replace('X', '.') }}", contenido)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade140] Kilos corregidos en ventas/detalle.html")


def main():
    print("=== Upgrade 140: Fix visual de Kilos ===")
    patch_ventas_lista()
    patch_ventas_detalle()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()