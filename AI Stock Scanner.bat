@echo off
title AI Stock Scanner

call venv\Scripts\activate

echo Starting Dashboard...
start "" streamlit run dashboard.py

timeout /t 3 >nul

echo Scanning Market...
python scanner.py

pause