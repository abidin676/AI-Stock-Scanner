@echo off
setlocal EnableExtensions
chcp 65001 >nul
title River Alpha Launcher
cd /d "%~dp0"

set "PYTHON_EXE=venv\Scripts\python.exe"

echo =====================================================
echo              RIVER ALPHA SCANNER
echo =====================================================
echo.

call :check_environment
if errorlevel 1 goto :scan_error

echo [1/2] Scanning fresh SET + USA data...
echo.
"%PYTHON_EXE%" scanner.py --mode ALL --force-refresh
set "SCAN_EXIT_CODE=%ERRORLEVEL%"

if not "%SCAN_EXIT_CODE%"=="0" goto :scan_failed

echo.
echo [2/2] Opening Dashboard...
call "Open Dashboard Only.bat" --from-main
set "DASHBOARD_EXIT_CODE=%ERRORLEVEL%"

if not "%DASHBOARD_EXIT_CODE%"=="0" goto :dashboard_failed

endlocal
exit /b 0

:check_environment
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python environment not found: %PYTHON_EXE%
    echo Run Setup Environment.bat first.
    exit /b 1
)

if not exist "scanner.py" (
    echo ERROR: scanner.py not found.
    exit /b 1
)

if not exist "dashboard.py" (
    echo ERROR: dashboard.py not found.
    exit /b 1
)

if not exist "Open Dashboard Only.bat" (
    echo ERROR: Open Dashboard Only.bat not found.
    exit /b 1
)

"%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Streamlit is not installed in the virtual environment.
    echo Run Setup Environment.bat first.
    exit /b 1
)

exit /b 0

:scan_error
echo.
echo ERROR: Launcher environment check failed. Dashboard was not opened.
pause
endlocal
exit /b 1

:scan_failed
echo.
echo ERROR: Fresh scan failed with exit code %SCAN_EXIT_CODE%.
echo Dashboard was not opened. Last Scan Time was not updated.
pause
endlocal
exit /b %SCAN_EXIT_CODE%

:dashboard_failed
echo.
echo ERROR: Dashboard could not be opened after the successful scan.
pause
endlocal
exit /b %DASHBOARD_EXIT_CODE%
