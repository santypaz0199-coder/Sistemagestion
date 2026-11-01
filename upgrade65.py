# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade65] escrito: {relpath}")


APP65_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app64 import app
from app import admin_required
from database import get_db


def _contar_pendientes(conn):
    return conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='subido' AND estado='pendiente_pago'").fetchone()[0]


# ===== B2B unificado =====
@app.route('/b2b')
@login_required
@admin_required
def b2b_index():
    tab = request.args.get('tab', 'cuentas')
    conn = get_db()

    # Cuentas
    if tab == 'cuentas':
        estado = request.args.get('estado', 'pendiente')
        if estado == 'todas':
            cuentas = conn.execute("SELECT * FROM mayoristas_cuentas ORDER BY id DESC").fetchall()
        else:
            cuentas = conn.execute("SELECT * FROM mayoristas_cuentas WHERE estado=? ORDER BY id DESC",
                                   (estado,)).fetchall()
        counts = {
            'pendiente': conn.execute("SELECT COUNT(*) FROM mayoristas_cuentas WHERE estado='pendiente'").fetchone()[0],
            'aprobado': conn.execute("SELECT COUNT(*) FROM mayoristas_cuentas WHERE estado='aprobado'").fetchone()[0],
            'rechazado': conn.execute("SELECT COUNT(*) FROM mayoristas_cuentas WHERE estado='rechazado'").fetchone()[0],
        }
        pagos_pendientes_count = _contar_pendientes(conn)
        conn.close()
        return render_template('mayoristas/lista.html',
                               tab='cuentas', cuentas=cuentas, estado=estado, counts=counts,
                               pagos_pendientes_count=pagos_pendientes_count)

    # Pagos pendientes
    elif tab == 'pagos':
        filtro = request.args.get('filtro', 'subido')
        if filtro == 'subido':
            rows = conn.execute("""
                SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email
                FROM ordenes_venta o
                JOIN clientes c ON c.id = o.cliente_id
                WHERE o.comprobante_estado = 'subido'
                AND o.estado = 'pendiente_pago'
                ORDER BY o.comprobante_subido_en ASC
            """).fetchall()
        elif filtro == 'todos':
            rows = conn.execute("""
                SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email
                FROM ordenes_venta o
                JOIN clientes c ON c.id = o.cliente_id
                WHERE o.comprobante_estado IN ('subido','aprobado','rechazado')
                ORDER BY o.id DESC LIMIT 100
            """).fetchall()
        else:
            rows = []

        counts = {
            'subido': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='subido' AND estado='pendiente_pago'").fetchone()[0],
            'aprobado': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='aprobado'").fetchone()[0],
            'rechazado': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='rechazado'").fetchone()[0],
        }
        conn.close()
        return render_template('mayoristas/lista_pagos.html',
                               tab='pagos', rows=rows, filtro=filtro, counts=counts)

    conn.close()
    return redirect(url_for('b2b_index', tab='cuentas'))


# Redirects de compatibilidad
def _redir_mayoristas():
    return redirect(url_for('b2b_index', tab='cuentas'))

def _redir_pagos():
    return redirect(url_for('b2b_index', tab='pagos'))

app.view_functions['mayoristas_lista'] = _redir_mayoristas
app.view_functions['pagos_pendientes_lista'] = _redir_pagos


# ===== Aprobar/Rechazar cuentas (ya existen pero las re-registramos) =====
@app.route('/b2b/cuenta/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def b2b_cuenta_aprobar(id):
    from flask_login import current_user
    conn = get_db()
    cuenta = conn.execute("SELECT * FROM mayoristas_cuentas WHERE id=?", (id,)).fetchone()
    if not cuenta:
        conn.close(); flash('Cuenta no encontrada.', 'error')
        return redirect(url_for('b2b_index', tab='cuentas'))

    cliente_existente = conn.execute("SELECT id FROM clientes WHERE lower(email)=?",
                                      (cuenta['email'].lower(),)).fetchone()
    if cliente_existente:
        cliente_id = cliente_existente['id']
        conn.execute("UPDATE clientes SET es_mayorista=1, activo=1 WHERE id=?", (cliente_id,))
    else:
        cur = conn.execute("""INSERT INTO clientes
            (nombre_completo, tipo_doc, nro_doc, email, telefono,
             es_minorista, es_mayorista, activo, vendedor_id)
            VALUES (?, ?, ?, ?, ?, 0, 1, 1, ?)""",
            (cuenta['nombre_completo'], 'CUIT', cuenta['cuit'], cuenta['email'],
             cuenta['telefono'], current_user.id))
        cliente_id = cur.lastrowid

    conn.execute("""UPDATE mayoristas_cuentas SET estado='aprobado',
        cliente_id=?, aprobado_por=?, aprobado_en=datetime('now') WHERE id=?""",
        (cliente_id, current_user.id, id))
    conn.commit(); conn.close()

    try:
        from app4 import enviar_email, get_config
        cuerpo = f"""Hola {cuenta['nombre_completo']},

Tu cuenta fue aprobada. Ya podes ingresar al catalogo y hacer pedidos.

https://familiazaragoza.com/catalogo/login

{get_config('firma_email')}"""
        enviar_email(cuenta['email'], 'Tu cuenta fue aprobada - Familia Zaragoza ®', cuerpo)
    except Exception as e:
        print(f"[b2b aprobar email] {e}")

    flash(f'Cuenta de {cuenta["nombre_completo"]} aprobada.', 'success')
    return redirect(url_for('b2b_index', tab='cuentas'))


@app.route('/b2b/cuenta/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def b2b_cuenta_rechazar(id):
    from flask_login import current_user
    motivo = request.form.get('motivo', '').strip()
    conn = get_db()
    cuenta = conn.execute("SELECT * FROM mayoristas_cuentas WHERE id=?", (id,)).fetchone()
    if not cuenta:
        conn.close(); flash('Cuenta no encontrada.', 'error')
        return redirect(url_for('b2b_index', tab='cuentas'))

    conn.execute("""UPDATE mayoristas_cuentas SET estado='rechazado',
        aprobado_por=?, aprobado_en=datetime('now'), motivo_rechazo=? WHERE id=?""",
        (current_user.id, motivo or None, id))
    conn.commit(); conn.close()

    try:
        from app4 import enviar_email, get_config
        cuerpo = f"""Hola {cuenta['nombre_completo']},

Lamentablemente no pudimos aprobar tu cuenta en este momento.

{f'Motivo: {motivo}' if motivo else ''}

Si crees que es un error, responde este email y lo revisamos.

{get_config('firma_email')}"""
        enviar_email(cuenta['email'], 'Sobre tu registro - Familia Zaragoza ®', cuerpo)
    except Exception as e:
        print(f"[b2b rechazar email] {e}")

    flash('Cuenta rechazada.', 'success')
    return redirect(url_for('b2b_index', tab='cuentas'))


# Aprobar/Rechazar pagos (re-registramos apuntando de vuelta a B2B)
@app.route('/b2b/pago/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def b2b_pago_aprobar(id):
    from flask_login import current_user
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('b2b_index', tab='pagos'))

    if not orden['stock_descontado']:
        try:
            from app import aplicar_descuento_stock
            aplicar_descuento_stock(conn, id, current_user.id)
        except Exception as e:
            print(f"[b2b pago aprobar stock] {e}")

    conn.execute("""UPDATE ordenes_venta SET
        estado='pagado_sin_enviar',
        comprobante_estado='aprobado',
        comprobante_aprobado_por=?,
        comprobante_aprobado_en=datetime('now')
        WHERE id=?""",
        (current_user.id, id))
    conn.commit()

    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
    conn.close()

    if cliente and cliente['email']:
        try:
            from app4 import get_config
            from app39 import _enviar_con_remitente
            cuerpo = f"""Hola {cliente['nombre_completo']},

Tu pago fue aprobado. Tu pedido {orden['numero_interno']} ya esta en preparacion.

En cuanto lo despachemos te enviamos el numero de seguimiento.

{get_config('firma_email')}"""
            _enviar_con_remitente(cliente['email'], f'Pago aprobado - Pedido {orden["numero_interno"]}', cuerpo, None)
        except Exception as e:
            print(f"[b2b notificar aprobado] {e}")

    flash(f'Pedido {orden["numero_interno"]} marcado como pagado.', 'success')
    return redirect(url_for('b2b_index', tab='pagos'))


@app.route('/b2b/pago/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def b2b_pago_rechazar(id):
    motivo = request.form.get('motivo', '').strip()
    if not motivo:
        flash('Indica el motivo.', 'error')
        return redirect(url_for('b2b_index', tab='pagos'))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('b2b_index', tab='pagos'))

    conn.execute("""UPDATE ordenes_venta SET
        comprobante_estado='rechazado',
        comprobante_motivo_rechazo=?
        WHERE id=?""", (motivo, id))
    conn.commit()

    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
    conn.close()

    if cliente and cliente['email']:
        try:
            from app4 import get_config
            from app39 import _enviar_con_remitente
            cuerpo = f"""Hola {cliente['nombre_completo']},

Revisamos el comprobante de tu pedido {orden['numero_interno']} y no pudimos aprobarlo.

Motivo: {motivo}

Podes subir un nuevo comprobante desde "Mis pedidos" en el catalogo.

{get_config('firma_email')}"""
            _enviar_con_remitente(cliente['email'], f'Comprobante rechazado - Pedido {orden["numero_interno"]}', cuerpo, None)
        except Exception as e:
            print(f"[b2b notificar rechazo] {e}")

    flash('Comprobante rechazado.', 'warning')
    return redirect(url_for('b2b_index', tab='pagos'))


# Redirects viejos de aprobar/rechazar
def _redir_aprob(id):
    return redirect(url_for('b2b_cuenta_aprobar', id=id), 307)

def _redir_rechaz(id):
    return redirect(url_for('b2b_cuenta_rechazar', id=id), 307)

app.view_functions['mayoristas_aprobar'] = _redir_aprob
app.view_functions['mayoristas_rechazar'] = _redir_rechaz
app.view_functions['pagos_pendientes_aprobar'] = lambda id: redirect(url_for('b2b_pago_aprobar', id=id), 307)
app.view_functions['pagos_pendientes_rechazar'] = lambda id: redirect(url_for('b2b_pago_rechazar', id=id), 307)
'''


# Template unificado con tabs
MAYORISTAS_LISTA = r'''{% extends "base.html" %}
{% block title %}B2B{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">B2B - Mayoristas</h4>
<div class="text-muted small">Cuentas del catalogo publico y pagos pendientes</div>
</div>
<div class="d-flex gap-2">
<button type="button" class="btn btn-outline-primary btn-sm" onclick="copiarLinkCatalogo()">
<i class="bi bi-share"></i> Compartir link del catalogo
</button>
<a href="/catalogo" target="_blank" class="btn btn-outline-secondary btn-sm">
<i class="bi bi-box-arrow-up-right"></i> Abrir catalogo
</a>
</div>
</div>

<!-- Tabs -->
<ul class="nav nav-pills mb-3">
<li class="nav-item">
<a class="nav-link {% if tab=='cuentas' %}active{% endif %}" href="{{ url_for('b2b_index', tab='cuentas') }}">
<i class="bi bi-people"></i> Cuentas
{% if counts.pendiente %}<span class="badge bg-warning text-dark ms-1">{{ counts.pendiente }}</span>{% endif %}
</a>
</li>
<li class="nav-item">
<a class="nav-link {% if tab=='pagos' %}active{% endif %}" href="{{ url_for('b2b_index', tab='pagos') }}">
<i class="bi bi-cash-coin"></i> Pagos pendientes
{% if pagos_pendientes_count %}<span class="badge bg-danger ms-1">{{ pagos_pendientes_count }}</span>{% endif %}
</a>
</li>
</ul>

<!-- Sub-tabs de cuentas -->
<ul class="nav nav-pills mb-3" style="font-size:.85rem;">
<li class="nav-item"><a class="nav-link {% if estado=='pendiente' %}active{% endif %}" href="{{ url_for('b2b_index', tab='cuentas', estado='pendiente') }}"><i class="bi bi-hourglass-split"></i> Pendientes ({{ counts.pendiente }})</a></li>
<li class="nav-item"><a class="nav-link {% if estado=='aprobado' %}active{% endif %}" href="{{ url_for('b2b_index', tab='cuentas', estado='aprobado') }}"><i class="bi bi-check-circle"></i> Aprobadas ({{ counts.aprobado }})</a></li>
<li class="nav-item"><a class="nav-link {% if estado=='rechazado' %}active{% endif %}" href="{{ url_for('b2b_index', tab='cuentas', estado='rechazado') }}"><i class="bi bi-x-circle"></i> Rechazadas ({{ counts.rechazado }})</a></li>
<li class="nav-item"><a class="nav-link {% if estado=='todas' %}active{% endif %}" href="{{ url_for('b2b_index', tab='cuentas', estado='todas') }}">Todas</a></li>
</ul>

{% if cuentas %}
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light">
<tr><th>Fecha</th><th>Nombre</th><th>Email</th><th>Telefono</th><th>CUIT</th><th>Estado</th><th class="text-end">Acciones</th></tr>
</thead>
<tbody>
{% for c in cuentas %}
<tr>
<td class="small text-muted">{{ c.creado[:16] if c.creado else '' }}</td>
<td class="fw-semibold">{{ c.nombre_completo }}</td>
<td class="small">{{ c.email }}</td>
<td class="small">{{ c.telefono or '—' }}</td>
<td class="small">{{ c.cuit or '—' }}</td>
<td>
{% if c.estado == 'pendiente' %}<span class="badge bg-warning text-dark">Pendiente</span>
{% elif c.estado == 'aprobado' %}<span class="badge bg-success">Aprobada</span>
{% else %}<span class="badge bg-danger">Rechazada</span>{% endif %}
</td>
<td class="text-end text-nowrap">
{% if c.estado == 'pendiente' %}
<form method="post" action="{{ url_for('b2b_cuenta_aprobar', id=c.id) }}" class="d-inline" onsubmit="return confirm('Aprobar la cuenta de {{ c.nombre_completo }}? Se creara el cliente automaticamente.')">
<button class="btn btn-sm btn-success"><i class="bi bi-check-lg"></i> Aprobar</button>
</form>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openRechazar({{ c.id }}, {{ c.nombre_completo|tojson }})"><i class="bi bi-x-lg"></i> Rechazar</button>
{% elif c.estado == 'rechazado' %}
<span class="small text-muted">{{ c.motivo_rechazo or '—' }}</span>
{% elif c.estado == 'aprobado' %}
<button type="button" class="btn btn-sm btn-outline-primary" onclick="copiarLinkMayorista('{{ c.email }}')" title="Compartir link del catalogo">
<i class="bi bi-share"></i>
</button>
{% endif %}
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
{% else %}
<div class="card shadow-sm"><div class="card-body text-center py-5">
<i class="bi bi-people fs-1 text-muted"></i>
<p class="text-muted mt-3 mb-0">No hay cuentas en este estado.</p>
</div></div>
{% endif %}

<!-- Modal rechazar -->
<div class="modal fade" id="rechazarModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="rechazar-form" method="post">
<div class="modal-header"><h6 class="modal-title">Rechazar cuenta de <span id="rechazar-nombre"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="small text-muted">Se le enviara un email al mayorista avisandole del rechazo.</p>
<div class="mb-2"><label class="form-label">Motivo (opcional)</label>
<textarea name="motivo" class="form-control" rows="3" placeholder="Ej: CUIT invalido"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">Rechazar</button>
</div>
</form></div></div></div>

<script>
function openRechazar(id, nombre) {
  document.getElementById('rechazar-form').action = '/b2b/cuenta/' + id + '/rechazar';
  document.getElementById('rechazar-nombre').textContent = nombre;
  new bootstrap.Modal(document.getElementById('rechazarModal')).show();
}

function copiarLinkCatalogo() {
  const link = window.location.origin + '/catalogo';
  navigator.clipboard.writeText(link).then(() => {
    alert('Link copiado al portapapeles:\n\n' + link + '\n\nPodes pegarlo en WhatsApp, email, redes sociales, etc.');
  }).catch(err => {
    prompt('Copia este link manualmente:', link);
  });
}

function copiarLinkMayorista(email) {
  const link = window.location.origin + '/catalogo/registro';
  const texto = 'Hola! Te comparto el catalogo de Familia Zaragoza ®. Podes registrarte como mayorista en:\n\n' + link;
  navigator.clipboard.writeText(texto).then(() => {
    alert('Mensaje copiado. Podes enviarselo a ' + email + ' por WhatsApp o email.');
  }).catch(err => {
    prompt('Copia este mensaje manualmente:', texto);
  });
}
</script>
{% endblock %}
'''


MAYORISTAS_LISTA_PAGOS = r'''{% extends "base.html" %}
{% block title %}B2B - Pagos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">B2B - Mayoristas</h4>
<div class="text-muted small">Cuentas del catalogo publico y pagos pendientes</div>
</div>
<div class="d-flex gap-2">
<button type="button" class="btn btn-outline-primary btn-sm" onclick="copiarLinkCatalogo()">
<i class="bi bi-share"></i> Compartir link del catalogo
</button>
<a href="/catalogo" target="_blank" class="btn btn-outline-secondary btn-sm">
<i class="bi bi-box-arrow-up-right"></i> Abrir catalogo
</a>
</div>
</div>

<!-- Tabs -->
<ul class="nav nav-pills mb-3">
<li class="nav-item">
<a class="nav-link" href="{{ url_for('b2b_index', tab='cuentas') }}">
<i class="bi bi-people"></i> Cuentas
</a>
</li>
<li class="nav-item">
<a class="nav-link active" href="{{ url_for('b2b_index', tab='pagos') }}">
<i class="bi bi-cash-coin"></i> Pagos pendientes
{% if counts.subido %}<span class="badge bg-danger ms-1">{{ counts.subido }}</span>{% endif %}
</a>
</li>
</ul>

<!-- Sub-tabs de pagos -->
<ul class="nav nav-pills mb-3" style="font-size:.85rem;">
<li class="nav-item"><a class="nav-link {% if filtro=='subido' %}active{% endif %}" href="{{ url_for('b2b_index', tab='pagos', filtro='subido') }}"><i class="bi bi-hourglass-split"></i> Esperando aprobacion ({{ counts.subido }})</a></li>
<li class="nav-item"><a class="nav-link {% if filtro=='todos' %}active{% endif %}" href="{{ url_for('b2b_index', tab='pagos', filtro='todos') }}"><i class="bi bi-list-check"></i> Todos los comprobantes</a></li>
</ul>

{% if rows %}
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light">
<tr><th>Pedido</th><th>Fecha subida</th><th>Cliente</th><th class="text-end">Total</th><th>Comprobante</th><th class="text-end">Acciones</th></tr>
</thead>
<tbody>
{% for r in rows %}
<tr>
<td class="fw-semibold">{{ r.numero_interno }}</td>
<td class="small text-muted">{{ r.comprobante_subido_en[:16] if r.comprobante_subido_en else '—' }}</td>
<td>
<div class="small fw-semibold">{{ r.cliente_nombre }}</div>
<div class="small text-muted">{{ r.cliente_email }}</div>
</td>
<td class="text-end fw-semibold">${{ '{:,.0f}'.format(r.total).replace(',','.') }}</td>
<td>
{% if r.comprobante_estado == 'subido' %}<span class="badge bg-warning text-dark">Esperando</span>
{% elif r.comprobante_estado == 'aprobado' %}<span class="badge bg-success">Aprobado</span>
{% elif r.comprobante_estado == 'rechazado' %}<span class="badge bg-danger">Rechazado</span>{% endif %}
{% if r.comprobante_archivo %}
<a href="{{ url_for('pagos_pendientes_ver_comprobante', id=r.id) }}" target="_blank" class="btn btn-sm btn-outline-secondary ms-2" title="Ver comprobante"><i class="bi bi-file-earmark-text"></i></a>
{% endif %}
</td>
<td class="text-end text-nowrap">
{% if r.comprobante_estado == 'subido' and r.estado == 'pendiente_pago' %}
<form method="post" action="{{ url_for('b2b_pago_aprobar', id=r.id) }}" class="d-inline" onsubmit="return confirm('Aprobar el pago? Se marcara como pagado y se descontara stock.')">
<button class="btn btn-sm btn-success"><i class="bi bi-check-lg"></i> Aprobar</button>
</form>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openRechazarPago({{ r.id }}, '{{ r.numero_interno }}')"><i class="bi bi-x-lg"></i> Rechazar</button>
{% elif r.comprobante_motivo_rechazo %}
<div class="small text-muted">Motivo: {{ r.comprobante_motivo_rechazo }}</div>
{% endif %}
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
{% else %}
<div class="card shadow-sm"><div class="card-body text-center py-5">
<i class="bi bi-check2-circle fs-1 text-success"></i>
<h5 class="mt-3">Sin comprobantes pendientes</h5>
<p class="text-muted mb-0">Todos los pagos estan al dia.</p>
</div></div>
{% endif %}

<!-- Modal rechazar pago -->
<div class="modal fade" id="rechazarPagoModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="rechazar-pago-form" method="post">
<div class="modal-header"><h6 class="modal-title">Rechazar comprobante del pedido <span id="rechazar-pago-num"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="small text-muted">Se le enviara un email al cliente con el motivo. Va a poder subir un comprobante nuevo.</p>
<div class="mb-2"><label class="form-label">Motivo del rechazo *</label>
<textarea name="motivo" class="form-control" rows="3" required placeholder="Ej: El monto transferido no coincide con el total del pedido"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">Rechazar y notificar</button>
</div>
</form></div></div></div>

<script>
function openRechazarPago(id, num) {
  document.getElementById('rechazar-pago-form').action = '/b2b/pago/' + id + '/rechazar';
  document.getElementById('rechazar-pago-num').textContent = num;
  new bootstrap.Modal(document.getElementById('rechazarPagoModal')).show();
}

function copiarLinkCatalogo() {
  const link = window.location.origin + '/catalogo';
  navigator.clipboard.writeText(link).then(() => {
    alert('Link copiado al portapapeles:\n\n' + link);
  }).catch(err => {
    prompt('Copia este link manualmente:', link);
  });
}
</script>
{% endblock %}
'''


def patch_base_html():
    """Cambia 'Mayoristas' por 'B2B' y elimina el link de 'Pagos pendientes'."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade65] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Eliminar el link de "Pagos pendientes" (ahora esta dentro de B2B)
    patron_pagos = re.compile(
        r'<a href="\{\{ url_for\(\'pagos_pendientes_lista\'\) \}\}".*?</a>\n?',
        re.DOTALL
    )
    contenido, n = patron_pagos.subn('', contenido)
    if n > 0:
        print(f"[upgrade65] link 'Pagos pendientes' eliminado del sidebar ({n} ocurrencia)")

    # 2. Cambiar el texto "Mayoristas" por "B2B" y la URL por b2b_index
    viejo_may = '<a href="{{ url_for(\'mayoristas_lista\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'mayoristas\') %}active{% endif %}"><i class="bi bi-person-plus"></i> Mayoristas</a>'
    nuevo_may = '<a href="{{ url_for(\'b2b_index\') }}" class="{% if request.endpoint and (request.endpoint.startswith(\'b2b\') or request.endpoint.startswith(\'mayoristas\')) %}active{% endif %}"><i class="bi bi-shop"></i> B2B</a>'

    if viejo_may in contenido:
        contenido = contenido.replace(viejo_may, nuevo_may, 1)
        print("[upgrade65] link 'Mayoristas' renombrado a 'B2B'")
    else:
        # Variante: puede tener icono distinto
        patron_may = re.compile(
            r'<a href="\{\{ url_for\(\'mayoristas_lista\'\) \}\}"[^>]*>.*?</a>',
            re.DOTALL
        )
        contenido, n = patron_may.subn(nuevo_may, contenido, count=1)
        if n > 0:
            print("[upgrade65] link 'Mayoristas' renombrado a 'B2B' (patron)")
        else:
            print("[upgrade65] ADVERTENCIA: no se encontro el link de Mayoristas")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 65: B2B unificado (U65) ===")
    escribir('app65.py', APP65_PY)
    escribir('templates/mayoristas/lista.html', MAYORISTAS_LISTA)
    escribir('templates/mayoristas/lista_pagos.html', MAYORISTAS_LISTA_PAGOS)
    patch_base_html()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()