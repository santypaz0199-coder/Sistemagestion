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
    print(f"[upgrade69] escrito: {relpath}")


DASHBOARD_HTML = r'''{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
<div>
<h3 class="mb-1" style="font-weight:700; letter-spacing:-.02em;">Hola, {{ current_user.nombre }} 👋</h3>
<div class="text-muted">{{ hoy.strftime('%d/%m/%Y') }} · {{ 'Administrador' if current_user.es_admin else 'Usuario' }}</div>
</div>
</div>

<!-- ALERTAS CLICKEABLES -->
<div class="row g-2 mb-4">
{% if envios_pendientes and envios_pendientes > 0 %}
<div class="col-md-6">
<a href="{{ url_for('ventas_lista', estado='pagado_sin_enviar') }}" class="text-decoration-none">
<div class="alert alert-warning d-flex align-items-center mb-0" style="border-left:4px solid #f59e0b; border-radius:10px;">
<i class="bi bi-truck fs-4 me-3"></i>
<div>
<div class="fw-semibold text-dark">{{ envios_pendientes }} envio{{ 's' if envios_pendientes != 1 else '' }} pendiente{{ 's' if envios_pendientes != 1 else '' }}</div>
<div class="small text-muted">Ordenes cobradas esperando despacho</div>
</div>
<i class="bi bi-chevron-right ms-auto text-muted"></i>
</div>
</a>
</div>
{% endif %}
{% if ordenes_por_cobrar and ordenes_por_cobrar > 0 %}
<div class="col-md-6">
<a href="{{ url_for('ventas_lista', estado='pendiente_pago') }}" class="text-decoration-none">
<div class="alert alert-info d-flex align-items-center mb-0" style="border-left:4px solid #06b6d4; border-radius:10px;">
<i class="bi bi-cash-coin fs-4 me-3"></i>
<div>
<div class="fw-semibold text-dark">{{ ordenes_por_cobrar }} orden{{ 'es' if ordenes_por_cobrar != 1 else '' }} por cobrar</div>
<div class="small text-muted">Saldo pendiente de acreditacion</div>
</div>
<i class="bi bi-chevron-right ms-auto text-muted"></i>
</div>
</a>
</div>
{% endif %}
</div>

<!-- 3 KPIs CON GRAFICOS SEMANALES -->
<div class="row g-3 mb-4">
<div class="col-md-4">
<div class="card" style="border-left:3px solid #3b5bdb;">
<div class="card-body py-3">
<div class="d-flex justify-content-between align-items-start mb-1">
<div>
<div class="kpi-label" style="margin-bottom:.15rem;">Ventas de {{ mes_actual_label }}</div>
<div class="fs-5 fw-bold" style="letter-spacing:-.02em;">${{ '{:,.0f}'.format(actual.ventas).replace(',','.') }}</div>
</div>
{% if variacion.ventas is not none %}
<span class="badge {% if variacion.ventas >= 0 %}bg-success{% else %}bg-danger{% endif %}" style="font-size:.7rem;">
<i class="bi bi-arrow-{% if variacion.ventas >= 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(variacion.ventas|abs) }}%
</span>
{% endif %}
</div>
<div class="text-muted small mb-2" style="font-size:.72rem;">por semana · vs {{ variacion.mes_anterior_label }}</div>
<div style="height:110px; position:relative;"><canvas id="chart-kpi-ventas"></canvas></div>
</div>
</div>
</div>

<div class="col-md-4">
<div class="card" style="border-left:3px solid #ef4444;">
<div class="card-body py-3">
<div class="d-flex justify-content-between align-items-start mb-1">
<div>
<div class="kpi-label" style="margin-bottom:.15rem;">Gastos de {{ mes_actual_label }}</div>
<div class="fs-5 fw-bold" style="letter-spacing:-.02em;">${{ '{:,.0f}'.format(gastos_mes).replace(',','.') }}</div>
</div>
{% if var_gastos is not none %}
<span class="badge {% if var_gastos > 0 %}bg-danger{% else %}bg-success{% endif %}" style="font-size:.7rem;">
<i class="bi bi-arrow-{% if var_gastos >= 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(var_gastos|abs) }}%
</span>
{% endif %}
</div>
<div class="text-muted small mb-2" style="font-size:.72rem;">por semana · vs {{ variacion.mes_anterior_label }}</div>
<div style="height:110px; position:relative;"><canvas id="chart-kpi-gastos"></canvas></div>
</div>
</div>
</div>

<div class="col-md-4">
<div class="card" style="border-left:3px solid #10b981;">
<div class="card-body py-3">
<div class="d-flex justify-content-between align-items-start mb-1">
<div>
<div class="kpi-label" style="margin-bottom:.15rem;">Saldo actual (caja)</div>
<div class="fs-5 fw-bold {% if saldo_actual >= 0 %}text-success{% else %}text-danger{% endif %}" style="letter-spacing:-.02em;">
${{ '{:,.0f}'.format(saldo_actual).replace(',','.') }}
</div>
</div>
</div>
<div class="text-muted small mb-2" style="font-size:.72rem;">semana a semana · vs mes anterior</div>
<div style="height:110px; position:relative;"><canvas id="chart-kpi-saldo"></canvas></div>
</div>
</div>
</div>
</div>

<!-- ACCESOS DIRECTOS -->
<div class="row g-3 mb-4">
<div class="col-md-4">
<a href="{{ url_for('ventas_nueva') }}" class="text-decoration-none">
<div class="card card-kpi text-center h-100" style="transition:transform .15s, box-shadow .15s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 24px rgba(59,91,219,.12)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
<div class="kpi-icon kpi-icon-primary mx-auto"><i class="bi bi-cart-plus"></i></div>
<div class="fw-semibold text-dark">Crear orden</div>
<div class="small text-muted">Nueva venta</div>
</div>
</a>
</div>
<div class="col-md-4">
<a href="{{ url_for('clientes_nuevo') }}" class="text-decoration-none">
<div class="card card-kpi text-center h-100" style="transition:transform .15s, box-shadow .15s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 24px rgba(59,91,219,.12)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
<div class="kpi-icon kpi-icon-success mx-auto"><i class="bi bi-person-plus"></i></div>
<div class="fw-semibold text-dark">Añadir cliente</div>
<div class="small text-muted">Nuevo registro</div>
</div>
</a>
</div>
{% if current_user.es_admin %}
<div class="col-md-4">
<a href="{{ url_for('productos_nuevo') }}" class="text-decoration-none">
<div class="card card-kpi text-center h-100" style="transition:transform .15s, box-shadow .15s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 24px rgba(59,91,219,.12)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
<div class="kpi-icon kpi-icon-warning mx-auto"><i class="bi bi-box-seam"></i></div>
<div class="fw-semibold text-dark">Nuevo producto</div>
<div class="small text-muted">Agregar al catalogo</div>
</div>
</a>
</div>
{% endif %}
</div>

<!-- OBJETIVOS -->
{% if objetivos_dashboard is defined and objetivos_dashboard %}
<div class="card shadow-sm mb-4">
<div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0"><i class="bi bi-bullseye"></i> Objetivos de {{ objetivos_dashboard.mes_label }} {{ objetivos_dashboard.anio }}</h6>
<a href="{{ url_for('objetivos_lista') }}" class="btn btn-sm btn-outline-secondary">Gestionar</a>
</div>

{% if objetivos_dashboard.global.objetivo > 0 %}
<div class="mb-3">
<div class="d-flex justify-content-between mb-1">
<span class="small fw-semibold"><i class="bi bi-globe"></i> Objetivo global</span>
<span class="small">
${{ '{:,.0f}'.format(objetivos_dashboard.global.facturado).replace(',','.') }} / ${{ '{:,.0f}'.format(objetivos_dashboard.global.objetivo).replace(',','.') }}
· <strong>{{ '%.1f'|format(objetivos_dashboard.global.pct) }}%</strong>
</span>
</div>
<div class="progress-fz {% if objetivos_dashboard.global.pct >= 75 %}p-ok{% elif objetivos_dashboard.global.pct >= 50 %}p-warn{% else %}p-low{% endif %}" style="height:10px;">
<div class="progress-bar" style="width:{{ [objetivos_dashboard.global.pct, 100]|min }}%"></div>
</div>
</div>
{% endif %}

{% if objetivos_dashboard.vendedores %}
<div class="row g-2">
{% for v in objetivos_dashboard.vendedores %}
<div class="col-md-6">
<div class="border rounded p-2">
<div class="d-flex justify-content-between mb-1">
<span class="small fw-semibold">{{ v.nombre }}</span>
<span class="small">
{% if v.objetivo > 0 %}{{ '%.0f'|format(v.pct) }}%{% else %}<span class="text-muted">Sin objetivo</span>{% endif %}
</span>
</div>
{% if v.objetivo > 0 %}
<div class="progress-fz {% if v.pct >= 75 %}p-ok{% elif v.pct >= 50 %}p-warn{% else %}p-low{% endif %}" style="height:6px;">
<div class="progress-bar" style="width:{{ [v.pct, 100]|min }}%"></div>
</div>
<div class="small text-muted mt-1">${{ '{:,.0f}'.format(v.facturado).replace(',','.') }} / ${{ '{:,.0f}'.format(v.objetivo).replace(',','.') }}</div>
{% else %}
<div class="text-muted small">Sin objetivo asignado</div>
{% endif %}
</div>
</div>
{% endfor %}
</div>
{% endif %}
</div>
</div>
{% endif %}

<!-- GRAFICOS MENSUALES -->
<div class="row g-3 mb-4">
<div class="col-md-7">
<div class="card"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0">Ventas de los ultimos 6 meses</h6>
<span class="badge-soft-primary">$ total por mes</span>
</div>
<canvas id="chart-6meses" height="110"></canvas>
</div></div>
</div>
<div class="col-md-5">
<div class="card"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0">Ventas dia por dia · {{ mes_actual_label }}</h6>
</div>
<canvas id="chart-diario" height="150"></canvas>
</div></div>
</div>
</div>

<!-- TOP PRODUCTOS Y PROVINCIAS -->
<div class="row g-3 mb-4">
<div class="col-md-6">
<div class="card"><div class="card-body">
<h6 class="mb-3">Top 5 productos del mes</h6>
{% if top_prods %}
<canvas id="chart-productos" height="180"></canvas>
{% else %}
<p class="text-muted small mb-0">Sin ventas cobradas este mes aun.</p>
{% endif %}
</div></div>
</div>
<div class="col-md-6">
<div class="card"><div class="card-body">
<h6 class="mb-3">Top 5 provincias por facturacion</h6>
{% if top_provs %}
<canvas id="chart-provincias" height="180"></canvas>
{% else %}
<p class="text-muted small mb-0">Sin datos de provincias aun.</p>
{% endif %}
</div></div>
</div>
</div>

<!-- ALERTAS ADMIN Y ULTIMOS CLIENTES -->
{% if current_user.es_admin %}
<div class="row g-3">
<div class="col-md-6">
<div class="card"><div class="card-body">
<h6 class="mb-3">Alertas</h6>
<a href="{{ url_for('ventas_lista', estado='pendiente_pago') }}" class="d-flex justify-content-between align-items-center py-2 border-bottom text-decoration-none text-dark">
<span class="small"><i class="bi bi-exclamation-circle text-warning"></i> Ordenes pendientes de pago</span>
<strong>{{ pendientes }}</strong>
</a>
<a href="{{ url_for('ventas_lista') }}" class="d-flex justify-content-between align-items-center py-2 border-bottom text-decoration-none text-dark">
<span class="small"><i class="bi bi-file-earmark-x text-secondary"></i> Pendientes de facturar</span>
<strong>{{ ordenes_pendientes_facturar }}</strong>
</a>
<a href="{{ url_for('productos_lista') }}" class="d-flex justify-content-between align-items-center py-2 border-bottom text-decoration-none text-dark">
<span class="small"><i class="bi bi-exclamation-triangle text-danger"></i> Productos con bajo stock</span>
<strong>{{ bajo_stock }}</strong>
</a>
<a href="{{ url_for('clientes_lista') }}" class="d-flex justify-content-between align-items-center py-2 text-decoration-none text-dark">
<span class="small"><i class="bi bi-people text-primary"></i> Clientes activos</span>
<strong>{{ total_clientes }}</strong>
</a>
</div></div>
</div>
<div class="col-md-6">
<div class="card"><div class="card-body">
<h6 class="mb-3">Ultimos clientes agregados</h6>
{% for c in ultimos_clientes %}
<div class="d-flex justify-content-between align-items-center py-2 border-bottom">
<div>
<div class="small fw-semibold">{{ c.nombre_completo }}</div>
<div class="text-muted" style="font-size:.75rem;">{{ c.provincia or '—' }}</div>
</div>
<span class="text-muted" style="font-size:.75rem;">{{ c.creado[:10] if c.creado else '' }}</span>
</div>
{% else %}
<p class="text-muted small mb-0">Sin clientes cargados.</p>
{% endfor %}
</div></div>
</div>
</div>
{% endif %}

<script>
// ====== Configuracion de colores ======
const primaryColor = '#3b5bdb';
const palette = ['#3b5bdb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

// ====== Datos de semanas ======
{% if semanas_actual is defined and semanas_actual %}
const semLabels = [{% for s in semanas_actual %}"S{{ s.semana }}"{% if not loop.last %},{% endif %}{% endfor %}];
const mesActualLabel = {{ sem_mes_actual|tojson }};
const mesAntLabel = {{ sem_mes_ant|tojson }};
const ventasAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.ventas) }}{% if not loop.last %},{% endif %}{% endfor %}];
const ventasAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.ventas) }}{% if not loop.last %},{% endif %}{% endfor %}];
const gastosAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.gastos) }}{% if not loop.last %},{% endif %}{% endfor %}];
const gastosAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.gastos) }}{% if not loop.last %},{% endif %}{% endfor %}];
const saldoAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.saldo) }}{% if not loop.last %},{% endif %}{% endfor %}];
const saldoAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.saldo) }}{% if not loop.last %},{% endif %}{% endfor %}];
{% else %}
const semLabels = [];
const mesActualLabel = '';
const mesAntLabel = '';
const ventasAct = []; const ventasAnt = [];
const gastosAct = []; const gastosAnt = [];
const saldoAct = []; const saldoAnt = [];
{% endif %}

// ====== Helper: dibujar grafico de lineas ======
function buildLineChart(canvasId, dataAct, dataAnt, colorAct, colorAnt) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  if (!dataAct.length && !dataAnt.length) return;

  const tieneDatos = dataAct.some(v => v !== 0) || dataAnt.some(v => v !== 0);
  if (!tieneDatos) {
    const ctx = el.getContext('2d');
    el.width = el.parentElement.clientWidth;
    el.height = el.parentElement.clientHeight;
    ctx.fillStyle = '#e5e7eb';
    ctx.font = '13px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Sin datos', el.width / 2, el.height / 2);
    return;
  }

  new Chart(el, {
    type: 'line',
    data: {
      labels: semLabels,
      datasets: [
        {
          label: mesActualLabel,
          data: dataAct,
          borderColor: colorAct,
          backgroundColor: colorAct + '22',
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: colorAct,
          pointBorderColor: '#fff',
          pointBorderWidth: 2
        },
        {
          label: mesAntLabel,
          data: dataAnt,
          borderColor: colorAnt,
          backgroundColor: colorAnt + '11',
          borderWidth: 2,
          borderDash: [5, 4],
          tension: 0.35,
          fill: false,
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBackgroundColor: colorAnt
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { boxWidth: 8, boxHeight: 8, padding: 6, font: { size: 10 }, color: '#6b7280', usePointStyle: true }
        },
        tooltip: {
          callbacks: {
            label: function(c) { return c.dataset.label + ': $' + Number(c.raw).toLocaleString('es-AR'); }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: '#f1f3f8' },
          ticks: {
            color: '#9ca3af',
            font: { size: 9 },
            maxTicksLimit: 4,
            callback: function(v) {
              const abs = Math.abs(v);
              if (abs >= 1000000) return '$' + (v/1000000).toFixed(1) + 'M';
              if (abs >= 1000) return '$' + (v/1000).toFixed(0) + 'k';
              return '$' + v;
            }
          }
        },
        x: { grid: { display: false }, ticks: { color: '#9ca3af', font: { size: 10 } } }
      }
    }
  });
}

buildLineChart('chart-kpi-ventas', ventasAct, ventasAnt, '#3b5bdb', '#a5b4fc');
buildLineChart('chart-kpi-gastos', gastosAct, gastosAnt, '#ef4444', '#fca5a5');
buildLineChart('chart-kpi-saldo', saldoAct, saldoAnt, '#10b981', '#6ee7b7');

// ====== Graficos mensuales existentes ======
const data6meses = {
  labels: [{% for m in ultimos6 %}'{{ m.label }}'{% if not loop.last %},{% endif %}{% endfor %}],
  values: [{% for m in ultimos6 %}{{ m.total }}{% if not loop.last %},{% endif %}{% endfor %}]
};
new Chart(document.getElementById('chart-6meses'), {
  type: 'bar',
  data: { labels: data6meses.labels, datasets: [{ data: data6meses.values, backgroundColor: primaryColor, borderRadius: 8, borderSkipped: false, maxBarThickness: 40 }] },
  options: { responsive: true, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => '$' + Number(c.raw).toLocaleString('es-AR') } } }, scales: { y: { beginAtZero: true, grid: { color: '#f1f3f8' }, ticks: { callback: (v) => '$' + (v/1000).toFixed(0) + 'k', color: '#9ca3af' } }, x: { grid: { display: false }, ticks: { color: '#6b7280' } } } }
});

const diarioLabels = [{% for d in por_dia %}{{ d.label }}{% if not loop.last %},{% endif %}{% endfor %}];
const diarioValues = [{% for d in por_dia %}{{ d.total }}{% if not loop.last %},{% endif %}{% endfor %}];
new Chart(document.getElementById('chart-diario'), {
  type: 'line',
  data: { labels: diarioLabels, datasets: [{ data: diarioValues, borderColor: primaryColor, backgroundColor: 'rgba(59,91,219,0.08)', borderWidth: 2, fill: true, tension: .35, pointRadius: 0, pointHoverRadius: 5 }] },
  options: { responsive: true, plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => 'Dia ' + c[0].label, label: (c) => '$' + Number(c.raw).toLocaleString('es-AR') } } }, scales: { y: { beginAtZero: true, grid: { color: '#f1f3f8' }, ticks: { callback: (v) => '$' + (v/1000).toFixed(0) + 'k', color: '#9ca3af' } }, x: { grid: { display: false }, ticks: { color: '#9ca3af', maxRotation: 0, autoSkip: true, maxTicksLimit: 10 } } } }
});

{% if top_prods %}
new Chart(document.getElementById('chart-productos'), {
  type: 'bar',
  data: { labels: [{% for p in top_prods %}{{ p.nombre|tojson }}{% if not loop.last %},{% endif %}{% endfor %}], datasets: [{ data: [{% for p in top_prods %}{{ p.cantidad }}{% if not loop.last %},{% endif %}{% endfor %}], backgroundColor: palette.slice(0, {{ top_prods|length }}), borderRadius: 8, borderSkipped: false }] },
  options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => c.raw + ' unidades' } } }, scales: { x: { beginAtZero: true, grid: { color: '#f1f3f8' }, ticks: { color: '#9ca3af' } }, y: { grid: { display: false }, ticks: { color: '#4b5563' } } } }
});
{% endif %}

{% if top_provs %}
new Chart(document.getElementById('chart-provincias'), {
  type: 'doughnut',
  data: { labels: [{% for p in top_provs %}{{ p.provincia|tojson }}{% if not loop.last %},{% endif %}{% endfor %}], datasets: [{ data: [{% for p in top_provs %}{{ p.total }}{% if not loop.last %},{% endif %}{% endfor %}], backgroundColor: palette.slice(0, {{ top_provs|length }}), borderWidth: 0, spacing: 2 }] },
  options: { responsive: true, cutout: '62%', plugins: { legend: { position: 'right', labels: { boxWidth: 10, padding: 12, font: { size: 12 }, color: '#4b5563' } }, tooltip: { callbacks: { label: (c) => c.label + ': $' + Number(c.raw).toLocaleString('es-AR') } } } }
});
{% endif %}
</script>
{% endblock %}
'''


def main():
    print("=== Upgrade 69: Dashboard completo con graficos semanales ===")
    escribir('templates/dashboard.html', DASHBOARD_HTML)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()