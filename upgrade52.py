# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    if os.path.dirname(ruta):
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade52] escrito: {relpath}")


BACKUP_BAT = r'''@echo off
setlocal enabledelayedexpansion

REM ============================================
REM  BACKUP Sistema Familia Zaragoza
REM  Compatible con Windows 10 y 11 (sin wmic)
REM ============================================

set "ORIGEN=C:\SistemaFZ"

REM Obtener fecha y hora via PowerShell (funciona en Windows 10/11)
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
    print("=== Upgrade 52: Fix backup.bat sin wmic ===")
    escribir('backup.bat', BACKUP_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: backup.bat para probar")


if __name__ == '__main__':
    main()