@echo off
title DraveFoto - EXE bouwen
cd /d "%~dp0"
set "VPY=%~dp0.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo Nieuwe .venv maken met Python 3.13...
  py -3.13 -m venv .venv || goto mislukt
)
"%VPY%" -m pip install -q --upgrade pip
"%VPY%" -m pip install -q -r requirements.txt pyinstaller || goto mislukt
"%VPY%" make_icon.py
"%VPY%" -m PyInstaller --noconfirm --clean --windowed --onedir --name DraveFoto --icon assets\icon.ico --add-data "assets;assets" --add-data "DraveFoto-Snelgids.pdf;." --collect-all pillow_heif --hidden-import drave_update --exclude-module tkinter --exclude-module PyQt6.QtWebEngineCore --exclude-module PyQt6.QtWebEngineWidgets --exclude-module PyQt6.QtQml --exclude-module PyQt6.QtQuick --exclude-module PyQt6.QtMultimedia dravefoto.py
if errorlevel 1 goto mislukt
if not exist "dist\DraveFoto\DraveFoto.exe" goto mislukt
xcopy /e /i /y assets "dist\DraveFoto\assets" >nul
copy /y DraveFoto-Snelgids.pdf "dist\DraveFoto\" >nul
echo.
echo KLAAR: dist\DraveFoto\DraveFoto.exe
exit /b 0
:mislukt
echo MISLUKT - kijk hierboven voor de fout.
exit /b 1
