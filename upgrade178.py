import sqlite3
import os

def arreglar_base_de_datos():
    print("Iniciando el arreglo definitivo de la base de datos...")
    print("Por favor, espera unos segundos...\n")
    
    ruta_db = 'sistema.db'
    if not os.path.exists(ruta_db):
        print("No se encontró la base de datos.")
        return

    conn = sqlite3.connect(ruta_db)
    cursor = conn.cursor()

    # Buscamos el nombre exacto de la tabla
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%rdenes_venta%'")
    resultado = cursor.fetchone()
    
    if not resultado:
        print("No se encontró la tabla de ventas.")
        return
        
    tabla = resultado[0]
    print(f"Tabla encontrada: '{tabla}'")

    # Obtenemos las columnas que ya existen
    cursor.execute(f"PRAGMA table_info('{tabla}')")
    columnas_actuales = [col[1] for col in cursor.fetchall()]

    # Lista completa de TODO lo que necesita el sistema para guardar la orden
    columnas_necesarias = [
        'destinatario_nombre', 
        'destinatario_documento', 
        'destinatario_telefono', 
        'destinatario_email', 
        'destinatario_provincia', 
        'destinatario_localidad', 
        'destinatario_cp', 
        'destinatario_calle', 
        'destinatario_piso', 
        'destinatario_depto', 
        'destinatario_detalles'
    ]

    agregadas = 0
    for col in columnas_necesarias:
        if col not in columnas_actuales:
            try:
                cursor.execute(f"ALTER TABLE '{tabla}' ADD COLUMN {col} TEXT")
                print(f" -> Se agregó el espacio para guardar: {col}")
                agregadas += 1
            except Exception as e:
                print(f" -> Error al agregar {col}: {e}")

    conn.commit()
    conn.close()
    
    if agregadas > 0:
        print(f"\n¡Listo! Se agregaron {agregadas} espacios nuevos a tu base de datos.")
    else:
        print("\nLa base de datos ya estaba completa.")
        
    print("\nAHORA ANDA AL NAVEGADOR Y APRIETA Ctrl + F5 EN LA PANTALLA DE NUEVA ORDEN.")

if __name__ == '__main__':
    arreglar_base_de_datos()