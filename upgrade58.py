# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app53():
    """Fuerza que mi_pedido_detalle pase datos_pago al template."""
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        print("[upgrade58] no existe app53.py"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar la funcion mi_pedido_detalle completa y reemplazar el return
    import re

    # Buscar cualquier variante del return
    patron_return = re.compile(
        r"return render_template\('catalogo/mi_pedido_detalle\.html',\s*orden=orden,\s*items=items,\s*mayorista=m[^)]*\)"
    )
    match = patron_return.search(contenido)

    if match:
        nuevo_return = "return render_template('catalogo/mi_pedido_detalle.html', orden=orden, items=items, mayorista=m, datos_pago=datos_pago)"
        contenido = contenido[:match.start()] + nuevo_return + contenido[match.end():]
        print("[upgrade58] return de mi_pedido_detalle reemplazado")

    # Asegurar que datos_pago se calcule antes del return
    if 'from app57 import _datos_pago' not in contenido:
        # Buscar el bloque items = conn.execute... y agregar despues
        buscar = """    items = conn.execute(\"\"\"SELECT oi.*, p.nombre as producto_nombre, p.sku, p.foto
        FROM orden_items oi JOIN productos p ON p.id = oi.producto_id
        WHERE oi.orden_id=?\"\"\", (id,)).fetchall()"""

        nuevo = """    items = conn.execute(\"\"\"SELECT oi.*, p.nombre as producto_nombre, p.sku, p.foto
        FROM orden_items oi JOIN productos p ON p.id = oi.producto_id
        WHERE oi.orden_id=?\"\"\", (id,)).fetchall()

    # Cargar datos de pago
    try:
        from app57 import _datos_pago
        datos_pago = _datos_pago(conn)
    except Exception as e:
        print(f"[mi_pedido_detalle] error datos_pago: {e}")
        datos_pago = {}"""

        if buscar in contenido:
            contenido = contenido.replace(buscar, nuevo, 1)
            print("[upgrade58] carga de datos_pago agregada")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_template():
    """Reescribe la seccion de comprobante del template del pedido del mayorista."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'mi_pedido_detalle.html')
    if not os.path.exists(ruta):
        print("[upgrade58] no existe mi_pedido_detalle.html"); return

    # Reescribir el template completo para asegurar consistencia
    template = r'''{% extends "catalogo/base.html" %}
{% block title %}Pedido {{ orden.numero_interno }} — Familia Zaragoza ®{% endblock %}

{% block content %}
<div class="container py-5">
  <div class="d-flex justify-content-between align-items-start mb-4">
    <div>
      <h1 style="font-weight:300;font-size:2rem;margin-bottom:.5rem;">Pedido {{ orden.numero_interno }}</h1>
      <p style="color:var(--cat-text-muted);">{{ orden.fecha }}</p>
    </div>
    <a href="{{ url_for('catalogo.mis_pedidos') }}" style="color:var(--cat-text-muted);text-decoration:none;"><i class="bi bi-arrow-left"></i> Volver</a>
  </div>

  <div class="cat-form-card" style="max-width:100%;padding:2rem;">
    <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Productos</h6>
    <table class="table" style="color:var(--cat-text);">
      <thead>
        <tr style="border-bottom:1px solid var(--cat-border);">
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:.75rem 0;">Producto</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:.75rem 0;text-align:center;">Cant.</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:.75rem 0;text-align:right;">Precio</th>
          <th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:.75rem 0;text-align:right;">Subtotal</th>
        </tr>
      </thead>
      <tbody>
        {% for it in items %}
        <tr style="border-bottom:1px solid var(--cat-border);">
          <td style="padding:.75rem 0;">{{ it.producto_nombre }}</td>
          <td style="padding:.75rem 0;text-align:center;">{{ '%g'|format(it.cantidad) }}</td>
          <td style="padding:.75rem 0;text-align:right;">${{ '%.2f'|format(it.precio_unitario) }}</td>
          <td style="padding:.75rem 0;text-align:right;">${{ '%.2f'|format(it.subtotal) }}</td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr>
          <td colspan="3" style="text-align:right;font-weight:600;padding-top:1rem;">Total</td>
          <td style="text-align:right;font-weight:600;color:var(--cat-accent);padding-top:1rem;font-size:1.1rem;">${{ '%.2f'|format(orden.total) }}</td>
        </tr>
      </tfoot>
    </table>

    {% if orden.notas %}
    <hr style="border-color:var(--cat-border);margin:1.5rem 0;">
    <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:.5rem;">Notas</h6>
    <p style="color:var(--cat-text);">{{ orden.notas }}</p>
    {% endif %}

    <!-- ===== ESTADO DEL PAGO ===== -->
    <hr style="border-color:var(--cat-border);margin:1.5rem 0;">
    <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:1rem;">Estado del pago</h6>

    {% if orden.comprobante_estado == 'aprobado' %}
    <div class="cat-alert cat-alert-success">
      <i class="bi bi-check-circle"></i> Tu pago fue aprobado. Estamos preparando tu pedido.
    </div>
    {% elif orden.comprobante_estado == 'subido' %}
    <div class="cat-alert cat-alert-info">
      <i class="bi bi-hourglass-split"></i> Comprobante recibido. Estamos verificando el pago. Te avisamos por email cuando lo aprobemos.
    </div>
    {% if orden.comprobante_archivo %}
    <a href="{{ url_for('catalogo.ver_mi_comprobante', id=orden.id) }}" target="_blank" style="color:var(--cat-accent);font-size:.85rem;display:inline-block;margin-top:.5rem;">
      <i class="bi bi-file-earmark-text"></i> Ver comprobante subido
    </a>
    {% endif %}
    {% elif orden.comprobante_estado == 'rechazado' %}
    <div class="cat-alert cat-alert-danger">
      <i class="bi bi-x-circle"></i> <strong>Comprobante rechazado</strong>
      {% if orden.comprobante_motivo_rechazo %}<br>Motivo: {{ orden.comprobante_motivo_rechazo }}{% endif %}
      <br>Podes subir uno nuevo a continuacion.
    </div>
    {% endif %}

    <!-- ===== DATOS DE PAGO (siempre visibles si esta pendiente) ===== -->
    {% if orden.estado == 'pendiente_pago' and orden.comprobante_estado != 'subido' %}
    <div style="background:var(--cat-surface-2);border:1px solid var(--cat-border);border-radius:10px;padding:1.5rem;margin-top:1rem;">
      <h6 style="color:var(--cat-text);font-weight:600;margin-bottom:1rem;"><i class="bi bi-bank"></i> Datos para la transferencia</h6>

      {% if not datos_pago or (not datos_pago.pago_alias and not datos_pago.pago_cbu) %}
      <div class="cat-alert cat-alert-warning" style="margin-bottom:0;">
        <i class="bi bi-exclamation-triangle"></i>
        Los datos de transferencia aun no estan configurados.
        <br><small>Contactanos por email y te los enviamos.</small>
      </div>
      {% else %}
      <div class="row g-2 mb-3">
        {% if datos_pago.pago_alias %}
        <div class="col-md-6"><div style="background:var(--cat-surface);padding:.75rem;border-radius:6px;"><div style="color:var(--cat-text-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;">Alias</div><div style="font-weight:500;font-size:1rem;">{{ datos_pago.pago_alias }}</div></div></div>
        {% endif %}
        {% if datos_pago.pago_cbu %}
        <div class="col-md-6"><div style="background:var(--cat-surface);padding:.75rem;border-radius:6px;"><div style="color:var(--cat-text-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;">CBU</div><div style="font-weight:500;font-size:.9rem;font-family:monospace;">{{ datos_pago.pago_cbu }}</div></div></div>
        {% endif %}
        {% if datos_pago.pago_titular %}
        <div class="col-md-6"><div style="background:var(--cat-surface);padding:.75rem;border-radius:6px;"><div style="color:var(--cat-text-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;">Titular</div><div style="font-weight:500;">{{ datos_pago.pago_titular }}</div></div></div>
        {% endif %}
        {% if datos_pago.pago_cuit %}
        <div class="col-md-6"><div style="background:var(--cat-surface);padding:.75rem;border-radius:6px;"><div style="color:var(--cat-text-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;">CUIT</div><div style="font-weight:500;">{{ datos_pago.pago_cuit }}</div></div></div>
        {% endif %}
        {% if datos_pago.pago_banco %}
        <div class="col-12"><div style="background:var(--cat-surface);padding:.75rem;border-radius:6px;"><div style="color:var(--cat-text-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;">Banco</div><div style="font-weight:500;">{{ datos_pago.pago_banco }}</div></div></div>
        {% endif %}
      </div>
      {% if datos_pago.pago_instrucciones %}
      <p style="color:var(--cat-text-muted);font-size:.85rem;margin-bottom:1rem;">{{ datos_pago.pago_instrucciones }}</p>
      {% endif %}

      <!-- Formulario para subir comprobante -->
      <form method="post" action="{{ url_for('catalogo.subir_comprobante', id=orden.id) }}" enctype="multipart/form-data" style="border-top:1px solid var(--cat-border);padding-top:1rem;">
        <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;display:block;margin-bottom:.5rem;">Ya transferiste? Subi el comprobante *</label>
        <input type="file" name="comprobante" class="form-control mb-2" accept=".pdf,.jpg,.jpeg,.png,.webp" required style="background:var(--cat-surface);border:1px solid var(--cat-border);color:var(--cat-text);">
        <button type="submit" class="cat-btn">Enviar comprobante</button>
      </form>
      {% endif %}
    </div>
    {% endif %}

    <!-- Cancelar pedido -->
    {% if orden.estado == 'pendiente_pago' and orden.comprobante_estado == 'sin_comprobante' %}
    <form method="post" action="{{ url_for('catalogo.cancelar_pedido_mayorista', id=orden.id) }}" class="mt-3" onsubmit="return confirm('Cancelar este pedido?')">
      <button type="submit" style="background:none;border:1px solid var(--cat-border);color:#f87171;padding:.5rem 1rem;border-radius:6px;font-size:.8rem;">Cancelar pedido</button>
    </form>
    {% endif %}

  </div>
</div>
{% endblock %}
'''

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(template)
    print("[upgrade58] template mi_pedido_detalle reescrito")


def verificar_config():
    """Verifica que los datos de pago estén cargados."""
    import sqlite3
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade58] sin DB"); return
    conn = sqlite3.connect(db)
    claves = ['pago_alias', 'pago_cbu', 'pago_titular']
    faltan = []
    for k in claves:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
        if not row or not row[0]:
            faltan.append(k)
    conn.close()
    if faltan:
        print(f"[upgrade58] AVISO: estos datos de pago estan vacios: {', '.join(faltan)}")
        print("[upgrade58] => Anda a Configuracion -> Datos de pago y completalos")
    else:
        print("[upgrade58] Datos de pago OK")


def main():
    print("=== Upgrade 58: Fix datos de pago en pedido del mayorista ===")
    patch_app53()
    patch_template()
    verificar_config()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")
    print("Despues entrá al pedido del mayorista y deberías ver los datos de transferencia")


if __name__ == '__main__':
    main()