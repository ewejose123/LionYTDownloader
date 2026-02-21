@echo off
setlocal enabledelayedexpansion
title Lion YT Downloader Builder
echo ======================================================
echo          LION YT DOWNLOADER - PRO BUILDER
echo ======================================================
echo.

:: 1. Preguntar por la versión
set /p VERSION="Introduce el numero de version (ej. 1.0.5): "
set APP_NAME=LionYTDownloader
set ZIP_NAME=%APP_NAME%_v%VERSION%.zip

:: 2. Limpieza de seguridad
echo [+] Limpiando temporales...
if exist build rd /s /q build
:: No borramos dist entero por si tienes archivos ahi, solo la carpeta de la app
if exist "dist\%APP_NAME%" rd /s /q "dist\%APP_NAME%"
if exist "%ZIP_NAME%" del /f /q "%ZIP_NAME%"

echo.
echo [+] Compilando en modo ONEDIR (Mas estable)...
echo.

:: 3. Ejecución de PyInstaller
:: Usamos --onedir para evitar errores de interprete
pyinstaller --noconsole --onedir --clean ^
    --name "%APP_NAME%" ^
    --icon="icon.ico" ^
    --add-data "icon.ico;." ^
    main.py

echo.
echo ======================================================
echo   COMPILACION TERMINADA
echo ======================================================
echo.

:: 4. Verificación y empaquetado de FFmpeg
if not exist "ffmpeg.exe" (
    echo [!] ERROR: ffmpeg.exe no encontrado en la raiz.
    pause
    exit /b
)
if not exist "ffprobe.exe" (
    echo [!] ERROR: ffprobe.exe no encontrado en la raiz.
    pause
    exit /b
)

echo [+] Copiando FFmpeg y FFprobe al paquete...
copy /y "ffmpeg.exe" "dist\%APP_NAME%\"
copy /y "ffprobe.exe" "dist\%APP_NAME%\"

echo [+] Comprimiendo el paquete en %ZIP_NAME%...
:: Entramos a dist para que el ZIP no tenga rutas absolutas feas
cd dist
tar -a -cf "..\%ZIP_NAME%" %APP_NAME%
cd ..

echo.
echo ======================================================
echo   EXITO: %ZIP_NAME% generado.
echo   Este ZIP contiene la carpeta completa lista para usar.
echo ======================================================
echo.
pause