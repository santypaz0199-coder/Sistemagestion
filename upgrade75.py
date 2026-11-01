# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade75] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Buscar la función buildLineChart y reemplazarla por buildBarChart
    patron_funcion = re.compile(
        r'function buildLineChart\(canvasId, dataAct, dataAnt, colorAct, colorAnt\) \{.*?(?=buildLineChart\(\'chart-kpi-ventas\')',
        re.DOTALL
    )

    nueva_funcion = '''function buildBarChart(canvasId, dataAct, dataAnt, colorAct, colorAnt) {
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
          maxBarThickness: 14
        },
        {
          label: mesAntLabel,
          data: dataAnt,
          backgroundColor: colorAnt,
          borderRadius: 4,
          borderSkipped: false,
          maxBarThickness: 14
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

'''
    contenido, n = patron_funcion.subn(nueva_funcion, contenido)
    if n > 0:
        print("[upgrade75] Función de gráfico reemplazada por barras")
    else:
        print("[upgrade75] ADVERTENCIA: no se encontró buildLineChart")

    # 2. Cambiar las llamadas a la función
    contenido = contenido.replace('buildLineChart(', 'buildBarChart(')

    # 3. Ajustar los colores de las barras (más sólidos, sin transparencia)
    contenido = contenido.replace("'#a5b4fc'", "'#c7d2fe'")  # gris azulado suave para mes anterior
    contenido = contenido.replace("'#fca5a5'", "'#fecaca'")  # rojo suave
    contenido = contenido.replace("'#6ee7b7'", "'#a7f3d0'")  # verde suave

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade75] Colores de barras ajustados")


def main():
    print("=== Upgrade 75: Gráficos semanales como barras fijas (4 semanas) ===")
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()