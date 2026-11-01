import sqlite3
import os

def actualizar_base_de_datos():
    print("Iniciando actualizacion de la base de datos...")
    
    ruta_db = 'sistema.db'
    if not os.path.exists(ruta_db):
        print("Error: No se encontró el archivo sistema.db en esta carpeta.")
        return

    conn = sqlite3.connect(ruta_db)
    cursor = conn.cursor()

    # Usamos el nombre exacto de la tabla que vimos en tu error
    tabla = 'órdenes_venta' 

    # Lista de todas las columnas que el sistema intenta guardar
    columnas = [
        ('destinatario_nombre', 'TEXT'),
        ('destinatario_documento', 'TEXT'),
        ('destinatario_telefono', 'TEXT'),
        ('destinatario_email', 'TEXT'),
        ('destinatario_provincia', 'TEXT'),
        ('destinatario_localidad', 'TEXT'),
        ('destinatario_cp', 'TEXT'),
        ('destinatario_calle', 'TEXT'),
        ('destinatario_piso', 'TEXT'),
        ('destinatario_depto', 'TEXT'),
        ('destinatario_detalles', 'TEXT')
    ]

    print(f"Revisando la tabla: {tabla}")
    
    for col, tipo in columnas:
        try:
            # Intentamos agregar la columna
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
            print(f" -> Columna agregada con exito: {col}")
        except sqlite3.OperationalError as e:
            # Si ya existe, SQLite tira un error, pero lo ignoramos
            if "duplicate column name" in str(e).lower() or "ya existe" in str(e).lower():
                print(f" -> La columna {col} ya existía.")
            else:
                print(f" -> Error con la columna {col}: {e}")

    conn.commit()
    conn.close()
    print("\n¡Base de datos actualizada correctamente!")
    print("Ahora podes crear la orden sin problemas.")
    print("ACORDATE: Cuando abras el navegador, presiona Ctrl + F5 en la pantalla de nueva orden.")

if __name__ == '__main__':
    actualizar_base_de_datos()