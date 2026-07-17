@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title River Alpha Dashboard
cd /d "%~dp0"

set "PYTHON_EXE=venv\Scripts\python.exe"
set "DASHBOARD_PORT=8501"
set "DASHBOARD_ACTION=START"
set "DASHBOARD_PID="
set "PID_FILE=output\dashboard.pid"

call :check_environment
if errorlevel 1 goto :dashboard_error

call :find_existing_dashboard
if /i "!DASHBOARD_ACTION!"=="REUSE" (
    echo Reusing River Alpha Dashboard on port !DASHBOARD_PORT! ^(PID !DASHBOARD_PID!^).
    call :wait_for_dashboard
    if errorlevel 1 goto :dashboard_error
) else (
    call :find_free_dashboard_port
    if errorlevel 1 goto :dashboard_error

    call :start_dashboard
    if errorlevel 1 goto :dashboard_error

    call :wait_for_dashboard
    if errorlevel 1 goto :dashboard_error
)

start "" "http://localhost:!DASHBOARD_PORT!"

if /i not "%~1"=="--from-main" (
    echo.
    echo Dashboard opened without running a new scan.
    pause
)

endlocal
exit /b 0

:check_environment
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python environment not found: %PYTHON_EXE%
    echo Run Setup Environment.bat first.
    exit /b 1
)

if not exist "dashboard.py" (
    echo ERROR: dashboard.py not found.
    exit /b 1
)

"%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Streamlit is not installed in the virtual environment.
    echo Run Setup Environment.bat first.
    exit /b 1
)

exit /b 0

:find_existing_dashboard
if exist "!PID_FILE!" (
    set "SAVED_DASHBOARD_PID="
    set "SAVED_DASHBOARD_PORT="
    for /f "tokens=1,2" %%P in (!PID_FILE!) do (
        set "SAVED_DASHBOARD_PID=%%P"
        set "SAVED_DASHBOARD_PORT=%%Q"
    )

    call :is_streamlit_dashboard !SAVED_DASHBOARD_PID!
    if /i "!PROCESS_KIND!"=="RIVER_ALPHA" (
        call :find_port_for_pid !SAVED_DASHBOARD_PID!
        if not defined FOUND_DASHBOARD_PORT if defined SAVED_DASHBOARD_PORT (
            set "FOUND_DASHBOARD_PORT=!SAVED_DASHBOARD_PORT!"
        )

        if defined FOUND_DASHBOARD_PORT (
            set "DASHBOARD_PID=!SAVED_DASHBOARD_PID!"
            set "DASHBOARD_PORT=!FOUND_DASHBOARD_PORT!"
            set "DASHBOARD_ACTION=REUSE"
            exit /b 0
        )
    )
)

for %%D in (8501 8502 8503 8504 8505 8506 8507 8508 8509 8510) do (
    set "PORT_PID="
    for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%%D .*LISTENING"') do (
        if not defined PORT_PID set "PORT_PID=%%P"
    )

    if defined PORT_PID (
        call :is_streamlit_dashboard !PORT_PID!
        if /i "!PROCESS_KIND!"=="RIVER_ALPHA" (
            set "DASHBOARD_PID=!PORT_PID!"
            set "DASHBOARD_PORT=%%D"
            set "DASHBOARD_ACTION=REUSE"
            if not exist "output" mkdir "output" >nul 2>&1
            >"!PID_FILE!" echo !DASHBOARD_PID! !DASHBOARD_PORT!
            exit /b 0
        )
    )
)

exit /b 0

:find_port_for_pid
set "FOUND_DASHBOARD_PORT="
if "%~1"=="" exit /b 0

for %%D in (8501 8502 8503 8504 8505 8506 8507 8508 8509 8510) do (
    for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%%D .*LISTENING"') do (
        if "%%P"=="%~1" set "FOUND_DASHBOARD_PORT=%%D"
    )
)

exit /b 0

:is_streamlit_dashboard
set "PROCESS_KIND=OTHER"
if "%~1"=="" exit /b 0

for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter 'ProcessId=%~1' -ErrorAction SilentlyContinue; if ($p -and $p.CommandLine -match '(?i)streamlit' -and $p.CommandLine -match '(?i)dashboard\.py') { 'RIVER_ALPHA' } else { 'OTHER' }"`) do set "PROCESS_KIND=%%K"
exit /b 0

:find_free_dashboard_port
for %%D in (8501 8502 8503 8504 8505 8506 8507 8508 8509 8510) do (
    netstat -ano -p tcp | findstr /R /C:":%%D .*LISTENING" >nul
    if errorlevel 1 (
        set "DASHBOARD_PORT=%%D"
        exit /b 0
    )
)

echo ERROR: No free dashboard port is available from 8501 through 8510.
exit /b 1

:start_dashboard
echo Starting River Alpha Dashboard on port !DASHBOARD_PORT!...
set "DASHBOARD_PID="

for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$python = (Resolve-Path '%PYTHON_EXE%').Path; $dashboard = (Resolve-Path 'dashboard.py').Path; $arguments = @('-m', 'streamlit', 'run', ([char]34 + $dashboard + [char]34), '--server.port=!DASHBOARD_PORT!', '--server.address=localhost', '--server.headless=true', '--browser.gatherUsageStats=false'); $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -PassThru; $process.Id"`) do set "DASHBOARD_PID=%%P"

if not defined DASHBOARD_PID (
    echo ERROR: Streamlit process could not be started.
    exit /b 1
)

if not exist "output" mkdir "output" >nul 2>&1
>"!PID_FILE!" echo !DASHBOARD_PID! !DASHBOARD_PORT!
exit /b 0

:wait_for_dashboard
for /l %%N in (1,1,30) do (
    netstat -ano -p tcp | findstr /R /C:":!DASHBOARD_PORT! .*LISTENING" >nul
    if not errorlevel 1 exit /b 0
    timeout /t 1 /nobreak >nul
)

echo ERROR: Dashboard process did not listen on port !DASHBOARD_PORT! within 30 seconds.
exit /b 1

:dashboard_error
echo.
echo ERROR: Dashboard was not opened.
if /i not "%~1"=="--from-main" pause
endlocal
exit /b 1
