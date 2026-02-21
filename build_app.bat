@echo off
title Generador Lion YT Downloader
echo ======================================================
echo          LION YT DOWNLOADER - BUILD SYSTEM
echo ======================================================
echo.

:: 1. Limpieza de carpetas temporales de PyInstaller
echo [+] Limpiando carpetas temporales de compilacion...
if exist build rd /s /q build

:: 2. En lugar de borrar la carpeta DIST entera (donde podria estar ffmpeg), 
:: borramos solo el ejecutable anterior si existe.
echo [+] Eliminando version anterior del programa...
if exist "dist\LionYTDownloader.exe" del /f /q "dist\LionYTDownloader.exe"

echo [+] Iniciando compilacion con PyInstaller...
echo     (Esto puede tardar un par de minutos...)
echo.

:: 3. Ejecucion de PyInstaller
:: --name: Define el nombre del archivo final
:: --icon: Aplica el icono al archivo .exe
:: --add-data: Incrusta el icono dentro del binario para que la UI lo encuentre
pyinstaller --noconsole --onefile --clean ^
    --name "LionYTDownloader" ^
    --icon="icon.ico" ^
    --add-data "icon.ico;." ^
    main.py

echo.
echo ======================================================
echo   COMPILACION TERMINADA
echo ======================================================
echo.
echo [!] RECUERDA:
echo Para que el programa funcione, debes copiar ffmpeg.exe 
echo y ffprobe.exe dentro de la carpeta 'dist' junto al nuevo .exe
echo.
pause