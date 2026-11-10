#!/bin/bash
# Shell launcher script for Webcam Controller

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Prefer python3.12 when available (required by ai-edge-litert wheels)
PYTHON_BIN="python3"
if command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="python3.12"
fi

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    "$PYTHON_BIN" -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    # Repair venv python symlink if system /usr/bin/python3 was upgraded across minor versions
    if ! .venv/bin/python3 -c "import uvicorn" >/dev/null 2>&1; then
        if [ -d ".venv/lib/python3.12" ] && command -v python3.12 >/dev/null 2>&1; then
            ln -sf "$(command -v python3.12)" .venv/bin/python3
        fi
    fi
    source .venv/bin/activate
fi

# Run python launcher
python3 start.py
