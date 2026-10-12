@echo off
title Build Standalone Executables
cd /d "%~dp0"

echo ========================================================
echo        CLEANING AND BUILDING STANDALONE EXECUTABLES
echo ========================================================

rem Remove old build and dist directories if they exist
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [*] Compiling sender.exe...
py -m PyInstaller --onefile --clean --name sender sender.py

echo [*] Compiling receiver.exe...
py -m PyInstaller --onefile --clean --name receiver receiver.py

echo [*] Compiling gui_app.exe (Windowed GUI)...
py -m PyInstaller --noconsole --onefile --clean --name gui_app gui_app.py

echo.
echo [*] Copying executables to current folder...
copy /y dist\sender.exe .\sender.exe
copy /y dist\receiver.exe .\receiver.exe
copy /y dist\gui_app.exe .\gui_app.exe

echo.
echo [✔] Done! Both sender.exe and receiver.exe have been created.
pause
