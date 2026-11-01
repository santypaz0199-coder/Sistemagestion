# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app61():
    ruta = os.path.join(BASE, 'app61.py')
    if not os.path.exists(ruta):
        print("[upgrade62] no existe app61.py"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    viejo = "from app57 import app"
    nuevo = "from app48 import app"

    if nuevo in contenido and viejo not in contenido:
        print("[upgrade62] ya estaba corregido")
        return

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade62] import corregido: from app48 import app")
    else:
        print("[upgrade62] ADVERTENCIA: no se encontro 'from app57 import app'")


def main():
    print("=== Upgrade 62: Fix import app en app61 ===")
    patch_app61()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()