# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app53():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        print("[upgrade106] no existe app53.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Buscar el render_template del GET (cuando recién se entra al checkout)
    viejo_get = """    conn.close()
    return render_template('catalogo/checkout.html',
                           items=items, subtotal=subtotal, mayorista=m,
                           transportistas=transportistas)"""

    nuevo_get = """    # Calcular envío para el GET (para que no explote al entrar)
    from app95 import calcular_envio_carrito
    info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, 'sucursal')
    total_con_envio = subtotal + info_envio.get('costo_envio', 0)

    conn.close()
    return render_template('catalogo/checkout.html',
                           items=items, subtotal=subtotal, mayorista=m,
                           transportistas=transportistas,
                           info_envio=info_envio, total_con_envio=total_con_envio)"""

    if viejo_get in contenido:
        contenido = contenido.replace(viejo_get, nuevo_get)
        print("[upgrade106] Cálculo de envío agregado al GET del Checkout")
    else:
        print("[upgrade106] ADVERTENCIA: no se encontró el render exacto del GET. Intentando variante...")
        # Variante por si el formato del código tiene otros espacios
        import re
        patron = re.compile(r"conn\.close\(\)\s*return render_template\('catalogo/checkout\.html',\s*items=items,\s*subtotal=subtotal,\s*mayorista=m,\s*transportistas=transportistas\)", re.DOTALL)
        contenido, n = patron.subn(nuevo_get, contenido)
        if n > 0:
            print("[upgrade106] Cálculo de envío agregado al GET (por regex)")
        else:
            print("[upgrade106] ERROR: no se pudo inyectar el cálculo en el GET.")

    # 2. Asegurarnos de que en el POST también esté capturando bien el requerimiento de factura
    # (Por si el paso anterior falló)
    if 'requiere_factura = 1 if request.form.get' not in contenido:
        buscar_post = "        tipo_envio = request.form.get('tipo_envio', '').strip()"
        nuevo_post = "        tipo_envio = request.form.get('tipo_envio', '').strip()\n        requiere_factura = 1 if request.form.get('requiere_factura') else 0"
        if buscar_post in contenido:
            contenido = contenido.replace(buscar_post, nuevo_post)
            print("[upgrade106] Variable requiere_factura agregada al POST")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 106: Fix cálculo de envío al entrar al Checkout ===")
    patch_app53()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el catalogo")


if __name__ == '__main__':
    main()