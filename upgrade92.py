# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade92] escrito: {relpath}")

def patch_clientes_top():
    ruta = os.path.join(BASE, 'templates', 'clientes', 'top.html')
    if not os.path.exists(ruta):
        print("[upgrade92] no existe clientes/top.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # El error está en que el <input type="hidden"> está dentro del <select>
    # Lo movemos afuera y limpiamos el form
    viejo_form = '''<form class="card shadow-sm p-3 mb-3">
<div class="row g-2 align-items-end">
<div class="col-md-3">
<label class="form-label small text-muted">Periodo</label>
<select name="periodo" class="form-select form-select-sm" onchange="this.form.submit()">
<input type="hidden" name="tab" value="{{ tab }}">
<option value="mes" {% if periodo=='mes' %}selected{% endif %}>Este mes</option>
<option value="trimestre" {% if periodo=='trimestre' %}selected{% endif %}>Ultimos 90 dias</option>
<option value="anio" {% if periodo=='anio' %}selected{% endif %}>Este año</option>
<option value="todo" {% if periodo=='todo' %}selected{% endif %}>Todo el historial</option>
</select>
</div>
</div>
</form>'''

    nuevo_form = '''<form class="card shadow-sm p-3 mb-3">
<input type="hidden" name="tab" value="{{ tab }}">
<div class="row g-2 align-items-end">
<div class="col-md-3">
<label class="form-label small text-muted">Periodo</label>
<select name="periodo" class="form-select form-select-sm" onchange="this.form.submit()">
<option value="mes" {% if periodo=='mes' %}selected{% endif %}>Este mes</option>
<option value="trimestre" {% if periodo=='trimestre' %}selected{% endif %}>Últimos 90 días</option>
<option value="anio" {% if periodo=='anio' %}selected{% endif %}>Este año</option>
<option value="todo" {% if periodo=='todo' %}selected{% endif %}>Todo el historial</option>
</select>
</div>
</div>
</form>'''

    if viejo_form in contenido:
        contenido = contenido.replace(viejo_form, nuevo_form)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade92] HTML del selector de periodo corregido en clientes/top.html")
    else:
        print("[upgrade92] ADVERTENCIA: no se encontró el formulario exacto en top.html")

# === BACKUP.BAT ===
BACKUP_BAT = r'''@echo off
setlocal enabledelayedexpansion

REM ============================================
REM  BACKUP Sistema Familia Zaragoza
REM ============================================

set "ORIGEN=C:\SistemaFZ"

REM Obtener fecha y hora (compatible con Win 10/11)
for /f "delims=" %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "FECHAHORA=%%a"

if "%FECHAHORA%"=="" (
  echo ERROR: no se pudo obtener la fecha.
  pause
  exit /b 1
)

set "DESTINO=C:\SistemaFZ_backups\%FECHAHORA%"

echo.
echo ============================================
echo  Creando backup en:
echo  %DESTINO%
echo ============================================
echo.

mkdir "%DESTINO%" 2>nul
if not exist "%DESTINO%" (
  echo ERROR: no se pudo crear la carpeta destino.
  pause
  exit /b 1
)

echo Copiando archivos...
xcopy "%ORIGEN%\*.py"       "%DESTINO%\" /Y /Q
xcopy "%ORIGEN%\*.bat"      "%DESTINO%\" /Y /Q
xcopy "%ORIGEN%\*.txt"      "%DESTINO%\" /Y /Q
xcopy "%ORIGEN%\*.db"       "%DESTINO%\" /Y /Q
xcopy "%ORIGEN%\templates"  "%DESTINO%\templates\" /E /I /Y /Q
xcopy "%ORIGEN%\uploads"    "%DESTINO%\uploads\"  /E /I /Y /Q

echo.
echo ============================================
echo  BACKUP COMPLETADO
echo  Guardado en: %DESTINO%
echo ============================================
echo.
echo Presiona una tecla para cerrar...
pause >nul
'''

def main():
    print("=== Upgrade 92: Fix selector de periodo y actualizar backup.bat ===")
    patch_clientes_top()
    escribir('backup.bat', BACKUP_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en la vista de top clientes")

if __name__ == '__main__':
    main()