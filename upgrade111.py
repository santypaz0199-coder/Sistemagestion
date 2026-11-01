# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app53():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        print("[upgrade111] no existe app53.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar el return del carrito que le faltan los datos
    viejo_return = """    conn.close()
    return render_template('catalogo/carrito.html', items=items, subtotal=subtotal, mayorista=m)"""

    nuevo_return = """    # Calcular envío para mostrarlo en el carrito
    from app95 import calcular_envio_carrito
    info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, 'sucursal')

    conn.close()
    return render_template('catalogo/carrito.html', items=items, subtotal=subtotal, mayorista=m, info_envio=info_envio)"""

    if viejo_return in contenido:
        contenido = contenido.replace(viejo_return, nuevo_return)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade111] Envío agregado a la función carrito() en app53.py")
    else:
        # Variante por si hay espacios distintos
        patron = re.compile(r"conn\.close\(\)\s*return render_template\('catalogo/carrito\.html',\s*items=items,\s*subtotal=subtotal,\s*mayorista=m\)", re.DOTALL)
        contenido, n = patron.subn(nuevo_return, contenido)
        if n > 0:
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print("[upgrade111] Envío agregado a la función carrito() (por regex)")
        else:
            print("[upgrade111] ADVERTENCIA: No se encontró el return exacto en la función carrito()")

def main():
    print("=== Upgrade 111: Fix info_envio en el Carrito ===")
    patch_app53()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")


if __name__ == '__main__':
    main()