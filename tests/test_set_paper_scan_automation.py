from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pandas as pd

from scripts.run_set_paper_scan import (
    APPROVAL_QUEUE_PATH,
    BANGKOK_TZ,
    CommandResult,
    EXIT_DUPLICATE_PROPOSAL,
    EXIT_RUNNER_ERROR,
    EXIT_SCANNER_FAILED,
    EXIT_SUCCESS,
    MANIFEST_PATH,
    METADATA_PATH,
    execute_automation,
)


RUN_TIME = datetime(2026, 7, 20, 16, 45, tzinfo=BANGKOK_TZ)


def prepare_project(root: Path) -> None:
    (root / "scanner.py").write_text("# scanner fixture\n", encoding="utf-8")
    (root / "output").mkdir()
    (root / "data").mkdir()


def publish_success(
    root: Path,
    *,
    scan_run_id: str,
    queue_rows: list[dict] | None = None,
) -> None:
    metadata = {
        "ScanRunId": scan_run_id,
        "RequestedScanMode": "SET",
        "ExecutedScanMode": "SET",
        "ExecutedMarkets": ["SET"],
        "SETSymbolsProcessed": 900,
        "ScanStatus": "SUCCESS",
    }
    manifest = {
        "ScanRunId": scan_run_id,
        "RequestedMode": "SET",
        "CompletedMarkets": ["SET"],
        "ForceRefresh": True,
        "Status": "SUCCESS",
    }
    (root / METADATA_PATH).write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    (root / MANIFEST_PATH).write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    pd.DataFrame(queue_rows or []).to_csv(root / APPROVAL_QUEUE_PATH, index=False)


def pending(symbol: str, scan_run_id: str) -> dict:
    return {
        "ProposalId": f"PTR-{symbol}-{scan_run_id}",
        "ScanRunId": scan_run_id,
        "RobotKey": f"SET|{symbol}|{scan_run_id}",
        "Symbol": symbol,
        "Market": "SET",
        "Action": "BUY",
        "Status": "PENDING_APPROVAL",
    }


def test_success_runs_exact_set_force_refresh_command_and_keeps_pending_only(tmp_path):
    prepare_project(tmp_path)
    commands: list[list[str]] = []

    def scanner(command, root, logger, timeout):
        commands.append(command)
        publish_success(
            root,
            scan_run_id="set-success-001",
            queue_rows=[pending("AOT.BK", "set-success-001")],
        )
        return CommandResult(0, "scanner success")

    code = execute_automation(
        tmp_path,
        now=RUN_TIME,
        scanner_runner=scanner,
    )

    assert code == EXIT_SUCCESS
    assert commands == [["python", "scanner.py", "--mode", "SET", "--force-refresh"]]
    queue = pd.read_csv(tmp_path / APPROVAL_QUEUE_PATH)
    assert queue.iloc[0]["Status"] == "PENDING_APPROVAL"
    assert set(queue["Market"]) == {"SET"}
    assert "SUCCESS: created 1 PENDING" in (tmp_path / "logs" / "set_paper_scan_2026-07-20.log").read_text(encoding="utf-8")


def test_no_candidates_is_success_with_required_message(tmp_path):
    prepare_project(tmp_path)

    def scanner(command, root, logger, timeout):
        publish_success(root, scan_run_id="set-empty-001")
        return CommandResult(0)

    code = execute_automation(tmp_path, now=RUN_TIME, scanner_runner=scanner)
    log_text = (tmp_path / "logs" / "set_paper_scan_2026-07-20.log").read_text(encoding="utf-8")

    assert code == EXIT_SUCCESS
    assert "No eligible SET candidates" in log_text


def test_schedule_skips_weekend_and_weekday_before_1645(tmp_path):
    prepare_project(tmp_path)
    calls = 0

    def scanner(command, root, logger, timeout):
        nonlocal calls
        calls += 1
        return CommandResult(0)

    saturday = datetime(2026, 7, 18, 16, 45, tzinfo=BANGKOK_TZ)
    too_early = datetime(2026, 7, 20, 16, 44, tzinfo=BANGKOK_TZ)

    assert execute_automation(tmp_path, now=saturday, scanner_runner=scanner) == EXIT_SUCCESS
    assert execute_automation(tmp_path, now=too_early, scanner_runner=scanner) == EXIT_SUCCESS
    assert calls == 0


def test_scanner_failure_rolls_back_queue_and_does_not_record_success(tmp_path):
    prepare_project(tmp_path)
    old_queue = pd.DataFrame([pending("OLD.BK", "old-run")])
    old_queue.to_csv(tmp_path / APPROVAL_QUEUE_PATH, index=False)
    old_bytes = (tmp_path / APPROVAL_QUEUE_PATH).read_bytes()

    def scanner(command, root, logger, timeout):
        pd.DataFrame([pending("NEW.BK", "failed-run")]).to_csv(
            root / APPROVAL_QUEUE_PATH,
            index=False,
        )
        return CommandResult(1, "provider failed")

    code = execute_automation(tmp_path, now=RUN_TIME, scanner_runner=scanner)

    assert code == EXIT_SCANNER_FAILED
    assert (tmp_path / APPROVAL_QUEUE_PATH).read_bytes() == old_bytes
    assert not (tmp_path / "logs" / "set_paper_scan_state.json").exists()
    assert "Rolled back Approval Queue" in (tmp_path / "logs" / "set_paper_scan_2026-07-20.log").read_text(encoding="utf-8")


def test_duplicate_daily_run_does_not_start_scanner_twice(tmp_path):
    prepare_project(tmp_path)
    calls = 0

    def scanner(command, root, logger, timeout):
        nonlocal calls
        calls += 1
        publish_success(root, scan_run_id="set-once-001")
        return CommandResult(0)

    first = execute_automation(tmp_path, now=RUN_TIME, scanner_runner=scanner)
    second = execute_automation(tmp_path, now=RUN_TIME, scanner_runner=scanner)

    assert first == EXIT_SUCCESS
    assert second == EXIT_SUCCESS
    assert calls == 1
    assert "DUPLICATE_RUN_SKIPPED" in (tmp_path / "logs" / "set_paper_scan_2026-07-20.log").read_text(encoding="utf-8")


def test_duplicate_symbol_scan_run_is_rejected_and_rolled_back(tmp_path):
    prepare_project(tmp_path)

    def scanner(command, root, logger, timeout):
        row = pending("DUP.BK", "set-duplicate-001")
        publish_success(root, scan_run_id="set-duplicate-001", queue_rows=[row, row])
        return CommandResult(0)

    code = execute_automation(tmp_path, now=RUN_TIME, scanner_runner=scanner)

    assert code == EXIT_DUPLICATE_PROPOSAL
    assert not (tmp_path / APPROVAL_QUEUE_PATH).exists()


def test_live_execution_config_is_rejected_before_scanner_starts(tmp_path):
    prepare_project(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "paper_broker_config.json").write_text(
        json.dumps({"paper_only": False, "execution_mode": "MANUAL"}),
        encoding="utf-8",
    )
    calls = 0

    def scanner(command, root, logger, timeout):
        nonlocal calls
        calls += 1
        return CommandResult(0)

    code = execute_automation(tmp_path, now=RUN_TIME, scanner_runner=scanner)

    assert code == EXIT_RUNNER_ERROR
    assert calls == 0
    assert "Live broker execution is not supported" in (
        tmp_path / "logs" / "set_paper_scan_2026-07-20.log"
    ).read_text(encoding="utf-8")


def test_runner_has_no_automatic_approve_fill_or_broker_api_path():
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_set_paper_scan.py"
    ).read_text(encoding="utf-8")

    assert "approve_proposal(" not in source
    assert "execute_approved_proposal(" not in source
    assert "execute_paper_order(" not in source
    assert "requests." not in source
    assert "httpx." not in source


def test_task_scripts_require_explicit_whatif_or_mutating_switch():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    installer = (scripts / "install_set_paper_scan_task.ps1").read_text(encoding="utf-8")
    uninstaller = (scripts / "uninstall_set_paper_scan_task.ps1").read_text(encoding="utf-8")
    batch = (scripts / "run_set_paper_scan.bat").read_text(encoding="utf-8")

    assert "[switch]$WhatIf" in installer
    assert "[switch]$Install" in installer
    assert "Register-ScheduledTask" in installer
    assert "[switch]$WhatIf" in uninstaller
    assert "[switch]$Uninstall" in uninstaller
    assert "python scripts\\run_set_paper_scan.py" in batch
