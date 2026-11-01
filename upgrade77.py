# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade77] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Asegurarnos de que el bloque HTML de los graficos este en el dashboard
    if 'chart-kpi-ventas' not in contenido:
        print("[upgrade77] El bloque de graficos no estaba. Reinsertando...")
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
        # Insertar justo despues de las alertas (antes de <!-- Accesos directos -->)
        buscar = '<!-- ACCESOS DIRECTOS -->'
        if buscar not in contenido:
            buscar = '<!-- Accesos directos -->'
        
        if buscar in contenido:
            contenido = contenido.replace(buscar, bloque_html + '\n' + buscar, 1)
            print("[upgrade77] Bloque HTML insertado antes de Accesos Directos.")
        else:
            # Si no encuentra accesos directos, lo pone antes del primer script
            buscar_script = '<script>'
            pos = contenido.find(buscar_script)
            if pos > 0:
                contenido = contenido[:pos] + bloque_html + contenido[pos:]
                print("[upgrade77] Bloque HTML insertado antes del script.")
            else:
                print("[upgrade77] No se encontró dónde insertar el bloque HTML.")

    # 2. Reescribir la función JS para hacerla a prueba de fallos
    patron_funcion = re.compile(
        r'function buildBarChart\(canvasId, dataAct, dataAnt, colorAct, colorAnt\) \{.*?\n\}',
        re.DOTALL
    )

    nueva_funcion = '''function buildBarChart(canvasId, dataAct, dataAnt, colorAct, colorAnt) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  
  try {
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

    const isPluginAvailable = typeof ChartDataLabels !== 'undefined';

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

    // Si el plugin de etiquetas está disponible, lo configuramos
    if (isPluginAvailable) {
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
    const ctx = el.getContext('2d');
    el.width = el.parentElement.clientWidth;
    el.height = el.parentElement.clientHeight;
    ctx.fillStyle = '#ef4444';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Error al cargar', el.width / 2, el.height / 2);
  }
}'''

    contenido, n = patron_funcion.subn(nueva_funcion, contenido)
    if n > 0:
        print("[upgrade77] Función JS reescrita a prueba de fallos.")
    else:
        print("[upgrade77] ADVERTENCIA: no se encontró la función buildBarChart.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade77] dashboard.html guardado.")


def main():
    print("=== Upgrade 77: Forzar aparición de gráficos y hacerlos a prueba de fallos ===")
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()