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
    print(f"[upgrade21] escrito: {relpath}")


PROVINCIAS = [
    'Ciudad Autónoma de Buenos Aires', 'Buenos Aires', 'Catamarca', 'Chaco', 'Chubut',
    'Córdoba', 'Corrientes', 'Entre Ríos', 'Formosa', 'Jujuy', 'La Pampa', 'La Rioja',
    'Mendoza', 'Misiones', 'Neuquén', 'Río Negro', 'Salta', 'San Juan', 'San Luis',
    'Santa Cruz', 'Santa Fe', 'Santiago del Estero', 'Tierra del Fuego', 'Tucumán',
]

LOCALIDADES = {
    'Ciudad Autónoma de Buenos Aires': ['Ciudad Autónoma de Buenos Aires'],
    'Buenos Aires': [
        'La Plata','Mar del Plata','Bahía Blanca','San Isidro','Vicente López','San Martín','Morón',
        'San Justo','Lomas de Zamora','Lanús','Avellaneda','Quilmes','Berazategui','Almirante Brown',
        'Ezeiza','Tigre','San Fernando','San Miguel','José C. Paz','Malvinas Argentinas','Pilar',
        'Escobar','Moreno','Merlo','Ituzaingó','Hurlingham','Tres de Febrero','San Nicolás',
        'Pergamino','Junín','Olavarría','Tandil','Azul','Luján','Chivilcoy','Bragado','Pehuajó',
        'Necochea','Coronel Suárez','Trenque Lauquen','Bolívar','Saladillo','Chascomús','Dolores',
        'Villa Gesell','Pinamar','Monte Hermoso','San Pedro','Zárate','Campana','Lobos','Cañuelas',
        'Mercedes','Chacabuco','Lincoln','General Villegas','Rojas','Colón','San Antonio de Areco',
    ],
    'Catamarca': ['San Fernando del Valle de Catamarca','Andalgalá','Tinogasta','Belén','Recreo','Santa María'],
    'Chaco': ['Resistencia','Presidencia Roque Sáenz Peña','Villa Ángela','Barranqueras','Charata',
              'General José de San Martín','Quitilipi','Machagai','Juan José Castelli'],
    'Chubut': ['Rawson','Trelew','Puerto Madryn','Comodoro Rivadavia','Esquel','Sarmiento','Rada Tilly','Gaiman'],
    'Córdoba': [
        'Córdoba','Villa María','Río Cuarto','San Francisco','Villa Carlos Paz','Alta Gracia',
        'Río Tercero','Villa Dolores','Jesús María','Cruz del Eje','Cosquín','La Falda','Deán Funes',
        'Marcos Juárez','Bell Ville','Laboulaye','Villa Nueva','Hernando','Oliva','Oncativo',
        'Arroyito','Morteros','Leones','Río Segundo','Villa Allende','Mendiolaza','Unquillo','Salsipuedes',
    ],
    'Corrientes': ['Corrientes','Goya','Paso de los Libres','Curuzú Cuatiá','Mercedes','Santo Tomé',
                   'Esquina','Bella Vista','Saladas','Monte Caseros','Ituzaingó'],
    'Entre Ríos': ['Paraná','Concordia','Gualeguaychú','Concepción del Uruguay','Colón','Gualeguay',
                   'Villaguay','Victoria','La Paz','Chajarí','Crespo','Federal','Villaguay','San José'],
    'Formosa': ['Formosa','Clorinda','Pirané','El Colorado','Las Lomitas','Ibarreta'],
    'Jujuy': ['San Salvador de Jujuy','Palpalá','San Pedro de Jujuy','Libertador General San Martín',
              'Humahuaca','Tilcara','La Quiaca','El Carmen'],
    'La Pampa': ['Santa Rosa','General Pico','Realicó','Eduardo Castex','General Acha','25 de Mayo',
                 'Macachín','Guatraché'],
    'La Rioja': ['La Rioja','Chilecito','Aimogasta','Chamical','Villa Unión','Aimogasta','Famatina'],
    'Mendoza': ['Mendoza','San Rafael','Godoy Cruz','Guaymallén','Las Heras','Maipú','Luján de Cuyo',
                'San Martín','Rivadavia','Tunuyán','Tupungato','General Alvear','Malargüe','Santa Rosa','La Paz'],
    'Misiones': ['Posadas','Oberá','Eldorado','Puerto Iguazú','San Vicente','Apóstoles',
                 'Leandro N. Alem','Jardín América','Montecarlo','Bernardo de Irigoyen'],
    'Neuquén': ['Neuquén','Plottier','Centenario','Cutral-Có','Zapala','San Martín de los Andes',
                'Junín de los Andes','Plaza Huincul','Chos Malal','Rincón de los Sauces'],
    'Río Negro': ['Viedma','San Carlos de Bariloche','General Roca','Cipolletti','Villa Regina',
                  'Cinco Saltos','Allen','El Bolsón','San Antonio Oeste','Ingeniero Jacobacci'],
    'Salta': ['Salta','San Ramón de la Nueva Orán','Tartagal','Metán','Rosario de la Frontera',
              'General Güemes','Cafayate','Cachi','Embarcación'],
    'San Juan': ['San Juan','Rawson','Rivadavia','Chimbas','Pocito','Caucete','San Martín',
                 'Santa Lucía','Albardón','Iglesia'],
    'San Luis': ['San Luis','Villa Mercedes','Merlo','Juana Koslay','La Punta','Quines','Concarán'],
    'Santa Cruz': ['Río Gallegos','Caleta Olivia','El Calafate','Pico Truncado','Puerto Deseado',
                   'Río Turbio','Las Heras','Puerto San Julián'],
    'Santa Fe': ['Santa Fe','Rosario','Rafaela','Venado Tuerto','Reconquista','Santo Tomé',
                 'Villa Gobernador Gálvez','San Lorenzo','Casilda','Cañada de Gómez',
                 'Villa Constitución','Esperanza','San Justo','Avellaneda','Villa Ocampo',
                 'Ceres','Tostado','Firmat','Rufino'],
    'Santiago del Estero': ['Santiago del Estero','La Banda','Termas de Río Hondo','Frías',
                            'Añatuya','Quimilí','Clodomira','Monte Quemado'],
    'Tierra del Fuego': ['Ushuaia','Río Grande','Tolhuin'],
    'Tucumán': ['San Miguel de Tucumán','Yerba Buena','Tafí Viejo','Concepción','Aguilares',
                'Bella Vista','Lules','Monteros','Banda del Río Salí','Alderetes','Famaillá','Simoca'],
}


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade21] sin DB."); return
    conn = sqlite3.connect(db)

    # Tabla provincias
    conn.execute("""
        CREATE TABLE IF NOT EXISTS provincias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    """)
    # Tabla localidades
    conn.execute("""
        CREATE TABLE IF NOT EXISTS localidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provincia_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            activo INTEGER DEFAULT 1,
            creado TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (provincia_id) REFERENCES provincias(id),
            UNIQUE(provincia_id, nombre)
        )
    """)
    print("[upgrade21] tablas provincias y localidades OK")

    # Precargar provincias
    for nombre in PROVINCIAS:
        try:
            conn.execute("INSERT OR IGNORE INTO provincias (nombre) VALUES (?)", (nombre,))
        except Exception as e:
            print(f"[upgrade21] error provincia {nombre}: {e}")
    conn.commit()

    # Precargar localidades
    prov_map = {r[1]: r[0] for r in conn.execute("SELECT id, nombre FROM provincias").fetchall()}
    total_loc = 0
    for prov_nombre, locs in LOCALIDADES.items():
        if prov_nombre not in prov_map:
            continue
        pid = prov_map[prov_nombre]
        for loc in locs:
            try:
                conn.execute("INSERT OR IGNORE INTO localidades (provincia_id, nombre) VALUES (?, ?)",
                             (pid, loc))
                total_loc += 1
            except Exception:
                pass
    conn.commit()
    print(f"[upgrade21] {total_loc} localidades precargadas")

    # Agregar columnas a clientes
    cols = [r[1] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()]
    if 'provincia_id' not in cols:
        conn.execute("ALTER TABLE clientes ADD COLUMN provincia_id INTEGER")
        print("[upgrade21] + clientes.provincia_id")
    if 'localidad_id' not in cols:
        conn.execute("ALTER TABLE clientes ADD COLUMN localidad_id INTEGER")
        print("[upgrade21] + clientes.localidad_id")

    # Intentar migrar datos existentes (buscar match por nombre)
    clientes = conn.execute("SELECT id, provincia, localidad FROM clientes WHERE provincia_id IS NULL AND provincia IS NOT NULL AND provincia != ''").fetchall()
    migrados = 0
    for cid, prov_texto, loc_texto in clientes:
        # Buscar provincia por nombre (case-insensitive, trim)
        row = conn.execute("SELECT id FROM provincias WHERE lower(trim(nombre)) = lower(trim(?))",
                           (prov_texto,)).fetchone()
        if row:
            pid = row[0]
            conn.execute("UPDATE clientes SET provincia_id=? WHERE id=?", (pid, cid))
            # Buscar localidad
            if loc_texto:
                loc_row = conn.execute(
                    "SELECT id FROM localidades WHERE provincia_id=? AND lower(trim(nombre)) = lower(trim(?))",
                    (pid, loc_texto)).fetchone()
                if loc_row:
                    conn.execute("UPDATE clientes SET localidad_id=? WHERE id=?", (loc_row[0], cid))
            migrados += 1
    conn.commit()
    print(f"[upgrade21] {migrados} clientes migrados a provincia_id")

    conn.close()


APP21_PY = r'''
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app18 import app
from app import permiso_required
from database import get_db


def _provincias(conn):
    return conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()


def _localidades_por_provincia(conn):
    rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    resultado = {}
    for r in rows:
        resultado.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})
    return resultado


@app.route('/api/localidades/por-provincia/<int:pid>')
@login_required
def api_localidades_por_provincia(pid):
    conn = get_db()
    rows = conn.execute("SELECT id, nombre FROM localidades WHERE provincia_id=? AND activo=1 ORDER BY nombre",
                        (pid,)).fetchall()
    conn.close()
    return jsonify([{'id': r['id'], 'nombre': r['nombre']} for r in rows])


@app.route('/api/localidades/agregar', methods=['POST'])
@login_required
def api_localidad_agregar():
    nombre = (request.json or {}).get('nombre', '').strip()
    provincia_id = (request.json or {}).get('provincia_id')
    if not nombre or not provincia_id:
        return jsonify({'ok': False, 'error': 'Nombre y provincia son obligatorios'}), 400
    try:
        provincia_id = int(provincia_id)
    except ValueError:
        return jsonify({'ok': False, 'error': 'Provincia invalida'}), 400
    conn = get_db()
    # Verificar que la provincia exista
    if not conn.execute("SELECT id FROM provincias WHERE id=?", (provincia_id,)).fetchone():
        conn.close()
        return jsonify({'ok': False, 'error': 'Provincia no encontrada'}), 404
    # Verificar si ya existe
    existente = conn.execute("SELECT id FROM localidades WHERE provincia_id=? AND lower(nombre)=lower(?)",
                             (provincia_id, nombre)).fetchone()
    if existente:
        conn.close()
        return jsonify({'ok': True, 'id': existente[0], 'nombre': nombre, 'existia': True})
    cur = conn.execute("INSERT INTO localidades (provincia_id, nombre) VALUES (?, ?)", (provincia_id, nombre))
    new_id = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'id': new_id, 'nombre': nombre, 'existia': False})


def _datos_cliente_form():
    try:
        provincia_id = int(request.form.get('provincia_id') or 0) or None
    except ValueError:
        provincia_id = None
    try:
        localidad_id = int(request.form.get('localidad_id') or 0) or None
    except ValueError:
        localidad_id = None
    return {
        'nombre_completo': request.form.get('nombre_completo', '').strip(),
        'tipo_doc': request.form.get('tipo_doc', '').strip(),
        'nro_doc': request.form.get('nro_doc', '').strip(),
        'provincia_id': provincia_id,
        'localidad_id': localidad_id,
        'codigo_postal': request.form.get('codigo_postal', '').strip(),
        'email': request.form.get('email', '').strip(),
        'telefono': request.form.get('telefono', '').strip(),
        'es_minorista': 1 if request.form.get('es_minorista') else 0,
        'es_mayorista': 1 if request.form.get('es_mayorista') else 0,
        'notas': request.form.get('notas', '').strip(),
    }


def _render_form(conn, cliente, valores):
    provincias = _provincias(conn)
    locs = _localidades_por_provincia(conn)
    return render_template('clientes/form.html', cliente=cliente, valores=valores,
                           provincias=provincias, localidades_por_provincia=locs)


@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
@permiso_required('clientes')
def clientes_nuevo_v2():
    conn = get_db()
    if request.method == 'POST':
        d = _datos_cliente_form()
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            conn.close()
            return _render_form(get_db(), None, d) if False else _render_form(_reopen(), None, d)
        # Guardar
        conn2 = get_db()
        conn2.execute("""INSERT INTO clientes
            (nombre_completo, tipo_doc, nro_doc, provincia_id, localidad_id, codigo_postal,
             email, telefono, es_minorista, es_mayorista, notas)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (d['nombre_completo'], d['tipo_doc'], d['nro_doc'], d['provincia_id'], d['localidad_id'],
             d['codigo_postal'], d['email'], d['telefono'], d['es_minorista'], d['es_mayorista'], d['notas']))
        conn2.commit(); conn2.close()
        conn.close()
        flash('Cliente creado.', 'success')
        return redirect(url_for('clientes_lista'))
    conn.close()
    return _render_form(get_db(), None, {})


def _reopen():
    return get_db()


@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permiso_required('clientes')
def clientes_editar_v3(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes_lista'))
    cliente = dict(row)

    if request.method == 'POST':
        d = _datos_cliente_form()
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            conn.close()
            return _render_form(get_db(), cliente, d)
        conn.execute("""UPDATE clientes SET
            nombre_completo=?, tipo_doc=?, nro_doc=?, provincia_id=?, localidad_id=?, codigo_postal=?,
            email=?, telefono=?, es_minorista=?, es_mayorista=?, notas=? WHERE id=?""",
            (d['nombre_completo'], d['tipo_doc'], d['nro_doc'], d['provincia_id'], d['localidad_id'],
             d['codigo_postal'], d['email'], d['telefono'], d['es_minorista'], d['es_mayorista'],
             d['notas'], id))
        conn.commit(); conn.close()
        flash('Cliente actualizado.', 'success')
        return redirect(url_for('clientes_lista'))

    conn.close()
    return _render_form(get_db(), cliente, {})


app.view_functions['clientes_nuevo'] = clientes_nuevo_v2
app.view_functions['clientes_editar'] = clientes_editar_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


CLIENTES_FORM = r'''{% extends "base.html" %}
{% block title %}Cliente{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if cliente else 'Nuevo' }} cliente</h4>
<a href="{{ url_for('clientes_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
{% set v = valores if valores else (cliente if cliente else {}) %}
<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-6">
<label class="form-label">Nombre completo *</label>
<input name="nombre_completo" class="form-control" required value="{{ v.get('nombre_completo') or '' }}">
</div>
<div class="col-md-3">
<label class="form-label">Tipo doc</label>
<select name="tipo_doc" class="form-select">
<option value="">--</option>
{% for t in ['CUIT','CUIL','DNI'] %}
<option value="{{ t }}" {% if v.get('tipo_doc') == t %}selected{% endif %}>{{ t }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-3">
<label class="form-label">Numero</label>
<input name="nro_doc" class="form-control" value="{{ v.get('nro_doc') or '' }}">
</div>
<div class="col-md-6">
<label class="form-label">Email</label>
<input type="email" name="email" class="form-control" value="{{ v.get('email') or '' }}">
</div>
<div class="col-md-6">
<label class="form-label">Telefono</label>
<input name="telefono" class="form-control" value="{{ v.get('telefono') or '' }}">
</div>

<div class="col-md-6">
<label class="form-label">Provincia</label>
<select name="provincia_id" id="provincia-select" class="form-select">
<option value="">— Sin provincia —</option>
{% for p in provincias %}
<option value="{{ p.id }}" {% if v.get('provincia_id') == p.id %}selected{% endif %}>{{ p.nombre }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-6">
<label class="form-label">Localidad</label>
<div class="input-group">
<select name="localidad_id" id="localidad-select" class="form-select" {% if not v.get('provincia_id') %}disabled{% endif %}>
<option value="">— Sin localidad —</option>
{% if v.get('provincia_id') and localidades_por_provincia.get(v.get('provincia_id')) %}
{% for l in localidades_por_provincia[v.get('provincia_id')] %}
<option value="{{ l.id }}" {% if v.get('localidad_id') == l.id %}selected{% endif %}>{{ l.nombre }}</option>
{% endfor %}
{% endif %}
</select>
<button type="button" class="btn btn-outline-secondary" id="btn-add-localidad" onclick="abrirAgregarLocalidad()" title="Agregar localidad que falta"><i class="bi bi-plus-lg"></i></button>
</div>
<div class="form-text">¿No esta tu localidad? Click en +</div>
</div>

<div class="col-md-4">
<label class="form-label">Codigo postal</label>
<input name="codigo_postal" class="form-control" value="{{ v.get('codigo_postal') or '' }}">
</div>

<div class="col-md-12">
<label class="form-label d-block">Tags *</label>
<div class="form-check form-check-inline">
<input class="form-check-input" type="checkbox" name="es_minorista" id="es_minorista" {% if v.get('es_minorista') %}checked{% endif %}>
<label class="form-check-label" for="es_minorista">Minorista</label>
</div>
<div class="form-check form-check-inline">
<input class="form-check-input" type="checkbox" name="es_mayorista" id="es_mayorista" {% if v.get('es_mayorista') %}checked{% endif %}>
<label class="form-check-label" for="es_mayorista">Mayorista</label>
</div>
<div class="form-text">Un cliente puede ser ambos a la vez.</div>
</div>
<div class="col-12">
<label class="form-label">Notas</label>
<textarea name="notas" class="form-control" rows="2">{{ v.get('notas') or '' }}</textarea>
</div>
</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>

<!-- Modal agregar localidad -->
<div class="modal fade" id="addLocalidadModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Agregar nueva localidad</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="text-muted small">Se agrega a la provincia seleccionada y queda disponible para todos los clientes.</p>
<div class="mb-2">
<label class="form-label">Provincia</label>
<input id="add-prov-nombre" class="form-control" disabled>
</div>
<div class="mb-2">
<label class="form-label">Nombre de la localidad *</label>
<input id="add-loc-nombre" class="form-control" placeholder="Ej: Villa Nueva" required>
</div>
<div id="add-loc-error" class="alert alert-danger py-2 small d-none"></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="button" class="btn btn-primary" onclick="guardarLocalidad()">Agregar</button>
</div>
</div></div></div>

<script>
const LOCALIDADES = {{ localidades_por_provincia|tojson }};
const provSelect = document.getElementById('provincia-select');
const locSelect = document.getElementById('localidad-select');
const btnAdd = document.getElementById('btn-add-localidad');

function actualizarLocalidades() {
  const pid = provSelect.value;
  locSelect.innerHTML = '<option value="">— Sin localidad —</option>';
  if (!pid) {
    locSelect.disabled = true;
    btnAdd.disabled = true;
    return;
  }
  locSelect.disabled = false;
  btnAdd.disabled = false;
  const lista = LOCALIDADES[pid] || [];
  lista.forEach(function(l) {
    const opt = document.createElement('option');
    opt.value = l.id;
    opt.textContent = l.nombre;
    locSelect.appendChild(opt);
  });
}

provSelect.addEventListener('change', actualizarLocalidades);
if (!provSelect.value) btnAdd.disabled = true;
// Si hay valor inicial (editar), actualizar una vez
if (provSelect.value) {
  const currentLoc = locSelect.value;
  actualizarLocalidades();
  if (currentLoc) locSelect.value = currentLoc;
}

function abrirAgregarLocalidad() {
  const pid = provSelect.value;
  if (!pid) return;
  const provNombre = provSelect.options[provSelect.selectedIndex].text;
  document.getElementById('add-prov-nombre').value = provNombre;
  document.getElementById('add-loc-nombre').value = '';
  document.getElementById('add-loc-error').classList.add('d-none');
  new bootstrap.Modal(document.getElementById('addLocalidadModal')).show();
}

async function guardarLocalidad() {
  const nombre = document.getElementById('add-loc-nombre').value.trim();
  const pid = provSelect.value;
  const errEl = document.getElementById('add-loc-error');
  errEl.classList.add('d-none');
  if (!nombre) {
    errEl.textContent = 'Escribi el nombre de la localidad';
    errEl.classList.remove('d-none');
    return;
  }
  try {
    const resp = await fetch('/api/localidades/agregar', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({nombre: nombre, provincia_id: parseInt(pid)})
    });
    const data = await resp.json();
    if (!data.ok) {
      errEl.textContent = data.error || 'Error al guardar';
      errEl.classList.remove('d-none');
      return;
    }
    // Agregar al JSON local
    if (!LOCALIDADES[pid]) LOCALIDADES[pid] = [];
    if (!LOCALIDADES[pid].some(l => l.id === data.id)) {
      LOCALIDADES[pid].push({id: data.id, nombre: data.nombre});
    }
    actualizarLocalidades();
    locSelect.value = data.id;
    bootstrap.Modal.getInstance(document.getElementById('addLocalidadModal')).hide();
  } catch (e) {
    errEl.textContent = 'Error de conexion: ' + e.message;
    errEl.classList.remove('d-none');
  }
}
</script>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app21; app21.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 21: Provincias + Localidades + Form cliente con cascada (F4.1) ===")
    migrar()
    escribir('app21.py', APP21_PY)
    escribir('templates/clientes/form.html', CLIENTES_FORM)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app21.py)")


if __name__ == '__main__':
    main()