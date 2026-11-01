# -*- coding: utf-8 -*-
import os, sqlite3, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_checkout_html():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'checkout.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Reemplazar el tipo de envío "Envio personal" por "Envío personalizado"
    buscar_card = '''<label class="tipo-envio-card" data-tipo="envio_personal" style="cursor:pointer;display:block;">
                <input type="radio" name="tipo_envio" value="envio_personal" style="display:none;">
                <div style="border:1px solid var(--cat-border);border-radius:10px;padding:1rem;text-align:center;">
                  <i class="bi bi-car-front" style="font-size:1.5rem;display:block;margin-bottom:.5rem;"></i>
                  <div style="font-weight:500;font-size:.85rem;">Envio personal</div>
                </div>
              </label>'''

    nuevo_card = '''<label class="tipo-envio-card" data-tipo="envio_personalizado" style="cursor:pointer;display:block;">
                <input type="radio" name="tipo_envio" value="envio_personalizado" style="display:none;">
                <div style="border:1px solid var(--cat-border);border-radius:10px;padding:1rem;text-align:center;">
                  <i class="bi bi-chat-dots" style="font-size:1.5rem;display:block;margin-bottom:.5rem;"></i>
                  <div style="font-weight:500;font-size:.85rem;">A coordinar</div>
                  <div style="color:var(--cat-text-muted);font-size:.75rem;">Personalizado / Retiro</div>
                </div>
              </label>'''

    if buscar_card in contenido:
        contenido = contenido.replace(buscar_card, nuevo_card)

    # 2. Reemplazar el bloque de "envio_personal" en el JS por el nuevo
    buscar_bloque = '''<!-- Bloque: envio personal -->
          <div class="bloque-envio" data-bloque="envio_personal" style="display:none;">
            <div class="cat-alert cat-alert-info" style="font-size:.85rem;margin-bottom:1rem;">Entrega personal dentro de la ciudad.</div>
            {% include 'catalogo/_form_direccion.html' %}
          </div>'''

    nuevo_bloque = '''<!-- Bloque: envio personalizado -->
          <div class="bloque-envio" data-bloque="envio_personalizado" style="display:none;">
            <div class="cat-alert cat-alert-info" style="font-size:.85rem;margin-bottom:1rem;">
              Coordinamos el envío personalmente (por tu zona o con tu propio transporte). El costo de este envío se arregla por fuera y no se cobra en esta orden.
            </div>
            <div class="mb-3">
              <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Aclaraciones (opcional)</label>
              <textarea name="notas_coordinacion" class="form-control" rows="2" style="background:var(--cat-surface-2);border:1px solid var(--cat-border);color:var(--cat-text);" placeholder="Ej: Paso a retirar el martes, o envío con mi transporte..."></textarea>
            </div>
          </div>'''

    if buscar_bloque in contenido:
        contenido = contenido.replace(buscar_bloque, nuevo_bloque)

    # 3. Asegurarnos de que el checkbox de factura esté correcto y visible
    buscar_notas = '''<textarea name="notas" class="form-control" rows="3" placeholder="Ej: entregar despues de las 18hs, es para regalo, etc."></textarea>'''
    nuevo_notas = '''<textarea name="notas" class="form-control" rows="3" placeholder="Ej: entregar despues de las 18hs, es para regalo, etc."></textarea>
          <div class="form-check mt-3">
            <input class="form-check-input" type="checkbox" name="requiere_factura" id="requiere_factura" value="1" style="background:var(--cat-surface); border-color:var(--cat-border);">
            <label class="form-check-label" for="requiere_factura" style="color:var(--cat-text);font-weight:600;font-size:.95rem;cursor:pointer;">Requiero Factura A/B</label>
          </div>'''
    
    if buscar_notas in contenido and 'requiere_factura' not in contenido:
        contenido = contenido.replace(buscar_notas, nuevo_notas)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade104] checkout.html actualizado (A coordinar + Factura)")


def patch_app53():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Forzar la lectura del requerimiento de factura
    buscar_accion = "        accion = request.form.get('accion', 'pagar')"
    nuevo_accion = "        accion = request.form.get('accion', 'pagar')\n        requiere_factura = 1 if request.form.get('requiere_factura') else 0"
    if buscar_accion in contenido and 'requiere_factura = 1 if' not in contenido:
        contenido = contenido.replace(buscar_accion, nuevo_accion)

    # 2. Actualizar el INSERT para guardar 'pendiente' si requiere factura
    # Reemplazamos directamente la parte del estado_facturacion
    buscar_estado = "'pendiente_pago', 'pendiente' if requiere_factura else 'no_requiere',"
    buscar_estado_viejo = "'pendiente_pago', 'no_requiere',"
    
    if buscar_estado_viejo in contenido:
        contenido = contenido.replace(buscar_estado_viejo, buscar_estado)

    # 3. Manejar el envío personalizado en el backend
    buscar_envio = "        if tipo_envio == 'envio_personal' and not (dest_calle and dest_loc and dest_prov):"
    nuevo_envio = "        if tipo_envio == 'envio_personalizado':\n            pass # No requiere validacion de calle\n        elif tipo_envio == 'envio_personal' and not (dest_calle and dest_loc and dest_prov):"
    if buscar_envio in contenido:
        contenido = contenido.replace(buscar_envio, nuevo_envio)

    # Si es envio_personalizado, forzar costo_envio a 0
    buscar_costo = "        info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, destino_calc)"
    nuevo_costo = """        info_envio = calcular_envio_carrito(conn, carrito_data, subtotal, destino_calc)
        if tipo_envio == 'envio_personalizado':
            info_envio['costo_envio'] = 0
            info_envio['requiere_cotizacion'] = False"""
            
    if buscar_costo in contenido:
        contenido = contenido.replace(buscar_costo, nuevo_costo)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade104] app53.py actualizado (Factura y Envío Personalizado)")


def main():
    print("=== Upgrade 104: Fix Factura + Envío a coordinar ===")
    patch_checkout_html()
    patch_app53()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()