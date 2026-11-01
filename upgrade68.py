# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade68] escrito: {relpath}")


# ===== Nuevo bloque: 3 gráficos de línea (reemplaza los 3 KPIs) =====
NUEVO_BLOQUE = '''<!-- Graficos KPI semanales (U68) -->
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
<canvas id="chart-kpi-ventas" height="110"></canvas>
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
<canvas id="chart-kpi-gastos" height="110"></canvas>
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
<canvas id="chart-kpi-saldo" height="110"></canvas>
</div>
</div>
</div>
</div>

'''


NUEVO_JS = '''
// ===== Graficos KPI semanales (U68) =====
{% if semanas_actual is defined and semanas_actual %}
(function() {
  const semLabels = [{% for s in semanas_actual %}"S{{ s.semana }}"{% if not loop.last %},{% endif %}{% endfor %}];
  const mesActualLabel = '{{ sem_mes_actual }}';
  const mesAntLabel = '{{ sem_mes_ant }}';

  const ventasAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.ventas) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const ventasAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.ventas) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const gastosAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.gastos) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const gastosAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.gastos) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const saldoAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.saldo) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const saldoAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.saldo) }}{% if not loop.last %},{% endif %}{% endfor %}];

  function hayDatos(arr1, arr2) {
    return arr1.some(v => v !== 0) || arr2.some(v => v !== 0);
  }

  function buildLineChart(canvasId, dataAct, dataAnt, colorAct, colorAnt) {
    const el = document.getElementById(canvasId);
    if (!el) return;

    // Si no hay datos, mostrar mensaje
    if (!hayDatos(dataAct, dataAnt)) {
      const ctx = el.getContext('2d');
      el.height = 110;
      ctx.fillStyle = '#e5e7eb';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Sin datos', el.width / 2, 60);
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
            backgroundColor: colorAnt + '15',
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
            labels: {
              boxWidth: 8,
              boxHeight: 8,
              padding: 6,
              font: { size: 10 },
              color: '#6b7280',
              usePointStyle: true
            }
          },
          tooltip: {
            callbacks: {
              label: function(c) {
                return c.dataset.label + ': $' + Number(c.raw).toLocaleString('es-AR');
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
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
            ticks: { color: '#9ca3af', font: { size: 10 } }
          }
        }
      }
    });
  }

  buildLineChart('chart-kpi-ventas', ventasAct, ventasAnt, '#3b5bdb', '#c7d2fe');
  buildLineChart('chart-kpi-gastos', gastosAct, gastosAnt, '#ef4444', '#fecaca');
  buildLineChart('chart-kpi-saldo', saldoAct, saldoAnt, '#10b981', '#a7f3d0');
})();
{% endif %}
'''


def quitar_bloque_u67(contenido):
    """Elimina el bloque HTML y JS que se agrego en U67."""

    # 1. Quitar el bloque HTML
    inicio_html = contenido.find('<!-- Comparativa semanal (U67) -->')
    if inicio_html > 0:
        # Buscar el cierre del row (3 col-md-4 con card cada uno)
        # El bloque termina con `</div>\n</div>\n</div>\n</div>` antes del `{% if current_user.es_admin %}`
        # Busco el siguiente marcador que se que venia despues: {% if current_user.es_admin %}
        siguiente = contenido.find('{% if current_user.es_admin %}', inicio_html)
        if siguiente > 0:
            contenido = contenido[:inicio_html] + contenido[siguiente:]
            print("[upgrade68] bloque HTML de U67 eliminado")
        else:
            # Fallback: buscar el {% endblock %}
            fin_alt = contenido.find('{% endblock %}', inicio_html)
            if fin_alt > 0:
                contenido = contenido[:inicio_html] + contenido[fin_alt:]
                print("[upgrade68] bloque HTML de U67 eliminado (fallback)")
    else:
        print("[upgrade68] no se encontro el bloque HTML de U67 (ya eliminado?)")

    # 2. Quitar el bloque JS
    inicio_js = contenido.find('// ===== Comparativa semanal (U67) =====')
    if inicio_js > 0:
        # El bloque termina con el {% endif %}
        fin_js = contenido.find('{% endif %}', inicio_js)
        if fin_js > 0:
            contenido = contenido[:inicio_js] + contenido[fin_js + len('{% endif %}'):]
            print("[upgrade68] bloque JS de U67 eliminado")
    else:
        print("[upgrade68] no se encontro el bloque JS de U67 (ya eliminado?)")

    return contenido


def reemplazar_kpis(contenido):
    """Reemplaza los 3 KPIs grandes por los 3 graficos de linea."""

    # Intentar primero buscar el marcador <!-- KPIs grandes -->
    inicio = contenido.find('<!-- KPIs grandes -->')
    if inicio == -1:
        # Fallback: buscar el row que contiene "Ventas de {{ mes_actual_label }}"
        patron_inicio = re.search(
            r'<div class="row g-3 mb-4">\s*<div class="col-md-4">\s*<div class="card-kpi"[^>]*>\s*<div class="kpi-icon kpi-icon-primary"><i class="bi bi-currency-dollar"></i></div>\s*<div class="kpi-label">Ventas de',
            contenido
        )
        if not patron_inicio:
            print("[upgrade68] ADVERTENCIA: no se encontro el bloque de KPIs")
            return contenido
        inicio = patron_inicio.start()

    # Fin: antes de {% if objetivos_dashboard
    fin = contenido.find('{% if objetivos_dashboard', inicio)
    if fin == -1:
        # Fallback: antes de <!-- Accesos directos
        fin = contenido.find('<!-- Accesos directos', inicio)
    if fin == -1:
        print("[upgrade68] ADVERTENCIA: no se encontro el cierre de KPIs")
        return contenido

    contenido = contenido[:inicio] + NUEVO_BLOQUE + contenido[fin:]
    print("[upgrade68] KPIs reemplazados por graficos de linea")
    return contenido


def agregar_js(contenido):
    """Agrega el JS de los nuevos graficos antes del </script> final."""

    if 'chart-kpi-ventas' in contenido and 'buildLineChart' in contenido:
        print("[upgrade68] JS de graficos ya estaba")
        return contenido

    # Buscar el ultimo </script>
    pos = contenido.rfind('</script>')
    if pos == -1:
        print("[upgrade68] ADVERTENCIA: no se encontro </script>")
        return contenido

    contenido = contenido[:pos] + NUEVO_JS + '\n' + contenido[pos:]
    print("[upgrade68] JS de graficos agregado")
    return contenido


def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade68] no existe dashboard.html"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    contenido = quitar_bloque_u67(contenido)
    contenido = reemplazar_kpis(contenido)
    contenido = agregar_js(contenido)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade68] dashboard.html actualizado")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 68: KPIs con graficos de linea semanales ===")
    patch_dashboard()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")
    print("Despues Ctrl+F5 en el dashboard para ver los cambios")


if __name__ == '__main__':
    main()