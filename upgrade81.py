# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade81] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Reducir la altura de los contenedores de los gráficos
    contenido = contenido.replace('<div style="height:130px; position:relative;"><canvas id="chart-kpi-', '<div style="height:110px; position:relative;"><canvas id="chart-kpi-')

    # 2. Reemplazar la función buildBarChart para que tenga el estilo de la foto (Eje Y visible, sin datalabels locos)
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
            maxBarThickness: 24
          },
          {
            label: mesAntLabel,
            data: dataAnt,
            backgroundColor: colorAnt,
            borderRadius: 4,
            borderSkipped: false,
            maxBarThickness: 24
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 10 } },
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
          y: { 
            beginAtZero: true, 
            display: true,
            grid: { color: '#f1f3f8', drawBorder: false },
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
          x: { 
            grid: { display: false }, 
            ticks: { color: '#6b7280', font: { size: 10, weight: '500' } } 
          }
        }
      }
    };

    // Mantenemos las etiquetas (datalabels) porque ayudan a ver el monto exacto, pero chiquitas
    if (typeof ChartDataLabels !== 'undefined') {
      config.plugins = [ChartDataLabels];
      config.options.plugins.datalabels = {
        display: true,
        anchor: 'end',
        align: 'top',
        offset: 2,
        color: '#6b7280',
        font: { size: 8, weight: '600' },
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
    if n > 0:
        print("[upgrade81] Función buildBarChart ajustada para tener Eje Y visible y barras más grandes.")
    else:
        print("[upgrade81] ADVERTENCIA: no se encontró la función buildBarChart.")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade81] dashboard.html actualizado.")


def main():
    print("=== Upgrade 81: Ajuste visual de gráficos ===")
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()