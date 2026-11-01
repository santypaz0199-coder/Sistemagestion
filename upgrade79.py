# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_base():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade79] no existe base.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Asegurar que estén los dos scripts (Chart.js y Datalabels)
    if 'chart.js' not in contenido:
        # Por si acaso no está
        buscar_head = '</head>'
        contenido = contenido.replace(buscar_head, '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n</head>', 1)
    
    if 'chartjs-plugin-datalabels' not in contenido:
        buscar_chart = 'chart.umd.min.js"></script>'
        if buscar_chart in contenido:
            nuevo_script = buscar_chart + '\n<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>'
            contenido = contenido.replace(buscar_chart, nuevo_script, 1)
            print("[upgrade79] Plugin datalabels agregado correctamente")

    # 2. Restaurar el script de scroll del sidebar (si no está)
    if 'sidebar_scroll_preserve' not in contenido:
        script_scroll = '''
<script>
(function() {
  const KEY = 'fz_sidebar_scroll';
  function init() {
    const nav = document.querySelector('.sidebar-nav');
    if (!nav) return;
    const saved = sessionStorage.getItem(KEY);
    if (saved !== null) {
      nav.scrollTop = parseInt(saved) || 0;
    }
    let timeout = null;
    nav.addEventListener('scroll', function() {
      clearTimeout(timeout);
      timeout = setTimeout(function() {
        sessionStorage.setItem(KEY, nav.scrollTop.toString());
      }, 100);
    });
    nav.querySelectorAll('a').forEach(function(link) {
      link.addEventListener('click', function() {
        sessionStorage.setItem(KEY, nav.scrollTop.toString());
      });
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>
</body>'''
        contenido = contenido.replace('</body>', script_scroll, 1)
        print("[upgrade79] Script de scroll restaurado")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade79] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Eliminar cualquier bloque viejo de gráficos semanales (por si quedaron restos)
    patron_viejo = re.compile(r'<!-- Graficos KPI semanales.*?</div>\s*</div>\s*</div>\s*</div>', re.DOTALL)
    contenido, _ = patron_viejo.subn('', contenido)
    
    patron_viejo2 = re.compile(r'<!-- Graficos KPI semanales \(U68\) -->.*?</div>\s*</div>\s*</div>', re.DOTALL)
    contenido, _ = patron_viejo2.subn('', contenido)

    # 2. Insertar el bloque HTML limpio justo después de las alertas
    bloque_html = '''<!-- Graficos KPI semanales -->
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
<div style="height:130px; position:relative;"><canvas id="chart-kpi-ventas"></canvas></div>
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
<div style="height:130px; position:relative;"><canvas id="chart-kpi-gastos"></canvas></div>
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
<div style="height:130px; position:relative;"><canvas id="chart-kpi-saldo"></canvas></div>
</div>
</div>
</div>
</div>
'''
    buscar_insert = '<!-- ACCESOS DIRECTOS -->'
    if buscar_insert not in contenido:
        buscar_insert = '<!-- Accesos directos -->'
    
    if buscar_insert in contenido:
        contenido = contenido.replace(buscar_insert, bloque_html + '\n' + buscar_insert, 1)
        print("[upgrade79] Bloque HTML de gráficos insertado")
    else:
        # Insertar antes del primer script
        pos_script = contenido.find('<script>')
        if pos_script > 0:
            contenido = contenido[:pos_script] + bloque_html + contenido[pos_script:]
            print("[upgrade79] Bloque HTML de gráficos insertado (fallback)")

    # 3. Reescribir la función JS para que use los datos correctos
    patron_funcion = re.compile(
        r'function buildBarChart\(canvasId, dataAct, dataAnt, colorAct, colorAnt\) \{.*?\n\}',
        re.DOTALL
    )

    nueva_funcion = '''function buildBarChart(canvasId, dataAct, dataAnt, colorAct, colorAnt) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  
  try {
    if (typeof Chart === 'undefined') return;

    const tieneDatos = dataAct.some(v => v !== 0) || dataAnt.some(v => v !== 0);
    if (!tieneDatos) {
      const ctx = el.getContext('2d');
      el.width = el.parentElement.clientWidth;
      el.height = el.parentElement.clientHeight;
      ctx.fillStyle = '#e5e7eb';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Sin datos aún', el.width / 2, el.height / 2);
      return;
    }

    const config = {
      type: 'bar',
      data: {
        labels: semLabels,
        datasets: [
          {
            label: mesActualLabel,
            data: dataAct,
            backgroundColor: colorAct,
            borderRadius: 4,
            borderSkipped: false,
            maxBarThickness: 16
          },
          {
            label: mesAntLabel,
            data: dataAnt,
            backgroundColor: colorAnt,
            borderRadius: 4,
            borderSkipped: false,
            maxBarThickness: 16
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 20 } },
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: { boxWidth: 8, boxHeight: 8, padding: 10, font: { size: 10 }, color: '#6b7280', usePointStyle: true }
          },
          tooltip: {
            callbacks: {
              label: function(c) { return c.dataset.label + ': $' + Number(c.raw).toLocaleString('es-AR'); }
            }
          }
        },
        scales: {
          y: { beginAtZero: true, display: false },
          x: { grid: { display: false }, ticks: { color: '#6b7280', font: { size: 10, weight: '500' } } }
        }
      }
    };

    if (typeof ChartDataLabels !== 'undefined') {
      config.plugins = [ChartDataLabels];
      config.options.plugins.datalabels = {
        display: true,
        anchor: 'end',
        align: 'top',
        offset: 4,
        color: '#4b5563',
        font: { size: 9, weight: '600' },
        formatter: function(value) {
          if (!value || value === 0) return '';
          if (value >= 1000000) return '$' + (value/1000000).toFixed(1) + 'M';
          if (value >= 1000) return '$' + (value/1000).toFixed(0) + 'k';
          return '$' + value;
        }
      };
    }

    new Chart(el, config);
  } catch(err) {
    console.error("Error al dibujar gráfico", canvasId, err);
  }
}'''

    contenido, n = patron_funcion.subn(nueva_funcion, contenido)
    if n == 0:
        print("[upgrade79] ADVERTENCIA: no se encontró la función buildBarChart para reemplazar.")
    
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade79] dashboard.html actualizado.")


def main():
    print("=== Upgrade 79: Fix definitivo de gráficos y sidebar (Limpieza profunda) ===")
    patch_base()
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()