@echo off
title Python Socket File Transfer - Receiver (Server)
cd /d "%~dp0"

set "PY_CMD="
where py >nul 2>&1 && set "PY_CMD=py"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
if not defined PY_CMD where python >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python315\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python315\python.exe"

if defined PY_CMD (
    "%PY_CMD%" receiver.py
) else (
    echo [ERROR] Python was not found on your system!
    echo Please install Python or add it to your PATH.
    pause
)
