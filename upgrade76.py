# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app67():
    """Actualiza el backend para que los rangos de fecha se vean como '30 a 04'."""
    ruta = os.path.join(BASE, 'app67.py')
    if not os.path.exists(ruta):
        print("[upgrade76] no existe app67.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Cambiar el formato del rango
    viejo = "            'rango': f\"{ini.strftime('%d/%m')} - {fin.strftime('%d/%m')}\","
    nuevo = "            'rango': f\"{ini.strftime('%d')} a {fin.strftime('%d/%m')}\","

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade76] Formato de fecha actualizado a 'D a DD/MM'")


def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade76] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Agregar el CDN del plugin de etiquetas antes del </head> o en el bloque de scripts
    if 'chartjs-plugin-datalabels' not in contenido:
        # Insertar en base.html o directamente aca en el script
        contenido = contenido.replace(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>',
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>'
        )
        # Nota: Chart.js ya esta importado en base.html, lo que hacemos es asegurarnos de que el plugin este. 
        # Si la linea no coincide, lo agregamos al principio del script interno.
        if 'chartjs-plugin-datalabels' not in contenido:
            contenido = contenido.replace('<script>\n// ====== Configuracion', '<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>\n<script>\n// ====== Configuracion')

    # 2. Extraer los labels del eje X de los datos de semanas
    # En lugar de "S1", usaremos el campo 'rango' (ej: "30 a 04")
    viejo_labels = 'const semLabels = [{% for s in semanas_actual %}"S{{ s.semana }}"{% if not loop.last %},{% endif %}{% endfor %}];'
    nuevo_labels = 'const semLabels = [{% for s in semanas_actual %}"{{ s.rango }}"{% if not loop.last %},{% endif %}{% endfor %}];'

    if viejo_labels in contenido:
        contenido = contenido.replace(viejo_labels, nuevo_labels, 1)
        print("[upgrade76] Labels del eje X cambiados a fechas")

    # 3. Reescribir la funcion buildBarChart para el estilo de la imagen
    patron_funcion = re.compile(
        r'function buildBarChart\(canvasId, dataAct, dataAnt, colorAct, colorAnt\) \{.*?\n\}',
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
          maxBarThickness: 20
        },
        {
          label: mesAntLabel,
          data: dataAnt,
          backgroundColor: colorAnt,
          borderRadius: 4,
          borderSkipped: false,
          maxBarThickness: 20
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: { top: 20 } // Espacio para las etiquetas de arriba
      },
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
        },
        datalabels: {
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
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          display: false // Ocultar eje Y para que quede limpio como la foto
        },
        x: {
          grid: { display: false },
          ticks: { color: '#6b7280', font: { size: 10, weight: '500' } }
        }
      }
    },
    plugins: [ChartDataLabels] // Activar el plugin
  });
}'''

    contenido, n = patron_funcion.subn(nueva_funcion, contenido)
    if n > 0:
        print("[upgrade76] Función buildBarChart reescrita (estilo limpio con labels arriba)")
    else:
        print("[upgrade76] ADVERTENCIA: no se encontró la función buildBarChart")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade76] dashboard.html actualizado")


def main():
    print("=== Upgrade 76: Estilo de gráfico como la imagen (montos arriba, fechas abajo) ===")
    patch_app67()
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()