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
    print(f"[upgrade20] escrito: {relpath}")


BASE_HTML = r'''<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><title>{% block title %}Sistema FZ{% endblock %}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --fz-bg:#f4f6fb; --fz-card:#ffffff; --fz-text:#1f2937; --fz-muted:#6b7280;
  --fz-border:#e8ecf3; --fz-primary:#3b5bdb; --fz-primary-soft:#eef2ff;
  --fz-success:#10b981; --fz-success-soft:#ecfdf5;
  --fz-danger:#ef4444; --fz-danger-soft:#fef2f2;
  --fz-warning:#f59e0b; --fz-warning-soft:#fffbeb;
  --fz-shadow:0 1px 3px rgba(16,24,40,.06), 0 1px 2px rgba(16,24,40,.04);
  --fz-shadow-md:0 4px 12px rgba(16,24,40,.08);
  --fz-radius:14px;
}
*{ -webkit-font-smoothing:antialiased; }
body{ background:var(--fz-bg); color:var(--fz-text); margin:0; font-family:'Inter',system-ui,-apple-system,sans-serif; font-size:.94rem; }
.sidebar{ width:245px; min-height:100vh; position:fixed; top:0; left:0;
  background:#111827; color:#e5e7eb; padding:1.25rem 0; display:flex; flex-direction:column; }
.sidebar .brand{ padding:0 1.5rem 1.25rem; font-weight:700; color:#fff;
  border-bottom:1px solid rgba(255,255,255,.08); margin-bottom:.75rem; font-size:1.05rem; letter-spacing:-.01em; }
.sidebar a{ color:#9ca3af; text-decoration:none; padding:.62rem 1.5rem;
  display:flex; align-items:center; gap:.7rem; font-size:.9rem; font-weight:500; transition:background .15s; }
.sidebar a:hover{ background:rgba(255,255,255,.05); color:#fff; }
.sidebar a.active{ background:var(--fz-primary); color:#fff; }
.sidebar a i{ font-size:1.08rem; }
.sidebar .user-info{ margin-top:auto; padding:1.25rem 1.5rem; border-top:1px solid rgba(255,255,255,.08); font-size:.82rem; }
.content{ margin-left:245px; padding:1.75rem 2.25rem; }
.content.sin-sidebar{ margin-left:0; padding-top:4rem; }

.card{ border:none; border-radius:var(--fz-radius); box-shadow:var(--fz-shadow); background:var(--fz-card); }
.card-body{ padding:1.25rem 1.5rem; }
.card-kpi{ background:var(--fz-card); border-radius:var(--fz-radius); box-shadow:var(--fz-shadow);
  padding:1.35rem 1.5rem; height:100%; position:relative; }
.card-kpi:hover{ box-shadow:var(--fz-shadow-md); }
.kpi-icon{ width:42px; height:42px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-size:1.15rem; margin-bottom:.9rem; }
.kpi-icon-primary{ background:var(--fz-primary-soft); color:var(--fz-primary); }
.kpi-icon-success{ background:var(--fz-success-soft); color:var(--fz-success); }
.kpi-icon-danger{ background:var(--fz-danger-soft); color:var(--fz-danger); }
.kpi-icon-warning{ background:var(--fz-warning-soft); color:var(--fz-warning); }
.kpi-label{ color:var(--fz-muted); font-size:.82rem; font-weight:500; margin-bottom:.35rem; }
.kpi-value{ font-size:1.65rem; font-weight:700; letter-spacing:-.02em; line-height:1.1; }
.kpi-delta{ font-size:.78rem; margin-top:.5rem; display:flex; align-items:center; gap:.25rem; }
.kpi-delta i{ font-size:.9rem; }

.btn-primary{ background:var(--fz-primary); border-color:var(--fz-primary); }
.btn-primary:hover{ background:#2f4bbf; border-color:#2f4bbf; }
.btn-outline-primary{ color:var(--fz-primary); border-color:var(--fz-primary); }
.btn-outline-primary:hover{ background:var(--fz-primary); border-color:var(--fz-primary); }
.btn-dark{ background:#111827; border-color:#111827; }
.btn-dark:hover{ background:#1f2937; border-color:#1f2937; }

.badge-soft-primary{ background:var(--fz-primary-soft); color:var(--fz-primary); padding:.4rem .8rem; border-radius:8px; font-weight:600; font-size:.8rem; }
.badge-soft-success{ background:var(--fz-success-soft); color:var(--fz-success); padding:.35rem .65rem; border-radius:6px; font-weight:600; font-size:.78rem; }
.badge-soft-danger{ background:var(--fz-danger-soft); color:var(--fz-danger); padding:.35rem .65rem; border-radius:6px; font-weight:600; font-size:.78rem; }
.badge-soft-warning{ background:var(--fz-warning-soft); color:var(--fz-warning); padding:.35rem .65rem; border-radius:6px; font-weight:600; font-size:.78rem; }

.table thead th{ font-weight:600; font-size:.8rem; text-transform:uppercase; letter-spacing:.02em; color:var(--fz-muted); border-bottom:1px solid var(--fz-border); }
.table>:not(caption)>*>*{ border-color:var(--fz-border); }
.form-control, .form-select{ border-radius:9px; border-color:var(--fz-border); }
.form-control:focus, .form-select:focus{ border-color:var(--fz-primary); box-shadow:0 0 0 3px rgba(59,91,219,.12); }
.alert{ border-radius:10px; border:none; }
h4, h5, h6{ font-weight:600; letter-spacing:-.01em; }
h4{ font-size:1.35rem; }
</style></head><body>
{% if current_user.is_authenticated %}
<aside class="sidebar">
<div class="brand">Familia Zaragoza ®</div>
<a href="{{ url_for('dashboard') }}" class="{% if request.endpoint=='dashboard' %}active{% endif %}"><i class="bi bi-speedometer2"></i> Dashboard</a>
{% if current_user.puede('clientes') %}<a href="{{ url_for('clientes_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('clientes') %}active{% endif %}"><i class="bi bi-people"></i> Clientes</a>{% endif %}
{% if current_user.puede('ventas') %}<a href="{{ url_for('ventas_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('ventas') %}active{% endif %}"><i class="bi bi-cart"></i> Ventas</a>{% endif %}
{% if current_user.es_admin %}
<a href="{{ url_for('compras_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('compras') %}active{% endif %}"><i class="bi bi-bag"></i> Compras</a>
<a href="{{ url_for('gastos_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('gastos') %}active{% endif %}"><i class="bi bi-cash-coin"></i> Gastos</a>
<a href="{{ url_for('reportes') }}" class="{% if request.endpoint and request.endpoint.startswith('reportes') %}active{% endif %}"><i class="bi bi-graph-up"></i> Reportes</a>
<a href="{{ url_for('emails_historial') }}" class="{% if request.endpoint and request.endpoint.startswith('emails') %}active{% endif %}"><i class="bi bi-envelope"></i> Emails</a>
<a href="{{ url_for('solicitudes_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('solicitudes') %}active{% endif %}"><i class="bi bi-inbox"></i> Solicitudes</a>
{% endif %}
{% if current_user.puede('productos') %}<a href="{{ url_for('productos_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('productos') %}active{% endif %}"><i class="bi bi-box-seam"></i> Productos</a>{% endif %}
{% if current_user.es_admin %}<a href="{{ url_for('usuarios_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('usuarios') %}active{% endif %}"><i class="bi bi-person-badge"></i> Usuarios</a>
<a href="{{ url_for('configuracion') }}" class="{% if request.endpoint and request.endpoint.startswith('configuracion') %}active{% endif %}"><i class="bi bi-gear"></i> Configuracion</a>{% endif %}
<div class="user-info">
<div class="d-flex align-items-center gap-2 mb-2"><i class="bi bi-person-circle fs-5 text-secondary"></i><div><div class="text-white">{{ current_user.nombre }}</div><small class="text-secondary">{{ 'Admin' if current_user.es_admin else 'Vendedor' }}</small></div></div>
<a href="{{ url_for('mi_cuenta') }}" class="btn btn-outline-light btn-sm w-100 mb-1" style="border-color:rgba(255,255,255,.15);"><i class="bi bi-key"></i> Mi cuenta</a>
<a href="{{ url_for('logout') }}" class="btn btn-outline-danger btn-sm w-100" style="border-color:rgba(239,68,68,.4);"><i class="bi bi-box-arrow-right"></i> Salir</a>
</div></aside>
{% endif %}
<main class="content {% if not current_user.is_authenticated %}sin-sidebar{% endif %}">
{% with messages = get_flashed_messages(with_categories=true) %}{% for cat, msg in messages %}
<div class="alert alert-{{ 'danger' if cat=='error' else ('success' if cat=='success' else 'info') }} alert-dismissible fade show">{{ msg }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
{% endfor %}{% endwith %}
{% block content %}{% endblock %}
</main>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>

{% if alertas_popup %}
<div class="modal fade" id="alertasModal" tabindex="-1" data-bs-backdrop="static">
<div class="modal-dialog modal-lg"><div class="modal-content">
<div class="modal-header">
<h5 class="modal-title"><i class="bi bi-exclamation-triangle-fill text-warning"></i> Alertas importantes</h5>
<button type="button" class="btn-close" data-bs-dismiss="modal" onclick="dismissAlertas()"></button>
</div>
<div class="modal-body">

{% if alertas_popup.productos_agotados %}
<div class="alert alert-danger py-2 px-3 mb-3" style="border-left:4px solid #ef4444;">
<div class="fw-semibold mb-2"><i class="bi bi-x-octagon-fill"></i> {{ alertas_popup.productos_agotados|length }} producto(s) agotado(s)</div>
<ul class="mb-0 ps-3 small">
{% for p in alertas_popup.productos_agotados %}
<li>{{ p.nombre }}{% if p.sku %} <span class="text-muted">({{ p.sku }})</span>{% endif %}</li>
{% endfor %}
</ul>
</div>
{% endif %}

{% if alertas_popup.productos_bajos %}
<div class="alert alert-warning py-2 px-3 mb-3" style="border-left:4px solid #f59e0b;">
<div class="fw-semibold mb-2"><i class="bi bi-exclamation-triangle-fill"></i> {{ alertas_popup.productos_bajos|length }} producto(s) con bajo stock</div>
<ul class="mb-0 ps-3 small">
{% for p in alertas_popup.productos_bajos %}
<li>{{ p.nombre }} — stock <strong>{{ '%g'|format(p.stock_actual) }}</strong> (mínimo {{ '%g'|format(p.stock_minimo) }})</li>
{% endfor %}
</ul>
</div>
{% endif %}

{% if alertas_popup.ordenes_viejas %}
<div class="alert alert-info py-2 px-3 mb-3" style="border-left:4px solid #06b6d4;">
<div class="fw-semibold mb-2"><i class="bi bi-clock-history"></i> {{ alertas_popup.ordenes_viejas|length }} orden(es) pagada(s) sin despachar hace más de {{ alertas_popup.horas_limite }}hs</div>
<ul class="mb-0 ps-3 small">
{% for o in alertas_popup.ordenes_viejas %}
<li><a href="{{ url_for('ventas_detalle', id=o.id) }}" class="text-decoration-none fw-semibold">{{ o.numero_interno }}</a> — {{ o.cliente_nombre }} <span class="text-muted">({{ o.horas_esperando }}hs esperando)</span></li>
{% endfor %}
</ul>
</div>
{% endif %}

</div>
<div class="modal-footer flex-wrap gap-2">
{% if alertas_popup.productos_agotados or alertas_popup.productos_bajos %}
<a href="{{ url_for('productos_lista', alerta='agotado') }}" class="btn btn-outline-danger btn-sm" onclick="dismissAlertas()"><i class="bi bi-box-seam"></i> Ver productos</a>
{% endif %}
{% if alertas_popup.ordenes_viejas %}
<a href="{{ url_for('ventas_lista', estado='pagado_sin_enviar') }}" class="btn btn-outline-primary btn-sm" onclick="dismissAlertas()"><i class="bi bi-truck"></i> Ver pendientes</a>
{% endif %}
<button type="button" class="btn btn-dark btn-sm" data-bs-dismiss="modal" onclick="dismissAlertas()">Entendido</button>
</div>
</div></div>
</div>
<script>
(function(){
  const COOLDOWN_HORAS = 4;
  const key = 'fz_alertas_last_dismissed';
  try {
    const last = localStorage.getItem(key);
    if (last) {
      const diff = Date.now() - parseInt(last);
      if (diff < COOLDOWN_HORAS * 3600 * 1000) return;
    }
  } catch(e) { }
  const modalEl = document.getElementById('alertasModal');
  if (!modalEl) return;
  new bootstrap.Modal(modalEl).show();
})();
function dismissAlertas() {
  try { localStorage.setItem('fz_alertas_last_dismissed', Date.now().toString()); } catch(e) {}
}
</script>
{% endif %}

</body></html>
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app18; app18.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 20: Agregar modal de alertas a base.html ===")
    escribir('templates/base.html', BASE_HTML)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")
    print("Si no aparece el popup, F12 → Console → localStorage.clear() → F5")


if __name__ == '__main__':
    main()