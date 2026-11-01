# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app67():
    """Agrega un endpoint para traer el detalle de las ventas/gastos."""
    ruta = os.path.join(BASE, 'app67.py')
    if not os.path.exists(ruta):
        print("[upgrade84] no existe app67.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if '/api/detalle-semana' in contenido:
        print("[upgrade84] endpoint de detalle ya existe")
        return

    nuevo_codigo = '''

from flask import jsonify

@app.route('/api/detalle-mes/<tipo>')
@login_required
def detalle_mes(tipo):
    from datetime import date
    from flask_login import current_user
    conn = get_db()
    hoy = date.today()
    ini_mes = hoy.replace(day=1).isoformat()
    
    if hoy.month == 1:
        ant_ini = date(hoy.year-1, 12, 1).isoformat()
        ant_fin = date(hoy.year-1, 12, 31).isoformat()
    else:
        ant_ini = date(hoy.year, hoy.month-1, 1).isoformat()
        # ultimo dia del mes anterior
        import calendar
        ult_dia = calendar.monthrange(hoy.year, hoy.month-1)[1]
        ant_fin = date(hoy.year, hoy.month-1, ult_dia).isoformat()

    resultado = {'actual': [], 'anterior': []}

    if tipo == 'ventas':
        q_act = """SELECT o.fecha, o.numero_interno, c.nombre_completo as cliente, o.total, o.estado 
                   FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id
                   WHERE date(o.fecha) >= ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                   ORDER BY o.fecha DESC"""
        q_ant = """SELECT o.fecha, o.numero_interno, c.nombre_completo as cliente, o.total, o.estado 
                   FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id
                   WHERE date(o.fecha) BETWEEN ? AND ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                   ORDER BY o.fecha DESC"""
    elif tipo == 'gastos':
        q_act = """SELECT fecha, descripcion as numero_interno, 'Gasto' as cliente, monto as total, 'Pagado' as estado 
                   FROM gastos WHERE date(fecha) >= ? ORDER BY fecha DESC"""
        q_ant = """SELECT fecha, descripcion as numero_interno, 'Gasto' as cliente, monto as total, 'Pagado' as estado 
                   FROM gastos WHERE date(fecha) BETWEEN ? AND ? ORDER BY fecha DESC"""
    else:
        conn.close()
        return jsonify(resultado)

    rows_act = conn.execute(q_act, (ini_mes,)).fetchall()
    rows_ant = conn.execute(q_ant, (ant_ini, ant_fin)).fetchall()

    resultado['actual'] = [dict(r) for r in rows_act]
    resultado['anterior'] = [dict(r) for r in rows_ant]

    conn.close()
    return jsonify(resultado)
'''
    contenido += nuevo_codigo
    
    # Asegurar que jsonify y login_required estén importados en app67
    if 'from flask import jsonify' not in contenido:
        contenido = contenido.replace('from app66 import app', 'from app66 import app\nfrom flask import jsonify\nfrom flask_login import login_required')

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade84] Endpoint de detalle agregado a app67.py")


def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade84] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Modificar el Modal para que tenga una tabla abajo
    viejo_modal = '''<div class="modal-body" style="height: 500px; position: relative;">
<canvas id="chart-modal-canvas"></canvas>
</div>'''
    nuevo_modal = '''<div class="modal-body">
<div style="height: 400px; position: relative; margin-bottom: 2rem;">
<canvas id="chart-modal-canvas"></canvas>
</div>
<h5 class="mb-3 text-muted" style="font-size: 1rem;"><i class="bi bi-list-ul"></i> Detalle de movimientos</h5>
<div class="table-responsive" style="max-height: 300px; overflow-y: auto;">
<table class="table table-sm table-hover align-middle">
<thead class="table-light" style="position: sticky; top: 0; z-index: 1;">
<tr>
<th>Fecha</th>
<th>Referencia / Cliente</th>
<th class="text-end">Monto</th>
</tr>
</thead>
<tbody id="tabla-detalle-body">
<tr><td colspan="3" class="text-center text-muted">Cargando...</td></tr>
</tbody>
</table>
</div>
</div>'''
    
    if viejo_modal in contenido:
        contenido = contenido.replace(viejo_modal, nuevo_modal)
        print("[upgrade84] Estructura del Modal actualizada con tabla")

    # 2. Modificar el JS para que haga fetch a la API y llene la tabla
    viejo_js = '''            modalChartInstance = new Chart(ctx, config);
        }, { once: true });
        
        modal.show();
    };'''

    nuevo_js = '''            modalChartInstance = new Chart(ctx, config);
            
            // Cargar la tabla de detalles
            const tbody = document.getElementById('tabla-detalle-body');
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted"><div class="spinner-border spinner-border-sm"></div> Cargando...</td></tr>';
            
            fetch('/api/detalle-mes/' + tipo)
                .then(r => r.json())
                .then(data => {
                    tbody.innerHTML = '';
                    const items = data.actual;
                    if (!items || items.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">No hay movimientos este mes.</td></tr>';
                        return;
                    }
                    items.forEach(it => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td class="small text-muted">${it.fecha}</td>
                            <td class="small">${it.cliente} <span class="text-muted">(${it.numero_interno})</span></td>
                            <td class="text-end fw-semibold">$${Number(it.total).toLocaleString('es-AR')}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                })
                .catch(e => {
                    tbody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Error al cargar detalles.</td></tr>';
                });
                
        }, { once: true });
        
        modal.show();
    };'''

    if viejo_js in contenido:
        contenido = contenido.replace(viejo_js, nuevo_js)
        print("[upgrade84] Lógica JS para cargar la tabla agregada")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade84] dashboard.html actualizado.")


def main():
    print("=== Upgrade 84: Detalle de ventas en el gráfico ampliado ===")
    patch_app67()
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()