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
    print(f"[upgrade67] escrito: {relpath}")


APP67_PY = r'''
from datetime import date
from calendar import monthrange
from app66 import app
from flask import request
from flask_login import current_user
from database import get_db

MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def _semanas_del_mes(anio, mes):
    """Divide un mes en semanas (lunes a domingo)."""
    from datetime import timedelta
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, monthrange(anio, mes)[1])
    semanas = []
    inicio = primer_dia
    while inicio <= ultimo_dia:
        dias_hasta_domingo = 6 - inicio.weekday()
        fin = inicio + timedelta(days=dias_hasta_domingo)
        if fin > ultimo_dia:
            fin = ultimo_dia
        semanas.append((inicio, fin))
        inicio = fin + timedelta(days=1)
    return semanas


def _datos_semanales(conn, anio, mes):
    """Devuelve ventas, gastos y saldo por semana del mes dado."""
    semanas = _semanas_del_mes(anio, mes)
    resultado = []
    for i, (ini, fin) in enumerate(semanas, start=1):
        ini_s, fin_s = ini.isoformat(), fin.isoformat()

        ventas = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM ordenes_venta "
            "WHERE date(fecha) BETWEEN ? AND ? "
            "AND estado IN ('pagado_sin_enviar','pagado_enviado')",
            (ini_s, fin_s)).fetchone()[0] or 0

        gastos = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM gastos "
            "WHERE date(fecha) BETWEEN ? AND ?",
            (ini_s, fin_s)).fetchone()[0] or 0

        compras = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM compras "
            "WHERE date(fecha) BETWEEN ? AND ?",
            (ini_s, fin_s)).fetchone()[0] or 0

        egresos = float(gastos) + float(compras)
        ventas_f = float(ventas)
        resultado.append({
            'semana': i,
            'rango': f"{ini.strftime('%d/%m')} - {fin.strftime('%d/%m')}",
            'ventas': ventas_f,
            'gastos': egresos,
            'saldo': ventas_f - egresos,
        })
    return resultado


def _pad_semanas(semanas, total):
    """Rellena con semanas vacias hasta llegar a 'total'."""
    while len(semanas) < total:
        semanas.append({
            'semana': len(semanas) + 1,
            'rango': '',
            'ventas': 0,
            'gastos': 0,
            'saldo': 0,
        })
    return semanas


@app.context_processor
def _ctx_semanas_dashboard():
    if request.endpoint != 'dashboard':
        return {}
    if not current_user.is_authenticated or not current_user.es_admin:
        return {}

    conn = get_db()
    try:
        hoy = date.today()
        if hoy.month == 1:
            ant_anio, ant_mes = hoy.year - 1, 12
        else:
            ant_anio, ant_mes = hoy.year, hoy.month - 1

        sem_act = _datos_semanales(conn, hoy.year, hoy.month)
        sem_ant = _datos_semanales(conn, ant_anio, ant_mes)

        # Padding para que ambas listas tengan la misma longitud
        max_len = max(len(sem_act), len(sem_ant))
        sem_act = _pad_semanas(sem_act, max_len)
        sem_ant = _pad_semanas(sem_ant, max_len)

        return {
            'semanas_actual': sem_act,
            'semanas_ant': sem_ant,
            'sem_mes_actual': MESES_ES[hoy.month],
            'sem_mes_ant': MESES_ES[ant_mes],
        }
    finally:
        conn.close()
'''


BLOQUE_HTML = '''<!-- Comparativa semanal (U67) -->
{% if semanas_actual is defined and semanas_actual %}
<div class="row g-3 mb-4">
<div class="col-md-4">
<div class="card"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-2">
<h6 class="mb-0"><i class="bi bi-bar-chart-line text-primary"></i> Ventas por semana</h6>
</div>
<div class="small text-muted mb-2">Comparativa {{ sem_mes_actual }} vs {{ sem_mes_ant }}</div>
<canvas id="chart-sem-ventas" height="200"></canvas>
</div></div>
</div>
<div class="col-md-4">
<div class="card"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-2">
<h6 class="mb-0"><i class="bi bi-bar-chart-line text-danger"></i> Gastos por semana</h6>
</div>
<div class="small text-muted mb-2">Gastos + compras · {{ sem_mes_actual }} vs {{ sem_mes_ant }}</div>
<canvas id="chart-sem-gastos" height="200"></canvas>
</div></div>
</div>
<div class="col-md-4">
<div class="card"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-2">
<h6 class="mb-0"><i class="bi bi-bar-chart-line text-success"></i> Saldo por semana</h6>
</div>
<div class="small text-muted mb-2">Ventas - Egresos · {{ sem_mes_actual }} vs {{ sem_mes_ant }}</div>
<canvas id="chart-sem-saldo" height="200"></canvas>
</div></div>
</div>
</div>
{% endif %}

'''


BLOQUE_JS = '''
// ===== Comparativa semanal (U67) =====
{% if semanas_actual is defined and semanas_actual %}
(function() {
  const labels = [{% for s in semanas_actual %}"Sem {{ s.semana }}"{% if not loop.last %},{% endif %}{% endfor %}];
  const mesActualLabel = '{{ sem_mes_actual }}';
  const mesAntLabel = '{{ sem_mes_ant }}';

  const ventasAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.ventas) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const ventasAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.ventas) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const gastosAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.gastos) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const gastosAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.gastos) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const saldoAct = [{% for s in semanas_actual %}{{ '%.2f'|format(s.saldo) }}{% if not loop.last %},{% endif %}{% endfor %}];
  const saldoAnt = [{% for s in semanas_ant %}{{ '%.2f'|format(s.saldo) }}{% if not loop.last %},{% endif %}{% endfor %}];

  function buildWeekly(canvasId, dataAct, dataAnt, colorAct, colorAnt) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    new Chart(el, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: mesActualLabel,
            data: dataAct,
            backgroundColor: colorAct,
            borderRadius: 6,
            borderSkipped: false,
            maxBarThickness: 22
          },
          {
            label: mesAntLabel,
            data: dataAnt,
            backgroundColor: colorAnt,
            borderRadius: 6,
            borderSkipped: false,
            maxBarThickness: 22
          }
        ]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 10, padding: 8, font: { size: 11 } }
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
            grid: { color: '#f1f3f8' },
            ticks: {
              color: '#9ca3af',
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
            ticks: { color: '#6b7280' }
          }
        }
      }
    });
  }

  buildWeekly('chart-sem-ventas', ventasAct, ventasAnt, '#3b5bdb', '#cbd5e1');
  buildWeekly('chart-sem-gastos', gastosAct, gastosAnt, '#ef4444', '#fca5a5');
  buildWeekly('chart-sem-saldo', saldoAct, saldoAnt, '#10b981', '#86efac');
})();
{% endif %}
'''


def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade67] no existe dashboard.html"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'chart-sem-ventas' in contenido:
        print("[upgrade67] dashboard ya tiene comparativa semanal")
        return

    # 1. Insertar el bloque HTML antes del ultimo {% if current_user.es_admin %} (Alertas)
    pos_html = contenido.rfind('{% if current_user.es_admin %}')
    if pos_html > 0:
        contenido = contenido[:pos_html] + BLOQUE_HTML + contenido[pos_html:]
        print("[upgrade67] bloque HTML insertado antes de Alertas")
    else:
        # Fallback: insertar antes del ultimo </div> del content block
        pos_fb = contenido.rfind('{% endblock %}')
        if pos_fb > 0:
            contenido = contenido[:pos_fb] + BLOQUE_HTML + contenido[pos_fb:]
            print("[upgrade67] bloque HTML insertado antes de endblock")
        else:
            print("[upgrade67] ADVERTENCIA: no se encontro donde insertar HTML")
            return

    # 2. Insertar el bloque JS antes del ultimo </script>
    pos_js = contenido.rfind('</script>')
    if pos_js > 0:
        contenido = contenido[:pos_js] + BLOQUE_JS + '\n' + contenido[pos_js:]
        print("[upgrade67] bloque JS insertado antes de </script>")
    else:
        print("[upgrade67] ADVERTENCIA: no se encontro </script>")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade67] dashboard.html actualizado")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 67: Comparativa semanal en dashboard ===")
    escribir('app67.py', APP67_PY)
    patch_dashboard()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()