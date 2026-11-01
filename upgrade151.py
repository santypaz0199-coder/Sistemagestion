# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_backend_validos():
    """Devuelve el tipo 'entrega' a la lista de válidos en app4 y app145."""
    for arch in ['app4.py', 'app145.py']:
        ruta = os.path.join(BASE, arch)
        if not os.path.exists(ruta): continue
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
            
        buscar = "TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'factura'}"
        nuevo = "TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'factura', 'entrega'}"
        
        if buscar in contenido:
            contenido = contenido.replace(buscar, nuevo)
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print(f"[upgrade151] Tipo 'entrega' restaurado en {arch}")

def patch_modal_email():
    """Modifica los botones dentro del modal de Email para aplicar la lógica."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    buscar_botones_modal = r'''<div class="d-grid gap-2">
<button type="submit" class="btn btn-outline-primary" onclick="this.form.action=this.form.getAttribute('data-url')+'/confirmacion'"><i class="bi bi-file-text"></i> Enviar orden</button>
<button type="submit" class="btn btn-outline-success" onclick="this.form.action=this.form.getAttribute('data-url')+'/pago'"><i class="bi bi-cash-coin"></i> Notificar pago</button>
<button type="submit" class="btn btn-outline-info" onclick="this.form.action=this.form.getAttribute('data-url')+'/envio'"><i class="bi bi-truck"></i> Notificar envio</button>
<button type="submit" class="btn btn-outline-secondary" onclick="this.form.action=this.form.getAttribute('data-url')+'/entrega'"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button type="submit" class="btn btn-outline-dark" onclick="this.form.action=this.form.getAttribute('data-url')+'/factura'"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>'''

    nuevo_botones_modal = r'''<div class="d-grid gap-2">
<button type="submit" class="btn btn-outline-primary" onclick="this.form.action=this.form.getAttribute('data-url')+'/confirmacion'"><i class="bi bi-file-text"></i> Enviar orden</button>
<button type="submit" class="btn btn-outline-success" onclick="this.form.action=this.form.getAttribute('data-url')+'/pago'"><i class="bi bi-cash-coin"></i> Notificar pago</button>
<button type="submit" class="btn btn-outline-info" onclick="this.form.action=this.form.getAttribute('data-url')+'/envio'"><i class="bi bi-truck"></i> Notificar envio</button>

{% if orden.tipo_envio in ('retira_deposito', 'envio_personalizado') %}
    {% if orden.estado != 'pendiente_pago' %}
    <button type="submit" class="btn btn-outline-secondary" onclick="this.form.action=this.form.getAttribute('data-url')+'/entrega'"><i class="bi bi-box-seam"></i> Notificar entrega (Local/Retiro)</button>
    {% else %}
    <button type="button" class="btn btn-outline-secondary" disabled title="Primero tenés que acreditar el pago"><i class="bi bi-box-seam"></i> Notificar entrega (Requiere Pago)</button>
    {% endif %}
{% endif %}

<button type="submit" class="btn btn-outline-dark" onclick="this.form.action=this.form.getAttribute('data-url')+'/factura'"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>'''

    if buscar_botones_modal in contenido:
        contenido = contenido.replace(buscar_botones_modal, nuevo_botones_modal)
        print("[upgrade151] Botones del Modal de Email actualizados con la logica de entrega.")
    else:
        # Si el string no coincide exactamente (por espacios), usamos regex
        patron = re.compile(r'<div class="d-grid gap-2">\s*<button type="submit" class="btn btn-outline-primary".*?/factura\'.*?</button>\s*</div>', re.DOTALL)
        contenido, n = patron.subn(nuevo_botones_modal, contenido)
        if n > 0:
            print("[upgrade151] Botones del Modal actualizados (por regex).")
        else:
            print("[upgrade151] ADVERTENCIA: No se pudo modificar el Modal de Email.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 151: Logica inteligente para Notificar Entrega ===")
    patch_backend_validos()
    patch_modal_email()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()