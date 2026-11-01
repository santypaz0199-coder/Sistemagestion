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
    print(f"[upgrade63] escrito: {relpath}")


APP63_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import admin_required
from database import get_db


# ===== MEDIOS DE PAGO: editar =====
@app.route('/catalogos/medios-pago/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def medios_pago_editar(id):
    nombre = request.form.get('nombre', '').strip()
    try:
        comision = float(request.form.get('comision_pct') or 0)
    except ValueError:
        comision = 0
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('medios_pago_gestionar'))

    conn = get_db()
    # Verificar que no exista otro con ese nombre
    existe = conn.execute("SELECT id FROM medios_pago WHERE lower(nombre)=lower(?) AND id!=?",
                           (nombre, id)).fetchone()
    if existe:
        conn.close()
        flash('Ya existe otro medio con ese nombre.', 'error')
        return redirect(url_for('medios_pago_gestionar'))

    conn.execute("UPDATE medios_pago SET nombre=?, comision_pct=? WHERE id=?",
                 (nombre, comision, id))
    conn.commit(); conn.close()
    flash('Medio de pago actualizado.', 'success')
    return redirect(url_for('medios_pago_gestionar'))


# ===== TRANSPORTISTAS: editar con URL inteligente =====
@app.route('/catalogos/transportistas/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def transportistas_editar_v2(id):
    nombre = request.form.get('nombre', '').strip()
    url_seg = request.form.get('url_seguimiento', '').strip()
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('transportistas_gestionar'))

    conn = get_db()
    # Verificar que no exista otro con ese nombre
    existe = conn.execute("SELECT id FROM transportistas WHERE lower(nombre)=lower(?) AND id!=?",
                           (nombre, id)).fetchone()
    if existe:
        conn.close()
        flash('Ya existe otro transportista con ese nombre.', 'error')
        return redirect(url_for('transportistas_gestionar'))

    conn.execute("UPDATE transportistas SET nombre=?, url_seguimiento=? WHERE id=?",
                 (nombre, url_seg or None, id))
    conn.commit(); conn.close()
    flash('Transportista actualizado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


@app.route('/catalogos/transportistas/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def transportistas_eliminar_v2(id):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE transportista_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE transportistas SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Transportista desactivado (tiene {total} envios).', 'success')
    else:
        conn.execute("DELETE FROM transportistas WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Transportista eliminado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


app.view_functions['transportistas_editar'] = transportistas_editar_v2
app.view_functions['transportistas_eliminar'] = transportistas_eliminar_v2


# ===== Helper para construir URL de seguimiento =====
def construir_url_seguimiento(url_base, nro_guia):
    """
    Dada una URL base y un numero de guia, devuelve la URL final.
    - Si tiene {guia}, lo reemplaza.
    - Si NO tiene, agrega el numero al final (con / si hace falta).
    """
    if not url_base or not nro_guia:
        return None
    guia = str(nro_guia).strip()
    if not guia:
        return None

    if '{guia}' in url_base:
        return url_base.replace('{guia}', guia)

    # Agregar al final
    url = url_base.rstrip('/')
    return f'{url}/{guia}'


@app.context_processor
def _helper_seguimiento():
    return {'construir_url_seguimiento': construir_url_seguimiento}
'''


# Template de medios de pago con edición
MEDIOS_PAGO_HTML = r'''{% extends "base.html" %}
{% block title %}Medios de pago{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Medios de pago</h4>
<div class="text-muted small">Edita comisiones, activa o desactiva los medios</div>
</div>
<a href="{{ url_for('catalogos_index') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">
<div class="col-md-4">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-plus-circle"></i> Nuevo medio</h6>
<form method="post" action="{{ url_for('medios_pago_nuevo') }}">
<div class="mb-2">
<label class="form-label small">Nombre *</label>
<input name="nombre" class="form-control" required placeholder="Ej: Mercado Pago QR">
</div>
<div class="mb-3">
<label class="form-label small">% Comision (opcional)</label>
<input type="number" step="0.01" min="0" name="comision_pct" class="form-control" placeholder="Ej: 3.5">
<div class="form-text">Ej: Mercado Pago 3.5%, tarjeta 2%, efectivo 0%.</div>
</div>
<button class="btn btn-dark w-100">Crear medio</button>
</form>
</div></div>
</div>

<div class="col-md-8">
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th>Nombre</th><th class="text-end">Comision</th><th class="text-end">Pagos</th><th>Estado</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for m in medios %}
<tr class="{% if not m.activo %}text-muted{% endif %}">
<td class="fw-semibold">{{ m.nombre }}</td>
<td class="text-end">{% if m.comision_pct %}{{ '%.2f'|format(m.comision_pct) }}%{% else %}—{% endif %}</td>
<td class="text-end">{{ m.total_pagos }}</td>
<td>
{% if m.activo %}<span class="badge bg-success">Activo</span>
{% else %}<span class="badge bg-secondary">Inactivo</span>{% endif %}
</td>
<td class="text-end text-nowrap">
<button type="button" class="btn btn-sm btn-outline-secondary" title="Editar" onclick="openEditarMedio({{ m.id }}, {{ m.nombre|tojson }}, {{ (m.comision_pct or 0)|tojson }})">
<i class="bi bi-pencil"></i>
</button>
<form method="post" action="{{ url_for('medios_pago_toggle', id=m.id) }}" class="d-inline">
<button class="btn btn-sm btn-outline-secondary" title="{% if m.activo %}Desactivar{% else %}Activar{% endif %}">
<i class="bi bi-{% if m.activo %}pause{% else %}play{% endif %}"></i>
</button>
</form>
<form method="post" action="{{ url_for('medios_pago_eliminar', id=m.id) }}" class="d-inline"
      onsubmit="return confirm('{% if m.total_pagos > 0 %}Tiene {{ m.total_pagos }} pagos. Se desactivara.{% else %}Eliminar definitivamente?{% endif %}')">
<button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
</form>
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
</div>
</div>

<!-- Modal editar medio -->
<div class="modal fade" id="editarMedioModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="editar-medio-form" method="post">
<div class="modal-header"><h6 class="modal-title">Editar medio de pago</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2">
<label class="form-label">Nombre *</label>
<input name="nombre" id="medio-nombre" class="form-control" required>
</div>
<div class="mb-2">
<label class="form-label">% Comision</label>
<input type="number" step="0.01" min="0" name="comision_pct" id="medio-comision" class="form-control">
<div class="form-text">Porcentaje que cobra el medio sobre el monto (ej: 3.5 para 3.5%).</div>
</div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-primary">Guardar cambios</button>
</div>
</form></div></div></div>

<script>
function openEditarMedio(id, nombre, comision) {
  document.getElementById('editar-medio-form').action = '/catalogos/medios-pago/' + id + '/editar';
  document.getElementById('medio-nombre').value = nombre;
  document.getElementById('medio-comision').value = comision || 0;
  new bootstrap.Modal(document.getElementById('editarMedioModal')).show();
}
</script>
{% endblock %}
'''


# Template de transportistas con edición y explicación
TRANSPORTISTAS_HTML = r'''{% extends "base.html" %}
{% block title %}Transportistas{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Transportistas</h4>
<div class="text-muted small">Configura la URL base de seguimiento. El sistema le agrega el numero de guia automaticamente.</div>
</div>
<a href="{{ url_for('catalogos_index') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">
<div class="col-md-4">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-plus-circle"></i> Nuevo transportista</h6>
<form method="post" action="{{ url_for('transportistas_nuevo') }}">
<div class="mb-2">
<label class="form-label small">Nombre *</label>
<input name="nombre" class="form-control" required placeholder="Ej: OCA">
</div>
<div class="mb-2">
<label class="form-label small">URL base de seguimiento</label>
<input name="url_seguimiento" class="form-control" placeholder="https://ejemplo.com/track/">
<div class="form-text">
El sistema <strong>agrega el numero de guia al final automaticamente</strong>. Ejemplo:
<ul class="mb-0 mt-1 ps-3" style="font-size:.75rem;">
<li>URL base: <code>https://viacargo.com.ar/seguimiento-de-envio/</code></li>
<li>Guia <code>999039474109</code> → <code>https://viacargo.com.ar/seguimiento-de-envio/999039474109</code></li>
</ul>
Opcionalmente podes usar <code>{guia}</code> como placeholder si la URL no termina con el numero.
</div>
</div>
<button class="btn btn-dark w-100">Crear transportista</button>
</form>
</div></div>
</div>

<div class="col-md-8">
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th>Nombre</th><th>URL base</th><th class="text-end">Envios</th><th>Estado</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for t in transportistas %}
<tr class="{% if not t.activo %}text-muted{% endif %}">
<td class="fw-semibold">{{ t.nombre }}</td>
<td class="small text-muted">{% if t.url_seguimiento %}<code style="font-size:.7rem;">{{ t.url_seguimiento[:60] }}{% if t.url_seguimiento|length > 60 %}...{% endif %}</code>{% else %}—{% endif %}</td>
<td class="text-end">{{ t.total_envios }}</td>
<td>
{% if t.activo %}<span class="badge bg-success">Activo</span>
{% else %}<span class="badge bg-secondary">Inactivo</span>{% endif %}
</td>
<td class="text-end text-nowrap">
<button type="button" class="btn btn-sm btn-outline-secondary" onclick='openEditarTransp({{ t.id }}, {{ t.nombre|tojson }}, {{ (t.url_seguimiento or "")|tojson }})' title="Editar"><i class="bi bi-pencil"></i></button>
<form method="post" action="{{ url_for('transportistas_toggle', id=t.id) }}" class="d-inline">
<button class="btn btn-sm btn-outline-secondary" title="{% if t.activo %}Desactivar{% else %}Activar{% endif %}">
<i class="bi bi-{% if t.activo %}pause{% else %}play{% endif %}"></i>
</button>
</form>
<form method="post" action="{{ url_for('transportistas_eliminar', id=t.id) }}" class="d-inline"
      onsubmit="return confirm('{% if t.total_envios > 0 %}Tiene {{ t.total_envios }} envios. Se desactivara.{% else %}Eliminar definitivamente?{% endif %}')">
<button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
</form>
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
</div>
</div>

<div class="card shadow-sm mt-3"><div class="card-body">
<h6 class="mb-2"><i class="bi bi-info-circle"></i> Como funciona el seguimiento</h6>
<p class="small text-muted mb-2">El link de seguimiento se construye automaticamente asi:</p>
<ul class="small text-muted mb-0">
<li>Si la URL base termina en <code>/</code> → se agrega la guia directo: <code>https://ejemplo.com/track/123456</code></li>
<li>Si la URL base NO termina en <code>/</code> → tambien se agrega: <code>https://ejemplo.com/track/123456</code></li>
<li>Si la URL contiene <code>{guia}</code> → se reemplaza: <code>https://ejemplo.com/track/{guia}</code> → <code>https://ejemplo.com/track/123456</code></li>
</ul>
</div></div>

<!-- Modal editar transportista -->
<div class="modal fade" id="editarTranspModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="editar-transp-form" method="post">
<div class="modal-header"><h6 class="modal-title">Editar transportista</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2">
<label class="form-label">Nombre *</label>
<input name="nombre" id="transp-nombre" class="form-control" required>
</div>
<div class="mb-2">
<label class="form-label">URL base de seguimiento</label>
<input name="url_seguimiento" id="transp-url" class="form-control" placeholder="https://ejemplo.com/track/">
<div class="form-text">El sistema agrega el numero de guia al final. Ejemplo: <code>https://viacargo.com.ar/seguimiento-de-envio/</code></div>
</div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-primary">Guardar cambios</button>
</div>
</form></div></div></div>

<script>
function openEditarTransp(id, nombre, url) {
  document.getElementById('editar-transp-form').action = '/catalogos/transportistas/' + id + '/editar';
  document.getElementById('transp-nombre').value = nombre;
  document.getElementById('transp-url').value = url || '';
  new bootstrap.Modal(document.getElementById('editarTranspModal')).show();
}
</script>
{% endblock %}
'''


def patch_ventas_detalle():
    """Reemplaza el bloque de envío con link generado automáticamente + texto explicativo."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta):
        print("[upgrade63] no existe ventas/detalle.html"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'link-seguimiento-auto' in contenido:
        print("[upgrade63] ventas/detalle ya tiene link auto")
        return

    # Buscar el bloque donde muestra el numero de guia actual
    # Insertar el link dinamico justo despues del campo nro_guia en el bloque de envio
    buscar = '''<div class="col-md-6">
<label class="form-label small">Nro de guia</label>
<input name="nro_guia" class="form-control form-control-sm" value="{{ orden.nro_guia or '' }}" placeholder="Se puede cargar despues">
</div>'''

    nuevo = '''<div class="col-md-6">
<label class="form-label small">Nro de guia</label>
<input name="nro_guia" class="form-control form-control-sm" value="{{ orden.nro_guia or '' }}" placeholder="Se puede cargar despues">
</div>

{% if orden.nro_guia %}
{% set url_seg = construir_url_seguimiento(transportista_url_actual, orden.nro_guia) %}
{% if url_seg %}
<div class="col-12 link-seguimiento-auto">
<div class="alert alert-light border py-2 px-3 mb-2">
<div class="small mb-1"><strong><i class="bi bi-link-45deg"></i> Link de seguimiento generado:</strong></div>
<a href="{{ url_seg }}" target="_blank" class="small text-decoration-none" style="word-break:break-all;">
{{ url_seg }}
</a>
</div>
<div class="small text-muted" style="font-size:.75rem;">
<i class="bi bi-info-circle"></i>
Si el link no funciona, copia el numero de guia <strong>{{ orden.nro_guia }}</strong> y pegalo manualmente en el sitio del transportista.
</div>
</div>
{% endif %}
{% endif %}'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade63] ventas/detalle con link de seguimiento automatico")
    else:
        print("[upgrade63] ADVERTENCIA: no se encontro el bloque de nro_guia en ventas/detalle")


def patch_ventas_detalle_route():
    """Pasa la URL base del transportista al template del detalle."""
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'transportista_url_actual' in contenido:
        print("[upgrade63] app39 ya pasa transportista_url_actual")
        return

    viejo = """    remitentes_disponibles = _remitentes_disponibles(conn)

    conn.close()
    return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, medios=medios, transportistas=transportistas,
                           archivos=archivos, emails=emails,
                           remitentes_disponibles=remitentes_disponibles)"""

    nuevo = """    remitentes_disponibles = _remitentes_disponibles(conn)

    # URL base del transportista actual (para construir el link de seguimiento)
    transportista_url_actual = None
    if orden['transportista_id']:
        t_row = conn.execute("SELECT url_seguimiento FROM transportistas WHERE id=?",
                              (orden['transportista_id'],)).fetchone()
        if t_row:
            transportista_url_actual = t_row['url_seguimiento']

    conn.close()
    return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, medios=medios, transportistas=transportistas,
                           archivos=archivos, emails=emails,
                           remitentes_disponibles=remitentes_disponibles,
                           transportista_url_actual=transportista_url_actual)"""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade63] app39 pasa transportista_url_actual")
    else:
        print("[upgrade63] ADVERTENCIA: no se encontro el bloque de detalle en app39")


def patch_imprimir_seguimiento():
    """Agrega texto de seguimiento manual en la vista de impresion."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'imprimir.html')
    if not os.path.exists(ruta):
        print("[upgrade63] no existe ventas/imprimir.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'seguimiento-manual-hint' in contenido:
        print("[upgrade63] imprimir ya tiene hint de seguimiento")
        return

    buscar = '''{% if orden.nro_guia %}<p><strong>Nro guia:</strong> {{ orden.nro_guia }}</p>{% endif %}'''

    nuevo = '''{% if orden.nro_guia %}
<p><strong>Nro guia:</strong> {{ orden.nro_guia }}</p>
<div class="seguimiento-manual-hint" style="font-size:11px;color:#6b7280;margin-top:4px;">
Si no podes acceder al link de seguimiento, copia el numero de guia y pegalo en el sitio del transportista.
</div>
{% endif %}'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade63] imprimir con hint de seguimiento")
    else:
        print("[upgrade63] ADVERTENCIA: no se encontro el nro_guia en imprimir")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 63: Medios de pago editables + Transportistas URL dinamica ===")
    escribir('app63.py', APP63_PY)
    escribir('templates/catalogos/medios_pago.html', MEDIOS_PAGO_HTML)
    escribir('templates/catalogos/transportistas.html', TRANSPORTISTAS_HTML)
    patch_ventas_detalle()
    patch_ventas_detalle_route()
    patch_imprimir_seguimiento()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()