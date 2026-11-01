import os
import sqlite3

def actualizar_base_de_datos():
    print("1. Actualizando base de datos (agregando columnas faltantes)...")
    
    # Buscamos el archivo de la base de datos
    ruta_db = 'sistema.db'
    if not os.path.exists(ruta_db):
        print("No se encontró sistema.db, saltando este paso.")
        return

    conn = sqlite3.connect(ruta_db)
    cursor = conn.cursor()

    # Obtenemos las columnas actuales de la tabla
    cursor.execute("PRAGMA table_info(ordenes_venta)")
    columnas_existentes = [col[1] for col in cursor.fetchall()]

    # Columnas que queremos agregar si no existen
    columnas_nuevas = [
        ('destinatario_documento', 'TEXT'),
        ('destinatario_cp', 'TEXT'),
        ('destinatario_piso', 'TEXT'),
        ('destinatario_depto', 'TEXT'),
        ('destinatario_detalles', 'TEXT')
    ]

    for nombre_col, tipo_col in columnas_nuevas:
        if nombre_col not in columnas_existentes:
            try:
                cursor.execute(f"ALTER TABLE ordenes_venta ADD COLUMN {nombre_col} {tipo_col}")
                print(f"   -> Columna agregada: {nombre_col}")
            except Exception as e:
                print(f"   -> Error agregando {nombre_col}: {e}")
        else:
            print(f"   -> La columna {nombre_col} ya existía.")

    conn.commit()
    conn.close()
    print("Base de datos actualizada correctamente.\n")


def actualizar_formulario():
    print("2. Actualizando formulario (arreglando Código Postal)...")
    
    ruta_archivo = os.path.join('templates', 'ventas', 'form.html')
    
    if not os.path.exists(os.path.dirname(ruta_archivo)):
        print(f"Error: No se encontró la carpeta {os.path.dirname(ruta_archivo)}")
        return

    # Leemos el archivo actual
    with open(ruta_archivo, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Arreglamos el JS para que el Código Postal NO se bloquee
    viejo_js = "const camposFijos = ['dest_nombre', 'dest_doc', 'dest_tel', 'dest_email', 'dest_prov', 'dest_loc', 'dest_cp'];"
    nuevo_js = "const camposFijos = ['dest_nombre', 'dest_doc', 'dest_tel', 'dest_email', 'dest_prov', 'dest_loc'];"
    
    if viejo_js in contenido:
        contenido = contenido.replace(viejo_js, nuevo_js)

    # 2. Aseguramos que el input del CP no tenga readonly por defecto
    viejo_input = '<input name="dest_cp" id="dest_cp" class="form-control" required>'
    nuevo_input = '<input name="dest_cp" id="dest_cp" class="form-control" required placeholder="Ej: 1425">'
    
    if viejo_input in contenido:
        contenido = contenido.replace(viejo_input, nuevo_input)

    # Guardamos el archivo modificado
    try:
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("¡Formulario actualizado con exito! El Código Postal ya se puede editar.")
    except Exception as e:
        print(f"Hubo un error al guardar el formulario: {e}")

if __name__ == '__main__':
    actualizar_base_de_datos()
    actualizar_formulario()
    print("\n¡TODO LISTO! Reinicia el servidor (run.bat) y presiona Ctrl+F5 en el navegador.")