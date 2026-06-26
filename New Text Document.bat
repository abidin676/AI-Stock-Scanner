@echo off
title AI Stock Scanner

call venv\Scripts\activate

:MENU
cls
echo ==========================
echo     AI STOCK SCANNER
echo ==========================
echo.
echo 1. SET
echo 2. SET100
echo 3. US100
echo 4. Exit
echo.

set /p choice=เลือกตลาด :

if "%choice%"=="1" copy /Y watchlists\set.txt watchlists\current.txt >nul
if "%choice%"=="2" copy /Y watchlists\set100.txt watchlists\current.txt >nul
if "%choice%"=="3" copy /Y watchlists\us100.txt watchlists\current.txt >nul
if "%choice%"=="4" exit

echo.
echo Scanning...
python scanner.py

echo.
echo Opening Dashboard...
start "" streamlit run dashboard.py