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
    print(f"[upgrade36] escrito: {relpath}")


APP36_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app35 import app
from app import admin_required
from database import get_db


# ===== Canales =====
@app.route('/catalogos/canales')
@login_required
@admin_required
def canales_gestionar():
    conn = get_db()
    canales = conn.execute("""
        SELECT c.*, 
        (SELECT COUNT(*) FROM ordenes_venta WHERE canal_id = c.id) as total_ordenes
        FROM canales_venta c ORDER BY c.activo DESC, c.nombre
    """).fetchall()
    conn.close()
    return render_template('catalogos/canales.html', canales=canales)


@app.route('/catalogos/canales/nuevo', methods=['POST'])
@login_required
@admin_required
def canales_nuevo():
    nombre = request.form.get('nombre', '').strip()
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('canales_gestionar'))
    conn = get_db()
    if conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)=lower(?)", (nombre,)).fetchone():
        conn.close(); flash('Ya existe un canal con ese nombre.', 'error')
        return redirect(url_for('canales_gestionar'))
    conn.execute("INSERT INTO canales_venta (nombre, activo) VALUES (?, 1)", (nombre,))
    conn.commit(); conn.close()
    flash('Canal creado.', 'success')
    return redirect(url_for('canales_gestionar'))


@app.route('/catalogos/canales/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def canales_toggle(id):
    conn = get_db()
    conn.execute("UPDATE canales_venta SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Canal actualizado.', 'success')
    return redirect(url_for('canales_gestionar'))


@app.route('/catalogos/canales/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def canales_eliminar(id):
    conn = get_db()
    # Si tiene ordenes, solo desactivar. Si no, borrar de verdad.
    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE canal_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE canales_venta SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Canal desactivado (tiene {total} ordenes asociadas, no se puede borrar).', 'success')
    else:
        conn.execute("DELETE FROM canales_venta WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Canal eliminado definitivamente.', 'success')
    return redirect(url_for('canales_gestionar'))


# ===== Medios de pago =====
@app.route('/catalogos/medios-pago')
@login_required
@admin_required
def medios_pago_gestionar():
    conn = get_db()
    medios = conn.execute("""
        SELECT m.*, 
        (SELECT COUNT(*) FROM pagos WHERE medio_pago_id = m.id) as total_pagos
        FROM medios_pago m ORDER BY m.activo DESC, m.nombre
    """).fetchall()
    conn.close()
    return render_template('catalogos/medios_pago.html', medios=medios)


@app.route('/catalogos/medios-pago/nuevo', methods=['POST'])
@login_required
@admin_required
def medios_pago_nuevo():
    nombre = request.form.get('nombre', '').strip()
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('medios_pago_gestionar'))
    try:
        comision = float(request.form.get('comision_pct') or 0)
    except ValueError:
        comision = 0
    conn = get_db()
    if conn.execute("SELECT id FROM medios_pago WHERE lower(nombre)=lower(?)", (nombre,)).fetchone():
        conn.close(); flash('Ya existe un medio con ese nombre.', 'error')
        return redirect(url_for('medios_pago_gestionar'))
    conn.execute("INSERT INTO medios_pago (nombre, comision_pct, activo) VALUES (?, ?, 1)",
                 (nombre, comision))
    conn.commit(); conn.close()
    flash('Medio de pago creado.', 'success')
    return redirect(url_for('medios_pago_gestionar'))


@app.route('/catalogos/medios-pago/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def medios_pago_toggle(id):
    conn = get_db()
    conn.execute("UPDATE medios_pago SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Medio de pago actualizado.', 'success')
    return redirect(url_for('medios_pago_gestionar'))


@app.route('/catalogos/medios-pago/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def medios_pago_eliminar(id):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM pagos WHERE medio_pago_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE medios_pago SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Medio desactivado (tiene {total} pagos asociados).', 'success')
    else:
        conn.execute("DELETE FROM medios_pago WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Medio eliminado definitivamente.', 'success')
    return redirect(url_for('medios_pago_gestionar'))


# ===== Transportistas =====
@app.route('/catalogos/transportistas')
@login_required
@admin_required
def transportistas_gestionar():
    conn = get_db()
    transportistas = conn.execute("""
        SELECT t.*, 
        (SELECT COUNT(*) FROM ordenes_venta WHERE transportista_id = t.id) as total_envios
        FROM transportistas t ORDER BY t.activo DESC, t.nombre
    """).fetchall()
    conn.close()
    return render_template('catalogos/transportistas.html', transportistas=transportistas)


@app.route('/catalogos/transportistas/nuevo', methods=['POST'])
@login_required
@admin_required
def transportistas_nuevo():
    nombre = request.form.get('nombre', '').strip()
    url_seg = request.form.get('url_seguimiento', '').strip()
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('transportistas_gestionar'))
    conn = get_db()
    if conn.execute("SELECT id FROM transportistas WHERE lower(nombre)=lower(?)", (nombre,)).fetchone():
        conn.close(); flash('Ya existe un transportista con ese nombre.', 'error')
        return redirect(url_for('transportistas_gestionar'))
    conn.execute("INSERT INTO transportistas (nombre, url_seguimiento, activo) VALUES (?, ?, 1)",
                 (nombre, url_seg or None))
    conn.commit(); conn.close()
    flash('Transportista creado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


@app.route('/catalogos/transportistas/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def transportistas_editar(id):
    nombre = request.form.get('nombre', '').strip()
    url_seg = request.form.get('url_seguimiento', '').strip()
    conn = get_db()
    conn.execute("UPDATE transportistas SET nombre=?, url_seguimiento=? WHERE id=?",
                 (nombre, url_seg or None, id))
    conn.commit(); conn.close()
    flash('Transportista actualizado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


@app.route('/catalogos/transportistas/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def transportistas_toggle(id):
    conn = get_db()
    conn.execute("UPDATE transportistas SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Transportista actualizado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


@app.route('/catalogos/transportistas/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def transportistas_eliminar(id):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE transportista_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE transportistas SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Transportista desactivado (tiene {total} envios asociados).', 'success')
    else:
        conn.execute("DELETE FROM transportistas WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Transportista eliminado definitivamente.', 'success')
    return redirect(url_for('transportistas_gestionar'))


# ===== Pantalla de catalogos principal =====
@app.route('/catalogos')
@login_required
@admin_required
def catalogos_index():
    return render_template('catalogos/index.html')


# ===== Redirects de compatibilidad =====
# Nada que agregar


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


CATALOGOS_INDEX = r'''{% extends "base.html" %}
{% block title %}Catalogos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Catalogos</h4>
<div class="text-muted small">Canales de venta, medios de pago y transportistas</div>
</div>
</div>

<div class="row g-3">
<div class="col-md-4">
<a href="{{ url_for('canales_gestionar') }}" class="text-decoration-none">
<div class="card-kpi h-100" style="transition:box-shadow .15s;">
<div class="kpi-icon kpi-icon-primary"><i class="bi bi-broadcast"></i></div>
<div class="fw-semibold text-dark">Canales de venta</div>
<div class="small text-muted">Web, ML, Instagram, WhatsApp, local...</div>
</div></a>
</div>
<div class="col-md-4">
<a href="{{ url_for('medios_pago_gestionar') }}" class="text-decoration-none">
<div class="card-kpi h-100">
<div class="kpi-icon kpi-icon-success"><i class="bi bi-cash-coin"></i></div>
<div class="fw-semibold text-dark">Medios de pago</div>
<div class="small text-muted">Efectivo, transferencia, tarjeta, MP, QR...</div>
</div></a>
</div>
<div class="col-md-4">
<a href="{{ url_for('transportistas_gestionar') }}" class="text-decoration-none">
<div class="card-kpi h-100">
<div class="kpi-icon kpi-icon-warning"><i class="bi bi-truck"></i></div>
<div class="fw-semibold text-dark">Transportistas</div>
<div class="small text-muted">Andreani, Via Cargo, Correo Argentino...</div>
</div></a>
</div>
</div>
{% endblock %}
'''


CANALES_HTML = r'''{% extends "base.html" %}
{% block title %}Canales de venta{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Canales de venta</h4>
<div class="text-muted small">Los inactivos no aparecen al crear orden, pero se mantienen en el historial.</div>
</div>
<a href="{{ url_for('catalogos_index') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">
<div class="col-md-4">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-plus-circle"></i> Nuevo canal</h6>
<form method="post" action="{{ url_for('canales_nuevo') }}">
<div class="mb-3">
<label class="form-label small">Nombre *</label>
<input name="nombre" class="form-control" required placeholder="Ej: Tienda fisica">
</div>
<button class="btn btn-dark w-100">Crear canal</button>
</form>
</div></div>
</div>

<div class="col-md-8">
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th>Nombre</th><th class="text-end">Ordenes</th><th>Estado</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for c in canales %}
<tr class="{% if not c.activo %}text-muted{% endif %}">
<td class="fw-semibold">{{ c.nombre }}</td>
<td class="text-end">{{ c.total_ordenes }}</td>
<td>
{% if c.activo %}<span class="badge bg-success">Activo</span>
{% else %}<span class="badge bg-secondary">Inactivo</span>{% endif %}
</td>
<td class="text-end text-nowrap">
<form method="post" action="{{ url_for('canales_toggle', id=c.id) }}" class="d-inline">
<button class="btn btn-sm btn-outline-secondary" title="{% if c.activo %}Desactivar{% else %}Activar{% endif %}">
<i class="bi bi-{% if c.activo %}pause{% else %}play{% endif %}"></i>
</button>
</form>
<form method="post" action="{{ url_for('canales_eliminar', id=c.id) }}" class="d-inline"
      onsubmit="return confirm('{% if c.total_ordenes > 0 %}Este canal tiene {{ c.total_ordenes }} ordenes. Se desactivara (no se borra).{% else %}Eliminar definitivamente este canal?{% endif %}')">
<button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
</form>
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
</div>
</div>

<div class="alert alert-light border mt-3 small">
<i class="bi bi-info-circle"></i> 
<strong>Nota:</strong> los canales con ordenes asociadas no se pueden borrar, solo desactivar.
Los canales inactivos siguen apareciendo en las ordenes viejas para mantener el historial correcto.
</div>
{% endblock %}
'''


MEDIOS_PAGO_HTML = r'''{% extends "base.html" %}
{% block title %}Medios de pago{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Medios de pago</h4>
<div class="text-muted small">Los inactivos no aparecen al cobrar, pero se mantienen en el historial.</div>
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
<form method="post" action="{{ url_for('medios_pago_toggle', id=m.id) }}" class="d-inline">
<button class="btn btn-sm btn-outline-secondary" title="{% if m.activo %}Desactivar{% else %}Activar{% endif %}">
<i class="bi bi-{% if m.activo %}pause{% else %}play{% endif %}"></i>
</button>
</form>
<form method="post" action="{{ url_for('medios_pago_eliminar', id=m.id) }}" class="d-inline"
      onsubmit="return confirm('{% if m.total_pagos > 0 %}Este medio tiene {{ m.total_pagos }} pagos. Se desactivara.{% else %}Eliminar definitivamente?{% endif %}')">
<button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
</form>
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
</div>
</div>
{% endblock %}
'''


TRANSPORTISTAS_HTML = r'''{% extends "base.html" %}
{% block title %}Transportistas{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Transportistas</h4>
<div class="text-muted small">Configura la URL de seguimiento para que los clientes puedan rastrear su envio.</div>
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
<label class="form-label small">URL de seguimiento</label>
<input name="url_seguimiento" class="form-control" placeholder="https://ejemplo.com/track/{guia}">
<div class="form-text">Usa <code>{guia}</code> donde va el numero. Si el correo no tiene URL directa, deja la base (ej: correoargentino.com/formulario) y el sistema mostrara el numero para copiar.</div>
</div>
<button class="btn btn-dark w-100">Crear transportista</button>
</form>
</div></div>
</div>

<div class="col-md-8">
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th>Nombre</th><th>URL seguimiento</th><th class="text-end">Envios</th><th>Estado</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for t in transportistas %}
<tr class="{% if not t.activo %}text-muted{% endif %}">
<td class="fw-semibold">{{ t.nombre }}</td>
<td class="small text-muted">{% if t.url_seguimiento %}<code style="font-size:.7rem;">{{ t.url_seguimiento[:50] }}{% if t.url_seguimiento|length > 50 %}...{% endif %}</code>{% else %}—{% endif %}</td>
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

<div class="modal fade" id="editarTranspModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="editar-transp-form" method="post">
<div class="modal-header"><h6 class="modal-title">Editar transportista</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2">
<label class="form-label">Nombre</label>
<input name="nombre" id="transp-nombre" class="form-control" required>
</div>
<div class="mb-2">
<label class="form-label">URL de seguimiento</label>
<input name="url_seguimiento" id="transp-url" class="form-control" placeholder="https://ejemplo.com/track/{guia}">
<div class="form-text">Usa <code>{guia}</code> como placeholder.</div>
</div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-primary">Guardar</button>
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


def patch_base_html():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade36] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'catalogos_index' in contenido:
        print("[upgrade36] base.html ya tiene Catalogos")
        return

    # Insertar antes de Configuracion
    buscar = '<a href="{{ url_for(\'configuracion\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'configuracion\') %}active{% endif %}"><i class="bi bi-gear"></i> Configuracion</a>'
    if buscar not in contenido:
        print("[upgrade36] no se encontro link de Configuracion")
        return

    nuevo = ('<a href="{{ url_for(\'catalogos_index\') }}" class="{% if request.endpoint and request.endpoint.startswith(\'catalogos\') %}active{% endif %}">'
             '<i class="bi bi-tags"></i> Catalogos</a>\n'
             + buscar)
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade36] link Catalogos agregado a base.html")


def patch_objetivos_lista():
    ruta = os.path.join(BASE, 'templates', 'objetivos', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade36] no existe objetivos/lista.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'canales_gestionar' in contenido:
        print("[upgrade36] objetivos/lista.html ya tiene boton gestionar")
        return

    buscar = '<h6 class="mb-1"><i class="bi bi-broadcast"></i> Objetivos por canal</h6>'
    if buscar not in contenido:
        print("[upgrade36] no se encontro el titulo de canales")
        return

    nuevo = (buscar + '\n<a href="{{ url_for(\'canales_gestionar\') }}" class="btn btn-sm btn-outline-secondary mt-1">'
             '<i class="bi bi-gear"></i> Gestionar canales</a>')
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade36] boton gestionar canales agregado a objetivos/lista.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app36; app36.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 36: Gestion de canales, medios de pago y transportistas ===")
    escribir('app36.py', APP36_PY)
    escribir('templates/catalogos/index.html', CATALOGOS_INDEX)
    escribir('templates/catalogos/canales.html', CANALES_HTML)
    escribir('templates/catalogos/medios_pago.html', MEDIOS_PAGO_HTML)
    escribir('templates/catalogos/transportistas.html', TRANSPORTISTAS_HTML)
    patch_base_html()
    patch_objetivos_lista()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app36.py)")


if __name__ == '__main__':
    main()