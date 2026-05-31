#!/bin/bash
set -e
echo "Installing Research Report Monitor..."
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then echo "Python 3.8+ required"; exit 1; fi
if [ ! -d "venv" ]; then $PYTHON -m venv venv; fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt
mkdir -p reports data logs
echo "Done! Run: source venv/bin/activate && python main.py"
