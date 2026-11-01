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
    print(f"[upgrade64] escrito: {relpath}")


APP64_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app63 import app
from app import admin_required
from database import get_db


# ===== MEDIOS DE PAGO: pagina de edicion separada =====
@app.route('/catalogos/medios-pago/<int:id>/editar', methods=['GET'])
@login_required
@admin_required
def medios_pago_editar_form(id):
    conn = get_db()
    medio = conn.execute("SELECT * FROM medios_pago WHERE id=?", (id,)).fetchone()
    conn.close()
    if not medio:
        flash('Medio de pago no encontrado.', 'error')
        return redirect(url_for('medios_pago_gestionar'))
    return render_template('catalogos/medios_pago_form.html', medio=dict(medio))


@app.route('/catalogos/medios-pago/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def medios_pago_editar_guardar(id):
    nombre = request.form.get('nombre', '').strip()
    try:
        comision = float(request.form.get('comision_pct') or 0)
    except ValueError:
        comision = 0
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('medios_pago_editar_form', id=id))

    conn = get_db()
    existe = conn.execute("SELECT id FROM medios_pago WHERE lower(nombre)=lower(?) AND id!=?",
                           (nombre, id)).fetchone()
    if existe:
        conn.close()
        flash('Ya existe otro medio con ese nombre.', 'error')
        return redirect(url_for('medios_pago_editar_form', id=id))

    conn.execute("UPDATE medios_pago SET nombre=?, comision_pct=? WHERE id=?",
                 (nombre, comision, id))
    conn.commit(); conn.close()
    flash('Medio de pago actualizado.', 'success')
    return redirect(url_for('medios_pago_gestionar'))
'''


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
<a href="{{ url_for('medios_pago_editar_form', id=m.id) }}" class="btn btn-sm btn-outline-secondary" title="Editar"><i class="bi bi-pencil"></i></a>
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
{% endblock %}
'''


MEDIOS_PAGO_FORM = r'''{% extends "base.html" %}
{% block title %}Editar medio de pago{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Editar medio de pago</h4>
<div class="text-muted small">Cambia el nombre o la comision</div>
</div>
<a href="{{ url_for('medios_pago_gestionar') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row">
<div class="col-md-6">
<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="mb-3">
<label class="form-label">Nombre *</label>
<input name="nombre" class="form-control" required value="{{ medio.nombre }}">
</div>
<div class="mb-3">
<label class="form-label">% Comision</label>
<input type="number" step="0.01" min="0" name="comision_pct" class="form-control" value="{{ medio.comision_pct or 0 }}">
<div class="form-text">
Porcentaje que cobra este medio sobre el monto. Ejemplos:
<ul class="mb-0 mt-1 ps-3" style="font-size:.78rem;">
<li>Efectivo / Transferencia: <strong>0</strong></li>
<li>Tarjeta de debito: <strong>1.5</strong></li>
<li>Tarjeta de credito: <strong>2.5</strong></li>
<li>Mercado Pago: <strong>3.5</strong></li>
<li>QR: <strong>0.8</strong></li>
</ul>
</div>
</div>
<div class="d-flex gap-2 mt-4">
<button type="submit" class="btn btn-dark">Guardar cambios</button>
<a href="{{ url_for('medios_pago_gestionar') }}" class="btn btn-outline-secondary">Cancelar</a>
</div>
</form>
</div></div>
</div>
</div>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 64: Fix edicion de medios de pago (pagina dedicada) ===")
    escribir('app64.py', APP64_PY)
    escribir('templates/catalogos/medios_pago.html', MEDIOS_PAGO_HTML)
    escribir('templates/catalogos/medios_pago_form.html', MEDIOS_PAGO_FORM)
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()