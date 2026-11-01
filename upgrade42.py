# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app40():
    ruta = os.path.join(BASE, 'app40.py')
    if not os.path.exists(ruta):
        print("[upgrade42] no existe app40.py"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Agregar import de ImmutableMultiDict
    if 'from werkzeug.datastructures import ImmutableMultiDict' not in contenido:
        buscar = 'from database import get_db'
        if buscar in contenido:
            contenido = contenido.replace(buscar,
                'from werkzeug.datastructures import ImmutableMultiDict\n' + buscar, 1)
            print("[upgrade42] import ImmutableMultiDict agregado")

    # 2. Reemplazar el form_data={} del GET inicial por ImmutableMultiDict()
    viejo = """    return render_template('campanas/form.html',
                           remitentes=remitentes, provincias=provincias,
                           vendedores=vendedores, form_data={},
                           preview_count=None, descripcion_filtros=[])"""
    nuevo = """    return render_template('campanas/form.html',
                           remitentes=remitentes, provincias=provincias,
                           vendedores=vendedores, form_data=ImmutableMultiDict(),
                           preview_count=None, descripcion_filtros=[])"""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo)
        print("[upgrade42] form_data ahora es ImmutableMultiDict() en el GET inicial")
    else:
        print("[upgrade42] ADVERTENCIA: no se encontro el render del GET inicial")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

    # 3. Tambien hacer mas robusto el template (por si acaso)
    ruta_tpl = os.path.join(BASE, 'templates', 'campanas', 'form.html')
    if os.path.exists(ruta_tpl):
        with open(ruta_tpl, 'r', encoding='utf-8') as f:
            contenido_tpl = f.read()

        viejo_tpl = """<select name="filtro_provincia" class="form-select" multiple size="6">
{% for p in provincias %}
<option value="{{ p.id }}" {% if p.id|string in form_data.getlist('filtro_provincia') %}selected{% endif %}>{{ p.nombre }}</option>
{% endfor %}
</select>"""
        nuevo_tpl = """{% set provs_sel = form_data.getlist('filtro_provincia') if form_data.getlist is defined else form_data.get('filtro_provincia', []) %}
{% if provs_sel is string %}{% set provs_sel = [provs_sel] %}{% endif %}
<select name="filtro_provincia" class="form-select" multiple size="6">
{% for p in provincias %}
<option value="{{ p.id }}" {% if p.id|string in provs_sel %}selected{% endif %}>{{ p.nombre }}</option>
{% endfor %}
</select>"""

        if viejo_tpl in contenido_tpl:
            contenido_tpl = contenido_tpl.replace(viejo_tpl, nuevo_tpl)
            with open(ruta_tpl, 'w', encoding='utf-8') as f:
                f.write(contenido_tpl)
            print("[upgrade42] template de campanas adaptado (robusto con getlist o get)")
        else:
            print("[upgrade42] ADVERTENCIA: no se encontro el select de provincias")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app40; app40.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 42: Fix form_data en campanas (getlist) ===")
    patch_app40()

    # Actualizar run.bat
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("[upgrade42] run.bat actualizado")

    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()