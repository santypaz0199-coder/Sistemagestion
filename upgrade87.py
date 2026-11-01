# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app67():
    ruta = os.path.join(BASE, 'app67.py')
    if not os.path.exists(ruta):
        print("[upgrade87] no existe app67.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if '/api/detalle-ciudades' in contenido:
        print("[upgrade87] endpoint de ciudades ya existe")
        return

    nuevo_endpoint = '''

@app.route('/api/detalle-ciudades')
@login_required
def detalle_ciudades():
    from datetime import date
    conn = get_db()
    hoy = date.today()
    ini_mes = hoy.replace(day=1).isoformat()

    rows = conn.execute("""
        SELECT COALESCE(p.nombre, 'Sin provincia') as provincia,
               COALESCE(c.localidad, 'Sin localidad') as localidad,
               COUNT(o.id) as cantidad,
               SUM(o.total) as total
        FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        LEFT JOIN provincias p ON p.id = c.provincia_id
        WHERE o.estado IN ('pagado_sin_enviar','pagado_enviado')
        AND date(o.fecha) >= ?
        GROUP BY c.provincia_id, c.localidad
        ORDER BY total DESC
        LIMIT 15
    """, (ini_mes,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
'''
    contenido += nuevo_endpoint
    
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade87] Endpoint de ciudades agregado a app67.py")


def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade87] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Agregar el botón al gráfico de provincias
    viejo_tarjeta_prov = '''<h6 class="mb-3">Top 5 provincias por facturacion</h6>
{% if top_provs %}
<canvas id="chart-provincias" height="180"></canvas>'''
    
    nuevo_tarjeta_prov = '''<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0">Top 5 provincias por facturacion</h6>
{% if top_provs %}
<button class="btn btn-sm btn-light border" style="padding:2px 6px;" onclick="abrirProvinciasGrande()" title="Ver detalle ampliado">
<i class="bi bi-arrows-fullscreen text-muted" style="font-size:0.8rem;"></i>
</button>
{% endif %}
</div>
{% if top_provs %}
<canvas id="chart-provincias" height="180"></canvas>'''

    if viejo_tarjeta_prov in contenido:
        contenido = contenido.replace(viejo_tarjeta_prov, nuevo_tarjeta_prov)
        print("[upgrade87] Boton de expandir agregado a Provincias")

    # 2. Agregar el modal de provincias antes de cerrar el HTML
    modal_prov = '''
<!-- Modal Provincias Ampliado -->
<div class="modal fade" id="modalProvinciasAmpliado" tabindex="-1">
<div class="modal-dialog modal-xl modal-dialog-centered">
<div class="modal-content">
<div class="modal-header">
<h5 class="modal-title">Top Provincias y Ciudades</h5>
<button type="button" class="btn-close" data-bs-dismiss="modal"></button>
</div>
<div class="modal-body">
<div class="row">
<div class="col-md-5">
<div style="height: 350px; position: relative;">
<canvas id="chart-provincias-grande"></canvas>
</div>
</div>
<div class="col-md-7">
<h6 class="mb-3 text-muted"><i class="bi bi-geo-alt"></i> Top 15 Ciudades que más compran (Mes actual)</h6>
<div class="table-responsive" style="max-height: 350px; overflow-y: auto;">
<table class="table table-sm table-hover align-middle">
<thead class="table-light" style="position: sticky; top: 0; z-index: 1;">
<tr>
<th>Provincia</th>
<th>Ciudad / Localidad</th>
<th class="text-end">Órdenes</th>
<th class="text-end">Total</th>
</tr>
</thead>
<tbody id="tabla-ciudades-body">
<tr><td colspan="4" class="text-center text-muted">Cargando...</td></tr>
</tbody>
</table>
</div>
</div>
</div>
</div>
</div>
</div>
</div>
'''
    if 'modalProvinciasAmpliado' not in contenido:
        contenido = contenido.replace('{% endblock %}', modal_prov + '\n{% endblock %}')
        print("[upgrade87] Estructura del Modal de Provincias agregada")

    # 3. Agregar la lógica JS
    js_prov = '''
        // ====== MODAL PROVINCIAS ======
        const topProvsData = {{ top_provs|tojson if top_provs else '[]' }};
        let provChartInstance = null;

        window.abrirProvinciasGrande = function() {
            const modalEl = document.getElementById('modalProvinciasAmpliado');
            const modal = new bootstrap.Modal(modalEl);
            
            modalEl.addEventListener('shown.bs.modal', function () {
                if (provChartInstance) { provChartInstance.destroy(); }
                const ctx = document.getElementById('chart-provincias-grande').getContext('2d');
                
                const labelsProv = topProvsData.map(p => p.provincia);
                const dataProv = topProvsData.map(p => p.total);

                provChartInstance = new Chart(ctx, {
                    type: 'doughnut',
                    data: { 
                        labels: labelsProv, 
                        datasets: [{ 
                            data: dataProv, 
                            backgroundColor: ['#3b5bdb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'], 
                            borderWidth: 0 
                        }] 
                    },
                    options: { 
                        responsive: true, 
                        maintainAspectRatio: false,
                        cutout: '55%', 
                        plugins: { 
                            legend: { position: 'bottom', labels: { usePointStyle: true, padding: 20, font: { size: 12 } } },
                            tooltip: { callbacks: { label: function(c) { return c.label + ': $' + Number(c.raw).toLocaleString('es-AR'); } } }
                        } 
                    }
                });

                // Cargar tabla de ciudades
                const tbody = document.getElementById('tabla-ciudades-body');
                tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted"><div class="spinner-border spinner-border-sm"></div> Cargando...</td></tr>';
                
                fetch('/api/detalle-ciudades')
                    .then(r => r.json())
                    .then(data => {
                        tbody.innerHTML = '';
                        if (!data || data.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No hay ventas este mes.</td></tr>';
                            return;
                        }
                        data.forEach(it => {
                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td class="small text-muted">${it.provincia}</td>
                                <td class="fw-semibold">${it.localidad}</td>
                                <td class="text-end text-muted">${it.cantidad}</td>
                                <td class="text-end fw-semibold text-success">$${Number(it.total).toLocaleString('es-AR')}</td>
                            `;
                            tbody.appendChild(tr);
                        });
                    })
                    .catch(e => {
                        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Error al cargar datos.</td></tr>';
                    });
            }, { once: true });
            modal.show();
        };
'''
    if 'abrirProvinciasGrande' not in contenido:
        # Insertarlo antes del catch de DOMContentLoaded
        buscar_js = '    } catch(e) {\n        console.error("Error crítico en Dashboard:", e);'
        if buscar_js in contenido:
            contenido = contenido.replace(buscar_js, js_prov + '\n' + buscar_js)
            print("[upgrade87] Lógica JS de provincias agregada")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade87] dashboard.html actualizado.")


def main():
    print("=== Upgrade 87: Detalle ampliado de Provincias y Ciudades ===")
    patch_app67()
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()