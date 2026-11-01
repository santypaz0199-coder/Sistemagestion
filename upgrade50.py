# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app49():
    ruta = os.path.join(BASE, 'app49.py')
    if not os.path.exists(ruta):
        print("[upgrade50] no existe app49.py"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    viejo = "from flask import Blueprint, render_template, abort"
    nuevo = "from flask import Blueprint, render_template, abort, request"

    if nuevo in contenido:
        print("[upgrade50] import ya estaba correcto")
    elif viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade50] import de request agregado")
    else:
        print("[upgrade50] ADVERTENCIA: no se encontro el import de flask")


def main():
    print("=== Upgrade 50: Fix import request en app49 ===")
    patch_app49()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()