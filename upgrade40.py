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
    print(f"[upgrade40] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade40] sin DB."); return
    conn = sqlite3.connect(db)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS campanas_envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campana_id INTEGER NOT NULL,
            cliente_id INTEGER,
            destinatario TEXT NOT NULL,
            estado TEXT NOT NULL,
            error TEXT,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campana_id) REFERENCES campanas(id) ON DELETE CASCADE,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)
    print("[upgrade40] tabla campanas_envios OK")

    cols = [r[1] for r in conn.execute("PRAGMA table_info(campanas)").fetchall()]
    if 'remitente' not in cols:
        conn.execute("ALTER TABLE campanas ADD COLUMN remitente TEXT")
        print("[upgrade40] + campanas.remitente")
    if 'asunto' not in cols:
        conn.execute("ALTER TABLE campanas ADD COLUMN asunto TEXT")
        print("[upgrade40] + campanas.asunto")
    if 'estado' not in cols:
        conn.execute("ALTER TABLE campanas ADD COLUMN estado TEXT DEFAULT 'borrador'")
        print("[upgrade40] + campanas.estado")
    if 'total_enviados' not in cols:
        conn.execute("ALTER TABLE campanas ADD COLUMN total_enviados INTEGER DEFAULT 0")
        print("[upgrade40] + campanas.total_enviados")
    if 'total_errores' not in cols:
        conn.execute("ALTER TABLE campanas ADD COLUMN total_errores INTEGER DEFAULT 0")
        print("[upgrade40] + campanas.total_errores")
    if 'enviada_en' not in cols:
        conn.execute("ALTER TABLE campanas ADD COLUMN enviada_en TEXT")
        print("[upgrade40] + campanas.enviada_en")

    conn.commit(); conn.close()


APP40_PY = r'''
import os, re, time
from datetime import date
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app39 import app, _enviar_con_remitente, _remitentes_disponibles, _remitente_por_email
from app import admin_required
from database import get_db


def _construir_filtros():
    """Toma los filtros del form y devuelve (sql_where, params, descripcion)."""
    where = ["c.activo = 1", "c.email IS NOT NULL", "c.email != ''", "c.email LIKE '%@%'"]
    params = []
    descripcion = []

    if request.form.get('filtro_tags') == 'minorista':
        where.append("c.es_minorista = 1")
        descripcion.append("Minoristas")
    elif request.form.get('filtro_tags') == 'mayorista':
        where.append("c.es_mayorista = 1")
        descripcion.append("Mayoristas")

    provincia_ids = request.form.getlist('filtro_provincia')
    if provincia_ids:
        placeholders = ','.join(['?'] * len(provincia_ids))
        where.append(f"c.provincia_id IN ({placeholders})")
        params += [int(p) for p in provincia_ids]
        descripcion.append(f"{len(provincia_ids)} provincia(s)")

    clase = request.form.get('filtro_clase', '').strip()
    if clase == 'con_compras':
        where.append("""c.id IN (
            SELECT cliente_id FROM ordenes_venta
            WHERE estado IN ('pagado_sin_enviar','pagado_enviado')
            GROUP BY cliente_id
        )""")
        descripcion.append("Con compras")
    elif clase == 'sin_compras':
        where.append("""c.id NOT IN (
            SELECT cliente_id FROM ordenes_venta
            WHERE estado IN ('pagado_sin_enviar','pagado_enviado')
        )""")
        descripcion.append("Sin compras")

    color = request.form.get('filtro_color', '').strip()
    if color:
        # Calcular dias en Python es complejo en SQL puro, hacemos un post-filtro
        descripcion.append(f"Color {color}")

    vendedor_id = request.form.get('filtro_vendedor', '').strip()
    if vendedor_id:
        where.append("c.vendedor_id = ?")
        params.append(int(vendedor_id))
        descripcion.append(f"Vendedor #{vendedor_id}")

    return ' AND '.join(where), params, descripcion, color


def _clientes_filtrados(conn, where_sql, params, color_filter=''):
    from datetime import datetime, date as _date
    rows = conn.execute(f"SELECT c.*, p.nombre as provincia_nombre, u.nombre as vendedor_nombre FROM clientes c LEFT JOIN provincias p ON p.id = c.provincia_id LEFT JOIN usuarios u ON u.id = c.vendedor_id WHERE {where_sql}", params).fetchall()

    if not color_filter:
        return rows

    # Filtrar por color RFM en Python
    resultado = []
    hoy = _date.today()
    for r in rows:
        ult = conn.execute("""SELECT MAX(COALESCE(fecha_envio, fecha)) FROM ordenes_venta
            WHERE cliente_id = ? AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
            (r['id'],)).fetchone()[0]
        dias = None
        if ult:
            try:
                f = datetime.strptime(ult[:10], '%Y-%m-%d').date()
                dias = (hoy - f).days
            except Exception:
                pass
        if dias is None:
            color = 'gris'
        elif dias <= 45:
            color = 'verde-brillante'
        elif dias <= 66:
            color = 'verde'
        elif dias <= 87:
            color = 'amarillo'
        elif dias <= 108:
            color = 'naranja'
        else:
            color = 'rojo'
        if color == color_filter:
            resultado.append(r)
    return resultado


def _render_variables(texto, cliente):
    return (texto
            .replace('{{nombre}}', cliente['nombre_completo'] or '')
            .replace('{{nombre_completo}}', cliente['nombre_completo'] or '')
            .replace('{{provincia}}', cliente['provincia_nombre'] or '')
            .replace('{{localidad}}', cliente['localidad'] or '')
            .replace('{{vendedor}}', cliente['vendedor_nombre'] or 'Equipo Familia Zaragoza'))


@app.route('/campanas')
@login_required
@admin_required
def campanas_lista():
    conn = get_db()
    campanas = conn.execute("""
        SELECT c.*, u.nombre as creado_por_nombre
        FROM campanas c LEFT JOIN usuarios u ON u.id = (SELECT usuario_id FROM campanas_envios WHERE campana_id = c.id LIMIT 1)
        ORDER BY c.id DESC LIMIT 100
    """).fetchall()
    conn.close()
    return render_template('campanas/lista.html', campanas=campanas)


@app.route('/campanas/nueva', methods=['GET', 'POST'])
@login_required
@admin_required
def campanas_nueva():
    conn = get_db()
    if request.method == 'POST':
        accion = request.form.get('accion', 'preview')

        where_sql, params, descripcion, color_filter = _construir_filtros()
        clientes = _clientes_filtrados(conn, where_sql, params, color_filter)

        if accion == 'preview':
            remitentes = _remitentes_disponibles(conn)
            provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
            vendedores = conn.execute("SELECT id, nombre FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall()
            conn.close()
            return render_template('campanas/form.html',
                                   remitentes=remitentes, provincias=provincias,
                                   vendedores=vendedores,
                                   form_data=request.form,
                                   preview_count=len(clientes),
                                   descripcion_filtros=descripcion)

        if accion == 'guardar' or accion == 'enviar':
            nombre = request.form.get('nombre', '').strip()
            asunto = request.form.get('asunto', '').strip()
            cuerpo = request.form.get('cuerpo', '').strip()
            remitente_email = request.form.get('remitente_email', '').strip()

            if not nombre or not asunto or not cuerpo:
                conn.close(); flash('Completa nombre, asunto y cuerpo.', 'error')
                return redirect(url_for('campanas_nueva'))

            if not clientes:
                conn.close(); flash('No hay destinatarios con esos filtros.', 'error')
                return redirect(url_for('campanas_nueva'))

            # Guardar campaña
            import json as _json
            filtros_json = _json.dumps({
                'tags': request.form.get('filtro_tags'),
                'provincias': request.form.getlist('filtro_provincia'),
                'clase': request.form.get('filtro_clase'),
                'color': request.form.get('filtro_color'),
                'vendedor': request.form.get('filtro_vendedor'),
                'descripcion': descripcion,
            })
            cur = conn.execute("""INSERT INTO campanas (nombre, filtros_json, cuerpo_html, asunto, remitente, estado)
                VALUES (?,?,?,?,?,?)""",
                (nombre, filtros_json, cuerpo, asunto,
                 remitente_email or None,
                 'borrador' if accion == 'guardar' else 'enviando'))
            campana_id = cur.lastrowid
            conn.commit()

            if accion == 'guardar':
                conn.close()
                flash(f'Campaña guardada como borrador ({len(clientes)} destinatarios).', 'success')
                return redirect(url_for('campanas_lista'))

            # Enviar
            remitente_override = _remitente_por_email(conn, remitente_email) if remitente_email else None
            enviados = 0
            errores = 0
            errores_detalle = []
            for i, cliente in enumerate(clientes):
                try:
                    asunto_final = _render_variables(asunto, cliente)
                    cuerpo_final = _render_variables(cuerpo, cliente)
                    ok, msg = _enviar_con_remitente(cliente['email'], asunto_final, cuerpo_final,
                                                     remitente_override=remitente_override)
                    conn.execute("""INSERT INTO campanas_envios (campana_id, cliente_id, destinatario, estado, error)
                        VALUES (?,?,?,?,?)""",
                        (campana_id, cliente['id'], cliente['email'], 'ok' if ok else 'error', None if ok else msg))
                    if ok:
                        enviados += 1
                    else:
                        errores += 1
                        errores_detalle.append(f"{cliente['email']}: {msg}")
                    # Rate limit
                    if i < len(clientes) - 1:
                        time.sleep(0.5)
                except Exception as e:
                    errores += 1
                    errores_detalle.append(f"{cliente['email']}: {e}")
                    conn.execute("""INSERT INTO campanas_envios (campana_id, cliente_id, destinatario, estado, error)
                        VALUES (?,?,?,?,?)""",
                        (campana_id, cliente['id'], cliente['email'], 'error', str(e)))

            conn.execute("""UPDATE campanas SET estado='enviada', total_enviados=?, total_errores=?,
                enviada_en=datetime('now') WHERE id=?""",
                (enviados, errores, campana_id))
            conn.commit(); conn.close()

            if errores == 0:
                flash(f'Campaña enviada: {enviados} emails OK.', 'success')
            else:
                flash(f'Campaña enviada: {enviados} OK, {errores} errores. Revisa el detalle.', 'warning')
            return redirect(url_for('campanas_detalle', id=campana_id))

    remitentes = _remitentes_disponibles(conn)
    provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
    vendedores = conn.execute("SELECT id, nombre FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('campanas/form.html',
                           remitentes=remitentes, provincias=provincias,
                           vendedores=vendedores, form_data={},
                           preview_count=None, descripcion_filtros=[])


@app.route('/campanas/<int:id>')
@login_required
@admin_required
def campanas_detalle(id):
    conn = get_db()
    campana = conn.execute("SELECT * FROM campanas WHERE id=?", (id,)).fetchone()
    if not campana:
        conn.close(); flash('Campaña no encontrada.', 'error')
        return redirect(url_for('campanas_lista'))
    envios = conn.execute("""SELECT e.*, c.nombre_completo FROM campanas_envios e
        LEFT JOIN clientes c ON c.id = e.cliente_id
        WHERE e.campana_id=? ORDER BY e.id DESC""", (id,)).fetchall()
    conn.close()
    return render_template('campanas/detalle.html', campana=campana, envios=envios)


@app.route('/campanas/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def campanas_eliminar(id):
    conn = get_db()
    conn.execute("DELETE FROM campanas WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Campaña eliminada.', 'success')
    return redirect(url_for('campanas_lista'))


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


CAMPANAS_LISTA = r'''{% extends "base.html" %}
{% block title %}Campañas{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Campañas de email</h4>
<div class="text-muted small">Envia promociones, novedades y ofertas a grupos de clientes</div>
</div>
<a href="{{ url_for('campanas_nueva') }}" class="btn btn-dark"><i class="bi bi-plus-lg"></i> Nueva campaña</a>
</div>

{% if campanas %}
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light">
<tr><th>#</th><th>Nombre</th><th>Asunto</th><th>Estado</th><th class="text-end">Enviados</th><th class="text-end">Errores</th><th>Fecha</th><th class="text-end">Acciones</th></tr>
</thead>
<tbody>
{% for c in campanas %}
<tr>
<td class="fw-semibold">{{ c.id }}</td>
<td>{{ c.nombre }}</td>
<td class="small text-muted">{{ c.asunto or '—' }}</td>
<td>
{% if c.estado == 'enviada' %}<span class="badge bg-success">Enviada</span>
{% elif c.estado == 'enviando' %}<span class="badge bg-info text-dark">Enviando...</span>
{% else %}<span class="badge bg-secondary">Borrador</span>{% endif %}
</td>
<td class="text-end">{% if c.total_enviados %}<strong class="text-success">{{ c.total_enviados }}</strong>{% else %}—{% endif %}</td>
<td class="text-end">{% if c.total_errores %}<strong class="text-danger">{{ c.total_errores }}</strong>{% else %}—{% endif %}</td>
<td class="small text-muted">{{ (c.enviada_en or c.creado)[:16] if (c.enviada_en or c.creado) else '' }}</td>
<td class="text-end text-nowrap">
<a href="{{ url_for('campanas_detalle', id=c.id) }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-eye"></i></a>
<form method="post" action="{{ url_for('campanas_eliminar', id=c.id) }}" class="d-inline" onsubmit="return confirm('Eliminar campaña?')">
<button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button>
</form>
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
{% else %}
<div class="card shadow-sm"><div class="card-body text-center py-5">
<i class="bi bi-megaphone fs-1 text-muted"></i>
<h5 class="mt-3">Sin campañas todavía</h5>
<p class="text-muted mb-3">Crea tu primera campaña para avisarle a tus clientes sobre novedades, ofertas o promociones.</p>
<a href="{{ url_for('campanas_nueva') }}" class="btn btn-dark"><i class="bi bi-plus-lg"></i> Crear primera campaña</a>
</div></div>
{% endif %}
{% endblock %}
'''


CAMPANAS_FORM = r'''{% extends "base.html" %}
{% block title %}Nueva campaña{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Nueva campaña</h4>
<div class="text-muted small">Configura los filtros, escribi el mensaje y previsualiza antes de enviar</div>
</div>
<a href="{{ url_for('campanas_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<form method="post" id="campana-form">
<input type="hidden" name="accion" id="accion-input" value="preview">
<div class="row g-3">

<div class="col-md-8">
<!-- Mensaje -->
<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-pencil-square"></i> Mensaje</h6>
<div class="mb-3">
<label class="form-label">Nombre interno * <small class="text-muted">(para identificar la campaña)</small></label>
<input name="nombre" class="form-control" required placeholder="Ej: Promo Noviembre Yerbas" value="{{ form_data.get('nombre', '') }}">
</div>

<div class="row g-2 mb-3">
<div class="col-md-6">
<label class="form-label">Enviar desde</label>
<select name="remitente_email" class="form-select">
{% for r in remitentes %}
<option value="{{ r.email }}" {% if form_data.get('remitente_email') == r.email %}selected{% endif %}>{{ r.label }} · {{ r.email }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-6">
<label class="form-label">Asunto *</label>
<input name="asunto" class="form-control" required placeholder="Ej: Nuevas ofertas en Familia Zaragoza" value="{{ form_data.get('asunto', '') }}">
</div>
</div>

<div class="mb-3">
<label class="form-label">Cuerpo del email *</label>
<textarea name="cuerpo" class="form-control" rows="12" required placeholder="Hola {{ '{{nombre}}' }},&#10;&#10;Tenemos nuevas ofertas...">{{ form_data.get('cuerpo', '') }}</textarea>
<div class="form-text">
Variables disponibles:
<code>{{ '{{nombre}}' }}</code>
<code>{{ '{{provincia}}' }}</code>
<code>{{ '{{localidad}}' }}</code>
<code>{{ '{{vendedor}}' }}</code>
</div>
</div>
</div></div>

<!-- Filtros -->
<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-funnel"></i> Filtros de destinatarios</h6>
<div class="row g-3">
<div class="col-md-6">
<label class="form-label">Por tag</label>
<select name="filtro_tags" class="form-select">
<option value="">Todos</option>
<option value="minorista" {% if form_data.get('filtro_tags') == 'minorista' %}selected{% endif %}>Solo minoristas</option>
<option value="mayorista" {% if form_data.get('filtro_tags') == 'mayorista' %}selected{% endif %}>Solo mayoristas</option>
</select>
</div>
<div class="col-md-6">
<label class="form-label">Por compras</label>
<select name="filtro_clase" class="form-select">
<option value="">Todos</option>
<option value="con_compras" {% if form_data.get('filtro_clase') == 'con_compras' %}selected{% endif %}>Solo con compras</option>
<option value="sin_compras" {% if form_data.get('filtro_clase') == 'sin_compras' %}selected{% endif %}>Solo sin compras</option>
</select>
</div>
<div class="col-md-6">
<label class="form-label">Por color RFM</label>
<select name="filtro_color" class="form-select">
<option value="">Todos</option>
<option value="verde-brillante" {% if form_data.get('filtro_color') == 'verde-brillante' %}selected{% endif %}>Verde brillante (activos)</option>
<option value="verde" {% if form_data.get('filtro_color') == 'verde' %}selected{% endif %}>Verde</option>
<option value="amarillo" {% if form_data.get('filtro_color') == 'amarillo' %}selected{% endif %}>Amarillo</option>
<option value="naranja" {% if form_data.get('filtro_color') == 'naranja' %}selected{% endif %}>Naranja</option>
<option value="rojo" {% if form_data.get('filtro_color') == 'rojo' %}selected{% endif %}>Rojo (en riesgo)</option>
<option value="gris" {% if form_data.get('filtro_color') == 'gris' %}selected{% endif %}>Gris (sin compras)</option>
</select>
</div>
<div class="col-md-6">
<label class="form-label">Por vendedor</label>
<select name="filtro_vendedor" class="form-select">
<option value="">Todos</option>
{% for v in vendedores %}
<option value="{{ v.id }}" {% if form_data.get('filtro_vendedor') == v.id|string %}selected{% endif %}>{{ v.nombre }}</option>
{% endfor %}
</select>
</div>
<div class="col-12">
<label class="form-label">Por provincia <small class="text-muted">(Ctrl+click para varios)</small></label>
<select name="filtro_provincia" class="form-select" multiple size="6">
{% for p in provincias %}
<option value="{{ p.id }}" {% if p.id|string in form_data.getlist('filtro_provincia') %}selected{% endif %}>{{ p.nombre }}</option>
{% endfor %}
</select>
</div>
</div>
</div></div>

<div class="d-flex gap-2 flex-wrap">
<button type="button" class="btn btn-primary" onclick="setAccion('preview')"><i class="bi bi-eye"></i> Previsualizar destinatarios</button>
<button type="button" class="btn btn-outline-secondary" onclick="setAccion('guardar')"><i class="bi bi-save"></i> Guardar borrador</button>
{% if preview_count is not none and preview_count > 0 %}
<button type="button" class="btn btn-dark btn-lg" onclick="confirmarEnvio()"><i class="bi bi-send"></i> Enviar a {{ preview_count }} clientes</button>
{% endif %}
</div>
</form>
</div>

<!-- Panel de preview -->
<div class="col-md-4">
<div class="card shadow-sm sticky-top" style="top:20px;">
<div class="card-body">
<h6 class="mb-3"><i class="bi bi-info-circle"></i> Resumen</h6>
{% if preview_count is not none %}
<div class="text-center mb-3 p-3" style="background:#eef2ff; border-radius:12px;">
<div class="text-muted small">Destinatarios</div>
<div class="display-5 fw-bold" style="color:#3b5bdb;">{{ preview_count }}</div>
</div>
{% if descripcion_filtros %}
<div class="mb-2">
<div class="text-muted small mb-1">Filtros aplicados:</div>
{% for d in descripcion_filtros %}
<span class="badge bg-secondary me-1 mb-1">{{ d }}</span>
{% endfor %}
</div>
{% else %}
<div class="small text-muted mb-2">Sin filtros (todos los clientes activos con email)</div>
{% endif %}
<div class="alert alert-warning py-2 small">
<i class="bi bi-exclamation-triangle"></i> El envio es <strong>inmediato</strong>. Tiempo estimado: <strong>{{ (preview_count * 0.5 / 60)|round(1) }} min</strong>
</div>
{% else %}
<div class="text-center text-muted py-4">
<i class="bi bi-funnel fs-1 d-block mb-2"></i>
<p class="small mb-0">Configura los filtros y hace click en <strong>Previsualizar</strong> para ver cuantos destinatarios hay.</p>
</div>
{% endif %}
</div></div>
</div>
</div>
</form>

<div class="modal fade" id="confirmarModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title"><i class="bi bi-exclamation-triangle text-warning"></i> Confirmar envio</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p>Estas por enviar un email a <strong>{{ preview_count }} clientes</strong>. Esta accion no se puede deshacer.</p>
<div class="alert alert-info py-2 small mb-0">
<i class="bi bi-info-circle"></i> Los emails se envian de a uno con una pausa de 0.5s para no saturar el servidor.
</div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="button" class="btn btn-dark" onclick="enviarAhora()"><i class="bi bi-send"></i> Si, enviar ahora</button>
</div>
</div></div></div>

<script>
function setAccion(a) {
  document.getElementById('accion-input').value = a;
  document.getElementById('campana-form').submit();
}
function confirmarEnvio() {
  new bootstrap.Modal(document.getElementById('confirmarModal')).show();
}
function enviarAhora() {
  document.getElementById('accion-input').value = 'enviar';
  document.getElementById('campana-form').submit();
}
</script>
{% endblock %}
'''


CAMPANAS_DETALLE = r'''{% extends "base.html" %}
{% block title %}Campaña #{{ campana.id }}{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">{{ campana.nombre }}</h4>
<div class="text-muted small">Campaña #{{ campana.id }} · {{ campana.asunto or 'Sin asunto' }}</div>
</div>
<a href="{{ url_for('campanas_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3 mb-3">
<div class="col-md-4"><div class="card-kpi"><div class="kpi-label">Enviados OK</div><div class="kpi-value text-success">{{ campana.total_enviados or 0 }}</div></div></div>
<div class="col-md-4"><div class="card-kpi"><div class="kpi-label">Errores</div><div class="kpi-value {% if campana.total_errores %}text-danger{% endif %}">{{ campana.total_errores or 0 }}</div></div></div>
<div class="col-md-4"><div class="card-kpi"><div class="kpi-label">Estado</div><div class="kpi-value" style="font-size:1.2rem;">
{% if campana.estado == 'enviada' %}<span class="badge bg-success">Enviada</span>
{% elif campana.estado == 'enviando' %}<span class="badge bg-info text-dark">Enviando...</span>
{% else %}<span class="badge bg-secondary">Borrador</span>{% endif %}
</div></div></div>
</div>

<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-2">Mensaje enviado</h6>
<div class="small text-muted mb-1">De: <strong>{{ campana.remitente or '—' }}</strong></div>
<div class="small text-muted mb-2">Asunto: <strong>{{ campana.asunto }}</strong></div>
<div class="border rounded p-3 bg-light" style="white-space:pre-wrap; font-size:.9rem; max-height:300px; overflow-y:auto;">{{ campana.cuerpo_html }}</div>
</div></div>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-sm mb-0">
<thead class="table-light"><tr><th>Fecha</th><th>Cliente</th><th>Email</th><th>Estado</th><th>Error</th></tr></thead>
<tbody>
{% for e in envios %}
<tr>
<td class="small text-muted">{{ e.fecha[:16] if e.fecha else '' }}</td>
<td class="small">{{ e.nombre_completo or '—' }}</td>
<td class="small">{{ e.destinatario }}</td>
<td>{% if e.estado == 'ok' %}<span class="badge bg-success">OK</span>{% else %}<span class="badge bg-danger">Error</span>{% endif %}</td>
<td class="small text-danger">{{ e.error or '' }}</td>
</tr>
{% else %}
<tr><td colspan="5" class="text-center text-muted py-4">Sin envios registrados.</td></tr>
{% endfor %}
</tbody></table></div></div>
{% endblock %}
'''


def patch_base_html():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade40] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'campanas_lista' in contenido:
        print("[upgrade40] base.html ya tiene Campañas")
        return

    buscar = '<a href="{{ url_for(\'emails_historial\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'emails\') %}active{% endif %}"><i class="bi bi-envelope"></i> Emails</a>'
    if buscar not in contenido:
        print("[upgrade40] no se encontro link de Emails"); return

    nuevo = buscar + '\n<a href="{{ url_for(\'campanas_lista\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'campanas\') %}active{% endif %}"><i class="bi bi-megaphone"></i> Campañas</a>'
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade40] link Campañas agregado a base.html")


def patch_emails_historial():
    ruta = os.path.join(BASE, 'templates', 'emails', 'historial.html')
    if not os.path.exists(ruta):
        print("[upgrade40] no existe emails/historial.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'campanas_lista' in contenido:
        print("[upgrade40] emails/historial ya tiene link a campañas"); return

    buscar = '<a href="{{ url_for(\'emails_nuevo\') }}" class="btn btn-dark"><i class="bi bi-pencil-square"></i> Redactar correo</a>'
    if buscar not in contenido:
        print("[upgrade40] no se encontro boton redactar"); return

    nuevo = '<a href="{{ url_for(\'campanas_lista\') }}" class="btn btn-outline-dark"><i class="bi bi-megaphone"></i> Campañas</a>\n' + buscar
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade40] boton Campañas agregado a emails/historial.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app40; app40.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 40: Campañas de email masivo (U40) ===")
    migrar()
    escribir('app40.py', APP40_PY)
    escribir('templates/campanas/lista.html', CAMPANAS_LISTA)
    escribir('templates/campanas/form.html', CAMPANAS_FORM)
    escribir('templates/campanas/detalle.html', CAMPANAS_DETALLE)
    patch_base_html()
    patch_emails_historial()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app40.py)")


if __name__ == '__main__':
    main()