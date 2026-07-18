@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0\.."

set "VENV_SCRIPTS=%CD%\venv\Scripts"
set "PYTHON_EXE=%VENV_SCRIPTS%\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ERROR: River Alpha virtual environment not found: %PYTHON_EXE%
    echo Run the project environment setup before installing the scheduled task.
    endlocal
    exit /b 20
)

set "PATH=%VENV_SCRIPTS%;%PATH%"
python scripts\run_set_paper_scan.py %*
set "RUN_EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %RUN_EXIT_CODE%
