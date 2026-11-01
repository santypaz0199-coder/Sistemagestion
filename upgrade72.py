# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_ventas_lista():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade72] no existe ventas/lista.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Quitar el scroll interno de la tabla (que rompe los dropdowns)
    viejo_tabla = '''<!-- Tabla con scroll interno -->
<div class="card shadow-sm" style="max-height: calc(100vh - 320px); display: flex; flex-direction: column;">
<div class="table-responsive" style="overflow-y: auto; flex: 1;">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light" style="position: sticky; top: 0; z-index: 1;">'''

    nuevo_tabla = '''<!-- Tabla normal (sin scroll interno para que los dropdowns funcionen) -->
<div class="card shadow-sm">
<div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light">'''

    if viejo_tabla in contenido:
        contenido = contenido.replace(viejo_tabla, nuevo_tabla, 1)
        print("[upgrade72] scroll interno de tabla eliminado")
    else:
        # Variante sin comentario
        import re
        patron = re.compile(
            r'<div class="card shadow-sm" style="max-height:[^>]*>\s*<div class="table-responsive"[^>]*>\s*<table[^>]*>\s*<thead[^>]*>',
            re.DOTALL
        )
        contenido, n = patron.subn(nuevo_tabla, contenido, count=1)
        if n > 0:
            print("[upgrade72] scroll interno eliminado (patrón)")
        else:
            print("[upgrade72] ADVERTENCIA: no se encontró el bloque de tabla con scroll")

    # 2. Compactar los márgenes de los filtros para que la tabla suba
    contenido = contenido.replace(
        '<form class="card shadow-sm p-3 mb-3">',
        '<form class="card shadow-sm p-2 mb-2">'
    )
    # Achicar la botonera de filtros
    contenido = contenido.replace(
        '<div class="mt-2"><button class="btn btn-outline-secondary btn-sm"><i class="bi bi-search"></i> Filtrar</button></div>',
        '<div class="mt-1"><button class="btn btn-outline-secondary btn-sm py-1"><i class="bi bi-search"></i> Filtrar</button></div>'
    )
    # Achicar los inputs del filtro
    contenido = contenido.replace('class="form-control form-control-sm"', 'class="form-control form-control-sm py-1"')
    contenido = contenido.replace('class="form-select form-select-sm"', 'class="form-select form-select-sm py-1"')

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade72] layout compactado")


def main():
    print("=== Upgrade 72: Fix definitivo de Dropdowns (quitando scroll interno) ===")
    patch_ventas_lista()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()