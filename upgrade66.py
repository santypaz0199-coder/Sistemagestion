# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade66] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade66] sin DB."); return
    conn = sqlite3.connect(db)

    # Columna es_sistema en canales_venta
    cols = [r[1] for r in conn.execute("PRAGMA table_info(canales_venta)").fetchall()]
    if 'es_sistema' not in cols:
        conn.execute("ALTER TABLE canales_venta ADD COLUMN es_sistema INTEGER DEFAULT 0")
        print("[upgrade66] + canales_venta.es_sistema")

    # Marcar 'Tienda online' como canal del sistema
    conn.execute("UPDATE canales_venta SET es_sistema=1 WHERE lower(nombre)='tienda online'")
    print("[upgrade66] canal 'Tienda online' marcado como sistema")

    # Asegurar que exista y este activo
    if not conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)='tienda online'").fetchone():
        conn.execute("INSERT INTO canales_venta (nombre, activo, es_sistema) VALUES ('Tienda online', 1, 1)")
        print("[upgrade66] canal 'Tienda online' creado")
    else:
        conn.execute("UPDATE canales_venta SET activo=1, es_sistema=1 WHERE lower(nombre)='tienda online'")
        print("[upgrade66] canal 'Tienda online' reactivado y protegido")

    conn.commit(); conn.close()


APP66_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app65 import app
from app import admin_required
from database import get_db


def canales_gestionar_v2():
    conn = get_db()
    canales = conn.execute("""
        SELECT c.*,
        (SELECT COUNT(*) FROM ordenes_venta WHERE canal_id = c.id) as total_ordenes
        FROM canales_venta c ORDER BY c.es_sistema DESC, c.activo DESC, c.nombre
    """).fetchall()
    conn.close()
    return render_template('catalogos/canales.html', canales=canales)


def canales_toggle_v2(id):
    conn = get_db()
    canal = conn.execute("SELECT * FROM canales_venta WHERE id=?", (id,)).fetchone()
    if not canal:
        conn.close(); flash('Canal no encontrado.', 'error')
        return redirect(url_for('canales_gestionar'))
    if canal['es_sistema']:
        conn.close()
        flash('El canal "Tienda online" es del sistema y no se puede desactivar (recibe los pedidos del catalogo B2B).', 'error')
        return redirect(url_for('canales_gestionar'))
    conn.execute("UPDATE canales_venta SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Canal actualizado.', 'success')
    return redirect(url_for('canales_gestionar'))


def canales_eliminar_v2(id):
    conn = get_db()
    canal = conn.execute("SELECT * FROM canales_venta WHERE id=?", (id,)).fetchone()
    if not canal:
        conn.close(); flash('Canal no encontrado.', 'error')
        return redirect(url_for('canales_gestionar'))
    if canal['es_sistema']:
        conn.close()
        flash('El canal "Tienda online" es del sistema y no se puede eliminar (recibe los pedidos del catalogo B2B).', 'error')
        return redirect(url_for('canales_gestionar'))

    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE canal_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE canales_venta SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Canal desactivado (tiene {total} ordenes asociadas).', 'success')
    else:
        conn.execute("DELETE FROM canales_venta WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Canal eliminado definitivamente.', 'success')
    return redirect(url_for('canales_gestionar'))


app.view_functions['canales_gestionar'] = canales_gestionar_v2
app.view_functions['canales_toggle'] = canales_toggle_v2
app.view_functions['canales_eliminar'] = canales_eliminar_v2
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
<tr class="{% if not c.activo and not c.es_sistema %}text-muted{% endif %}">
<td>
<span class="fw-semibold">{{ c.nombre }}</span>
{% if c.es_sistema %}
<span class="badge bg-primary ms-1" style="font-size:.65rem;" title="Este canal recibe los pedidos del catalogo B2B y no se puede modificar">
<i class="bi bi-shield-lock"></i> SISTEMA
</span>
{% endif %}
</td>
<td class="text-end">{{ c.total_ordenes }}</td>
<td>
{% if c.es_sistema %}
<span class="badge bg-success">Activo</span>
{% elif c.activo %}
<span class="badge bg-success">Activo</span>
{% else %}
<span class="badge bg-secondary">Inactivo</span>
{% endif %}
</td>
<td class="text-end text-nowrap">
{% if c.es_sistema %}
<span class="text-muted small"><i class="bi bi-lock-fill"></i> Protegido</span>
{% else %}
<form method="post" action="{{ url_for('canales_toggle', id=c.id) }}" class="d-inline">
<button class="btn btn-sm btn-outline-secondary" title="{% if c.activo %}Desactivar{% else %}Activar{% endif %}">
<i class="bi bi-{% if c.activo %}pause{% else %}play{% endif %}"></i>
</button>
</form>
<form method="post" action="{{ url_for('canales_eliminar', id=c.id) }}" class="d-inline"
      onsubmit="return confirm('{% if c.total_ordenes > 0 %}Este canal tiene {{ c.total_ordenes }} ordenes. Se desactivara (no se borra).{% else %}Eliminar definitivamente este canal?{% endif %}')">
<button class="btn btn-sm btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
</form>
{% endif %}
</td>
</tr>
{% endfor %}
</tbody></table></div></div>
</div>
</div>

<div class="alert alert-light border mt-3 small">
<i class="bi bi-info-circle"></i>
<strong>Nota:</strong>
<ul class="mb-0 ps-3">
<li><strong>Canales con ordenes</strong> asociadas no se pueden borrar, solo desactivar.</li>
<li><strong>Canal "Tienda online"</strong> (marcado como SISTEMA) recibe los pedidos del catalogo B2B. No se puede desactivar, eliminar ni renombrar. Es fundamental para que funcione el catalogo con inicio de sesion.</li>
<li>Los canales inactivos siguen apareciendo en las ordenes viejas para mantener el historial.</li>
</ul>
</div>
{% endblock %}
'''


def patch_app53_canal_seguro():
    """Asegura que el canal Tienda online siempre exista al crear pedido del catalogo."""
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'canal_protegido_catalogo' in contenido:
        print("[upgrade66] app53 ya tiene canal protegido")
        return

    viejo = """        # Buscar el canal "Tienda online"
        canal = conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)='tienda online'").fetchone()
        canal_id = canal['id'] if canal else None"""

    nuevo = """        # Buscar el canal "Tienda online" (crear si no existe - canal protegido del catalogo)
        # canal_protegido_catalogo
        canal = conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)='tienda online'").fetchone()
        if canal:
            canal_id = canal['id']
        else:
            cur_canal = conn.execute("INSERT INTO canales_venta (nombre, activo, es_sistema) VALUES ('Tienda online', 1, 1)")
            canal_id = cur_canal.lastrowid"""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade66] app53 crea canal protegido si falta")
    else:
        print("[upgrade66] ADVERTENCIA: no se encontro el bloque de canal en app53")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 66: Canal 'Tienda online' protegido ===")
    migrar()
    escribir('app66.py', APP66_PY)
    escribir('templates/catalogos/canales.html', CANALES_HTML)
    patch_app53_canal_seguro()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()