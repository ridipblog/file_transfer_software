#!/usr/bin/env bash
# macOS double-clickable launcher for Unified App
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
else
    echo "[!] Error: Python 3 not found on this Mac."
    read -n 1 -s -r -p "Press any key to exit..."
    exit 1
fi

"$PY_BIN" app.py
echo ""
read -n 1 -s -r -p "Press any key to exit..."
