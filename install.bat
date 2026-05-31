@echo off
chcp 65001 >nul
echo Installing Research Report Monitor...
if not exist "venv" python -m venv venv
call venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install -r requirements.txt
if not exist "reports" mkdir reports
if not exist "data" mkdir data
if not exist "logs" mkdir logs
echo Done! Run: venv\Scripts\activate.bat then python main.py
pause
