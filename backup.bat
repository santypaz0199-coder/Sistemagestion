@echo off
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
