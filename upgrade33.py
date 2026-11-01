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
    print(f"[upgrade33] escrito: {relpath}")


def patch_template():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade33] no existe ventas/lista.html")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Si ya esta la version compacta, salir
    if 'stats-compact-ventas' in contenido:
        print("[upgrade33] ya estaba en version compacta")
        return

    # Buscar el bloque viejo (stats-header-ventas) y reemplazarlo por la version compacta
    inicio = contenido.find('<!-- Stats Header Ventas (U32) -->')
    if inicio == -1:
        print("[upgrade33] no se encontro el bloque de stats viejo")
        return

    # El bloque viejo termina antes del <form class="card shadow-sm p-3 mb-3">
    fin = contenido.find('<form class="card shadow-sm p-3 mb-3">', inicio)
    if fin == -1:
        print("[upgrade33] no se encontro el cierre del bloque")
        return

    bloque_nuevo = '''<!-- Stats Header Ventas (compacto U33) -->
<style>
.stats-compact-ventas{ display:flex; gap:8px; margin-bottom:1rem; flex-wrap:wrap; }
.stat-pill{ display:flex; align-items:center; gap:8px; padding:8px 14px; background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(16,24,40,.06); text-decoration:none; color:inherit; border-left:3px solid #6b7280; flex:1; min-width:150px; transition:box-shadow .15s; }
.stat-pill:hover{ box-shadow:0 4px 12px rgba(16,24,40,.08); color:inherit; }
.stat-pill .stat-icon{ width:28px; height:28px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:.85rem; flex-shrink:0; background:#f3f4f6; color:#6b7280; }
.stat-pill .stat-body{ display:flex; flex-direction:column; line-height:1.15; min-width:0; }
.stat-pill .stat-label{ font-size:.68rem; color:#6b7280; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stat-pill .stat-value{ font-size:1rem; font-weight:700; letter-spacing:-.01em; white-space:nowrap; }
.stat-pill.active{ background:#f0f4ff; border-left-width:3px; }
.stat-pill.p-primary{ border-left-color:#3b5bdb; } .stat-pill.p-primary .stat-icon{ background:#eef2ff; color:#3b5bdb; }
.stat-pill.p-warning{ border-left-color:#f59e0b; } .stat-pill.p-warning .stat-icon{ background:#fffbeb; color:#f59e0b; }
.stat-pill.p-info{ border-left-color:#06b6d4; } .stat-pill.p-info .stat-icon{ background:#ecfeff; color:#06b6d4; }
.stat-pill.p-danger{ border-left-color:#ef4444; } .stat-pill.p-danger .stat-icon{ background:#fef2f2; color:#ef4444; }
.stat-pill.p-success{ border-left-color:#10b981; } .stat-pill.p-success .stat-icon{ background:#ecfdf5; color:#10b981; }
.stat-pill.p-muted{ border-left-color:#6b7280; } .stat-pill.p-muted .stat-icon{ background:#f3f4f6; color:#6b7280; }
.stat-pill .stat-delta{ font-size:.65rem; font-weight:600; }
</style>

<div class="stats-compact-ventas">
<a href="{{ url_for('ventas_lista') }}" class="stat-pill p-primary {% if not estado and not con_saldo and not facturado %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-cart"></i></div>
<div class="stat-body">
<span class="stat-label">Ordenes mes</span>
<span class="stat-value">{{ stats.ordenes_mes }}
{% if stats.variacion_ordenes is not none %}
<span class="stat-delta {% if stats.variacion_ordenes >= 0 %}text-success{% else %}text-danger{% endif %}">{{ '%+.0f'|format(stats.variacion_ordenes) }}%</span>
{% endif %}
</span>
</div>
</a>

<a href="{{ url_for('ventas_lista', estado='pendiente_pago') }}" class="stat-pill p-warning {% if estado=='pendiente_pago' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-hourglass-split"></i></div>
<div class="stat-body">
<span class="stat-label">Pendientes pago</span>
<span class="stat-value">{{ stats.pendientes }}</span>
</div>
</a>

<a href="{{ url_for('ventas_lista', estado='pagado_sin_enviar') }}" class="stat-pill p-info {% if estado=='pagado_sin_enviar' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-truck"></i></div>
<div class="stat-body">
<span class="stat-label">Sin despachar</span>
<span class="stat-value">{{ stats.sin_despachar }}</span>
</div>
</a>

<a href="{{ url_for('ventas_lista', con_saldo='1') }}" class="stat-pill p-danger {% if con_saldo=='1' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-cash-coin"></i></div>
<div class="stat-body">
<span class="stat-label">A cobrar</span>
<span class="stat-value text-danger">${{ '{:,.0f}'.format(stats.a_cobrar).replace(',','.') }}</span>
</div>
</a>

<a href="{{ url_for('ventas_lista', facturado='1') }}" class="stat-pill p-success {% if facturado=='1' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-receipt"></i></div>
<div class="stat-body">
<span class="stat-label">Facturado mes</span>
<span class="stat-value">${{ '{:,.0f}'.format(stats.facturado_mes).replace(',','.') }}
{% if stats.variacion_facturado is not none %}
<span class="stat-delta {% if stats.variacion_facturado >= 0 %}text-success{% else %}text-danger{% endif %}">{{ '%+.0f'|format(stats.variacion_facturado) }}%</span>
{% endif %}
</span>
</div>
</a>

{% if con_saldo == '1' or facturado == '1' or estado or canal or tipo or q or desde or hasta %}
<a href="{{ url_for('ventas_lista') }}" class="stat-pill p-muted">
<div class="stat-icon"><i class="bi bi-x-lg"></i></div>
<div class="stat-body">
<span class="stat-label">Quitar filtros</span>
<span class="stat-value" style="font-size:.85rem;">Limpiar</span>
</div>
</a>
{% endif %}
</div>

'''

    contenido = contenido[:inicio] + bloque_nuevo + contenido[fin:]
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade33] stats de ventas ahora compactos")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app32; app32.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 33: Stats de ventas mas compactos ===")
    patch_template()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()