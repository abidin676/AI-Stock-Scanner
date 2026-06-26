@echo off
title AI Stock Scanner

call venv\Scripts\activate

echo ==================================
echo      AI STOCK SCANNER
echo ==================================
echo.

echo [1/2] Scanning Market...
python scanner.py

echo.
echo [2/2] Starting Dashboard...
start "" streamlit run dashboard.py

echo.
echo Dashboard is running.
pause