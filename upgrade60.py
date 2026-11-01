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
    print(f"[upgrade60] escrito: {relpath}")


def patch_base_scroll():
    """Agrega JS que preserva el scroll del sidebar entre navegaciones."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade60] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'sidebar_scroll_preserve' in contenido:
        print("[upgrade60] fix de scroll ya estaba")
        return

    # Insertar el script antes de </body>
    script = '''
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

    // Guardar al clickear un link (antes de que navegue)
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

    contenido = contenido.replace('</body>', script, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade60] JS de preservacion de scroll agregado a base.html")


def patch_clientes_stats():
    """Cambia las stats cards de Clientes por pills chiquitas."""
    ruta = os.path.join(BASE, 'templates', 'clientes', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade60] no existe clientes/lista.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'stats-compact-ventas' in contenido:
        print("[upgrade60] clientes ya tiene stats compactas")
        return

    # Buscar el bloque de stats actual
    buscar = '''<!-- Stats rapidos -->
<div class="row row-cols-2 row-cols-md-5 g-2 mb-3">
<div class="col"><a href="{{ url_for('clientes_lista') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="{% if not filtro_color and not filtro_clase %}border:2px solid #3b5bdb;{% endif %}"><div class="kpi-label">Total</div><div class="kpi-value">{{ stats.total }}</div></div></a></div>
<div class="col"><a href="{{ url_for('clientes_lista', color='verde-brillante') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #10b981;{% if filtro_color=='verde-brillante' %}background:#ecfdf5;{% endif %}"><div class="kpi-label"><span class="rfm-dot rfm-verde-brillante"></span> Verde brillante</div><div class="kpi-value">{{ stats.por_color['verde-brillante'] }}</div></div></a></div>
<div class="col"><a href="{{ url_for('clientes_lista', color='amarillo') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #fbbf24;{% if filtro_color=='amarillo' %}background:#fffbeb;{% endif %}"><div class="kpi-label"><span class="rfm-dot rfm-amarillo"></span> Amarillo</div><div class="kpi-value">{{ stats.por_color['amarillo'] }}</div></div></a></div>
<div class="col"><a href="{{ url_for('clientes_lista', color='rojo') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #ef4444;{% if filtro_color=='rojo' %}background:#fef2f2;{% endif %}"><div class="kpi-label"><span class="rfm-dot rfm-rojo"></span> Rojo (riesgo)</div><div class="kpi-value">{{ stats.por_color['rojo'] }}</div></div></a></div>
<div class="col"><a href="{{ url_for('clientes_lista', clase='top') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #fbbf24;{% if filtro_clase=='top' %}background:#fffbeb;{% endif %}"><div class="kpi-label">🏆 Top 20%</div><div class="kpi-value">{{ stats.por_clase['top'] }}</div></div></a></div>
</div>'''

    nuevo = '''<!-- Stats compactas -->
<style>
.stats-compact-cli{ display:flex; gap:8px; margin-bottom:1rem; flex-wrap:wrap; }
.stats-compact-cli .stat-pill{ display:flex; align-items:center; gap:8px; padding:8px 14px; background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(16,24,40,.06); text-decoration:none; color:inherit; border-left:3px solid #6b7280; flex:1; min-width:130px; transition:box-shadow .15s; }
.stats-compact-cli .stat-pill:hover{ box-shadow:0 4px 12px rgba(16,24,40,.08); color:inherit; }
.stats-compact-cli .stat-icon{ width:26px; height:26px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:.8rem; flex-shrink:0; background:#f3f4f6; }
.stats-compact-cli .stat-body{ display:flex; flex-direction:column; line-height:1.15; min-width:0; }
.stats-compact-cli .stat-label{ font-size:.65rem; color:#6b7280; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stats-compact-cli .stat-value{ font-size:.95rem; font-weight:700; letter-spacing:-.01em; }
.stats-compact-cli .stat-pill.active{ background:#f0f4ff; }
.stats-compact-cli .p-primary{ border-left-color:#3b5bdb; } .stats-compact-cli .p-primary .stat-icon{ background:#eef2ff; color:#3b5bdb; }
.stats-compact-cli .p-success{ border-left-color:#10b981; } .stats-compact-cli .p-success .stat-icon{ background:#ecfdf5; color:#10b981; }
.stats-compact-cli .p-warning{ border-left-color:#f59e0b; } .stats-compact-cli .p-warning .stat-icon{ background:#fffbeb; color:#f59e0b; }
.stats-compact-cli .p-danger{ border-left-color:#ef4444; } .stats-compact-cli .p-danger .stat-icon{ background:#fef2f2; color:#ef4444; }
.stats-compact-cli .p-violet{ border-left-color:#8b5cf6; } .stats-compact-cli .p-violet .stat-icon{ background:#f3e8ff; color:#8b5cf6; }
</style>

<div class="stats-compact-cli">
<a href="{{ url_for('clientes_lista') }}" class="stat-pill p-primary {% if not filtro_color and not filtro_clase %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-people"></i></div>
<div class="stat-body">
<span class="stat-label">Total</span>
<span class="stat-value">{{ stats.total }}</span>
</div>
</a>
<a href="{{ url_for('clientes_lista', color='verde-brillante') }}" class="stat-pill p-success {% if filtro_color=='verde-brillante' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-circle-fill"></i></div>
<div class="stat-body">
<span class="stat-label">Verde brillante</span>
<span class="stat-value">{{ stats.por_color['verde-brillante'] }}</span>
</div>
</a>
<a href="{{ url_for('clientes_lista', color='amarillo') }}" class="stat-pill p-warning {% if filtro_color=='amarillo' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-circle-fill"></i></div>
<div class="stat-body">
<span class="stat-label">Amarillo</span>
<span class="stat-value">{{ stats.por_color['amarillo'] }}</span>
</div>
</a>
<a href="{{ url_for('clientes_lista', color='rojo') }}" class="stat-pill p-danger {% if filtro_color=='rojo' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-circle-fill"></i></div>
<div class="stat-body">
<span class="stat-label">Rojo</span>
<span class="stat-value">{{ stats.por_color['rojo'] }}</span>
</div>
</a>
<a href="{{ url_for('clientes_lista', clase='top') }}" class="stat-pill p-violet {% if filtro_clase=='top' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-trophy"></i></div>
<div class="stat-body">
<span class="stat-label">Top 20%</span>
<span class="stat-value">{{ stats.por_clase['top'] }}</span>
</div>
</a>
</div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade60] clientes con stats compactas")
    else:
        print("[upgrade60] ADVERTENCIA: no se encontro el bloque de stats de clientes")


def patch_gastos_stats():
    """Cambia las stats cards de Gastos a pills chiquitas."""
    ruta = os.path.join(BASE, 'templates', 'gastos', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade60] no existe gastos/lista.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'stats-compact-gastos' in contenido:
        print("[upgrade60] gastos ya tiene stats compactas")
        return

    # Buscar el bloque de stats actual
    buscar = '''<!-- Stats mes actual vs mes anterior -->
<div class="row row-cols-2 row-cols-md-3 g-2 mb-3">
<div class="col">
<div class="card-kpi" style="border-left:3px solid #ef4444;">
<div class="kpi-label">Gastos del mes</div>
<div class="kpi-value">${{ '{:,.0f}'.format(stats.gastos_mes).replace(',','.') }}</div>
{% if stats.var_gastos is not none %}
<div class="kpi-delta {% if stats.var_gastos > 0 %}text-danger{% else %}text-success{% endif %}">
<i class="bi bi-arrow-{% if stats.var_gastos > 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(stats.var_gastos|abs) }}% vs mes anterior
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos del mes anterior</div>{% endif %}
</div>
</div>
<div class="col">
<div class="card-kpi" style="border-left:3px solid #f59e0b;">
<div class="kpi-label">Compras del mes</div>
<div class="kpi-value">${{ '{:,.0f}'.format(stats.compras_mes).replace(',','.') }}</div>
{% if stats.var_compras is not none %}
<div class="kpi-delta {% if stats.var_compras > 0 %}text-danger{% else %}text-success{% endif %}">
<i class="bi bi-arrow-{% if stats.var_compras > 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(stats.var_compras|abs) }}% vs mes anterior
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos del mes anterior</div>{% endif %}
</div>
</div>
<div class="col">
<div class="card-kpi" style="border-left:3px solid #1f2937;">
<div class="kpi-label">Total egresos del mes</div>
<div class="kpi-value">${{ '{:,.0f}'.format(stats.total_mes).replace(',','.') }}</div>
{% if stats.var_total is not none %}
<div class="kpi-delta {% if stats.var_total > 0 %}text-danger{% else %}text-success{% endif %}">
<i class="bi bi-arrow-{% if stats.var_total > 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(stats.var_total|abs) }}% vs mes anterior
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos del mes anterior</div>{% endif %}
</div>
</div>
</div>'''

    nuevo = '''<!-- Stats compactas -->
<style>
.stats-compact-gastos{ display:flex; gap:8px; margin-bottom:1rem; flex-wrap:wrap; }
.stats-compact-gastos .stat-pill{ display:flex; align-items:center; gap:8px; padding:10px 16px; background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(16,24,40,.06); color:inherit; border-left:3px solid #6b7280; flex:1; min-width:200px; }
.stats-compact-gastos .stat-icon{ width:30px; height:30px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:.9rem; flex-shrink:0; }
.stats-compact-gastos .stat-body{ display:flex; flex-direction:column; line-height:1.2; }
.stats-compact-gastos .stat-label{ font-size:.7rem; color:#6b7280; font-weight:500; }
.stats-compact-gastos .stat-value{ font-size:1.05rem; font-weight:700; letter-spacing:-.01em; }
.stats-compact-gastos .stat-delta{ font-size:.68rem; font-weight:600; margin-left:.3rem; }
</style>

<div class="stats-compact-gastos">
<div class="stat-pill" style="border-left-color:#ef4444;">
<div class="stat-icon" style="background:#fef2f2;color:#ef4444;"><i class="bi bi-wallet2"></i></div>
<div class="stat-body">
<span class="stat-label">Gastos del mes</span>
<span class="stat-value">${{ '{:,.0f}'.format(stats.gastos_mes).replace(',','.') }}
{% if stats.var_gastos is not none %}
<span class="stat-delta {% if stats.var_gastos > 0 %}text-danger{% else %}text-success{% endif %}">{{ '%+.0f'|format(stats.var_gastos) }}%</span>
{% endif %}
</span>
</div>
</div>
<div class="stat-pill" style="border-left-color:#f59e0b;">
<div class="stat-icon" style="background:#fffbeb;color:#f59e0b;"><i class="bi bi-bag"></i></div>
<div class="stat-body">
<span class="stat-label">Compras del mes</span>
<span class="stat-value">${{ '{:,.0f}'.format(stats.compras_mes).replace(',','.') }}
{% if stats.var_compras is not none %}
<span class="stat-delta {% if stats.var_compras > 0 %}text-danger{% else %}text-success{% endif %}">{{ '%+.0f'|format(stats.var_compras) }}%</span>
{% endif %}
</span>
</div>
</div>
<div class="stat-pill" style="border-left-color:#1f2937;">
<div class="stat-icon" style="background:#f3f4f6;color:#1f2937;"><i class="bi bi-calculator"></i></div>
<div class="stat-body">
<span class="stat-label">Total egresos del mes</span>
<span class="stat-value">${{ '{:,.0f}'.format(stats.total_mes).replace(',','.') }}
{% if stats.var_total is not none %}
<span class="stat-delta {% if stats.var_total > 0 %}text-danger{% else %}text-success{% endif %}">{{ '%+.0f'|format(stats.var_total) }}%</span>
{% endif %}
</span>
</div>
</div>
</div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade60] gastos con stats compactas")
    else:
        print("[upgrade60] ADVERTENCIA: no se encontro el bloque de stats de gastos")


def patch_productos_stats():
    """Cambia las stats cards de Productos a pills chiquitas."""
    ruta = os.path.join(BASE, 'templates', 'productos', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade60] no existe productos/lista.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'stats-compact-productos' in contenido:
        print("[upgrade60] productos ya tiene stats compactas")
        return

    # Buscar el bloque de stats
    buscar = '''<div class="row row-cols-2 row-cols-md-5 g-2 mb-3">
<div class="col"><div class="card-kpi"><div class="kpi-label">Total productos</div><div class="kpi-value">{{ stats.total }}</div></div></div>
<div class="col"><a href="{{ url_for('productos_lista', alerta='sin_foto') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #f59e0b;"><div class="kpi-label">Sin foto</div><div class="kpi-value">{{ stats.sin_foto }}</div></div></a></div>
<div class="col"><a href="{{ url_for('productos_lista', alerta='sin_precio') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #ef4444;"><div class="kpi-label">Sin precio</div><div class="kpi-value">{{ stats.sin_precio }}</div></div></a></div>
<div class="col"><a href="{{ url_for('productos_lista', alerta='agotado') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #6b7280;"><div class="kpi-label">Agotados</div><div class="kpi-value">{{ stats.agotados }}</div></div></a></div>
<div class="col"><a href="{{ url_for('productos_reservados') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #06b6d4;"><div class="kpi-label">Reservados</div><div class="kpi-value">{{ stats.reservados }}</div></div></a></div>
</div>'''

    nuevo = '''<!-- Stats compactas -->
<style>
.stats-compact-productos{ display:flex; gap:8px; margin-bottom:1rem; flex-wrap:wrap; }
.stats-compact-productos .stat-pill{ display:flex; align-items:center; gap:8px; padding:8px 14px; background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(16,24,40,.06); text-decoration:none; color:inherit; border-left:3px solid #6b7280; flex:1; min-width:120px; transition:box-shadow .15s; }
.stats-compact-productos .stat-pill:hover{ box-shadow:0 4px 12px rgba(16,24,40,.08); color:inherit; }
.stats-compact-productos .stat-icon{ width:26px; height:26px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:.8rem; flex-shrink:0; }
.stats-compact-productos .stat-body{ display:flex; flex-direction:column; line-height:1.15; min-width:0; }
.stats-compact-productos .stat-label{ font-size:.65rem; color:#6b7280; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stats-compact-productos .stat-value{ font-size:.95rem; font-weight:700; letter-spacing:-.01em; }
</style>

<div class="stats-compact-productos">
<div class="stat-pill" style="border-left-color:#3b5bdb;">
<div class="stat-icon" style="background:#eef2ff;color:#3b5bdb;"><i class="bi bi-box-seam"></i></div>
<div class="stat-body">
<span class="stat-label">Total</span>
<span class="stat-value">{{ stats.total }}</span>
</div>
</div>
<a href="{{ url_for('productos_lista', alerta='sin_foto') }}" class="stat-pill" style="border-left-color:#f59e0b;">
<div class="stat-icon" style="background:#fffbeb;color:#f59e0b;"><i class="bi bi-image"></i></div>
<div class="stat-body">
<span class="stat-label">Sin foto</span>
<span class="stat-value">{{ stats.sin_foto }}</span>
</div>
</a>
<a href="{{ url_for('productos_lista', alerta='sin_precio') }}" class="stat-pill" style="border-left-color:#ef4444;">
<div class="stat-icon" style="background:#fef2f2;color:#ef4444;"><i class="bi bi-currency-dollar"></i></div>
<div class="stat-body">
<span class="stat-label">Sin precio</span>
<span class="stat-value">{{ stats.sin_precio }}</span>
</div>
</a>
<a href="{{ url_for('productos_lista', alerta='agotado') }}" class="stat-pill" style="border-left-color:#6b7280;">
<div class="stat-icon" style="background:#f3f4f6;color:#6b7280;"><i class="bi bi-x-circle"></i></div>
<div class="stat-body">
<span class="stat-label">Agotados</span>
<span class="stat-value">{{ stats.agotados }}</span>
</div>
</a>
<a href="{{ url_for('productos_reservados') }}" class="stat-pill" style="border-left-color:#06b6d4;">
<div class="stat-icon" style="background:#ecfeff;color:#06b6d4;"><i class="bi bi-hourglass-split"></i></div>
<div class="stat-body">
<span class="stat-label">Reservados</span>
<span class="stat-value">{{ stats.reservados }}</span>
</div>
</a>
</div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade60] productos con stats compactas")
    else:
        print("[upgrade60] ADVERTENCIA: no se encontro el bloque de stats de productos")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 60: Fix scroll sidebar + stats compactas ===")
    patch_base_scroll()
    patch_clientes_stats()
    patch_gastos_stats()
    patch_productos_stats()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")
    print("Despues Ctrl+F5 en el navegador")


if __name__ == '__main__':
    main()