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
    print(f"[upgrade107] escrito: {relpath}")


# 1. ARREGLAR EL BACKEND (EL ERROR QUE NO TE DEJA AVANZAR)
def patch_app53():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Arreglar la validación del tipo de envío
    viejo_tipo = "if tipo_envio not in ('retira_deposito', 'transporte', 'envio_personal'):"
    nuevo_tipo = "if tipo_envio not in ('retira_deposito', 'transporte', 'envio_personalizado'):"
    if viejo_tipo in contenido:
        contenido = contenido.replace(viejo_tipo, nuevo_tipo)

    # Quitar la validación del transportista que rompía todo
    viejo_transp = """        transportista_id = request.form.get('transportista_id') or None
        if not transportista_id:
            conn.close()
            flash('Elegi un transportista.', 'error')
            return redirect(url_for('catalogo.checkout'))
"""
    if viejo_transp in contenido:
        contenido = contenido.replace(viejo_transp, "        transportista_id = None\n")

    # Asegurar que tome los datos si no se modificaron
    viejo_dest = """        dest_nombre = request.form.get('destinatario_nombre', '').strip() or m['nombre_completo']
        dest_prov = request.form.get('destinatario_provincia', '').strip()
        dest_loc = request.form.get('destinatario_localidad', '').strip()
        dest_cp = request.form.get('destinatario_cp', '').strip()
        dest_calle = request.form.get('destinatario_calle', '').strip()
        dest_detalles = request.form.get('destinatario_detalles', '').strip()"""
        
    nuevo_dest = """        dest_nombre = request.form.get('destinatario_nombre', '').strip() or m['nombre_completo']
        dest_prov = request.form.get('destinatario_provincia', '').strip() or m.get('provincia', '')
        dest_loc = request.form.get('destinatario_localidad', '').strip() or m.get('localidad', '')
        dest_cp = request.form.get('destinatario_cp', '').strip() or m.get('codigo_postal', '')
        dest_calle = request.form.get('destinatario_calle', '').strip()
        dest_detalles = request.form.get('destinatario_detalles', '').strip()"""

    if viejo_dest in contenido:
        contenido = contenido.replace(viejo_dest, nuevo_dest)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade107] app53.py: validaciones corregidas")


# 2. REESCRIBIR EL CHECKOUT CON TODAS LAS MEJORAS VISUALES Y DE LÓGICA
CHECKOUT_HTML = r'''{% extends "catalogo/base.html" %}
{% block title %}Checkout — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <h1 style="font-weight:300;font-size:2rem;margin-bottom:2rem;">Finalizar pedido</h1>

  <form method="post" id="form-checkout">
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

            <!-- Domicilio -->
            <div class="bloque-destino" data-destino-tipo="domicilio" style="display:none;">
              <div class="form-check mb-3 p-2 rounded" style="background:var(--cat-surface-2); border:1px solid var(--cat-border);">
                <input class="form-check-input" type="checkbox" id="check-domicilio-default" checked onchange="toggleDomicilio()">
                <label class="form-check-label fw-semibold" for="check-domicilio-default" style="font-size:.9rem; cursor:pointer;">
                  Usar los datos de mi cuenta (envío a mi dirección)
                </label>
              </div>
              <div id="preview-domicilio" style="display:block; background:var(--cat-surface); padding:1rem; border-radius:8px; margin-bottom:1rem; font-size:.9rem;">
                <div><strong>Recibe:</strong> {{ mayorista.nombre_completo }}</div>
                <div><strong>Dirección:</strong> {{ mayorista.calle or '—' }} {{ mayorista.altura or '' }} {% if mayorista.piso %}Piso {{ mayorista.piso }}{% endif %} {% if mayorista.depto %}Depto {{ mayorista.depto }}{% endif %}</div>
                <div><strong>Localidad:</strong> {{ mayorista.localidad or '—' }} ({{ mayorista.codigo_postal or '—' }}), {{ mayorista.provincia or '—' }}</div>
                <div><strong>Teléfono:</strong> {{ mayorista.telefono or '—' }}</div>
              </div>
              <div id="form-domicilio" style="display:none;">
                {% include 'catalogo/_form_direccion.html' %}
              </div>
            </div>

            <!-- Sucursal -->
            <div class="bloque-destino" data-destino-tipo="sucursal" style="display:none;">
              <div class="form-check mb-3 p-2 rounded" style="background:var(--cat-surface-2); border:1px solid var(--cat-border);">
                <input class="form-check-input" type="checkbox" id="check-sucursal-default" checked onchange="toggleSucursal()">
                <label class="form-check-label fw-semibold" for="check-sucursal-default" style="font-size:.9rem; cursor:pointer;">
                  Retiro en sucursal con mis datos
                </label>
              </div>
              <div id="preview-sucursal" style="display:block; background:var(--cat-surface); padding:1rem; border-radius:8px; margin-bottom:1rem; font-size:.9rem;">
                <div><strong>Retira:</strong> {{ mayorista.nombre_completo }} ({{ mayorista.cuit or '—' }})</div>
                <div><strong>Sucursal:</strong> {{ mayorista.localidad or '—' }} ({{ mayorista.codigo_postal or '—' }}), {{ mayorista.provincia or '—' }}</div>
                <div><strong>Teléfono:</strong> {{ mayorista.telefono or '—' }}</div>
              </div>
              <div id="form-sucursal" style="display:none;">
                <div class="row g-2">
                  <div class="col-md-6"><label style="color:var(--cat-text-muted);font-size:.8rem;">Nombre de quien retira</label><input name="destinatario_nombre" class="form-control" value="{{ mayorista.nombre_completo }}"></div>
                  <div class="col-md-6"><label style="color:var(--cat-text-muted);font-size:.8rem;">CUIT / DNI</label><input name="destinatario_doc" class="form-control" value="{{ mayorista.cuit or '' }}"></div>
                  <div class="col-md-6"><label style="color:var(--cat-text-muted);font-size:.8rem;">Localidad</label><input name="destinatario_localidad" class="form-control" value="{{ mayorista.localidad or '' }}"></div>
                  <div class="col-md-6"><label style="color:var(--cat-text-muted);font-size:.8rem;">Provincia</label><input name="destinatario_provincia" class="form-control" value="{{ mayorista.provincia or '' }}"></div>
                  <div class="col-md-6"><label style="color:var(--cat-text-muted);font-size:.8rem;">CP</label><input name="destinatario_cp" class="form-control" value="{{ mayorista.codigo_postal or '' }}"></div>
                  <div class="col-md-6"><label style="color:var(--cat-text-muted);font-size:.8rem;">Teléfono</label><input name="destinatario_tel" class="form-control" value="{{ mayorista.telefono or '' }}"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Bloque: envio personalizado -->
          <div class="bloque-envio" data-bloque="envio_personalizado" style="display:none;">
            <div class="cat-alert cat-alert-info" style="font-size:.85rem;margin-bottom:1rem;">
              Coordinamos el envío personalmente (por tu zona o con tu propio transporte). El valor de este envío se arregla por fuera.
            </div>
            <div class="form-check mb-2">
              <input class="form-check-input" type="checkbox" name="tildar_aclaracion" id="tildar_aclaracion" onchange="document.getElementById('aclaracion_text').disabled = !this.checked;">
              <label class="form-check-label" for="tildar_aclaracion" style="color:var(--cat-text);font-size:.9rem;cursor:pointer;">Quiero dejar una aclaración</label>
            </div>
            <textarea name="notas_coordinacion" id="aclaracion_text" class="form-control" rows="2" style="background:var(--cat-surface-2);border:1px solid var(--cat-border);color:var(--cat-text);" placeholder="Quiero coordinar envío personalizado por..." disabled></textarea>
          </div>
        </div>

        <!-- Notas y Factura -->
        <div class="cat-form-card mt-3" style="max-width:100%;padding:1.5rem;">
          <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Notas generales (opcional)</h6>
          <textarea name="notas" class="form-control" rows="2" placeholder="Ej: entregar despues de las 18hs, es para regalo, etc."></textarea>
          
          <hr style="border-color:var(--cat-border); margin:1.5rem 0;">
          
          <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" name="requiere_factura" id="requiere_factura" value="1" onchange="document.getElementById('opciones-factura').style.display = this.checked ? 'block' : 'none';">
            <label class="form-check-label fw-semibold" for="requiere_factura" style="color:var(--cat-text);font-size:.95rem;cursor:pointer;">Quiero Factura</label>
          </div>
          
          <div id="opciones-factura" style="display:none; margin-left:1.5rem;">
            <div class="form-check form-check-inline">
              <input class="form-check-input" type="radio" name="tipo_factura" id="fact_ab" value="A/B" onchange="document.getElementById('aviso-factura').style.display = 'block';">
              <label class="form-check-label" for="fact_ab">A / B</label>
            </div>
            <div class="form-check form-check-inline">
              <input class="form-check-input" type="radio" name="tipo_factura" id="fact_c" value="C" checked onchange="document.getElementById('aviso-factura').style.display = 'none';">
              <label class="form-check-label" for="fact_c">C</label>
            </div>
            <div id="aviso-factura" class="cat-alert cat-alert-warning mt-2 mb-0" style="display:none; font-size:.85rem; padding:.5rem;">
              <i class="bi bi-exclamation-triangle"></i> Solo realizamos Factura C. Si estás de acuerdo, marca A/B.
            </div>
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
            <span>${{ "{:,.2f}".format(item.subtotal).replace(",", "X").replace(".", ",").replace("X", ".") }}</span>
          </div>
          {% endfor %}
          <hr style="border-color:var(--cat-border);">
          <div class="d-flex justify-content-between mb-2">
            <span style="color:var(--cat-text-muted);">Peso total:</span>
            <span>{{ '%.1f'|format(info_envio.peso_total) }} kg</span>
          </div>
          {% if info_envio.requiere_cotizacion %}
          <div class="d-flex justify-content-between mb-2">
            <span class="text-warning">Valor de envío:</span>
            <span class="text-warning">A cotizar por Palet</span>
          </div>
          <hr style="border-color:var(--cat-border);">
          <div class="d-flex justify-content-between mb-3">
            <span style="font-weight:600;">Total productos</span>
            <span style="color:var(--cat-accent);font-weight:600;font-size:1.2rem;">${{ "{:,.2f}".format(subtotal).replace(",", "X").replace(".", ",").replace("X", ".") }}</span>
          </div>
          <div class="cat-alert cat-alert-warning" style="font-size:.85rem;padding:.5rem;">
            <i class="bi bi-exclamation-triangle"></i> {{ info_envio.mensaje_extra }}
          </div>
          {% else %}
          <div class="d-flex justify-content-between mb-2">
            <span style="color:var(--cat-text-muted);">Valor de envío:</span>
            <span>${{ "{:,.2f}".format(info_envio.costo_envio).replace(",", "X").replace(".", ",").replace("X", ".") }}</span>
          </div>
          <hr style="border-color:var(--cat-border);">
          <div class="d-flex justify-content-between">
            <span style="font-weight:600;">Total final</span>
            <span style="color:var(--cat-accent);font-weight:600;font-size:1.2rem;">${{ "{:,.2f}".format(total_con_envio).replace(",", "X").replace(".", ",").replace("X", ".") }}</span>
          </div>
          {% endif %}
          
          <button type="submit" name="accion" value="pagar" class="cat-btn w-100 text-center mt-3" style="background:#c9a96e; color:#000; border:none;">Pagar Ahora</button>
          <button type="button" class="cat-btn cat-btn-outline w-100 text-center mt-2" style="color:var(--cat-text); border:1px solid var(--cat-border);" onclick="mostrarModalGuardar()">Guardar Orden (Pagar después)</button>
        </div>
      </div>
    </div>
  </form>
</div>

<!-- MODAL GUARDAR ORDEN -->
<div class="modal fade" id="modalGuardar" tabindex="-1">
<div class="modal-dialog modal-dialog-centered">
<div class="modal-content" style="background:var(--cat-surface); border:1px solid var(--cat-border);">
<div class="modal-header border-0">
<h5 class="modal-title" style="color:var(--cat-text);">Guardar Orden</h5>
<button type="button" class="btn-close" data-bs-dismiss="modal" style="filter: invert(1);"></button>
</div>
<div class="modal-body" style="color:var(--cat-text-muted); font-size:.95rem;">
<p><i class="bi bi-info-circle text-warning fs-5"></i> Las órdenes se cancelan automáticamente pasadas las <strong>24hs</strong> en caso de no abonar en su totalidad la orden.</p>
<p>Debido a la desregulación en la yerba mate y en el valor de envío, serás notificado <strong>1 hora antes</strong> de su cancelación.</p>
</div>
<div class="modal-footer border-0">
<button type="button" class="cat-btn cat-btn-outline" data-bs-dismiss="modal">Volver</button>
<button type="button" class="cat-btn" style="background:#c9a96e; color:#000;" onclick="confirmarGuardar()">Entendido, Guardar</button>
</div>
</div>
</div>
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
function toggleDomicilio() {
  const chk = document.getElementById('check-domicilio-default');
  document.getElementById('preview-domicilio').style.display = chk.checked ? 'block' : 'none';
  document.getElementById('form-domicilio').style.display = chk.checked ? 'none' : 'block';
}
function toggleSucursal() {
  const chk = document.getElementById('check-sucursal-default');
  document.getElementById('preview-sucursal').style.display = chk.checked ? 'block' : 'none';
  document.getElementById('form-sucursal').style.display = chk.checked ? 'none' : 'block';
}
function mostrarModalGuardar() {
  new bootstrap.Modal(document.getElementById('modalGuardar')).show();
}
function confirmarGuardar() {
  const form = document.getElementById('form-checkout');
  const hiddenAccion = document.createElement('input');
  hiddenAccion.type = 'hidden';
  hiddenAccion.name = 'accion';
  hiddenAccion.value = 'guardar';
  form.appendChild(hiddenAccion);
  form.submit();
}
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

# 3. PINTAR LA TABLA DEL CARRITO
def patch_carrito_html():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'carrito.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Dar color a los encabezados de la tabla
    buscar_thead = '<thead>\n            <tr style="border-bottom:1px solid var(--cat-border);">'
    nuevo_thead = '<thead style="background:var(--cat-surface-2);">\n            <tr style="border-bottom:1px solid var(--cat-border);">'
    
    if buscar_thead in contenido:
        contenido = contenido.replace(buscar_thead, nuevo_thead)
        
    # Dar color a las filas alternadas
    buscar_tbody = '<tbody>'
    nuevo_tbody = '<tbody style="background:var(--cat-surface);">'
    if buscar_tbody in contenido:
        contenido = contenido.replace(buscar_tbody, nuevo_tbody)

    # Formatear precios a $0.000,00 en el carrito
    contenido = contenido.replace("${{ '%.2f'|format(item.precio) }}", "${{ '{:,.2f}'.format(item.precio).replace(',', 'X').replace('.', ',').replace('X', '.') }}")
    contenido = contenido.replace("${{ '%.2f'|format(item.subtotal) }}", "${{ '{:,.2f}'.format(item.subtotal).replace(',', 'X').replace('.', ',').replace('X', '.') }}")
    contenido = contenido.replace("${{ '%.2f'|format(subtotal) }}", "${{ '{:,.2f}'.format(subtotal).replace(',', 'X').replace('.', ',').replace('X', '.') }}")
    contenido = contenido.replace("${{ '%.2f'|format(info_envio.costo_envio) }}", "${{ '{:,.2f}'.format(info_envio.costo_envio).replace(',', 'X').replace('.', ',').replace('X', '.') }}")
    contenido = contenido.replace("${{ '%.2f'|format(subtotal + info_envio.costo_envio) }}", "${{ '{:,.2f}'.format(subtotal + info_envio.costo_envio).replace(',', 'X').replace('.', ',').replace('X', '.') }}")
    
    # Cambiar "Envío" por "Valor de envío"
    contenido = contenido.replace("<span style=\"color:var(--cat-text-muted);\">Envío ({{ info_envio.bultos }} bultos)</span>", "<span style=\"color:var(--cat-text-muted);\">Valor de envío ({{ info_envio.bultos }} bultos)</span>")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade107] carrito.html actualizado (colores y formato de precios)")


def main():
    print("=== Upgrade 107: Fix Checkout, Facturas, Envíos y Diseño ===")
    patch_app53()
    escribir('templates/catalogo/checkout.html', CHECKOUT_HTML)
    patch_carrito_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el catalogo")


if __name__ == '__main__':
    main()