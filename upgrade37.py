# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade37] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade37] sin DB."); return
    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(ordenes_venta)").fetchall()]
    if 'tipo_envio' not in cols:
        conn.execute("ALTER TABLE ordenes_venta ADD COLUMN tipo_envio TEXT")
        print("[upgrade37] + ordenes_venta.tipo_envio")
    if 'destino_tipo' not in cols:
        conn.execute("ALTER TABLE ordenes_venta ADD COLUMN destino_tipo TEXT")
        print("[upgrade37] + ordenes_venta.destino_tipo")
    if 'sucursal_detalle' not in cols:
        conn.execute("ALTER TABLE ordenes_venta ADD COLUMN sucursal_detalle TEXT")
        print("[upgrade37] + ordenes_venta.sucursal_detalle")
    conn.commit(); conn.close()


APP37_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app36 import app
from app import permiso_required
from database import get_db
from app4 import _cargar_orden


@app.route('/ventas/<int:id>/envio', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_envio_v3(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error')
        return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error')
        return redirect(url_for('ventas_lista'))

    tipo_envio = request.form.get('tipo_envio', '').strip()
    if tipo_envio not in ('retira_deposito', 'transporte', 'envio_personal'):
        conn.close(); flash('Tenes que elegir un tipo de envio.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    # Datos comunes
    dest_nombre = request.form.get('destinatario_nombre', '').strip() or None
    dest_prov = request.form.get('destinatario_provincia', '').strip() or None
    dest_loc = request.form.get('destinatario_localidad', '').strip() or None
    dest_cp = request.form.get('destinatario_cp', '').strip() or None
    dest_calle = request.form.get('destinatario_calle', '').strip() or None
    dest_detalles = request.form.get('destinatario_detalles', '').strip() or None

    if tipo_envio == 'retira_deposito':
        # No requiere transportista ni direccion
        conn.execute("""UPDATE ordenes_venta SET
            tipo_envio='retira_deposito', destino_tipo=NULL, sucursal_detalle=NULL,
            transportista_id=NULL, nro_guia=NULL,
            destinatario_nombre=?, destinatario_detalles=?,
            destinatario_provincia=NULL, destinatario_localidad=NULL,
            destinatario_cp=NULL, destinatario_calle=NULL
            WHERE id=?""",
            (dest_nombre, dest_detalles, id))
        conn.commit(); conn.close()
        flash('Datos de envio guardados: retira en deposito.', 'success')
        return redirect(url_for('ventas_detalle', id=id))

    if tipo_envio == 'envio_personal':
        # Requiere direccion, no requiere transportista
        if not (dest_calle and dest_loc and dest_prov):
            conn.close()
            flash('Para envio personal tenes que cargar calle, localidad y provincia del destinatario.', 'error')
            return redirect(url_for('ventas_detalle', id=id))
        conn.execute("""UPDATE ordenes_venta SET
            tipo_envio='envio_personal', destino_tipo='domicilio', sucursal_detalle=NULL,
            transportista_id=NULL, nro_guia=NULL,
            destinatario_nombre=?, destinatario_provincia=?, destinatario_localidad=?,
            destinatario_cp=?, destinatario_calle=?, destinatario_detalles=?
            WHERE id=?""",
            (dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles, id))
        conn.commit(); conn.close()
        flash('Datos de envio guardados: envio personal.', 'success')
        return redirect(url_for('ventas_detalle', id=id))

    # tipo_envio == 'transporte'
    destino_tipo = request.form.get('destino_tipo', '').strip()
    if destino_tipo not in ('domicilio', 'sucursal'):
        conn.close()
        flash('Para envio por transporte tenes que elegir destino: Domicilio o Sucursal.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    transportista_id = request.form.get('transportista_id') or None
    if not transportista_id:
        conn.close()
        flash('Para envio por transporte tenes que elegir un transportista.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    sucursal_detalle = request.form.get('sucursal_detalle', '').strip() or None
    if destino_tipo == 'sucursal' and not sucursal_detalle:
        conn.close()
        flash('Indica a que sucursal se envia.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    if destino_tipo == 'domicilio' and not (dest_calle and dest_loc and dest_prov):
        conn.close()
        flash('Para envio a domicilio tenes que cargar calle, localidad y provincia.', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    conn.execute("""UPDATE ordenes_venta SET
        tipo_envio='transporte', destino_tipo=?, sucursal_detalle=?,
        transportista_id=?, nro_guia=?,
        destinatario_nombre=?, destinatario_provincia=?, destinatario_localidad=?,
        destinatario_cp=?, destinatario_calle=?, destinatario_detalles=?
        WHERE id=?""",
        (destino_tipo, sucursal_detalle, int(transportista_id),
         request.form.get('nro_guia', '').strip() or None,
         dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles, id))
    conn.commit(); conn.close()
    flash('Datos de envio guardados: transporte a ' + ('domicilio' if destino_tipo == 'domicilio' else 'sucursal') + '.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


app.view_functions['ventas_envio'] = ventas_envio_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


# Nuevo template detalle con seccion de envio mejorada
VENTAS_DETALLE = r'''{% extends "base.html" %}
{% block title %}{{ orden.numero_interno }}{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-0">{{ orden.numero_interno }}
{% if orden.estado=='pendiente_pago' %}<span class="badge bg-warning text-dark ms-2">Pendiente pago</span>
{% elif orden.estado=='pagado_sin_enviar' %}<span class="badge bg-info text-dark ms-2">Pagado/Sin enviar</span>
{% elif orden.estado=='pagado_enviado' %}<span class="badge bg-success ms-2">Pagado/Enviado</span>
{% else %}<span class="badge bg-secondary ms-2">Cancelado</span>{% endif %}
</h4>
<div class="text-muted small">{{ orden.fecha }} - {{ orden.vendedor_nombre }} - {{ orden.canal_nombre or 'Sin canal' }}</div>
</div>
<div>
<a href="{{ url_for('ventas_lista') }}" class="btn btn-outline-secondary btn-sm"><i class="bi bi-arrow-left"></i> Volver</a>
{% if orden.estado=='pagado_sin_enviar' %}<form method="post" action="{{ url_for('ventas_estado', id=orden.id) }}" class="d-inline"><input type="hidden" name="estado" value="pagado_enviado"><button class="btn btn-success btn-sm"><i class="bi bi-truck"></i> Marcar enviado</button></form>{% endif %}
{% if orden.estado!='cancelado' %}<form method="post" action="{{ url_for('ventas_estado', id=orden.id) }}" class="d-inline" onsubmit="return confirm('Cancelar y devolver stock?')"><input type="hidden" name="estado" value="cancelado"><button class="btn btn-outline-danger btn-sm"><i class="bi bi-x-lg"></i> Cancelar</button></form>{% endif %}
</div></div>

<div class="row g-3 mb-3">
<div class="col-md-6"><div class="card shadow-sm h-100"><div class="card-body">
<h6 class="text-muted mb-3"><i class="bi bi-person"></i> Cliente</h6>
<div class="fw-semibold">{{ orden.cliente_nombre }}</div>
{% if orden.cliente_doc %}<div class="small text-muted">{{ orden.cliente_tipo_doc or '' }} {{ orden.cliente_doc }}</div>{% endif %}
{% if orden.cliente_email %}<div class="small"><i class="bi bi-envelope"></i> {{ orden.cliente_email }}</div>{% endif %}
{% if orden.cliente_telefono %}<div class="small"><i class="bi bi-telephone"></i> {{ orden.cliente_telefono }}</div>{% endif %}
<div class="small"><i class="bi bi-geo-alt"></i> {{ orden.cliente_provincia or '-' }}, {{ orden.cliente_localidad or '-' }}</div>
</div></div></div>
<div class="col-md-6"><div class="card shadow-sm h-100"><div class="card-body">
<h6 class="text-muted mb-3"><i class="bi bi-receipt"></i> Resumen</h6>
<table class="table table-sm mb-0">
<tr><td>Tipo:</td><td class="text-end">{{ orden.tipo }}</td></tr>
<tr><td>Subtotal:</td><td class="text-end">${{ '%.2f'|format(orden.subtotal) }}</td></tr>
<tr><td>Descuento:</td><td class="text-end">${{ '%.2f'|format(orden.descuento) }}</td></tr>
<tr class="fw-bold"><td>Total:</td><td class="text-end">${{ '%.2f'|format(orden.total) }}</td></tr>
<tr><td>Pagado:</td><td class="text-end">${{ '%.2f'|format(total_pagado) }}</td></tr>
<tr><td>Saldo:</td><td class="text-end {% if total_pagado < orden.total %}text-danger{% else %}text-success{% endif %}">${{ '%.2f'|format(orden.total - total_pagado) }}</td></tr>
</table></div></div></div>
</div>

<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="text-muted mb-3">Productos</h6>
<table class="table table-sm mb-0"><thead><tr><th>Producto</th><th class="text-end">Cant.</th><th class="text-end">Precio</th><th class="text-end">Subtotal</th></tr></thead><tbody>
{% for it in items %}<tr><td>{{ it.producto_nombre }} {% if it.sku %}<small class="text-muted">({{ it.sku }})</small>{% endif %}</td><td class="text-end">{{ '%g'|format(it.cantidad) }}</td><td class="text-end">${{ '%.2f'|format(it.precio_unitario) }}</td><td class="text-end">${{ '%.2f'|format(it.subtotal) }}</td></tr>{% endfor %}
</tbody></table></div></div>

<!-- ===== DATOS DE ENVIO (U37) ===== -->
<div class="card shadow-sm mb-3" style="border-left:4px solid #3b5bdb;">
<div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0"><i class="bi bi-truck"></i> Datos de envio</h6>
{% if orden.tipo_envio %}
{% if orden.tipo_envio == 'retira_deposito' %}<span class="badge bg-warning text-dark">Retira en deposito</span>
{% elif orden.tipo_envio == 'envio_personal' %}<span class="badge bg-info text-dark">Envio personal</span>
{% elif orden.tipo_envio == 'transporte' %}<span class="badge bg-success">Transporte{% if orden.destino_tipo %} / {{ 'Domicilio' if orden.destino_tipo == 'domicilio' else 'Sucursal' }}{% endif %}</span>
{% endif %}
{% else %}<span class="badge bg-secondary">Sin definir</span>{% endif %}
</div>

<form method="post" action="{{ url_for('ventas_envio', id=orden.id) }}" id="form-envio">

<!-- Tipo de envio -->
<label class="form-label fw-semibold small mb-2">Tipo de envio *</label>
<div class="row g-2 mb-3">
<div class="col-md-4">
<label class="tipo-card {% if orden.tipo_envio == 'retira_deposito' %}active{% endif %}" data-tipo="retira_deposito">
<input type="radio" name="tipo_envio" value="retira_deposito" class="d-none" {% if orden.tipo_envio == 'retira_deposito' %}checked{% endif %} required>
<div class="text-center p-3 border rounded h-100" style="cursor:pointer;">
<i class="bi bi-shop fs-3 d-block mb-1"></i>
<div class="fw-semibold small">Retira en deposito</div>
<div class="text-muted" style="font-size:.72rem;">El cliente pasa a retirar</div>
</div>
</label>
</div>
<div class="col-md-4">
<label class="tipo-card {% if orden.tipo_envio == 'transporte' %}active{% endif %}" data-tipo="transporte">
<input type="radio" name="tipo_envio" value="transporte" class="d-none" {% if orden.tipo_envio == 'transporte' %}checked{% endif %}>
<div class="text-center p-3 border rounded h-100" style="cursor:pointer;">
<i class="bi bi-truck fs-3 d-block mb-1"></i>
<div class="fw-semibold small">Medio de transporte</div>
<div class="text-muted" style="font-size:.72rem;">Andreani, Via Cargo, etc.</div>
</div>
</label>
</div>
<div class="col-md-4">
<label class="tipo-card {% if orden.tipo_envio == 'envio_personal' %}active{% endif %}" data-tipo="envio_personal">
<input type="radio" name="tipo_envio" value="envio_personal" class="d-none" {% if orden.tipo_envio == 'envio_personal' %}checked{% endif %}>
<div class="text-center p-3 border rounded h-100" style="cursor:pointer;">
<i class="bi bi-car-front fs-3 d-block mb-1"></i>
<div class="fw-semibold small">Envio personal</div>
<div class="text-muted" style="font-size:.72rem;">Entrega en la ciudad</div>
</div>
</label>
</div>
</div>

<!-- BLOQUE: RETIRA EN DEPOSITO -->
<div class="bloque-tipo" data-bloque="retira_deposito" {% if orden.tipo_envio != 'retira_deposito' %}style="display:none;"{% endif %}>
<div class="alert alert-light border mb-2 small"><i class="bi bi-info-circle"></i> El cliente retira personalmente en el deposito. No requiere direccion ni transportista.</div>
<div class="mb-2">
<label class="form-label small">Nombre de quien retira</label>
<input name="destinatario_nombre" class="form-control form-control-sm" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}" placeholder="Nombre y apellido">
</div>
<div class="mb-2">
<label class="form-label small">Notas adicionales</label>
<textarea name="destinatario_detalles" class="form-control form-control-sm" rows="2" placeholder="Ej: retira los martes por la tarde">{{ orden.destinatario_detalles or '' }}</textarea>
</div>
</div>

<!-- BLOQUE: TRANSPORTE -->
<div class="bloque-tipo" data-bloque="transporte" {% if orden.tipo_envio != 'transporte' %}style="display:none;"{% endif %}>

<label class="form-label fw-semibold small mb-2">Destino *</label>
<div class="row g-2 mb-3">
<div class="col-md-6">
<label class="destino-card {% if orden.destino_tipo == 'domicilio' %}active{% endif %}" data-destino="domicilio">
<input type="radio" name="destino_tipo" value="domicilio" class="d-none" {% if orden.destino_tipo == 'domicilio' %}checked{% endif %}>
<div class="p-2 border rounded d-flex align-items-center gap-2" style="cursor:pointer;">
<i class="bi bi-house fs-5"></i>
<div><div class="fw-semibold small">Domicilio</div><div class="text-muted" style="font-size:.72rem;">Direccion completa</div></div>
</div>
</label>
</div>
<div class="col-md-6">
<label class="destino-card {% if orden.destino_tipo == 'sucursal' %}active{% endif %}" data-destino="sucursal">
<input type="radio" name="destino_tipo" value="sucursal" class="d-none" {% if orden.destino_tipo == 'sucursal' %}checked{% endif %}>
<div class="p-2 border rounded d-flex align-items-center gap-2" style="cursor:pointer;">
<i class="bi bi-building fs-5"></i>
<div><div class="fw-semibold small">Sucursal</div><div class="text-muted" style="font-size:.72rem;">Retira en sucursal del correo</div></div>
</div>
</label>
</div>
</div>

<div class="row g-2 mb-3">
<div class="col-md-6">
<label class="form-label small">Transportista *</label>
<select name="transportista_id" class="form-select form-select-sm">
<option value="">-- Elegir --</option>
{% for t in transportistas %}
<option value="{{ t.id }}" {% if orden.transportista_id == t.id %}selected{% endif %}>{{ t.nombre }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-6">
<label class="form-label small">Nro de guia</label>
<input name="nro_guia" class="form-control form-control-sm" value="{{ orden.nro_guia or '' }}" placeholder="Se puede cargar despues">
</div>
</div>

<div class="bloque-destino" data-destino-tipo="domicilio" {% if orden.destino_tipo != 'domicilio' %}style="display:none;"{% endif %}>
<div class="row g-2">
<div class="col-md-6"><label class="form-label small">Nombre del destinatario</label><input name="destinatario_nombre" class="form-control form-control-sm" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}"></div>
<div class="col-md-6"><label class="form-label small">Calle y altura *</label><input name="destinatario_calle" class="form-control form-control-sm" value="{{ orden.destinatario_calle or '' }}"></div>
<div class="col-md-4"><label class="form-label small">Localidad *</label><input name="destinatario_localidad" class="form-control form-control-sm" value="{{ orden.destinatario_localidad or '' }}"></div>
<div class="col-md-4"><label class="form-label small">Provincia *</label><input name="destinatario_provincia" class="form-control form-control-sm" value="{{ orden.destinatario_provincia or '' }}"></div>
<div class="col-md-4"><label class="form-label small">CP</label><input name="destinatario_cp" class="form-control form-control-sm" value="{{ orden.destinatario_cp or '' }}"></div>
<div class="col-12"><label class="form-label small">Detalles adicionales</label><textarea name="destinatario_detalles" class="form-control form-control-sm" rows="2">{{ orden.destinatario_detalles or '' }}</textarea></div>
</div>
</div>

<div class="bloque-destino" data-destino-tipo="sucursal" {% if orden.destino_tipo != 'sucursal' %}style="display:none;"{% endif %}>
<div class="row g-2">
<div class="col-md-6"><label class="form-label small">Nombre del destinatario</label><input name="destinatario_nombre" class="form-control form-control-sm" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}"></div>
<div class="col-md-6"><label class="form-label small">Sucursal donde retira *</label><input name="sucursal_detalle" class="form-control form-control-sm" value="{{ orden.sucursal_detalle or '' }}" placeholder="Ej: Sucursal Andreani Cordoba Centro"></div>
<div class="col-md-4"><label class="form-label small">Localidad de la sucursal</label><input name="destinatario_localidad" class="form-control form-control-sm" value="{{ orden.destinatario_localidad or '' }}"></div>
<div class="col-md-4"><label class="form-label small">Provincia</label><input name="destinatario_provincia" class="form-control form-control-sm" value="{{ orden.destinatario_provincia or '' }}"></div>
<div class="col-md-4"><label class="form-label small">CP</label><input name="destinatario_cp" class="form-control form-control-sm" value="{{ orden.destinatario_cp or '' }}"></div>
<div class="col-12"><label class="form-label small">Detalles adicionales</label><textarea name="destinatario_detalles" class="form-control form-control-sm" rows="2">{{ orden.destinatario_detalles or '' }}</textarea></div>
</div>
</div>
</div>

<!-- BLOQUE: ENVIO PERSONAL -->
<div class="bloque-tipo" data-bloque="envio_personal" {% if orden.tipo_envio != 'envio_personal' %}style="display:none;"{% endif %}>
<div class="alert alert-light border mb-2 small"><i class="bi bi-info-circle"></i> Entrega personal dentro de la ciudad. No requiere transportista.</div>
<div class="row g-2">
<div class="col-md-6"><label class="form-label small">Nombre del destinatario</label><input name="destinatario_nombre" class="form-control form-control-sm" value="{{ orden.destinatario_nombre or orden.cliente_nombre }}"></div>
<div class="col-md-6"><label class="form-label small">Calle y altura *</label><input name="destinatario_calle" class="form-control form-control-sm" value="{{ orden.destinatario_calle or '' }}"></div>
<div class="col-md-4"><label class="form-label small">Localidad *</label><input name="destinatario_localidad" class="form-control form-control-sm" value="{{ orden.destinatario_localidad or '' }}"></div>
<div class="col-md-4"><label class="form-label small">Provincia *</label><input name="destinatario_provincia" class="form-control form-control-sm" value="{{ orden.destinatario_provincia or '' }}"></div>
<div class="col-md-4"><label class="form-label small">CP</label><input name="destinatario_cp" class="form-control form-control-sm" value="{{ orden.destinatario_cp or '' }}"></div>
<div class="col-12"><label class="form-label small">Detalles / horarios</label><textarea name="destinatario_detalles" class="form-control form-control-sm" rows="2" placeholder="Ej: entregar despues de las 18hs">{{ orden.destinatario_detalles or '' }}</textarea></div>
</div>
</div>

<div class="mt-3"><button class="btn btn-dark btn-sm">Guardar datos de envio</button></div>
</form>
</div></div>
<!-- ===== FIN DATOS DE ENVIO ===== -->

<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="text-muted mb-3"><i class="bi bi-envelope-paper"></i> Notificaciones por email</h6>
<div class="d-flex flex-wrap gap-2">
<button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-confirmacion"><i class="bi bi-file-text"></i> Enviar orden</button>
<button class="btn btn-outline-success btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-pago"><i class="bi bi-cash-coin"></i> Notificar pago</button>
<button class="btn btn-outline-info btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-envio"><i class="bi bi-truck"></i> Notificar envio</button>
<button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-entrega"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button class="btn btn-outline-dark btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-factura"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>

{% set tipos_botones = [('confirmacion','mail-confirmacion','Enviar orden'),('pago','mail-pago','Notificar pago'),('envio','mail-envio','Notificar envio'),('entrega','mail-entrega','Notificar entrega'),('factura','mail-factura','Enviar factura')] %}
{% for tipo, col_id, titulo in tipos_botones %}
<div class="collapse mt-3" id="{{ col_id }}">
<div class="border rounded p-3 bg-light">
<h6 class="mb-2">{{ titulo }}</h6>
{% if tipo == 'envio' and (not orden.transportista_nombre or not orden.nro_guia) %}
<div class="alert alert-warning py-2 small mb-2"><i class="bi bi-exclamation-triangle"></i> Carga primero el transportista y el numero de guia para que el cliente reciba el link de seguimiento.</div>
{% endif %}
<form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo=tipo) }}">
<div class="mb-2">
<label class="form-label small">Destinatario</label>
<input name="destinatario" type="email" class="form-control form-control-sm" value="{{ orden.cliente_email or '' }}" required>
</div>
{% if tipo == 'factura' %}
<div class="mb-2">
<label class="form-label small">Adjuntar (opcional)</label>
{% if archivos %}
{% for a in archivos %}
<div class="form-check">
<input class="form-check-input" type="checkbox" name="adjunto_id" value="{{ a.id }}" id="adj-{{ a.id }}">
<label class="form-check-label small" for="adj-{{ a.id }}"><i class="bi bi-paperclip"></i> {{ a.nombre_original }}</label>
</div>
{% endfor %}
{% else %}
<div class="small text-muted">No hay archivos subidos.</div>
{% endif %}
</div>
{% endif %}
<button class="btn btn-primary btn-sm"><i class="bi bi-send"></i> Enviar</button>
</form>
</div>
</div>
{% endfor %}
</div></div>

<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="text-muted mb-3"><i class="bi bi-paperclip"></i> Adjuntos</h6>
<form method="post" action="{{ url_for('ventas_adjunto_subir', id=orden.id) }}" enctype="multipart/form-data" class="mb-3">
<div class="row g-2 align-items-end">
<div class="col-md-4"><label class="form-label small">Archivo</label><input type="file" name="archivo" class="form-control form-control-sm" required></div>
<div class="col-md-3"><label class="form-label small">Tipo</label><select name="tipo" class="form-select form-select-sm">
<option value="factura">Factura</option>
<option value="comprobante">Comprobante</option>
<option value="guia">Guia</option>
<option value="otro">Otro</option>
</select></div>
<div class="col-md-3"><button class="btn btn-dark btn-sm"><i class="bi bi-upload"></i> Subir</button></div>
</div>
</form>
{% if archivos %}
<table class="table table-sm mb-0">
<thead><tr><th>Tipo</th><th>Archivo</th><th>Subido</th><th class="text-end"></th></tr></thead>
<tbody>
{% for a in archivos %}
<tr><td><span class="badge bg-secondary">{{ a.tipo }}</span></td>
<td class="small"><i class="bi bi-file-earmark"></i> {{ a.nombre_original }}</td>
<td class="small text-muted">{{ a.fecha[:16] if a.fecha else '' }}</td>
<td class="text-end">
<a href="{{ url_for('ventas_adjunto_descargar', id=orden.id, aid=a.id) }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-download"></i></a>
<form method="post" action="{{ url_for('ventas_adjunto_eliminar', id=orden.id, aid=a.id) }}" class="d-inline" onsubmit="return confirm('Eliminar archivo?')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
</td></tr>
{% endfor %}
</tbody></table>
{% else %}<div class="text-muted small">Sin archivos subidos.</div>{% endif %}
</div></div>

<div class="row g-3 mb-3">
<div class="col-md-6"><div class="card shadow-sm h-100"><div class="card-body">
<h6 class="text-muted mb-3"><i class="bi bi-cash"></i> Pagos</h6>
{% if pagos %}<table class="table table-sm mb-3"><thead><tr><th>Fecha</th><th>Medio</th><th class="text-end">Monto</th><th class="text-end">Neto</th><th></th></tr></thead><tbody>
{% for p in pagos %}<tr><td class="small">{{ p.fecha }}</td><td class="small">{{ p.medio_nombre or '-' }}</td><td class="text-end">${{ '%.2f'|format(p.monto) }}</td><td class="text-end">${{ '%.2f'|format(p.monto_neto) }}</td>
<td class="text-end">{% if orden.estado=='pendiente_pago' %}<form method="post" action="{{ url_for('ventas_pago_eliminar', id=orden.id, pago_id=p.id) }}" class="d-inline" onsubmit="return confirm('Eliminar pago?')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>{% endif %}</td></tr>{% endfor %}
</tbody></table>{% else %}<p class="text-muted small">Sin pagos.</p>{% endif %}
{% if orden.estado!='cancelado' and total_pagado < orden.total %}
<button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#pago-form"><i class="bi bi-plus-lg"></i> Registrar pago</button>
<div class="collapse mt-2" id="pago-form"><form method="post" action="{{ url_for('ventas_pago', id=orden.id) }}" class="border rounded p-2 bg-light">
<div class="row g-2">
<div class="col-md-6"><label class="form-label small">Monto *</label><input type="number" step="0.01" min="0.01" name="monto" value="{{ '%.2f'|format(orden.total - total_pagado) }}" class="form-control form-control-sm" required></div>
<div class="col-md-6"><label class="form-label small">Medio</label><select name="medio_pago_id" class="form-select form-select-sm">{% for m in medios %}<option value="{{ m.id }}">{{ m.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-6"><label class="form-label small">Comision MP</label><input type="number" step="0.01" min="0" name="comision" value="0" class="form-control form-control-sm"></div>
<div class="col-md-6"><label class="form-label small">Fecha</label><input type="date" name="fecha" class="form-control form-control-sm" value="{{ orden.fecha }}"></div>
<div class="col-12"><button class="btn btn-primary btn-sm">Registrar</button></div>
</div></form></div>
{% endif %}
</div></div></div>

<div class="col-md-6"><div class="card shadow-sm h-100"><div class="card-body">
<h6 class="text-muted mb-3"><i class="bi bi-file-earmark-text"></i> Facturacion</h6>
<div class="mb-2">
{% if orden.estado_facturacion=='facturada' %}<span class="badge bg-success">Facturada</span><div class="small mt-1">Nro ARCA: <strong>{{ orden.nro_factura_arca }}</strong></div><div class="small text-muted">Fecha: {{ orden.fecha_factura }}</div>
{% elif orden.estado_facturacion=='pendiente' %}<span class="badge bg-warning text-dark">Pendiente de facturar</span>
{% else %}<span class="badge bg-secondary">No requiere</span>{% endif %}
</div>
<button class="btn btn-outline-primary btn-sm" data-bs-toggle="collapse" data-bs-target="#factura-form"><i class="bi bi-pencil"></i> Actualizar</button>
<div class="collapse mt-2" id="factura-form"><form method="post" action="{{ url_for('ventas_factura', id=orden.id) }}" class="border rounded p-2 bg-light">
<div class="mb-2"><select name="estado_facturacion" class="form-select form-select-sm">
<option value="no_requiere" {% if orden.estado_facturacion=='no_requiere' %}selected{% endif %}>No requiere</option>
<option value="pendiente" {% if orden.estado_facturacion=='pendiente' %}selected{% endif %}>Pendiente de facturar</option>
<option value="facturada" {% if orden.estado_facturacion=='facturada' %}selected{% endif %}>Facturada</option></select></div>
<div class="row g-2">
<div class="col-md-6"><label class="form-label small">Nro ARCA</label><input name="nro_factura_arca" class="form-control form-control-sm" value="{{ orden.nro_factura_arca or '' }}"></div>
<div class="col-md-6"><label class="form-label small">Fecha</label><input type="date" name="fecha_factura" class="form-control form-control-sm" value="{{ orden.fecha_factura or '' }}"></div>
</div>
<button class="btn btn-primary btn-sm mt-2">Guardar</button></form></div>
</div></div></div>
</div>

<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="text-muted mb-3"><i class="bi bi-clock-history"></i> Historial de esta orden</h6>
{% if emails %}
<table class="table table-sm mb-0"><thead><tr><th>Fecha</th><th>Tipo</th><th>Destinatario</th><th>Asunto</th><th>Estado</th></tr></thead><tbody>
{% for e in emails %}
<tr><td class="small">{{ e.fecha[:16] if e.fecha else '' }}</td>
<td><span class="badge bg-secondary">{{ e.tipo }}</span></td>
<td class="small">{{ e.destinatario }}</td>
<td class="small">{{ e.asunto }}</td>
<td>{% if e.estado=='ok' %}<span class="badge bg-success">OK</span>{% else %}<span class="badge bg-danger">Error</span>{% endif %}</td></tr>
{% endfor %}
</tbody></table>
{% else %}<div class="text-muted small">Sin emails enviados aun.</div>{% endif %}
</div></div>

<style>
.tipo-card.active > div, .destino-card.active > div{ border-color:#3b5bdb !important; background:#f0f4ff; box-shadow:0 0 0 2px rgba(59,91,219,.15); }
.tipo-card > div:hover, .destino-card > div:hover{ background:#f8f9fc; }
</style>

<script>
function updateFormEnvio() {
  const tipoRadio = document.querySelector('input[name="tipo_envio"]:checked');
  const tipo = tipoRadio ? tipoRadio.value : '';
  const destinoRadio = document.querySelector('input[name="destino_tipo"]:checked');
  const destino = destinoRadio ? destinoRadio.value : '';

  // Marcar cards activas
  document.querySelectorAll('.tipo-card').forEach(el => {
    el.classList.toggle('active', el.dataset.tipo === tipo);
  });
  document.querySelectorAll('.destino-card').forEach(el => {
    el.classList.toggle('active', el.dataset.destino === destino);
  });

  // Mostrar/ocultar bloques
  document.querySelectorAll('.bloque-tipo').forEach(el => {
    el.style.display = (el.dataset.bloque === tipo) ? 'block' : 'none';
  });
  document.querySelectorAll('.bloque-destino').forEach(el => {
    el.style.display = (tipo === 'transporte' && el.dataset.destinoTipo === destino) ? 'block' : 'none';
  });
}

document.querySelectorAll('.tipo-card').forEach(el => {
  el.addEventListener('click', () => {
    const radio = el.querySelector('input[type="radio"]');
    if (radio) { radio.checked = true; updateFormEnvio(); }
  });
});
document.querySelectorAll('.destino-card').forEach(el => {
  el.addEventListener('click', () => {
    const radio = el.querySelector('input[type="radio"]');
    if (radio) { radio.checked = true; updateFormEnvio(); }
  });
});

document.addEventListener('DOMContentLoaded', updateFormEnvio);
</script>
{% endblock %}
'''


def patch_imprimir():
    """Agrega el tipo de envio a la vista de impresion."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'imprimir.html')
    if not os.path.exists(ruta):
        print("[upgrade37] no existe ventas/imprimir.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'tipo_envio_label' in contenido:
        print("[upgrade37] imprimir ya tiene tipo_envio"); return

    # Insertar en la seccion de datos de envio
    buscar = '<h3>Datos de envio</h3>'
    if buscar not in contenido:
        print("[upgrade37] no se encontro seccion de envio en imprimir"); return

    nuevo = '''<h3>Datos de envio</h3>
{% if orden.tipo_envio %}
<div class="mb-2" style="display:flex; gap:6px; flex-wrap:wrap;">
{% if orden.tipo_envio == 'retira_deposito' %}
<span style="background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;">RETIRA EN DEPOSITO</span>
{% elif orden.tipo_envio == 'envio_personal' %}
<span style="background:#cffafe;color:#155e75;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;">ENVIO PERSONAL</span>
{% elif orden.tipo_envio == 'transporte' %}
<span style="background:#d1fae5;color:#065f46;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;">TRANSPORTE{% if orden.destino_tipo %} / {{ 'DOMICILIO' if orden.destino_tipo == 'domicilio' else 'SUCURSAL' }}{% endif %}</span>
{% endif %}
</div>
{% endif %}'''

    contenido = contenido.replace(buscar, nuevo, 1)

    # Agregar sucursal_detalle antes de la direccion si es sucursal
    buscar2 = '{% if orden.destinatario_calle %}'
    if buscar2 in contenido:
        nuevo2 = '''{% if orden.sucursal_detalle %}<p><strong>Sucursal:</strong> {{ orden.sucursal_detalle }}</p>{% endif %}
{% if orden.destinatario_calle %}'''
        contenido = contenido.replace(buscar2, nuevo2, 1)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade37] vista de impresion actualizada")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app37; app37.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 37: Tipos de envio (retira / transporte / personal) ===")
    migrar()
    escribir('app37.py', APP37_PY)
    escribir('templates/ventas/detalle.html', VENTAS_DETALLE)
    patch_imprimir()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app37.py)")


if __name__ == '__main__':
    main()