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
    print(f"[upgrade41] escrito: {relpath}")


def migrar():
    """Agrega usuario_id a campanas (para saber quien la creo)."""
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade41] sin DB."); return
    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(campanas)").fetchall()]
    if 'usuario_id' not in cols:
        conn.execute("ALTER TABLE campanas ADD COLUMN usuario_id INTEGER")
        print("[upgrade41] + campanas.usuario_id")
    conn.commit(); conn.close()


def patch_app40():
    """Reemplaza campanas_lista y campanas_nueva para usar usuario_id de campanas."""
    ruta = os.path.join(BASE, 'app40.py')
    if not os.path.exists(ruta):
        print("[upgrade41] no existe app40.py"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Reemplazar la funcion campanas_lista
    viejo_lista = '''@app.route('/campanas')
@login_required
@admin_required
def campanas_lista():
    conn = get_db()
    campanas = conn.execute("""
        SELECT c.*, u.nombre as creado_por_nombre
        FROM campanas c LEFT JOIN usuarios u ON u.id = (SELECT usuario_id FROM campanas_envios WHERE campana_id = c.id LIMIT 1)
        ORDER BY c.id DESC LIMIT 100
    """).fetchall()
    conn.close()
    return render_template('campanas/lista.html', campanas=campanas)'''

    nuevo_lista = '''@app.route('/campanas')
@login_required
@admin_required
def campanas_lista():
    conn = get_db()
    campanas = conn.execute("""
        SELECT c.*, u.nombre as creado_por_nombre
        FROM campanas c LEFT JOIN usuarios u ON u.id = c.usuario_id
        ORDER BY c.id DESC LIMIT 100
    """).fetchall()
    conn.close()
    return render_template('campanas/lista.html', campanas=campanas)'''

    if viejo_lista in contenido:
        contenido = contenido.replace(viejo_lista, nuevo_lista)
        print("[upgrade41] campanas_lista corregida")
    else:
        print("[upgrade41] ADVERTENCIA: no se encontro la consulta vieja en campanas_lista")

    # Corregir el INSERT de campanas para incluir usuario_id
    viejo_insert = '''            cur = conn.execute("""INSERT INTO campanas (nombre, filtros_json, cuerpo_html, asunto, remitente, estado)
                VALUES (?,?,?,?,?,?)""",
                (nombre, filtros_json, cuerpo, asunto,
                 remitente_email or None,
                 'borrador' if accion == 'guardar' else 'enviando'))'''

    nuevo_insert = '''            cur = conn.execute("""INSERT INTO campanas (nombre, filtros_json, cuerpo_html, asunto, remitente, estado, usuario_id)
                VALUES (?,?,?,?,?,?,?)""",
                (nombre, filtros_json, cuerpo, asunto,
                 remitente_email or None,
                 'borrador' if accion == 'guardar' else 'enviando',
                 current_user.id))'''

    if viejo_insert in contenido:
        contenido = contenido.replace(viejo_insert, nuevo_insert)
        print("[upgrade41] INSERT de campanas corregido (con usuario_id)")
    else:
        print("[upgrade41] ADVERTENCIA: no se encontro el INSERT viejo")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app40; app40.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 41: Fix campanas (usuario_id) ===")
    migrar()
    patch_app40()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()