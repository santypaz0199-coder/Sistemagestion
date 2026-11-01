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
    print(f"[upgrade30] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade30] sin DB."); return
    conn = sqlite3.connect(db)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(ordenes_venta)").fetchall()]
    if 'fecha_envio' not in cols:
        conn.execute("ALTER TABLE ordenes_venta ADD COLUMN fecha_envio TEXT")
        print("[upgrade30] + ordenes_venta.fecha_envio")

    # Backfill: para ordenes ya enviadas, usar la fecha de la orden como aproximacion
    conn.execute("""
        UPDATE ordenes_venta SET fecha_envio = fecha
        WHERE estado = 'pagado_enviado' AND fecha_envio IS NULL
    """)
    print("[upgrade30] backfill fecha_envio de ordenes existentes")

    # Trigger: al pasar a pagado_enviado, registrar fecha_envio
    conn.execute("DROP TRIGGER IF EXISTS trg_ordenes_fecha_envio")
    conn.execute("""
        CREATE TRIGGER trg_ordenes_fecha_envio
        AFTER UPDATE OF estado ON ordenes_venta
        WHEN NEW.estado = 'pagado_enviado' AND OLD.estado != 'pagado_enviado'
        BEGIN
            UPDATE ordenes_venta SET fecha_envio = datetime('now') WHERE id = NEW.id;
        END
    """)
    print("[upgrade30] trigger trg_ordenes_fecha_envio OK")

    conn.commit(); conn.close()


APP30_PY = r'''
import re, urllib.parse
from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app29 import app
from database import get_db


def _limpiar_tel(t):
    if not t:
        return ''
    n = re.sub(r'\D', '', t)
    if n and not n.startswith('54'):
        n = '54' + n
    return n


def _rfm_color(dias):
    if dias is None:
        return 'gris'
    if dias <= 45:
        return 'verde-brillante'
    if dias <= 66:
        return 'verde'
    if dias <= 87:
        return 'amarillo'
    if dias <= 108:
        return 'naranja'
    return 'rojo'


def _clasificar(num_compras, total_compras, top_threshold):
    if num_compras == 0:
        return 'sin-compras'
    if total_compras >= top_threshold and top_threshold > 0:
        return 'top'
    if num_compras >= 3:
        return 'recurrente'
    return 'ocasional'


@app.route('/clientes')
@login_required
def clientes_lista_v4():
    q = request.args.get('q', '').strip()
    filtro_tipo = request.args.get('tipo', '')
    provincia_id = request.args.get('provincia_id', '').strip()
    localidad_id = request.args.get('localidad_id', '').strip()
    vendedor_filtro = request.args.get('vendedor', '').strip()
    filtro_color = request.args.get('color', '').strip()
    filtro_clase = request.args.get('clase', '').strip()

    conn = get_db()

    # Query base con metricas de RFM
    sql = """SELECT c.*,
             p.nombre as provincia_nombre,
             l.nombre as localidad_nombre,
             v.nombre as vendedor_nombre,
             COALESCE((
                 SELECT SUM(o.total) FROM ordenes_venta o
                 WHERE o.cliente_id = c.id AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
             ), 0) as total_compras,
             COALESCE((
                 SELECT COUNT(DISTINCT o.id) FROM ordenes_venta o
                 WHERE o.cliente_id = c.id AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                 AND date(o.fecha) >= date('now','-12 months')
             ), 0) as compras_12m,
             (
                 SELECT MAX(COALESCE(o.fecha_envio, o.fecha))
                 FROM ordenes_venta o
                 WHERE o.cliente_id = c.id AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
             ) as ultimo_despacho
             FROM clientes c
             LEFT JOIN provincias p ON p.id = c.provincia_id
             LEFT JOIN localidades l ON l.id = c.localidad_id
             LEFT JOIN usuarios v ON v.id = c.vendedor_id
             WHERE c.activo=1"""
    params = []

    if not current_user.es_admin:
        sql += " AND c.vendedor_id = ?"; params.append(current_user.id)
    elif vendedor_filtro:
        sql += " AND c.vendedor_id = ?"; params.append(int(vendedor_filtro))

    if q:
        sql += " AND (c.nombre_completo LIKE ? OR c.nro_doc LIKE ? OR c.email LIKE ? OR c.telefono LIKE ?)"
        params += [f'%{q}%'] * 4
    if filtro_tipo == 'minorista':
        sql += " AND c.es_minorista=1"
    elif filtro_tipo == 'mayorista':
        sql += " AND c.es_mayorista=1"
    if provincia_id:
        sql += " AND c.provincia_id=?"; params.append(int(provincia_id))
    if localidad_id:
        sql += " AND c.localidad_id=?"; params.append(int(localidad_id))
    sql += " ORDER BY c.nombre_completo"

    rows = conn.execute(sql, params).fetchall()

    # Calcular threshold top 20%
    totales = sorted([r['total_compras'] for r in rows if r['total_compras'] > 0], reverse=True)
    top_threshold = 0
    if totales:
        corte = max(1, int(len(totales) * 0.2))
        top_threshold = totales[corte - 1]

    hoy = date.today()
    clientes = []
    for r in rows:
        d = dict(r)
        # Color
        if r['ultimo_despacho']:
            try:
                fecha_ult = datetime.strptime(r['ultimo_despacho'][:10], '%Y-%m-%d').date()
                dias = (hoy - fecha_ult).days
            except Exception:
                dias = None
        else:
            dias = None
        d['dias_desde_ultimo'] = dias
        d['rfm_color'] = _rfm_color(dias)
        d['clasificacion'] = _clasificar(r['compras_12m'], r['total_compras'], top_threshold)
        # URLs
        tel = _limpiar_tel(r['telefono'])
        if tel:
            nombre_corto = (r['nombre_completo'] or '').split()[0] if r['nombre_completo'] else 'cliente'
            msg = f"Hola {nombre_corto}! Te escribimos de Familia Zaragoza ® ¿En que te podemos ayudar?"
            d['wa_url'] = f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"
        else:
            d['wa_url'] = None
        d['mailto_url'] = None
        if r['email'] and '@' in r['email']:
            asunto = urllib.parse.quote('Consulta - Familia Zaragoza ®')
            d['mailto_url'] = f"mailto:{r['email']}?subject={asunto}"
        clientes.append(d)

    # Filtros por color/clase (post-procesamiento)
    if filtro_color:
        clientes = [c for c in clientes if c['rfm_color'] == filtro_color]
    if filtro_clase:
        clientes = [c for c in clientes if c['clasificacion'] == filtro_clase]

    provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
    locs_rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    localidades_por_provincia = {}
    for r in locs_rows:
        localidades_por_provincia.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})

    vendedores = []
    if current_user.es_admin:
        vendedores = conn.execute("SELECT id, nombre FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall()

    # Stats por color (del total sin filtros de color/clase aplicados)
    todos_rows = conn.execute(sql, params).fetchall()
    stats_color = {'verde-brillante': 0, 'verde': 0, 'amarillo': 0, 'naranja': 0, 'rojo': 0, 'gris': 0}
    stats_clase = {'top': 0, 'recurrente': 0, 'ocasional': 0, 'sin-compras': 0}
    for r in todos_rows:
        if r['ultimo_despacho']:
            try:
                fecha_ult = datetime.strptime(r['ultimo_despacho'][:10], '%Y-%m-%d').date()
                dias = (hoy - fecha_ult).days
            except Exception:
                dias = None
        else:
            dias = None
        stats_color[_rfm_color(dias)] += 1
        stats_clase[_clasificar(r['compras_12m'], r['total_compras'], top_threshold)] += 1

    stats = {
        'total': len(todos_rows),
        'minoristas': sum(1 for c in todos_rows if c['es_minorista']),
        'mayoristas': sum(1 for c in todos_rows if c['es_mayorista']),
        'por_color': stats_color,
        'por_clase': stats_clase,
    }
    conn.close()
    return render_template('clientes/lista.html', clientes=clientes, q=q,
                           filtro_tipo=filtro_tipo, provincia_id=provincia_id,
                           localidad_id=localidad_id, provincias=provincias,
                           localidades_por_provincia=localidades_por_provincia,
                           stats=stats, vendedores=vendedores, vendedor_filtro=vendedor_filtro,
                           filtro_color=filtro_color, filtro_clase=filtro_clase)


app.view_functions['clientes_lista'] = clientes_lista_v4


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


CLIENTES_LISTA = r'''{% extends "base.html" %}
{% block title %}Clientes{% endblock %}
{% block content %}
<style>
.rfm-dot{ width:14px; height:14px; border-radius:50%; display:inline-block; flex-shrink:0; }
.rfm-verde-brillante{ background:#10b981; box-shadow:0 0 0 3px rgba(16,185,129,.2); }
.rfm-verde{ background:#34d399; }
.rfm-amarillo{ background:#fbbf24; }
.rfm-naranja{ background:#f97316; }
.rfm-rojo{ background:#ef4444; }
.rfm-gris{ background:#9ca3af; }
.stats-mini{ display:flex; gap:.5rem; flex-wrap:wrap; font-size:.75rem; }
.stats-chip{ padding:.25rem .6rem; border-radius:20px; background:#f3f4f6; color:#4b5563; text-decoration:none; }
.stats-chip:hover{ background:#e5e7eb; color:#111827; }
.stats-chip.active{ background:#3b5bdb; color:#fff; }
</style>

<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Clientes</h4>
<div class="d-flex gap-2">
<a href="{{ url_for('clientes_top') }}" class="btn btn-outline-primary btn-sm"><i class="bi bi-trophy"></i> Top</a>
<a href="{{ url_for('clientes_nuevo') }}" class="btn btn-dark btn-sm"><i class="bi bi-plus-lg"></i> Nuevo</a>
</div>
</div>

<!-- Stats rapidos -->
<div class="row row-cols-2 row-cols-md-5 g-2 mb-3">
<div class="col"><a href="{{ url_for('clientes_lista') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="{% if not filtro_color and not filtro_clase %}border:2px solid #3b5bdb;{% endif %}"><div class="kpi-label">Total</div><div class="kpi-value">{{ stats.total }}</div></div></a></div>
<div class="col"><a href="{{ url_for('clientes_lista', color='verde-brillante') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #10b981;{% if filtro_color=='verde-brillante' %}background:#ecfdf5;{% endif %}"><div class="kpi-label"><span class="rfm-dot rfm-verde-brillante"></span> Verde brillante</div><div class="kpi-value">{{ stats.por_color['verde-brillante'] }}</div></div></a></div>
<div class="col"><a href="{{ url_for('clientes_lista', color='amarillo') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #fbbf24;{% if filtro_color=='amarillo' %}background:#fffbeb;{% endif %}"><div class="kpi-label"><span class="rfm-dot rfm-amarillo"></span> Amarillo</div><div class="kpi-value">{{ stats.por_color['amarillo'] }}</div></div></a></div>
<div class="col"><a href="{{ url_for('clientes_lista', color='rojo') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #ef4444;{% if filtro_color=='rojo' %}background:#fef2f2;{% endif %}"><div class="kpi-label"><span class="rfm-dot rfm-rojo"></span> Rojo (riesgo)</div><div class="kpi-value">{{ stats.por_color['rojo'] }}</div></div></a></div>
<div class="col"><a href="{{ url_for('clientes_lista', clase='top') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #fbbf24;{% if filtro_clase=='top' %}background:#fffbeb;{% endif %}"><div class="kpi-label">🏆 Top 20%</div><div class="kpi-value">{{ stats.por_clase['top'] }}</div></div></a></div>
</div>

<form class="card shadow-sm p-3 mb-3">
<div class="row g-2 align-items-end">
<div class="col-md-3">
<label class="form-label small text-muted">Buscar</label>
<input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="Nombre, doc, email, tel">
</div>
<div class="col-md-2">
<label class="form-label small text-muted">Tag</label>
<select name="tipo" class="form-select form-select-sm">
<option value="">Todos</option>
<option value="minorista" {% if filtro_tipo=='minorista' %}selected{% endif %}>Minorista</option>
<option value="mayorista" {% if filtro_tipo=='mayorista' %}selected{% endif %}>Mayorista</option>
</select>
</div>
<div class="col-md-2">
<label class="form-label small text-muted">Clasificacion</label>
<select name="clase" class="form-select form-select-sm">
<option value="">Todas</option>
<option value="top" {% if filtro_clase=='top' %}selected{% endif %}>Top 20%</option>
<option value="recurrente" {% if filtro_clase=='recurrente' %}selected{% endif %}>Recurrente</option>
<option value="ocasional" {% if filtro_clase=='ocasional' %}selected{% endif %}>Ocasional</option>
<option value="sin-compras" {% if filtro_clase=='sin-compras' %}selected{% endif %}>Sin compras</option>
</select>
</div>
<div class="col-md-2">
<label class="form-label small text-muted">Color</label>
<select name="color" class="form-select form-select-sm">
<option value="">Todos</option>
<option value="verde-brillante" {% if filtro_color=='verde-brillante' %}selected{% endif %}>Verde brillante</option>
<option value="verde" {% if filtro_color=='verde' %}selected{% endif %}>Verde</option>
<option value="amarillo" {% if filtro_color=='amarillo' %}selected{% endif %}>Amarillo</option>
<option value="naranja" {% if filtro_color=='naranja' %}selected{% endif %}>Naranja</option>
<option value="rojo" {% if filtro_color=='rojo' %}selected{% endif %}>Rojo</option>
<option value="gris" {% if filtro_color=='gris' %}selected{% endif %}>Sin compras</option>
</select>
</div>
{% if current_user.es_admin %}
<div class="col-md-2">
<label class="form-label small text-muted">Vendedor</label>
<select name="vendedor" class="form-select form-select-sm">
<option value="">Todos</option>
{% for v in vendedores %}
<option value="{{ v.id }}" {% if vendedor_filtro==v.id|string %}selected{% endif %}>{{ v.nombre }}</option>
{% endfor %}
</select>
</div>
{% endif %}
<div class="col-md-1">
<button class="btn btn-outline-secondary btn-sm w-100"><i class="bi bi-search"></i></button>
</div>
</div>
</form>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th width="30"></th><th>Nombre</th><th>Doc</th><th>Ciudad / Provincia</th>
<th>Clasificacion</th><th class="text-end">Compras</th><th>Ultima</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for c in clientes %}
<tr>
<td><span class="rfm-dot rfm-{{ c.rfm_color }}" title="{% if c.dias_desde_ultimo is not none %}Ultima compra hace {{ c.dias_desde_ultimo }} dias{% else %}Sin compras{% endif %}"></span></td>
<td>
<a href="{{ url_for('clientes_editar', id=c.id) }}" class="text-decoration-none fw-semibold">{{ c.nombre_completo }}</a>
{% if c.es_minorista %}<span class="badge bg-info text-dark" style="font-size:.6rem;">Min</span>{% endif %}
{% if c.es_mayorista %}<span class="badge bg-warning text-dark" style="font-size:.6rem;">May</span>{% endif %}
</td>
<td class="small text-muted text-nowrap">{{ c.tipo_doc or '' }} {{ c.nro_doc or '' }}</td>
<td class="small">
{% if c.localidad_nombre %}{{ c.localidad_nombre }}{% endif %}
{% if c.localidad_nombre and c.provincia_nombre %} · {% endif %}
{% if c.provincia_nombre %}<span class="text-muted">{{ c.provincia_nombre }}</span>{% endif %}
{% if not c.localidad_nombre and not c.provincia_nombre %}—{% endif %}
</td>
<td>
{% if c.clasificacion == 'top' %}<span class="badge" style="background:#fbbf24; color:#78350f;">🏆 Top</span>
{% elif c.clasificacion == 'recurrente' %}<span class="badge bg-success">Recurrente</span>
{% elif c.clasificacion == 'ocasional' %}<span class="badge bg-secondary">Ocasional</span>
{% else %}<span class="text-muted small">—</span>{% endif %}
</td>
<td class="text-end">
{% if c.total_compras > 0 %}
<div class="fw-semibold">${{ '{:,.0f}'.format(c.total_compras).replace(',', '.') }}</div>
{% else %}
<span class="text-muted small">$0</span>
{% endif %}
</td>
<td class="small text-muted text-nowrap">
{% if c.dias_desde_ultimo is not none %}
hace {{ c.dias_desde_ultimo }}d
{% else %}—{% endif %}
</td>
<td class="text-end text-nowrap">
{% if c.wa_url %}
<a href="{{ c.wa_url }}" target="_blank" class="btn btn-sm btn-outline-success" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>
{% else %}
<button class="btn btn-sm btn-outline-secondary" disabled title="Sin telefono"><i class="bi bi-whatsapp"></i></button>
{% endif %}
{% if c.mailto_url %}
<a href="{{ c.mailto_url }}" class="btn btn-sm btn-outline-primary" title="Email"><i class="bi bi-envelope"></i></a>
{% else %}
<button class="btn btn-sm btn-outline-secondary" disabled title="Sin email"><i class="bi bi-envelope"></i></button>
{% endif %}
<a href="{{ url_for('ventas_nueva') }}?cliente_id={{ c.id }}" class="btn btn-sm btn-outline-dark" title="Crear orden"><i class="bi bi-cart-plus"></i></a>
<a href="{{ url_for('clientes_editar', id=c.id) }}" class="btn btn-sm btn-outline-secondary" title="Editar"><i class="bi bi-pencil"></i></a>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrarCliente({{ c.id }}, {{ c.nombre_completo|tojson }})" title="Borrar"><i class="bi bi-trash"></i></button>
</td>
</tr>
{% else %}
<tr><td colspan="8" class="text-center text-muted py-4">Sin clientes con esos filtros.</td></tr>
{% endfor %}
</tbody></table></div></div>

<!-- Leyenda -->
<div class="card shadow-sm mt-3"><div class="card-body">
<h6 class="mb-2 small text-muted">Como se calcula el color</h6>
<div class="row g-2 small">
<div class="col-md-4"><span class="rfm-dot rfm-verde-brillante"></span> <strong>Verde brillante</strong> · hasta 45 dias desde el despacho</div>
<div class="col-md-4"><span class="rfm-dot rfm-verde"></span> <strong>Verde</strong> · 46-66 dias</div>
<div class="col-md-4"><span class="rfm-dot rfm-amarillo"></span> <strong>Amarillo</strong> · 67-87 dias</div>
<div class="col-md-4"><span class="rfm-dot rfm-naranja"></span> <strong>Naranja</strong> · 88-108 dias</div>
<div class="col-md-4"><span class="rfm-dot rfm-rojo"></span> <strong>Rojo</strong> · mas de 108 dias sin comprar</div>
<div class="col-md-4"><span class="rfm-dot rfm-gris"></span> <strong>Gris</strong> · nunca compro</div>
</div>
</div></div>

<div class="modal fade" id="borrarClienteModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="borrar-cliente-form" method="post">
<div class="modal-header"><h6 class="modal-title">Borrar cliente <span id="borrar-cliente-nombre"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
{% if current_user.es_admin %}
<div class="alert alert-warning py-2 small mb-3"><i class="bi bi-exclamation-triangle"></i> Como admin, el cliente se desactiva inmediatamente.</div>
{% else %}
<div class="alert alert-info py-2 small mb-3"><i class="bi bi-info-circle"></i> Se enviara una <strong>solicitud al admin</strong>.</div>
{% endif %}
<div class="mb-2"><label class="form-label">Motivo (opcional)</label><textarea name="motivo" class="form-control" rows="2"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">{% if current_user.es_admin %}Borrar{% else %}Enviar solicitud{% endif %}</button>
</div>
</form></div></div></div>

<script>
function openBorrarCliente(id, nombre) {
  document.getElementById('borrar-cliente-form').action = '/clientes/' + id + '/borrar';
  document.getElementById('borrar-cliente-nombre').textContent = nombre;
  new bootstrap.Modal(document.getElementById('borrarClienteModal')).show();
}
</script>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app30; app30.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 30: Colores RFM + Clasificacion (U30) ===")
    migrar()
    escribir('app30.py', APP30_PY)
    escribir('templates/clientes/lista.html', CLIENTES_LISTA)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app30.py)")


if __name__ == '__main__':
    main()