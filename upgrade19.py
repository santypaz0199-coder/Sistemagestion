# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade19] escrito: {relpath}")


APP18_PY = r'''
from flask import request
from flask_login import current_user
from app17 import app
from database import get_db

HORAS_LIMITE_DESPACHO = 48


def _alertas_stock_despacho(conn):
    productos_agotados = conn.execute("""
        SELECT id, nombre, sku FROM productos
        WHERE activo=1 AND stock_actual <= 0
        ORDER BY nombre
    """).fetchall()

    productos_bajos = conn.execute("""
        SELECT id, nombre, sku, stock_actual, stock_minimo FROM productos
        WHERE activo=1 AND stock_minimo > 0
          AND stock_actual <= stock_minimo
          AND stock_actual > 0
        ORDER BY (stock_actual - stock_minimo) ASC, nombre ASC
    """).fetchall()

    ordenes_viejas = conn.execute("""
        SELECT o.id, o.numero_interno, o.fecha, o.creado,
               c.nombre_completo as cliente_nombre, c.id as cliente_id,
               CAST((julianday('now') - julianday(
                   COALESCE((SELECT MAX(fecha) FROM pagos WHERE orden_id = o.id), o.fecha)
               )) * 24 AS INTEGER) as horas_esperando
        FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        WHERE o.estado = 'pagado_sin_enviar'
          AND COALESCE(
              (SELECT MAX(fecha) FROM pagos WHERE orden_id = o.id),
              o.fecha
          ) < datetime('now', '-' || ? || ' hours')
        ORDER BY o.creado ASC
    """, (HORAS_LIMITE_DESPACHO,)).fetchall()

    return {
        'productos_agotados': productos_agotados,
        'productos_bajos': productos_bajos,
        'ordenes_viejas': ordenes_viejas,
        'horas_limite': HORAS_LIMITE_DESPACHO,
        'total': len(productos_agotados) + len(productos_bajos) + len(ordenes_viejas),
    }


@app.context_processor
def _ctx_alertas_popup():
    if not current_user.is_authenticated or not current_user.es_admin:
        return {'alertas_popup': None}
    endpoint = request.endpoint or ''
    if endpoint != 'dashboard' and 'productos_lista' not in endpoint:
        return {'alertas_popup': None}
    conn = get_db()
    try:
        data = _alertas_stock_despacho(conn)
    finally:
        conn.close()
    return {'alertas_popup': data if data['total'] > 0 else None}


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app18; app18.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 19: Fix SQL parametrizado (alertas) ===")
    escribir('app18.py', APP18_PY)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()