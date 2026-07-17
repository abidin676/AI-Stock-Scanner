from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_LAUNCHER = PROJECT_ROOT / "AI Stock Scanner.bat"
DASHBOARD_ONLY_LAUNCHER = PROJECT_ROOT / "Open Dashboard Only.bat"


def launcher_text(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_main_launcher_scans_all_fresh_data_before_dashboard():
    source = launcher_text(MAIN_LAUNCHER)
    scan_command = '"%PYTHON_EXE%" scanner.py --mode ALL --force-refresh'
    dashboard_command = 'call "Open Dashboard Only.bat" --from-main'

    assert "[1/2] Scanning fresh SET + USA data..." in source
    assert "[2/2] Opening Dashboard..." in source
    assert scan_command in source
    assert source.index(scan_command) < source.index(dashboard_command)
    assert 'set "SCAN_EXIT_CODE=%ERRORLEVEL%"' in source
    assert 'if not "%SCAN_EXIT_CODE%"=="0" goto :scan_failed' in source
    assert "Dashboard was not opened" in source
    assert "pause" in source[source.index(":scan_failed") :]


def test_dashboard_only_launcher_never_runs_scanner_and_reuses_streamlit():
    source = launcher_text(DASHBOARD_ONLY_LAUNCHER)

    assert "scanner.py" not in source
    assert "streamlit" in source
    assert ":find_existing_dashboard" in source
    assert "dashboard.pid" in source
    assert "DASHBOARD_ACTION=REUSE" in source
    assert ">\"!PID_FILE!\" echo !DASHBOARD_PID! !DASHBOARD_PORT!" in source
    assert "call :wait_for_dashboard" in source
    assert "Start-Process" in source
    assert "-WindowStyle Hidden" in source
