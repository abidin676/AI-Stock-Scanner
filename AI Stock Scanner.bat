@echo off
setlocal EnableExtensions
chcp 65001 >nul
title River Alpha v1.5 Launcher
cd /d "%~dp0"

set "APP_VERSION=River Alpha v1.5"
set "PYTHON_EXE=venv\Scripts\python.exe"
set "DASHBOARD_PORT=8501"
set "DASHBOARD_ACTION=START"
set "MARKET=ALL"
set "STRATEGY_DISPLAY=Standard"
set "STRATEGY_ARG=standard"
set "WORKERS=8"
set "FORCE_REFRESH="
set "PURE_EARLY_SUPPORTED=0"

call :print_header
call :check_environment || goto :end
call :select_market
call :select_strategy
call :select_workers
call :select_force_refresh

echo.
set /p START_PROMPT="Press ENTER to Start..."

echo.
echo Activating virtual environment...
call venv\Scripts\activate

echo.
echo Preparing Dashboard...
call :resolve_dashboard_port || goto :end

if /i "%DASHBOARD_ACTION%"=="REUSE" (
    echo Dashboard already running on port %DASHBOARD_PORT%. Reusing it.
) else (
    echo Opening Dashboard on port %DASHBOARD_PORT%...
    start "River Alpha Dashboard" cmd /k ""%PYTHON_EXE%" -m streamlit run dashboard.py --server.port=%DASHBOARD_PORT% --server.headless=true --browser.gatherUsageStats=false"
)

echo.
echo Waiting for Dashboard...
timeout /t 3 /nobreak >nul

echo.
start "" "http://localhost:%DASHBOARD_PORT%"

echo.
echo Scanning Market...
echo Market        : %MARKET%
echo Strategy      : %STRATEGY_DISPLAY%
echo Workers       : %WORKERS%
if /i "%FORCE_CHOICE%"=="Y" echo Force Refresh : Yes
if not /i "%FORCE_CHOICE%"=="Y" echo Force Refresh : No
echo Dashboard     : http://localhost:%DASHBOARD_PORT%
echo.
"%PYTHON_EXE%" scanner.py --mode "%MARKET%" --strategy-mode "%STRATEGY_ARG%" --workers "%WORKERS%" %FORCE_REFRESH%

echo.
echo =========================================
echo Scan Complete
echo Market   : %MARKET%
echo Strategy : %STRATEGY_DISPLAY%
echo =========================================
echo.

:end
pause
endlocal
exit /b

:print_header
echo =========================================
echo %APP_VERSION%
echo =========================================
echo.
exit /b 0

:check_environment
echo Checking environment...

if not exist "scanner.py" (
    echo ERROR: scanner.py not found. Please run this file from the project root.
    exit /b 1
)

if not exist "dashboard.py" (
    echo ERROR: dashboard.py not found. Please run this file from the project root.
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo ERROR: %PYTHON_EXE% not found.
    echo Create or repair the virtual environment before launching River Alpha.
    exit /b 1
)

"%PYTHON_EXE%" -c "import sys; print('Python : ' + sys.version.split()[0])"
if errorlevel 1 (
    echo ERROR: Python in venv is not working.
    exit /b 1
)

"%PYTHON_EXE%" -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo ERROR: Streamlit is not installed in the virtual environment.
    echo Try: %PYTHON_EXE% -m pip install streamlit
    exit /b 1
)

"%PYTHON_EXE%" -c "import strategy_modes; raise SystemExit(0 if strategy_modes.normalize_strategy_mode('pure_early') == 'pure_early' else 1)" >nul 2>nul
if not errorlevel 1 set "PURE_EARLY_SUPPORTED=1"

echo Environment OK.
echo.
exit /b 0

:select_market
echo Market
echo [1] SET50
echo [2] SET100
echo [3] SET All
echo [4] USA Watchlist
echo [5] USA All
echo [6] ALL
echo.
set /p MARKET_CHOICE="Select Market [Default: 6]: "
if "%MARKET_CHOICE%"=="" set "MARKET_CHOICE=6"

if "%MARKET_CHOICE%"=="1" set "MARKET=SET50"
if "%MARKET_CHOICE%"=="2" set "MARKET=SET100"
if "%MARKET_CHOICE%"=="3" set "MARKET=SET All"
if "%MARKET_CHOICE%"=="4" set "MARKET=USA Watchlist"
if "%MARKET_CHOICE%"=="5" set "MARKET=USA All"
if "%MARKET_CHOICE%"=="6" set "MARKET=ALL"

if not "%MARKET_CHOICE%"=="1" if not "%MARKET_CHOICE%"=="2" if not "%MARKET_CHOICE%"=="3" if not "%MARKET_CHOICE%"=="4" if not "%MARKET_CHOICE%"=="5" if not "%MARKET_CHOICE%"=="6" (
    echo Invalid market choice. Using ALL.
    set "MARKET=ALL"
)
exit /b 0

:select_strategy
echo.
echo Strategy
echo [1] Standard
powershell -NoProfile -ExecutionPolicy Bypass -Command "$e=[char]::ConvertFromUtf32(0x1F331); [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); Write-Host ('[2] ' + $e + ' Early')"
if "%PURE_EARLY_SUPPORTED%"=="1" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$e=[char]::ConvertFromUtf32(0x1F331); [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); Write-Host ('[3] ' + $e + ' Pure Early')"
) else (
    echo [3] Pure Early ^(not supported by current Python code^)
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$e=[char]::ConvertFromUtf32(0x1F680); [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); Write-Host ('[4] ' + $e + ' Breakout')"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$e=[char]::ConvertFromUtf32(0x26A1); [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); Write-Host ('[5] ' + $e + ' Momentum')"
echo.
set /p STRATEGY_CHOICE="Select Strategy [Default: 1]: "
if "%STRATEGY_CHOICE%"=="" set "STRATEGY_CHOICE=1"

if "%STRATEGY_CHOICE%"=="1" (
    set "STRATEGY_DISPLAY=Standard"
    set "STRATEGY_ARG=standard"
)
if "%STRATEGY_CHOICE%"=="2" (
    set "STRATEGY_DISPLAY=Early"
    set "STRATEGY_ARG=early"
)
if "%STRATEGY_CHOICE%"=="3" (
    if "%PURE_EARLY_SUPPORTED%"=="1" (
        set "STRATEGY_DISPLAY=Pure Early"
        set "STRATEGY_ARG=pure_early"
    ) else (
        echo Pure Early is not supported by this Python build. Using Standard.
        set "STRATEGY_DISPLAY=Standard"
        set "STRATEGY_ARG=standard"
    )
)
if "%STRATEGY_CHOICE%"=="4" (
    set "STRATEGY_DISPLAY=Breakout"
    set "STRATEGY_ARG=breakout"
)
if "%STRATEGY_CHOICE%"=="5" (
    set "STRATEGY_DISPLAY=Momentum"
    set "STRATEGY_ARG=momentum"
)

if not "%STRATEGY_CHOICE%"=="1" if not "%STRATEGY_CHOICE%"=="2" if not "%STRATEGY_CHOICE%"=="3" if not "%STRATEGY_CHOICE%"=="4" if not "%STRATEGY_CHOICE%"=="5" (
    echo Invalid strategy choice. Using Standard.
    set "STRATEGY_DISPLAY=Standard"
    set "STRATEGY_ARG=standard"
)
exit /b 0

:select_workers
echo.
echo Workers
set /p WORKERS_INPUT="[8]: "
if not "%WORKERS_INPUT%"=="" set "WORKERS=%WORKERS_INPUT%"

echo %WORKERS%| findstr /R "^[1-9][0-9]*$" >nul
if errorlevel 1 (
    echo Invalid workers value. Using 8.
    set "WORKERS=8"
)
exit /b 0

:select_force_refresh
echo.
echo Force Refresh?
set /p FORCE_CHOICE="[Y/N]: "
if /i "%FORCE_CHOICE%"=="Y" set "FORCE_REFRESH=--force-refresh"
exit /b 0

:resolve_dashboard_port
set "DASHBOARD_PORT=8501"
set "DASHBOARD_ACTION=START"
set "PORT_PID="
set "PORT_KIND=OTHER"

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8501 .*LISTENING"') do (
    set "PORT_PID=%%P"
)

if not defined PORT_PID exit /b 0

echo Port 8501 is already in use by PID %PORT_PID%.
for /f "usebackq delims=" %%K in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$cmd=[string](Get-CimInstance Win32_Process -Filter 'ProcessId=%PORT_PID%' -ErrorAction SilentlyContinue).CommandLine; if ($cmd -like '*streamlit*' -and $cmd -like '*dashboard.py*') { 'RIVER_ALPHA' } else { 'OTHER' }"`) do (
    set "PORT_KIND=%%K"
)

if /i "%PORT_KIND%"=="RIVER_ALPHA" (
    set "DASHBOARD_ACTION=REUSE"
    exit /b 0
)

echo Port 8501 does not look like River Alpha Dashboard. Looking for a safe free port...
call :find_free_dashboard_port
if not defined DASHBOARD_PORT (
    echo ERROR: Could not find a free dashboard port from 8502 to 8510.
    exit /b 1
)
exit /b 0

:find_free_dashboard_port
set "DASHBOARD_PORT="
for %%P in (8502 8503 8504 8505 8506 8507 8508 8509 8510) do (
    netstat -ano | findstr /R /C:":%%P .*LISTENING" >nul
    if errorlevel 1 (
        set "DASHBOARD_PORT=%%P"
        exit /b 0
    )
)
exit /b 1
