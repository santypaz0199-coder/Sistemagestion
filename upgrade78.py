# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_base():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade78] no existe base.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Agregar el CDN de chartjs-plugin-datalabels si no está
    if 'chartjs-plugin-datalabels' not in contenido:
        buscar = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>'
        if buscar in contenido:
            nuevo = buscar + '\n<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>'
            contenido = contenido.replace(buscar, nuevo, 1)
            print("[upgrade78] Plugin de datalabels agregado a base.html")
        else:
            print("[upgrade78] ADVERTENCIA: no se encontró el CDN de Chart.js")

    # 2. Restaurar el guardado de scroll del sidebar
    if 'sidebar_scroll_preserve' not in contenido:
        script_scroll = '''
<script>
/* sidebar_scroll_preserve - mantiene la posicion del scroll del sidebar entre navegaciones */
(function() {
  const KEY = 'fz_sidebar_scroll';
  function init() {
    const nav = document.querySelector('.sidebar-nav');
    if (!nav) return;

    // Restaurar posicion guardada
    const saved = sessionStorage.getItem(KEY);
    if (saved !== null) {
      nav.scrollTop = parseInt(saved) || 0;
    }

    // Guardar al scrollear (con debounce)
    let timeout = null;
    nav.addEventListener('scroll', function() {
      clearTimeout(timeout);
      timeout = setTimeout(function() {
        sessionStorage.setItem(KEY, nav.scrollTop.toString());
      }, 100);
    });

    // Guardar al clickear un link
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
        print("[upgrade78] Script de scroll del sidebar restaurado")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade78] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Buscar y reemplazar la funcion buildBarChart para que sea ultra-segura
    patron_funcion = re.compile(
        r'function buildBarChart\(canvasId, dataAct, dataAnt, colorAct, colorAnt\) \{.*?\n\}',
        re.DOTALL
    )

    nueva_funcion = '''function buildBarChart(canvasId, dataAct, dataAnt, colorAct, colorAnt) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  
  try {
    if (typeof Chart === 'undefined') {
      console.error("Chart.js no está cargado");
      return;
    }

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

    // Si el plugin de datalabels está disponible en window, lo usamos
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
    // Mostrar un cartel de error en el canvas
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
        print("[upgrade78] Función buildBarChart actualizada a prueba de fallos")
    else:
        print("[upgrade78] ADVERTENCIA: no se encontró la función buildBarChart")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    print("=== Upgrade 78: Fix definitivo de gráficos y sidebar ===")
    patch_base()
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()