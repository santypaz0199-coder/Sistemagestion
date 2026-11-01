
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
