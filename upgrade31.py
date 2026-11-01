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
    print(f"[upgrade31] escrito: {relpath}")


APP31_PY = r'''
import io, csv, re
from flask import render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from app30 import app
from app import permiso_required
from database import get_db


def _detectar_dialecto(texto):
    # Prueba con , y con ;
    primera = texto.split('\n', 1)[0]
    if ';' in primera and primera.count(';') >= primera.count(','):
        return ';'
    return ','


def _leer_csv(file_storage):
    raw = file_storage.read()
    # Intentar UTF-8 con BOM, luego UTF-8, luego latin-1
    texto = None
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            texto = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        return None, 'No se pudo leer el archivo (encoding desconocido).'
    delim = _detectar_dialecto(texto)
    try:
        reader = csv.DictReader(io.StringIO(texto), delimiter=delim)
        filas = list(reader)
    except Exception as e:
        return None, f'Error parseando CSV: {e}'
    return filas, None


def _normalizar(s):
    if s is None:
        return ''
    return str(s).strip()


def _buscar_provincia(conn, nombre):
    if not nombre:
        return None
    row = conn.execute(
        "SELECT id FROM provincias WHERE lower(trim(nombre)) = lower(trim(?))",
        (nombre,)).fetchone()
    return row['id'] if row else None


def _buscar_localidad(conn, provincia_id, nombre):
    if not nombre or not provincia_id:
        return None
    row = conn.execute(
        "SELECT id FROM localidades WHERE provincia_id = ? AND lower(trim(nombre)) = lower(trim(?))",
        (provincia_id, nombre)).fetchone()
    return row['id'] if row else None


@app.route('/clientes/importar/plantilla')
@login_required
@permiso_required('clientes')
def clientes_importar_plantilla():
    conn = get_db()
    provincias = conn.execute("SELECT nombre FROM provincias ORDER BY nombre").fetchall()
    conn.close()
    lineas = [
        'nombre_completo,tipo_doc,nro_doc,email,telefono,provincia,localidad,codigo_postal,es_minorista,es_mayorista,notas',
        'Juan Perez,DNI,30123456,juan@gmail.com,+5491134567890,Cordoba,Cordoba,5000,1,0,Cliente desde 2024',
        'Distribuidora Sur SRL,CUIT,30712345678,ventas@distri.com,+5491145678901,Buenos Aires,La Plata,1900,0,1,Compra mensual',
        '',
        '# PROVINCIAS DISPONIBLES:',
    ]
    for p in provincias:
        lineas.append(f'# - {p["nombre"]}')
    lineas.append('')
    lineas.append('# Columnas: nombre_completo(oblig), tipo_doc(DNI/CUIT/CUIL), nro_doc, email, telefono, provincia, localidad, codigo_postal, es_minorista(1/0), es_mayorista(1/0), notas')
    csv_texto = '\n'.join(lineas) + '\n'
    return Response(
        csv_texto, mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename="plantilla_clientes.csv"'})


@app.route('/clientes/importar', methods=['GET', 'POST'])
@login_required
@permiso_required('clientes')
def clientes_importar():
    conn = get_db()
    vendedores = conn.execute(
        "SELECT id, nombre, rol FROM usuarios WHERE activo=1 ORDER BY nombre"
    ).fetchall()

    if request.method == 'POST':
        accion = request.form.get('accion', 'preview')
        file = request.files.get('archivo')
        if not file or not file.filename:
            conn.close(); flash('Selecciona un archivo CSV.', 'error')
            return redirect(url_for('clientes_importar'))

        filas, err = _leer_csv(file)
        if err:
            conn.close(); flash(err, 'error')
            return redirect(url_for('clientes_importar'))

        vendedor_asignar = request.form.get('vendedor_id')
        try:
            vendedor_id = int(vendedor_asignar) if vendedor_asignar else current_user.id
        except ValueError:
            vendedor_id = current_user.id

        # Preprocesar fila por fila
        procesadas = []
        for i, fila in enumerate(filas, start=2):  # start=2 por el header
            # Skip filas que empiezan con # o vacias
            nombre = _normalizar(fila.get('nombre_completo'))
            if not nombre or nombre.startswith('#'):
                continue

            d = {
                'fila': i,
                'nombre_completo': nombre,
                'tipo_doc': _normalizar(fila.get('tipo_doc')).upper(),
                'nro_doc': _normalizar(fila.get('nro_doc')),
                'email': _normalizar(fila.get('email')),
                'telefono': _normalizar(fila.get('telefono')),
                'provincia_texto': _normalizar(fila.get('provincia')),
                'localidad_texto': _normalizar(fila.get('localidad')),
                'codigo_postal': _normalizar(fila.get('codigo_postal')),
                'es_minorista': 1 if _normalizar(fila.get('es_minorista')) in ('1', 'si', 'true', 'x') else 0,
                'es_mayorista': 1 if _normalizar(fila.get('es_mayorista')) in ('1', 'si', 'true', 'x') else 0,
                'notas': _normalizar(fila.get('notas')),
            }
            # Validaciones
            errores = []
            if not (d['es_minorista'] or d['es_mayorista']):
                errores.append('sin tag (minorista/mayorista)')
            if d['tipo_doc'] and d['tipo_doc'] not in ('DNI','CUIT','CUIL'):
                errores.append(f"tipo_doc invalido: {d['tipo_doc']}")

            # Resolver provincia/localidad
            d['provincia_id'] = _buscar_provincia(conn, d['provincia_texto'])
            d['localidad_id'] = _buscar_localidad(conn, d['provincia_id'], d['localidad_texto'])

            # Detectar duplicado
            dup = False
            if d['email']:
                if conn.execute("SELECT id FROM clientes WHERE lower(trim(email)) = lower(trim(?))",
                                (d['email'],)).fetchone():
                    dup = True
            if not dup and d['nro_doc']:
                if conn.execute("SELECT id FROM clientes WHERE trim(nro_doc) = trim(?)",
                                (d['nro_doc'],)).fetchone():
                    dup = True

            if dup:
                errores.append('duplicado (mismo email o documento)')

            d['errores'] = errores
            procesadas.append(d)

        # Si el usuario pidio solo preview o hay errores, mostrar preview
        if accion == 'preview':
            conn.close()
            return render_template('clientes/importar_preview.html',
                                   procesadas=procesadas, vendedor_id=vendedor_id,
                                   vendedores=vendedores, nombre_archivo=file.filename)

        # Importar
        if accion == 'importar':
            importados = 0
            salteados = 0
            for d in procesadas:
                if d['errores']:
                    salteados += 1
                    continue
                conn.execute("""INSERT INTO clientes
                    (nombre_completo, tipo_doc, nro_doc, provincia, localidad,
                     provincia_id, localidad_id, codigo_postal, email, telefono,
                     es_minorista, es_mayorista, notas, vendedor_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (d['nombre_completo'], d['tipo_doc'], d['nro_doc'],
                     d['provincia_texto'], d['localidad_texto'],
                     d['provincia_id'], d['localidad_id'],
                     d['codigo_postal'], d['email'], d['telefono'],
                     d['es_minorista'], d['es_mayorista'], d['notas'], vendedor_id))
                importados += 1
            conn.commit(); conn.close()
            flash(f'Importacion completa: {importados} clientes creados, {salteados} salteados por errores.', 'success')
            return redirect(url_for('clientes_lista'))

    conn.close()
    return render_template('clientes/importar.html', vendedores=vendedores)


# Reemplazar la lista de clientes para agregar boton Importar
def clientes_lista_v5():
    from app30 import clientes_lista_v4
    return clientes_lista_v4()

app.view_functions['clientes_lista'] = clientes_lista_v5


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


IMPORTAR_HTML = r'''{% extends "base.html" %}
{% block title %}Importar clientes{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Importar clientes desde CSV</h4>
<div class="text-muted small">Subi un archivo con los clientes. Podes previsualizar antes de confirmar.</div>
</div>
<a href="{{ url_for('clientes_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">
<div class="col-md-7">
<div class="card shadow-sm">
<div class="card-body">
<h6 class="mb-3"><i class="bi bi-file-earmark-arrow-up"></i> Subir archivo</h6>
<form method="post" enctype="multipart/form-data">
<div class="mb-3">
<label class="form-label">Archivo CSV *</label>
<input type="file" name="archivo" class="form-control" accept=".csv,text/csv" required>
<div class="form-text">Maximo recomendado: 1000 clientes por importacion. Encoding UTF-8 o Latin-1. Separador coma o punto y coma.</div>
</div>

<div class="mb-3">
<label class="form-label">Asignar todos los clientes a</label>
<select name="vendedor_id" class="form-select">
<option value="{{ current_user.id }}">— A mi ({{ current_user.nombre }}) —</option>
{% for v in vendedores %}
<option value="{{ v.id }}">{{ v.nombre }} ({{ v.rol }})</option>
{% endfor %}
</select>
<div class="form-text">Despues podes reasignar clientes individualmente.</div>
</div>

<input type="hidden" name="accion" value="preview">
<button class="btn btn-primary"><i class="bi bi-eye"></i> Previsualizar</button>
</form>
</div></div>
</div>

<div class="col-md-5">
<div class="card shadow-sm mb-3">
<div class="card-body">
<h6 class="mb-2"><i class="bi bi-download"></i> Plantilla</h6>
<p class="text-muted small">Descarga el CSV de ejemplo con las cabeceras correctas y la lista de provincias validas.</p>
<a href="{{ url_for('clientes_importar_plantilla') }}" class="btn btn-outline-dark btn-sm">
<i class="bi bi-download"></i> Descargar plantilla
</a>
</div></div>

<div class="card shadow-sm">
<div class="card-body">
<h6 class="mb-2"><i class="bi bi-info-circle"></i> Columnas</h6>
<table class="table table-sm small mb-0">
<tr><td><code>nombre_completo</code></td><td>Obligatorio</td></tr>
<tr><td><code>tipo_doc</code></td><td>DNI / CUIT / CUIL</td></tr>
<tr><td><code>nro_doc</code></td><td>Sin puntos ni guiones</td></tr>
<tr><td><code>email</code></td><td>—</td></tr>
<tr><td><code>telefono</code></td><td>Con o sin +54</td></tr>
<tr><td><code>provincia</code></td><td>Nombre exacto (ver plantilla)</td></tr>
<tr><td><code>localidad</code></td><td>Si no existe, queda como texto</td></tr>
<tr><td><code>codigo_postal</code></td><td>—</td></tr>
<tr><td><code>es_minorista</code></td><td>1 o 0</td></tr>
<tr><td><code>es_mayorista</code></td><td>1 o 0</td></tr>
<tr><td><code>notas</code></td><td>Opcional</td></tr>
</table>
</div></div>
</div>
</div>
{% endblock %}
'''


IMPORTAR_PREVIEW = r'''{% extends "base.html" %}
{% block title %}Preview importacion{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Preview de importacion</h4>
<div class="text-muted small">Archivo: <strong>{{ nombre_archivo }}</strong> · {{ procesadas|length }} filas detectadas</div>
</div>
<a href="{{ url_for('clientes_importar') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Cambiar archivo</a>
</div>

{% set ok_count = procesadas|selectattr('errores', 'equalto', [])|list|length %}
{% set err_count = procesadas|length - ok_count %}

<div class="row g-2 mb-3">
<div class="col-md-6"><div class="card-kpi" style="border-left:3px solid #10b981;">
<div class="kpi-label">Listos para importar</div>
<div class="kpi-value">{{ ok_count }}</div>
</div></div>
<div class="col-md-6"><div class="card-kpi" style="border-left:3px solid #ef4444;">
<div class="kpi-label">Con errores (se saltearan)</div>
<div class="kpi-value">{{ err_count }}</div>
</div></div>
</div>

<div class="card shadow-sm mb-3"><div class="table-responsive">
<table class="table table-hover table-sm mb-0 align-middle">
<thead class="table-light"><tr>
<th>Fila</th><th>Nombre</th><th>Doc</th><th>Email</th><th>Telefono</th>
<th>Provincia</th><th>Localidad</th><th>Tags</th><th>Estado</th>
</tr></thead>
<tbody>
{% for d in procesadas %}
<tr class="{% if d.errores %}table-danger{% endif %}">
<td class="text-muted small">{{ d.fila }}</td>
<td class="fw-semibold">{{ d.nombre_completo }}</td>
<td class="small">{{ d.tipo_doc }} {{ d.nro_doc }}</td>
<td class="small">{{ d.email or '—' }}</td>
<td class="small">{{ d.telefono or '—' }}</td>
<td class="small">
{{ d.provincia_texto or '—' }}
{% if d.provincia_id %} <i class="bi bi-check-circle-fill text-success" title="Provincia encontrada"></i>
{% elif d.provincia_texto %} <i class="bi bi-exclamation-triangle-fill text-warning" title="Provincia no encontrada - se guardara como texto"></i>{% endif %}
</td>
<td class="small">
{{ d.localidad_texto or '—' }}
{% if d.localidad_id %} <i class="bi bi-check-circle-fill text-success" title="Localidad encontrada"></i>
{% elif d.localidad_texto %} <i class="bi bi-exclamation-triangle-fill text-warning" title="Localidad no encontrada - se guardara como texto"></i>{% endif %}
</td>
<td class="small">
{% if d.es_minorista %}<span class="badge bg-info text-dark">Min</span>{% endif %}
{% if d.es_mayorista %}<span class="badge bg-warning text-dark">May</span>{% endif %}
</td>
<td>
{% if d.errores %}
<div class="small text-danger">{% for e in d.errores %}{{ e }}{% if not loop.last %} · {% endif %}{% endfor %}</div>
{% else %}
<span class="badge bg-success">OK</span>
{% endif %}
</td>
</tr>
{% endfor %}
</tbody></table></div></div>

<form method="post" enctype="multipart/form-data">
<input type="hidden" name="vendedor_id" value="{{ vendedor_id }}">
<input type="hidden" name="accion" value="importar">
<div class="d-flex gap-2">
<a href="{{ url_for('clientes_importar') }}" class="btn btn-outline-secondary">Cancelar</a>
<button class="btn btn-dark btn-lg" {% if ok_count == 0 %}disabled{% endif %}>
<i class="bi bi-check2-circle"></i> Importar {{ ok_count }} cliente{% if ok_count != 1 %}s{% endif %}
</button>
</div>
</form>

<div class="alert alert-light border mt-3 small">
<i class="bi bi-info-circle"></i>
<strong>Notas:</strong>
<ul class="mb-0 ps-3">
<li>Las filas con errores <strong>NO se importan</strong> (se saltean).</li>
<li>Las provincias/localidades marcadas con <i class="bi bi-exclamation-triangle-fill text-warning"></i> se guardan como texto y podes corregirlas despues en el cliente.</li>
<li>Los duplicados (mismo email o documento) se detectan y se saltean automaticamente.</li>
</ul>
</div>
{% endblock %}
'''


def main():
    print("=== Upgrade 31: Importar clientes desde CSV (U31) ===")
    escribir('app31.py', APP31_PY)
    escribir('templates/clientes/importar.html', IMPORTAR_HTML)
    escribir('templates/clientes/importar_preview.html', IMPORTAR_PREVIEW)
    # Actualizar lista de clientes con boton Importar
    ruta_lista = os.path.join(BASE, 'templates', 'clientes', 'lista.html')
    if os.path.exists(ruta_lista):
        with open(ruta_lista, 'r', encoding='utf-8') as f:
            contenido = f.read()
        # Agregar boton Importar antes de Top
        viejo = '<a href="{{ url_for(\'clientes_top\') }}" class="btn btn-outline-primary btn-sm"><i class="bi bi-trophy"></i> Top</a>'
        nuevo = ('<a href="{{ url_for(\'clientes_importar\') }}" class="btn btn-outline-secondary btn-sm"><i class="bi bi-file-earmark-arrow-up"></i> Importar CSV</a>\n'
                 + viejo)
        if viejo in contenido and 'clientes_importar' not in contenido:
            contenido = contenido.replace(viejo, nuevo)
            with open(ruta_lista, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print("[upgrade31] boton Importar agregado a clientes/lista.html")
        else:
            print("[upgrade31] boton Importar ya estaba o no se encontro el patron")

    # Actualizar run.bat
    run_bat = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app31; app31.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    escribir('run.bat', run_bat)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app31.py)")


if __name__ == '__main__':
    main()