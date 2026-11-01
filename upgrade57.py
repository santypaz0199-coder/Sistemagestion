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
    print(f"[upgrade57] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade57] sin DB."); return
    conn = sqlite3.connect(db)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(ordenes_venta)").fetchall()]
    nuevas = {
        'comprobante_archivo': "TEXT",
        'comprobante_nombre': "TEXT",
        'comprobante_estado': "TEXT DEFAULT 'sin_comprobante'",
        'comprobante_subido_en': "TEXT",
        'comprobante_aprobado_por': "INTEGER",
        'comprobante_aprobado_en': "TEXT",
        'comprobante_motivo_rechazo': "TEXT",
    }
    for col, tipo in nuevas.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE ordenes_venta ADD COLUMN {col} {tipo}")
            print(f"[upgrade57] + ordenes_venta.{col}")

    # Config keys para datos de pago
    default_config = {
        'pago_alias': '',
        'pago_cbu': '',
        'pago_titular': 'Familia Zaragoza',
        'pago_cuit': '',
        'pago_banco': '',
        'pago_instrucciones': 'Una vez realizada la transferencia, subi el comprobante desde la seccion "Mis pedidos" del catalogo.',
    }
    for k, v in default_config.items():
        if not conn.execute("SELECT clave FROM configuracion WHERE clave=?", (k,)).fetchone():
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?)", (k, v))
            print(f"[upgrade57] + config {k}")

    conn.commit(); conn.close()


APP57_PY = r'''
import os
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from app49 import catalogo_bp
from app51 import get_current_mayorista, mayorista_requerido
from app48 import app as main_app
from app import admin_required
from database import get_db

BASE = os.path.dirname(os.path.abspath(__file__))
COMPROBANTES_DIR = os.path.join(BASE, 'uploads', 'comprobantes')
os.makedirs(COMPROBANTES_DIR, exist_ok=True)

EXT_VALIDAS = {'pdf', 'jpg', 'jpeg', 'png', 'webp'}
MAX_SIZE = 10 * 1024 * 1024


# ===== Helpers =====
def _guardar_comprobante(file):
    if not file or not file.filename:
        return None, None, 'Selecciona un archivo.'
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in EXT_VALIDAS:
        return None, None, f'Formato no permitido. Usa: {", ".join(EXT_VALIDAS)}.'
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE:
        return None, None, 'El archivo supera 10 MB.'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre = f"{timestamp}_{secure_filename(file.filename)}"
    file.save(os.path.join(COMPROBANTES_DIR, nombre))
    return nombre, file.filename, None


def _datos_pago(conn):
    claves = ['pago_alias', 'pago_cbu', 'pago_titular', 'pago_cuit', 'pago_banco', 'pago_instrucciones']
    resultado = {}
    for k in claves:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
        resultado[k] = row['valor'] if row and row['valor'] else ''
    return resultado


def _notificar(mayorista_email, asunto, cuerpo):
    try:
        from app39 import _enviar_con_remitente
        _enviar_con_remitente(mayorista_email, asunto, cuerpo, None)
    except Exception as e:
        print(f"[notificar] {e}")


# ===== Catalogo: mayorista sube comprobante =====
@catalogo_bp.route('/mis-pedidos/<int:id>/subir-comprobante', methods=['POST'])
@mayorista_requerido
def subir_comprobante(id):
    m = get_current_mayorista()
    if not m['cliente_id']:
        flash('Cuenta no vinculada.', 'error')
        return redirect(url_for('catalogo.mis_pedidos'))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=? AND cliente_id=?",
                         (id, m['cliente_id'])).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('catalogo.mis_pedidos'))

    if orden['estado'] != 'pendiente_pago':
        conn.close(); flash('Este pedido ya no esta pendiente de pago.', 'warning')
        return redirect(url_for('catalogo.mi_pedido_detalle', id=id))

    archivo = request.files.get('comprobante')
    nombre_arch, nombre_orig, err = _guardar_comprobante(archivo)
    if err:
        conn.close(); flash(err, 'error')
        return redirect(url_for('catalogo.mi_pedido_detalle', id=id))

    # Borrar comprobante anterior si existia
    if orden['comprobante_archivo']:
        try: os.remove(os.path.join(COMPROBANTES_DIR, orden['comprobante_archivo']))
        except: pass

    conn.execute("""UPDATE ordenes_venta SET
        comprobante_archivo=?, comprobante_nombre=?,
        comprobante_estado='subido', comprobante_subido_en=datetime('now'),
        comprobante_motivo_rechazo=NULL
        WHERE id=?""",
        (nombre_arch, nombre_orig, id))
    conn.commit()
    conn.close()

    # Notificar al admin
    try:
        from app4 import get_config
        admin_email = get_config('empresa_email') or get_config('smtp_remitente_email')
        if admin_email:
            cuerpo = f"""Nuevo comprobante subido:

Pedido: {orden['numero_interno']}
Cliente: {m['nombre_completo']} <{m['email']}>
Total: ${orden['total']:.2f}

Revisalo en: /pagos-pendientes

{get_config('firma_email')}"""
            _notificar(admin_email, f'Comprobante subido - {orden["numero_interno"]}', cuerpo)
    except Exception as e:
        print(f"[notificar admin] {e}")

    flash('Comprobante subido. Estamos verificando el pago.', 'success')
    return redirect(url_for('catalogo.mi_pedido_detalle', id=id))


@catalogo_bp.route('/mis-pedidos/<int:id>/cancelar', methods=['POST'])
@mayorista_requerido
def cancelar_pedido_mayorista(id):
    m = get_current_mayorista()
    if not m['cliente_id']:
        return redirect(url_for('catalogo.mis_pedidos'))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=? AND cliente_id=?",
                         (id, m['cliente_id'])).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('catalogo.mis_pedidos'))

    if orden['estado'] != 'pendiente_pago' or orden['comprobante_estado'] == 'subido':
        conn.close()
        flash('No podes cancelar este pedido. Ya fue pagado o el comprobante esta en revision.', 'error')
        return redirect(url_for('catalogo.mi_pedido_detalle', id=id))

    conn.execute("UPDATE ordenes_venta SET estado='cancelado' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Pedido cancelado.', 'success')
    return redirect(url_for('catalogo.mis_pedidos'))


@catalogo_bp.route('/comprobante/<int:id>')
@mayorista_requerido
def ver_mi_comprobante(id):
    m = get_current_mayorista()
    if not m['cliente_id']:
        abort(404)
    conn = get_db()
    orden = conn.execute("SELECT comprobante_archivo, comprobante_nombre FROM ordenes_venta WHERE id=? AND cliente_id=?",
                         (id, m['cliente_id'])).fetchone()
    conn.close()
    if not orden or not orden['comprobante_archivo']:
        abort(404)
    ruta = os.path.join(COMPROBANTES_DIR, orden['comprobante_archivo'])
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta, as_attachment=False, download_name=orden['comprobante_nombre'])


# ===== Admin: Pagos pendientes =====
@main_app.route('/pagos-pendientes')
@login_required
@admin_required
def pagos_pendientes_lista():
    filtro = request.args.get('filtro', 'subido')
    conn = get_db()

    if filtro == 'subido':
        # Solo comprobantes esperando aprobacion
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
    return render_template('pagos_pendientes/lista.html', rows=rows, filtro=filtro, counts=counts)


@main_app.route('/pagos-pendientes/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def pagos_pendientes_aprobar(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('pagos_pendientes_lista'))

    # Marcar como pagado (esto descuenta stock via trigger o via funcion)
    if not orden['stock_descontado']:
        # Aplicar descuento de stock
        try:
            from app import aplicar_descuento_stock
            aplicar_descuento_stock(conn, id, current_user.id)
        except Exception as e:
            print(f"[aprobar] error stock: {e}")

    conn.execute("""UPDATE ordenes_venta SET
        estado='pagado_sin_enviar',
        comprobante_estado='aprobado',
        comprobante_aprobado_por=?,
        comprobante_aprobado_en=datetime('now')
        WHERE id=?""",
        (current_user.id, id))
    conn.commit()

    # Datos para notificar
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
    conn.close()

    # Notificar al mayorista
    if cliente and cliente['email']:
        try:
            from app4 import get_config
            cuerpo = f"""Hola {cliente['nombre_completo']},

Tu pago fue aprobado. Tu pedido {orden['numero_interno']} ya esta en preparacion.

En cuanto lo despachemos te enviamos el numero de seguimiento.

{get_config('firma_email')}"""
            _notificar(cliente['email'], f'Pago aprobado - Pedido {orden["numero_interno"]}', cuerpo)
        except Exception as e:
            print(f"[notificar aprobado] {e}")

    flash(f'Pedido {orden["numero_interno"]} marcado como pagado. Stock descontado.', 'success')
    return redirect(url_for('pagos_pendientes_lista'))


@main_app.route('/pagos-pendientes/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def pagos_pendientes_rechazar(id):
    motivo = request.form.get('motivo', '').strip()
    if not motivo:
        flash('Indica el motivo del rechazo.', 'error')
        return redirect(url_for('pagos_pendientes_lista'))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('pagos_pendientes_lista'))

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
            cuerpo = f"""Hola {cliente['nombre_completo']},

Revisamos el comprobante de tu pedido {orden['numero_interno']} y no pudimos aprobarlo.

Motivo: {motivo}

Podes subir un nuevo comprobante desde "Mis pedidos" en el catalogo.

{get_config('firma_email')}"""
            _notificar(cliente['email'], f'Comprobante rechazado - Pedido {orden["numero_interno"]}', cuerpo)
        except Exception as e:
            print(f"[notificar rechazo] {e}")

    flash(f'Comprobante rechazado. Se notifico al cliente.', 'warning')
    return redirect(url_for('pagos_pendientes_lista'))


@main_app.route('/pagos-pendientes/<int:id>/comprobante')
@login_required
@admin_required
def pagos_pendientes_ver_comprobante(id):
    conn = get_db()
    orden = conn.execute("SELECT comprobante_archivo, comprobante_nombre FROM ordenes_venta WHERE id=?",
                         (id,)).fetchone()
    conn.close()
    if not orden or not orden['comprobante_archivo']:
        abort(404)
    ruta = os.path.join(COMPROBANTES_DIR, orden['comprobante_archivo'])
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta, as_attachment=False, download_name=orden['comprobante_nombre'])


# ===== Configuracion: Datos de pago =====
@main_app.route('/configuracion/datos-pago', methods=['GET', 'POST'])
@login_required
@admin_required
def configuracion_datos_pago():
    conn = get_db()
    if request.method == 'POST':
        for k in ['pago_alias', 'pago_cbu', 'pago_titular', 'pago_cuit', 'pago_banco', 'pago_instrucciones']:
            v = request.form.get(k, '').strip()
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                         "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (k, v))
        conn.commit(); conn.close()
        flash('Datos de pago guardados.', 'success')
        return redirect(url_for('configuracion_datos_pago'))

    datos = _datos_pago(conn)
    conn.close()
    return render_template('configuracion/datos_pago.html', datos=datos)
'''


PAGOS_PENDIENTES_LISTA = r'''{% extends "base.html" %}
{% block title %}Pagos pendientes{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Pagos pendientes</h4>
<div class="text-muted small">Aprueba o rechaza los comprobantes subidos por los mayoristas</div>
</div>
</div>

<ul class="nav nav-pills mb-3">
<li class="nav-item"><a class="nav-link {% if filtro=='subido' %}active{% endif %}" href="{{ url_for('pagos_pendientes_lista', filtro='subido') }}"><i class="bi bi-hourglass-split"></i> Esperando aprobacion {% if counts.subido %}<span class="badge bg-warning text-dark ms-1">{{ counts.subido }}</span>{% endif %}</a></li>
<li class="nav-item"><a class="nav-link {% if filtro=='todos' %}active{% endif %}" href="{{ url_for('pagos_pendientes_lista', filtro='todos') }}"><i class="bi bi-list-check"></i> Todos los comprobantes</a></li>
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
<form method="post" action="{{ url_for('pagos_pendientes_aprobar', id=r.id) }}" class="d-inline" onsubmit="return confirm('Aprobar el pago? Se marcara como pagado y se descontara stock.')">
<button class="btn btn-sm btn-success"><i class="bi bi-check-lg"></i> Aprobar</button>
</form>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openRechazar({{ r.id }}, '{{ r.numero_interno }}')"><i class="bi bi-x-lg"></i> Rechazar</button>
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

<div class="modal fade" id="rechazarModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="rechazar-form" method="post">
<div class="modal-header"><h6 class="modal-title">Rechazar comprobante de {{ 'pedido' }} <span id="rechazar-num"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="small text-muted">Se le enviara un email al cliente avisando del rechazo con el motivo. Va a poder subir un comprobante nuevo.</p>
<div class="mb-2"><label class="form-label">Motivo del rechazo *</label>
<textarea name="motivo" class="form-control" rows="3" required placeholder="Ej: El monto transferido no coincide con el total del pedido"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">Rechazar y notificar</button>
</div>
</form></div></div></div>

<script>
function openRechazar(id, num) {
  document.getElementById('rechazar-form').action = '/pagos-pendientes/' + id + '/rechazar';
  document.getElementById('rechazar-num').textContent = num;
  new bootstrap.Modal(document.getElementById('rechazarModal')).show();
}
</script>
{% endblock %}
'''


CONFIG_DATOS_PAGO = r'''{% extends "base.html" %}
{% block title %}Datos de pago{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Datos de pago</h4>
<div class="text-muted small">Esta informacion se le muestra al mayorista cuando hace un pedido</div>
</div>
<a href="{{ url_for('configuracion') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-6">
<label class="form-label">Alias de transferencia</label>
<input name="pago_alias" class="form-control" value="{{ datos.pago_alias }}" placeholder="Ej: FAMILIA.ZARAGOZA.MP">
</div>
<div class="col-md-6">
<label class="form-label">CBU</label>
<input name="pago_cbu" class="form-control" value="{{ datos.pago_cbu }}" placeholder="22 digitos">
</div>
<div class="col-md-6">
<label class="form-label">Titular de la cuenta</label>
<input name="pago_titular" class="form-control" value="{{ datos.pago_titular }}" placeholder="Familia Zaragoza SRL">
</div>
<div class="col-md-6">
<label class="form-label">CUIT del titular</label>
<input name="pago_cuit" class="form-control" value="{{ datos.pago_cuit }}" placeholder="30-71234567-8">
</div>
<div class="col-md-6">
<label class="form-label">Banco</label>
<input name="pago_banco" class="form-control" value="{{ datos.pago_banco }}" placeholder="Ej: Banco Nacion">
</div>
<div class="col-12">
<label class="form-label">Instrucciones adicionales</label>
<textarea name="pago_instrucciones" class="form-control" rows="3" placeholder="Instrucciones que se le muestran al mayorista">{{ datos.pago_instrucciones }}</textarea>
</div>
</div>
<div class="mt-4">
<button class="btn btn-dark"><i class="bi bi-save"></i> Guardar datos de pago</button>
</div>
</form>
</div></div>

<div class="alert alert-light border mt-3 small">
<i class="bi bi-info-circle"></i> Estos datos se incluyen automaticamente en el email que recibe el mayorista cuando hace un pedido.
</div>
{% endblock %}
'''


def patch_catalogo_mi_pedido_detalle():
    """Actualiza el detalle del pedido del catalogo con upload de comprobante."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'mi_pedido_detalle.html')
    if not os.path.exists(ruta):
        print("[upgrade57] no existe mi_pedido_detalle.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'subir-comprobante' in contenido:
        print("[upgrade57] mi_pedido_detalle ya tiene upload")
        return

    # Agregar bloque de comprobante + cancelar antes del cierre del card
    buscar = '''    {% if orden.notas %}
    <hr style="border-color:var(--cat-border);margin:1.5rem 0;">
    <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:.5rem;">Notas</h6>
    <p style="color:var(--cat-text);">{{ orden.notas }}</p>
    {% endif %}
  </div>
</div>'''

    nuevo = '''    {% if orden.notas %}
    <hr style="border-color:var(--cat-border);margin:1.5rem 0;">
    <h6 style="color:var(--cat-text-muted);text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;margin-bottom:.5rem;">Notas</h6>
    <p style="color:var(--cat-text);">{{ orden.notas }}</p>
    {% endif %}

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
    <a href="{{ url_for('catalogo.ver_mi_comprobante', id=orden.id) }}" target="_blank" style="color:var(--cat-accent);font-size:.85rem;">
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

    {% if orden.estado == 'pendiente_pago' and orden.comprobante_estado != 'subido' %}
    <div style="background:var(--cat-surface-2);border:1px solid var(--cat-border);border-radius:10px;padding:1.5rem;margin-top:1rem;">
      <h6 style="color:var(--cat-text);font-weight:600;margin-bottom:1rem;">Datos para la transferencia</h6>
      {% if datos_pago %}
      {% if datos_pago.pago_alias %}<p style="margin:.25rem 0;"><strong>Alias:</strong> {{ datos_pago.pago_alias }}</p>{% endif %}
      {% if datos_pago.pago_cbu %}<p style="margin:.25rem 0;"><strong>CBU:</strong> {{ datos_pago.pago_cbu }}</p>{% endif %}
      {% if datos_pago.pago_titular %}<p style="margin:.25rem 0;"><strong>Titular:</strong> {{ datos_pago.pago_titular }}</p>{% endif %}
      {% if datos_pago.pago_cuit %}<p style="margin:.25rem 0;"><strong>CUIT:</strong> {{ datos_pago.pago_cuit }}</p>{% endif %}
      {% if datos_pago.pago_banco %}<p style="margin:.25rem 0;"><strong>Banco:</strong> {{ datos_pago.pago_banco }}</p>{% endif %}
      {% if datos_pago.pago_instrucciones %}<p style="margin:.75rem 0 0 0;color:var(--cat-text-muted);font-size:.85rem;">{{ datos_pago.pago_instrucciones }}</p>{% endif %}
      {% endif %}

      <form method="post" action="{{ url_for('catalogo.subir_comprobante', id=orden.id) }}" enctype="multipart/form-data" class="mt-3">
        <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;display:block;margin-bottom:.5rem;">Subir comprobante *</label>
        <input type="file" name="comprobante" class="form-control mb-2" accept=".pdf,.jpg,.jpeg,.png,.webp" required style="background:var(--cat-surface);border:1px solid var(--cat-border);color:var(--cat-text);">
        <button type="submit" class="cat-btn">Enviar comprobante</button>
      </form>
    </div>
    {% endif %}

    {% if orden.estado == 'pendiente_pago' and orden.comprobante_estado == 'sin_comprobante' %}
    <form method="post" action="{{ url_for('catalogo.cancelar_pedido_mayorista', id=orden.id) }}" class="mt-3" onsubmit="return confirm('Cancelar este pedido?')">
      <button type="submit" style="background:none;border:1px solid var(--cat-border);color:#f87171;padding:.5rem 1rem;border-radius:6px;font-size:.8rem;">Cancelar pedido</button>
    </form>
    {% endif %}

  </div>
</div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade57] mi_pedido_detalle actualizado")
    else:
        print("[upgrade57] ADVERTENCIA: no se encontro el bloque en mi_pedido_detalle")


def patch_mis_pedidos_badge():
    """Agrega indicador de estado de pago en el listado."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'mis_pedidos.html')
    if not os.path.exists(ruta):
        print("[upgrade57] no existe mis_pedidos.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'comprobante_estado' in contenido:
        print("[upgrade57] mis_pedidos ya tiene estado comprobante")
        return

    buscar = '''          <td style="padding:1rem;">
            {% if p.estado == 'pendiente_pago' %}<span class="badge-cat badge-pendiente">Pendiente pago</span>
            {% elif p.estado == 'pagado_sin_enviar' %}<span class="badge-cat" style="background:rgba(6,182,212,.15);color:#22d3ee;">Pagado - En preparacion</span>
            {% elif p.estado == 'pagado_enviado' %}<span class="badge-cat badge-aprobado">Enviado</span>
            {% else %}<span class="badge-cat badge-rechazado">Cancelado</span>{% endif %}
          </td>'''

    nuevo = '''          <td style="padding:1rem;">
            {% if p.estado == 'pendiente_pago' %}
              {% if p.comprobante_estado == 'subido' %}<span class="badge-cat" style="background:rgba(6,182,212,.15);color:#22d3ee;">Comprobante en revision</span>
              {% elif p.comprobante_estado == 'rechazado' %}<span class="badge-cat badge-rechazado">Comprobante rechazado</span>
              {% else %}<span class="badge-cat badge-pendiente">Pendiente pago</span>{% endif %}
            {% elif p.estado == 'pagado_sin_enviar' %}<span class="badge-cat" style="background:rgba(6,182,212,.15);color:#22d3ee;">Pagado - En preparacion</span>
            {% elif p.estado == 'pagado_enviado' %}<span class="badge-cat badge-aprobado">Enviado</span>
            {% else %}<span class="badge-cat badge-rechazado">Cancelado</span>{% endif %}
          </td>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade57] mis_pedidos con estado de comprobante")
    else:
        print("[upgrade57] ADVERTENCIA: no se encontro el bloque de estado en mis_pedidos")


def patch_mi_pedido_detalle_datos_pago():
    """Pasa datos_pago al template desde la ruta."""
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'datos_pago=' in contenido and 'def mi_pedido_detalle' in contenido:
        # Verificar si ya lo pasa
        if 'datos_pago=_datos_pago' in contenido:
            print("[upgrade57] mi_pedido_detalle ya pasa datos_pago")
            return

    viejo = """    items = conn.execute(\"\"\"SELECT oi.*, p.nombre as producto_nombre, p.sku, p.foto
        FROM orden_items oi JOIN productos p ON p.id = oi.producto_id
        WHERE oi.orden_id=?\"\"\", (id,)).fetchall()
    conn.close()
    return render_template('catalogo/mi_pedido_detalle.html', orden=orden, items=items, mayorista=m)"""

    nuevo = """    items = conn.execute(\"\"\"SELECT oi.*, p.nombre as producto_nombre, p.sku, p.foto
        FROM orden_items oi JOIN productos p ON p.id = oi.producto_id
        WHERE oi.orden_id=?\"\"\", (id,)).fetchall()

    # Cargar datos de pago
    from app57 import _datos_pago
    datos_pago = _datos_pago(conn)
    conn.close()
    return render_template('catalogo/mi_pedido_detalle.html', orden=orden, items=items, mayorista=m, datos_pago=datos_pago)"""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade57] app53 pasa datos_pago al template")
    else:
        print("[upgrade57] ADVERTENCIA: no se encontro la funcion mi_pedido_detalle")


def patch_base_html_menu():
    """Agrega link 'Pagos pendientes' al sidebar."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade57] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'pagos_pendientes_lista' in contenido:
        print("[upgrade57] base.html ya tiene Pagos pendientes")
        return

    buscar = '<a href="{{ url_for(\'mayoristas_lista\') }}"'
    if buscar not in contenido:
        print("[upgrade57] no se encontro el link de Mayoristas"); return

    nuevo = ('<a href="{{ url_for(\'pagos_pendientes_lista\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'pagos_pendientes\') %}active{% endif %}">'
             '<i class="bi bi-cash-coin"></i> Pagos pendientes</a>\n' + buscar)
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade57] link Pagos pendientes agregado a base.html")


def patch_configuracion_index():
    """Agrega tarjeta 'Datos de pago' en Configuración."""
    ruta = os.path.join(BASE, 'templates', 'configuracion', 'index.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'configuracion_datos_pago' in contenido:
        print("[upgrade57] configuracion/index ya tiene datos de pago")
        return

    buscar = '<div class="col-md-4"><a href="{{ url_for(\'configuracion_remitentes\') }}"'
    if buscar not in contenido:
        print("[upgrade57] no se encontro la tarjeta de remitentes")
        return

    nuevo = '''<div class="col-md-4"><a href="{{ url_for('configuracion_datos_pago') }}" class="text-decoration-none"><div class="card shadow-sm h-100" style="border-left:3px solid #10b981;"><div class="card-body">
<i class="bi bi-bank fs-2 text-success"></i>
<h6 class="mt-2">Datos de pago</h6>
<p class="text-muted small mb-0">Alias, CBU, titular para transferencias del catalogo.</p>
</div></div></a></div>

''' + buscar

    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade57] tarjeta Datos de pago agregada a Configuracion")


def patch_checkout_email():
    """Mejora el email de notificación de pedido para incluir datos de pago reales."""
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'pago_alias' in contenido:
        print("[upgrade57] checkout ya usa datos de pago dinamicos")
        return

    viejo = """        # Al mayorista
        cuerpo = f\"\"\"Hola {mayorista['nombre_completo']},

Recibimos tu pedido {numero}.

Detalle:
{detalle}

Total: ${total:.2f}

Tipo de envio: {envio_txt}

Para confirmar el pedido, transferi el total a:
- ALIAS: (configurar)
- CBU: (configurar)
- Titular: Familia Zaragoza

Cuando recibamos el pago te avisamos por email y despachamos.

{firma}\"\"\""""

    nuevo = """        # Cargar datos de pago
        conn_dp = None
        try:
            from app57 import _datos_pago
            from database import get_db as _get_db
            conn_dp = _get_db()
            dp = _datos_pago(conn_dp)
            conn_dp.close()
        except Exception:
            dp = {}

        datos_pago_txt = ''
        if dp.get('pago_alias'): datos_pago_txt += f"- Alias: {dp['pago_alias']}\\n"
        if dp.get('pago_cbu'): datos_pago_txt += f"- CBU: {dp['pago_cbu']}\\n"
        if dp.get('pago_titular'): datos_pago_txt += f"- Titular: {dp['pago_titular']}\\n"
        if dp.get('pago_cuit'): datos_pago_txt += f"- CUIT: {dp['pago_cuit']}\\n"
        if dp.get('pago_banco'): datos_pago_txt += f"- Banco: {dp['pago_banco']}\\n"
        if not datos_pago_txt:
            datos_pago_txt = "- (los datos de pago se muestran en el sistema)"

        # Al mayorista
        cuerpo = f\"\"\"Hola {mayorista['nombre_completo']},

Recibimos tu pedido {numero}.

Detalle:
{detalle}

Total: ${total:.2f}

Tipo de envio: {envio_txt}

Para confirmar el pedido, transferi el total a:
{datos_pago_txt}

Cuando hagas la transferencia, subi el comprobante desde "Mis pedidos" en el catalogo.
Apenas lo aprobemos, te enviamos la confirmacion.

{firma}\"\"\""""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade57] email del checkout con datos de pago dinamicos")
    else:
        print("[upgrade57] ADVERTENCIA: no se encontro el bloque del email")


def patch_catalogo_base_flash():
    """Asegura que los templates del catalogo tengan las clases de alerta correctas."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'cat-alert-warning' in contenido:
        print("[upgrade57] catalogo base ya tiene cat-alert-warning")
        return

    buscar = '.cat-alert-info { background: rgba(6,182,212,.12); color: #22d3ee; border: 1px solid rgba(6,182,212,.25); }'
    if buscar not in contenido:
        print("[upgrade57] no se encontro el CSS de alertas")
        return

    nuevo = buscar + '\n.cat-alert-warning { background: rgba(245,158,11,.12); color: #fbbf24; border: 1px solid rgba(245,158,11,.25); }'
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade57] CSS alerta warning agregada al catalogo")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 57: Pagos pendientes + comprobantes (F6.4) ===")
    migrar()
    escribir('app57.py', APP57_PY)
    escribir('templates/pagos_pendientes/lista.html', PAGOS_PENDIENTES_LISTA)
    escribir('templates/configuracion/datos_pago.html', CONFIG_DATOS_PAGO)
    patch_catalogo_mi_pedido_detalle()
    patch_mis_pedidos_badge()
    patch_mi_pedido_detalle_datos_pago()
    patch_base_html_menu()
    patch_configuracion_index()
    patch_checkout_email()
    patch_catalogo_base_flash()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")
    print("")
    print("Configura primero: Configuracion -> Datos de pago")


if __name__ == '__main__':
    main()