@echo off
chcp 65001 >nul
title River Alpha Scanner
cd /d "%~dp0"

set "MARKET=ALL"
set "STRATEGY_DISPLAY=Standard"
set "STRATEGY_ARG=standard"
set "WORKERS=8"
set "FORCE_REFRESH="

echo =========================================
echo River Alpha v1.2
echo =========================================
echo.
echo Market
echo [1] SET50
echo [2] SET100
echo [3] SET All
echo [4] USA Watchlist
echo [5] USA All
echo [6] ALL
echo.
set /p MARKET_CHOICE="Select Market [Default: 6]: "

if "%MARKET_CHOICE%"=="1" set "MARKET=SET50"
if "%MARKET_CHOICE%"=="2" set "MARKET=SET100"
if "%MARKET_CHOICE%"=="3" set "MARKET=SET All"
if "%MARKET_CHOICE%"=="4" set "MARKET=USA Watchlist"
if "%MARKET_CHOICE%"=="5" set "MARKET=USA All"
if "%MARKET_CHOICE%"=="6" set "MARKET=ALL"

echo.
echo Strategy
echo [1] Standard
echo [2] 🌱 Early
echo [3] 🚀 Breakout
echo [4] ⚡ Momentum
echo.
set /p STRATEGY_CHOICE="Select Strategy [Default: 1]: "

if "%STRATEGY_CHOICE%"=="1" (
    set "STRATEGY_DISPLAY=Standard"
    set "STRATEGY_ARG=standard"
)
if "%STRATEGY_CHOICE%"=="2" (
    set "STRATEGY_DISPLAY=Early"
    set "STRATEGY_ARG=early"
)
if "%STRATEGY_CHOICE%"=="3" (
    set "STRATEGY_DISPLAY=Breakout"
    set "STRATEGY_ARG=breakout"
)
if "%STRATEGY_CHOICE%"=="4" (
    set "STRATEGY_DISPLAY=Momentum"
    set "STRATEGY_ARG=momentum"
)

echo.
echo Workers
set /p WORKERS_INPUT="[8]: "
if not "%WORKERS_INPUT%"=="" set "WORKERS=%WORKERS_INPUT%"

echo.
echo Force Refresh?
set /p FORCE_CHOICE="[Y/N]: "
if /i "%FORCE_CHOICE%"=="Y" set "FORCE_REFRESH=--force-refresh"

echo.
set /p START_PROMPT="Press ENTER to Start..."

echo.
echo Activating virtual environment...
call venv\Scripts\activate

echo.
echo Opening Dashboard...
powershell -NoProfile -Command "$listeners = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue; foreach ($listener in $listeners) { Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue }"
start "River Alpha Dashboard" cmd /k venv\Scripts\python.exe -m streamlit run dashboard.py --server.port=8501 --server.headless=true --browser.gatherUsageStats=false

echo.
echo Waiting for Dashboard...
timeout /t 3 /nobreak >nul

echo.
start "" http://localhost:8501

echo.
echo Scanning Market...
echo Market   : %MARKET%
echo Strategy : %STRATEGY_DISPLAY%
echo Workers  : %WORKERS%
if /i "%FORCE_CHOICE%"=="Y" echo Force Refresh : Yes
if not /i "%FORCE_CHOICE%"=="Y" echo Force Refresh : No
echo.
python scanner.py --mode "%MARKET%" --strategy-mode %STRATEGY_ARG% --workers %WORKERS% %FORCE_REFRESH%

echo.
echo =========================================
echo Scan Complete
echo Market : %MARKET%
echo Strategy : %STRATEGY_DISPLAY%
echo =========================================
echo.
pause
