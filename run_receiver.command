#!/usr/bin/env bash
# macOS double-clickable launcher for Receiver
cd "$(dirname "$0")"

# Find python3 on macOS
if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
else
    echo "[!] Error: Python 3 not found on this Mac."
    echo "Please install Python 3 from python.org or via Homebrew (brew install python3)."
    read -n 1 -s -r -p "Press any key to exit..."
    exit 1
fi

"$PY_BIN" receiver.py --port 5001
echo ""
read -n 1 -s -r -p "Press any key to exit..."
