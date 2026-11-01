import os

def restaurar_sistema():
    print("Iniciando la limpieza y restauración del sistema...")
    
    # 1. Arreglar el archivo run.bat (sacar el import que rompe todo)
    ruta_bat = 'run.bat'
    if os.path.exists(ruta_bat):
        with open(ruta_bat, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Buscamos y borramos cualquier rastro de app181
        contenido = contenido.replace('; import app181', '')
        contenido = contenido.replace('import app181; ', '')
        
        with open(ruta_bat, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(" -> run.bat limpio (ya no carga el módulo de pagos).")

    # 2. Borrar (o renombrar) el archivo que causaba los errores
    ruta_app181 = 'app181.py'
    if os.path.exists(ruta_app181):
        try:
            os.rename(ruta_app181, 'app181_BORRADO.txt')
            print(" -> Archivo app181.py desactivado (renombrado a app181_BORRADO.txt).")
        except Exception as e:
            print(f" -> No se pudo renombrar app181.py: {e}")

    print("\n¡Sistema restaurado! Ya podés abrir tu CMD, ejecutar run.bat y va a andar todo perfecto.")

if __name__ == '__main__':
    restaurar_sistema()