# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade105] escrito: {relpath}")


# 1. REESCRIBIR EL FORMULARIO DE DIRECCIÓN CON AUTOCOMPLETADO
FORM_DIRECCION = r'''<div class="row g-2">
  <div class="col-md-12">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Destinatario</label>
    <input name="destinatario_nombre" class="form-control" placeholder="Nombre y apellido" value="{{ mayorista.nombre_completo }}">
  </div>
  <div class="col-md-8">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Calle y altura *</label>
    <input name="destinatario_calle" class="form-control" placeholder="Ej: Av. Colon 123" value="{% if mayorista.calle %}{{ mayorista.calle }} {% endif %}{{ mayorista.altura or '' }}">
  </div>
  <div class="col-md-4">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">CP</label>
    <input name="destinatario_cp" class="form-control" value="{{ mayorista.codigo_postal or '' }}">
  </div>
  <div class="col-md-6">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Localidad *</label>
    <input name="destinatario_localidad" class="form-control" value="{{ mayorista.localidad or '' }}">
  </div>
  <div class="col-md-6">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Provincia *</label>
    <input name="destinatario_provincia" class="form-control" value="{{ mayorista.provincia or '' }}">
  </div>
  <div class="col-12">
    <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Piso / Depto / Referencias</label>
    <input name="destinatario_detalles" class="form-control" placeholder="Piso, depto, referencias" value="{% if mayorista.piso %}Piso {{ mayorista.piso }} {% endif %}{% if mayorista.depto %}Depto {{ mayorista.depto }}{% endif %}">
  </div>
</div>
'''

# 2. ACTUALIZAR EL CHECKOUT PARA INCLUIR LA LÓGICA DE MISIONES
CHECKOUT_HTML = r'''{% extends "catalogo/base.html" %}
{% block title %}Checkout — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <h1 style="font-weight:300;font-size:2rem;margin-bottom:2rem;">Finalizar pedido</h1>

  <form method="post">
    <div class="row g-4">
      <div class="col-md-8">

        <!-- Tipo de envio -->
        <div class="cat-form-card" style="max-width:100%;padding:1.5rem;">
          <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Tipo de envio *</h6>

          <div class="row g-2 mb-3">
            <div class="col-md-4">
              <label class="tipo-envio-card" data-tipo="retira_deposito" style="cursor:pointer;display:block;">
                <input type="radio" name="tipo_envio" value="retira_deposito" style="display:none;" required>
                <div style="border:1px solid var(--cat-border);border-radius:10px;padding:1rem;text-align:center;">
                  <i class="bi bi-shop" style="font-size:1.5rem;display:block;margin-bottom:.5rem;"></i>
                  <div style="font-weight:500;font-size:.85rem;">Retira en deposito</div>
                </div>
              </label>
            </div>
            <div class="col-md-4">
              <label class="tipo-envio-card" data-tipo="transporte" style="cursor:pointer;display:block;">
                <input type="radio" name="tipo_envio" value="transporte" style="display:none;">
                <div style="border:1px solid var(--cat-border);border-radius:10px;padding:1rem;text-align:center;">
                  <i class="bi bi-truck" style="font-size:1.5rem;display:block;margin-bottom:.5rem;"></i>
                  <div style="font-weight:500;font-size:.85rem;">Envio por transporte</div>
                </div>
              </label>
            </div>
            <div class="col-md-4">
              <label class="tipo-envio-card" data-tipo="envio_personalizado" style="cursor:pointer;display:block;">
                <input type="radio" name="tipo_envio" value="envio_personalizado" style="display:none;">
                <div style="border:1px solid var(--cat-border);border-radius:10px;padding:1rem;text-align:center;">
                  <i class="bi bi-chat-dots" style="font-size:1.5rem;display:block;margin-bottom:.5rem;"></i>
                  <div style="font-weight:500;font-size:.85rem;">A coordinar</div>
                  <div style="color:var(--cat-text-muted);font-size:.75rem;">Personalizado / Retiro</div>
                </div>
              </label>
            </div>
          </div>

          <!-- Bloque: retira -->
          <div class="bloque-envio" data-bloque="retira_deposito" style="display:none;">
            <div class="cat-alert cat-alert-info" style="font-size:.85rem;">Retiras personalmente en el deposito. Te avisamos cuando este listo.</div>
          </div>

          <!-- Bloque: transporte -->
          <div class="bloque-envio" data-bloque="transporte" style="display:none;">
            <div class="mb-3">
              <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Destino *</label>
              <div class="row g-2">
                <div class="col-md-6">
                  <label class="destino-card" data-destino="domicilio" style="cursor:pointer;display:block;">
                    <input type="radio" name="destino_tipo" value="domicilio" style="display:none;">
                    <div style="border:1px solid var(--cat-border);border-radius:10px;padding:.75rem;text-align:center;font-size:.85rem;">
                      <i class="bi bi-house"></i> Domicilio
                    </div>
                  </label>
                </div>
                <div class="col-md-6">
                  <label class="destino-card" data-destino="sucursal" style="cursor:pointer;display:block;">
                    <input type="radio" name="destino_tipo" value="sucursal" style="display:none;">
                    <div style="border:1px solid var(--cat-border);border-radius:10px;padding:.75rem;text-align:center;font-size:.85rem;">
                      <i class="bi bi-building"></i> Sucursal
                    </div>
                  </label>
                </div>
              </div>
            </div>

            <div class="bloque-destino" data-destino-tipo="domicilio" style="display:none;">
              <div class="cat-alert cat-alert-success" style="font-size:.8rem;padding:.5rem;margin-bottom:1rem;">
                <i class="bi bi-check-circle"></i> Usamos los datos de tu cuenta. Si querés enviarlo a otra dirección, modificalos acá.
              </div>
              {% include 'catalogo/_form_direccion.html' %}
            </div>
            <div class="bloque-destino" data-destino-tipo="sucursal" style="display:none;">
              <div class="mb-3">
                <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Sucursal donde retiras *</label>
                <input name="sucursal_detalle" class="form-control" placeholder="Ej: Sucursal Andreani Cordoba Centro">
              </div>
              <div class="row g-2">
                <div class="col-md-6">
                  <label style="color:var(--cat-text-muted);font-size:.8rem;">Localidad</label>
                  <input name="destinatario_localidad" class="form-control" value="{{ mayorista.localidad or '' }}">
                </div>
                <div class="col-md-6">
                  <label style="color:var(--cat-text-muted);font-size:.8rem;">Provincia</label>
                  <input name="destinatario_provincia" class="form-control" value="{{ mayorista.provincia or '' }}">
                </div>
              </div>
            </div>
          </div>

          <!-- Bloque: envio personalizado -->
          <div class="bloque-envio" data-bloque="envio_personalizado" style="display:none;">
            <div class="cat-alert cat-alert-info" style="font-size:.85rem;margin-bottom:1rem;">
              Coordinamos el envío personalmente (por tu zona o con tu propio transporte). El costo de este envío se arregla por fuera y no se cobra en esta orden.
            </div>
            <div class="mb-3">
              <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Aclaraciones (opcional)</label>
              <textarea name="notas_coordinacion" class="form-control" rows="2" style="background:var(--cat-surface-2);border:1px solid var(--cat-border);color:var(--cat-text);" placeholder="Ej: Paso a retirar el martes, o envío con mi transporte..."></textarea>
            </div>
          </div>
        </div>

        <!-- Notas y Factura -->
        <div class="cat-form-card mt-3" style="max-width:100%;padding:1.5rem;">
          <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Notas (opcional)</h6>
          <textarea name="notas" class="form-control" rows="3" placeholder="Ej: entregar despues de las 18hs, es para regalo, etc."></textarea>
          <div class="form-check mt-3">
            <input class="form-check-input" type="checkbox" name="requiere_factura" id="requiere_factura" value="1" style="background:var(--cat-surface); border-color:var(--cat-border);">
            <label class="form-check-label" for="requiere_factura" style="color:var(--cat-text);font-weight:600;font-size:.95rem;cursor:pointer;">Requiero Factura A/B</label>
          </div>
        </div>

      </div>

      <!-- Resumen -->
      <div class="col-md-4">
        <div class="cat-form-card" style="padding:1.5rem;">
          <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Tu pedido</h6>
          {% for item in items %}
          <div class="d-flex justify-content-between mb-2" style="font-size:.85rem;">
            <span>{{ item.producto.nombre }} <span style="color:var(--cat-text-muted);">x{{ item.cantidad|int }}</span></span>
            <span>${{ '%.2f'|format(item.subtotal) }}</span>
          </div>
          {% endfor %}
          <hr style="border-color:var(--cat-border);">
          <div class="d-flex justify-content-between mb-2">
            <span style="color:var(--cat-text-muted);">Peso total:</span>
            <span>{{ '%.1f'|format(info_envio.peso_total) }} kg ({{ info_envio.bultos }} bultos)</span>
          </div>
          {% if info_envio.requiere_cotizacion %}
          <div class="d-flex justify-content-between mb-2">
            <span class="text-warning">Costo de envío:</span>
            <span class="text-warning">A cotizar por Palet</span>
          </div>
          <hr style="border-color:var(--cat-border);">
          <div class="d-flex justify-content-between mb-3">
            <span style="font-weight:600;">Total productos</span>
            <span style="color:var(--cat-accent);font-weight:600;font-size:1.2rem;">${{ '%.2f'|format(subtotal) }}</span>
          </div>
          <div class="cat-alert cat-alert-warning" style="font-size:.85rem;padding:.5rem;">
            <i class="bi bi-exclamation-triangle"></i> {{ info_envio.mensaje_extra }}
          </div>
          {% else %}
          <div class="d-flex justify-content-between mb-2">
            <span style="color:var(--cat-text-muted);">Costo de envío:</span>
            <span>${{ '%.2f'|format(info_envio.costo_envio) }}</span>
          </div>
          <hr style="border-color:var(--cat-border);">
          <div class="d-flex justify-content-between">
            <span style="font-weight:600;">Total final</span>
            <span style="color:var(--cat-accent);font-weight:600;font-size:1.2rem;">${{ '%.2f'|format(total_con_envio) }}</span>
          </div>
          {% endif %}
          
          <button type="submit" name="accion" value="pagar" class="cat-btn w-100 text-center mt-3" style="background:#c9a96e; color:#000; border:none;">Pagar Ahora</button>
          <button type="submit" name="accion" value="guardar" class="cat-btn cat-btn-outline w-100 text-center mt-2" style="color:var(--cat-text); border:1px solid var(--cat-border);">Guardar Orden (Pagar después)</button>
          <div class="text-center mt-2 small text-muted">Las órdenes se cancelan a las 24hs si no se paga.</div>
        </div>
      </div>
    </div>
  </form>
</div>

<style>
.tipo-envio-card input:checked + div,
.destino-card input:checked + div {
  border-color: var(--cat-accent) !important;
  background: rgba(201,169,110,.08);
}
.tipo-envio-card:hover > div,
.destino-card:hover > div {
  border-color: var(--cat-text-muted);
}
</style>

<script>
function updateCheckoutForm() {
  const tipo = document.querySelector('input[name="tipo_envio"]:checked')?.value || '';
  const destino = document.querySelector('input[name="destino_tipo"]:checked')?.value || '';
  document.querySelectorAll('.bloque-envio').forEach(el => {
    el.style.display = el.dataset.bloque === tipo ? 'block' : 'none';
  });
  document.querySelectorAll('.bloque-destino').forEach(el => {
    el.style.display = (tipo === 'transporte' && el.dataset.destinoTipo === destino) ? 'block' : 'none';
  });
}
document.querySelectorAll('.tipo-envio-card').forEach(el => {
  el.addEventListener('click', () => {
    const radio = el.querySelector('input[type="radio"]');
    if (radio) { radio.checked = true; updateCheckoutForm(); }
  });
});
document.querySelectorAll('.destino-card').forEach(el => {
  el.addEventListener('click', () => {
    const radio = el.querySelector('input[type="radio"]');
    if (radio) { radio.checked = true; updateCheckoutForm(); }
  });
});
document.addEventListener('DOMContentLoaded', updateCheckoutForm);
</script>
{% endblock %}
'''

def patch_app53_checkout():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Asegurarnos de que los datos del destinatario tomen el valor del formulario, o en su defecto, el del perfil del cliente
    buscar_post = """        dest_nombre = request.form.get('destinatario_nombre', '').strip() or m['nombre_completo']
        dest_prov = request.form.get('destinatario_provincia', '').strip()
        dest_loc = request.form.get('destinatario_localidad', '').strip()
        dest_cp = request.form.get('destinatario_cp', '').strip()
        dest_calle = request.form.get('destinatario_calle', '').strip()
        dest_detalles = request.form.get('destinatario_detalles', '').strip()"""
        
    nuevo_post = """        dest_nombre = request.form.get('destinatario_nombre', '').strip() or m['nombre_completo']
        dest_prov = request.form.get('destinatario_provincia', '').strip() or m.get('provincia', '')
        dest_loc = request.form.get('destinatario_localidad', '').strip() or m.get('localidad', '')
        dest_cp = request.form.get('destinatario_cp', '').strip() or m.get('codigo_postal', '')
        dest_calle = request.form.get('destinatario_calle', '').strip()
        dest_detalles = request.form.get('destinatario_detalles', '').strip()"""

    if buscar_post in contenido:
        contenido = contenido.replace(buscar_post, nuevo_post)
        print("[upgrade105] app53.py: defaults de direccion desde el perfil de usuario")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    print("=== Upgrade 105: Autocompletado de datos en Checkout + Misiones ===")
    escribir('templates/catalogo/_form_direccion.html', FORM_DIRECCION)
    escribir('templates/catalogo/checkout.html', CHECKOUT_HTML)
    patch_app53_checkout()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el catalogo")


if __name__ == '__main__':
    main()