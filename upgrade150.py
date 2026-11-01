# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def limpiar_boton_entrega():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta):
        print("[upgrade150] no existe ventas/detalle.html")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Buscar y eliminar CUALQUIER botón que abra el colapso de 'mail-entrega'
    patron_boton = re.compile(r'<button[^>]*data-bs-target="#mail-entrega"[^>]*>.*?</button>', re.DOTALL)
    contenido, n_botones = patron_boton.subn('', contenido)
    print(f"[upgrade150] Botones de entrega eliminados: {n_botones}")

    # 2. Buscar y eliminar el bloque colapsable (el formulario) de 'mail-entrega'
    # Buscamos desde el div con id="mail-entrega" hasta el cierre del form y sus divs
    patron_form = re.compile(r'<div[^>]*id="mail-entrega"[^>]*>.*?</form>\s*</div>', re.DOTALL)
    contenido, n_forms = patron_form.subn('', contenido)
    print(f"[upgrade150] Formularios de entrega eliminados: {n_forms}")

    # 3. Si quedó algún resto de texto, lo limpiamos
    if 'Notificar entrega' in contenido:
        # Intento de limpieza más agresiva por si quedó algo suelto
        lineas = contenido.split('\n')
        lineas_limpias = [l for l in lineas if 'Notificar entrega' not in l and 'mail-entrega' not in l]
        contenido = '\n'.join(lineas_limpias)
        print("[upgrade150] Restos de texto de 'entrega' limpiados manualmente.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade150] Archivo detalle.html limpiado.")

def main():
    print("=== Upgrade 150: Eliminacion definitiva de 'Notificar entrega' ===")
    limpiar_boton_entrega()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()