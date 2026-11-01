# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app88():
    ruta = os.path.join(BASE, 'app88.py')
    if not os.path.exists(ruta):
        print("[upgrade89] no existe app88.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Arreglar el typo de order_id a orden_id
    viejo = "FROM pagos WHERE order_id=o.id),0)"
    nuevo = "FROM pagos WHERE orden_id=o.id),0)"

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo)
        print("[upgrade89] Typo corregido (order_id -> orden_id)")
    else:
        print("[upgrade89] ADVERTENCIA: no se encontró el typo")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 89: Fix typo order_id -> orden_id ===")
    patch_app88()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()