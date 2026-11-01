# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app145():
    ruta = os.path.join(BASE, 'app145.py')
    if not os.path.exists(ruta):
        print("[upgrade148] no existe app145.py")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Quitar el decorador @app.route de la función v3
    # para que no cree una ruta duplicada que Flask ignore
    buscar_ruta = """@app.route('/ventas/<int:id>/email/<tipo>', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_email_enviar_v3(id, tipo):"""
    
    nueva_ruta = """# Monkey-patch: eliminamos el decorador de ruta para forzar el reemplazo
@login_required
@permiso_required('ventas')
def ventas_email_enviar_v3(id, tipo):"""
    
    if buscar_ruta in contenido:
        contenido = contenido.replace(buscar_ruta, nueva_ruta)
        print("[upgrade148] Decorador de ruta eliminado en v3")

    # 2. Al final del archivo, forzar a Flask a usar v3
    if "app.view_functions['ventas_email_enviar'] = ventas_email_enviar_v3" not in contenido:
        contenido += "\n\n# Forzar a Flask a usar esta funcion para la ruta de emails\napp.view_functions['ventas_email_enviar'] = ventas_email_enviar_v3\n"
        print("[upgrade148] app.view_functions actualizado para usar v3")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_detalle_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Asegurarnos de que los botones tienen la lógica estricta
    buscar_botones = r'''<div class="d-flex flex-wrap gap-2">
<button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-confirmacion"><i class="bi bi-file-text"></i> Enviar orden</button>

{% if orden.estado == 'pendiente_pago' %}
<button class="btn btn-outline-success btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-pago" onclick="return confirm('Al enviar este correo, la orden se marcará automáticamente como PAGADA y se descontará el stock. ¿Continuar?')"><i class="bi bi-cash-coin"></i> Notificar pago (Cambia estado)</button>
{% elif orden.estado == 'pagado_sin_enviar' %}
<button class="btn btn-outline-success btn-sm" disabled title="La orden ya está pagada"><i class="bi bi-check-circle"></i> Pago acreditado</button>
{% endif %}

{% if orden.estado == 'pagado_sin_enviar' %}
<button class="btn btn-outline-info btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-envio" onclick="return confirm('Al enviar este correo, la orden se marcará como ENVIADA. ¿Continuar?')"><i class="bi bi-truck"></i> Notificar envio (Cambia estado)</button>
{% elif orden.estado != 'pagado_enviado' %}
<button class="btn btn-outline-info btn-sm" disabled title="Primero tenés que cobrar la orden"><i class="bi bi-truck"></i> Notificar envio</button>
{% elif orden.estado == 'pagado_enviado' %}
<button class="btn btn-outline-info btn-sm" disabled><i class="bi bi-truck"></i> Envio notificado</button>
{% endif %}

<button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-entrega"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button class="btn btn-outline-dark btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-factura"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>'''

    # Buscar la versión anterior (sin los confirm de JS, por si quedó de un paso previo)
    patron_botones = re.compile(r'<div class="d-flex flex-wrap gap-2">.*?</div>', re.DOTALL)
    
    # Reemplazar solo el bloque de botones
    if 'Notificar pago (Cambia estado)' not in contenido or 'confirm(' not in contenido:
        contenido = patron_botones.sub(buscar_botones, contenido, count=1)
        print("[upgrade148] Botones de notificación con reglas estrictas aplicados")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 148: Fix definitivo de lógica de estados ===")
    patch_app145()
    patch_detalle_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()