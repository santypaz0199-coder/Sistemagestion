# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app39():
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Modificar la ruta de enviar email para que cambie el estado automaticamente
    buscar_envio = """    ok, msg = _enviar_con_remitente(destino, asunto, cuerpo,
                                     remitente_override=remitente_override,
                                     adjuntos=adjuntos)
                                     
    remitente_usado = remitente_override['email'] if remitente_override else get_config('smtp_remitente_email')"""

    nuevo_envio = """    ok, msg = _enviar_con_remitente(destino, asunto, cuerpo,
                                     remitente_override=remitente_override,
                                     adjuntos=adjuntos)
                                     
    # AUTOMATIZACION DE ESTADOS
    if ok and tipo == 'pago' and orden['estado'] == 'pendiente_pago':
        from app import aplicar_descuento_stock
        if not orden['stock_descontado']:
            aplicar_descuento_stock(conn, id, current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
        conn.commit()
        flash('El estado de la orden se actualizo automaticamente a Pagado / Sin enviar.', 'success')

    remitente_usado = remitente_override['email'] if remitente_override else get_config('smtp_remitente_email')"""

    if buscar_envio in contenido:
        contenido = contenido.replace(buscar_envio, nuevo_envio)
        print("[upgrade143] Automatizacion de estado al enviar email de pago")

    # 2. Notificar pago parcial automaticamente
    buscar_pago = """    conn.commit(); conn.close()
    flash('Pago registrado.', 'success')
    return redirect(url_for('ventas_detalle', id=id))"""
    
    nuevo_pago = """    conn.commit()

    # Si es un pago parcial, enviamos un correo automatico avisando
    if total_pagado < orden['total']:
        try:
            from app4 import enviar_email, get_config, _plantilla_html_correo
            cliente = conn.execute("SELECT email, nombre_completo FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
            if cliente and cliente['email']:
                asunto = f'Recibimos un pago parcial - Orden {orden["numero_interno"]}'
                cuerpo = f"""Hola {cliente['nombre_completo']},

Registramos un pago parcial para tu pedido {orden['numero_interno']}.

Monto abonado: ${monto:.2f}
Saldo restante: ${orden['total'] - total_pagado:.2f}

Cuando abones el saldo total, te enviaremos la confirmacion definitiva.

{get_config('firma_email')}"""
                enviar_email(cliente['email'], asunto, cuerpo)
                conn.execute("INSERT INTO emails_enviados (destinatario, asunto, tipo, orden_id, estado) VALUES (?,?,?,?,?)",
                             (cliente['email'], asunto, 'pago_parcial', id, 'ok'))
                conn.commit()
        except Exception as e:
            print(f"Error al notificar pago parcial: {e}")

    conn.close()
    flash('Pago registrado y cliente notificado si fue parcial.', 'success')
    return redirect(url_for('ventas_detalle', id=id))"""

    if buscar_pago in contenido:
        contenido = contenido.replace(buscar_pago, nuevo_pago)
        print("[upgrade143] Notificacion automatica de pago parcial")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_detalle_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Reemplazar el bloque de botones de notificacion para agregarles logica visual
    buscar_botones = """<div class="d-flex flex-wrap gap-2">
<button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-confirmacion"><i class="bi bi-file-text"></i> Enviar orden</button>
<button class="btn btn-outline-success btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-pago"><i class="bi bi-cash-coin"></i> Notificar pago</button>
<button class="btn btn-outline-info btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-envio"><i class="bi bi-truck"></i> Notificar envio</button>
<button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-entrega"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button class="btn btn-outline-dark btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-factura"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>"""

    nuevo_botones = """<div class="d-flex flex-wrap gap-2">
<button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-confirmacion"><i class="bi bi-file-text"></i> Enviar orden</button>

{% if orden.estado == 'pendiente_pago' %}
<button class="btn btn-outline-success btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-pago" onclick="return confirm('Al enviar este correo, la orden se marcará automáticamente como PAGADA y se descontará el stock. ¿Continuar?')"><i class="bi bi-cash-coin"></i> Notificar pago (Cambia estado)</button>
{% elif orden.estado == 'pagado_sin_enviar' %}
<button class="btn btn-outline-success btn-sm" disabled title="La orden ya está pagada"><i class="bi bi-check-circle"></i> Orden pagada</button>
{% endif %}

{% if orden.estado == 'pagado_sin_enviar' %}
<button class="btn btn-outline-info btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-envio"><i class="bi bi-truck"></i> Notificar envio</button>
{% elif orden.estado != 'pagado_enviado' %}
<button class="btn btn-outline-info btn-sm" disabled title="Primero tenés que cobrar la orden"><i class="bi bi-truck"></i> Notificar envio</button>
{% endif %}

<button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-entrega"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button class="btn btn-outline-dark btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-factura"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>"""

    if buscar_botones in contenido:
        contenido = contenido.replace(buscar_botones, nuevo_botones)
        print("[upgrade143] Botones de notificacion con logica de estado aplicada")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 143: Notificaciones inteligentes y pagos parciales ===")
    patch_app39()
    patch_detalle_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()