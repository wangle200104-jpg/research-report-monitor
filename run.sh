#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f "venv/bin/activate" ]; then source venv/bin/activate; fi
python main.py "$@"
