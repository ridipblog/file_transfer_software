@echo off
title Python Socket File Transfer GUI
cd /d "%~dp0"

set "PY_CMD="
where py >nul 2>&1 && set "PY_CMD=py"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
if not defined PY_CMD where python >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python315\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python315\python.exe"

if defined PY_CMD (
    start "" "%PY_CMD%" gui_app.py
) else (
    echo [ERROR] Python was not found on your system!
    pause
)
