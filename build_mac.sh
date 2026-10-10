#!/usr/bin/env bash
# Script to build standalone macOS binaries on a Mac machine
cd "$(dirname "$0")"

echo "========================================================"
echo "       BUILDING STANDALONE MAC EXECUTABLES              "
echo "========================================================"

# Detect Operating System
OS="$(uname -s)"
if [ "$OS" != "Darwin" ]; then
    echo "[!] Notice: You are running this on $OS (Windows/Linux), not macOS."
    echo "    PyInstaller cannot create Mac binaries while running on Windows."
    echo "    To create a native Mac binary, this script must be run on an actual Mac."
    echo "    (For Windows, use 'build_exe.bat' to generate Windows .exe files)."
    echo ""
fi

# Detect Python command
if command -v py >/dev/null 2>&1; then
    PY_CMD="py"
elif command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1 && python --version >/dev/null 2>&1; then
    PY_CMD="python"
elif [ -f "$LOCALAPPDATA/Programs/Python/Python315/python.exe" ]; then
    PY_CMD="$LOCALAPPDATA/Programs/Python/Python315/python.exe"
else
    echo "[!] Error: No working Python command found."
    exit 1
fi

echo "[*] Using Python: $PY_CMD"

# Ensure pyinstaller is installed
"$PY_CMD" -m pip install --upgrade pyinstaller

# Clean old builds
rm -rf build dist

echo "[*] Compiling sender..."
"$PY_CMD" -m PyInstaller --onefile --clean --name sender sender.py

echo "[*] Compiling receiver..."
"$PY_CMD" -m PyInstaller --onefile --clean --name receiver receiver.py

# Copy to root directory
cp -f dist/sender ./sender_mac
cp -f dist/receiver ./receiver_mac
chmod +x ./sender_mac ./receiver_mac

echo ""
echo "[✔] Done! 'sender_mac' and 'receiver_mac' have been built."
