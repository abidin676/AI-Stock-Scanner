from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping

import pandas as pd


try:
    from zoneinfo import ZoneInfo

    BANGKOK_TZ = ZoneInfo("Asia/Bangkok")
except Exception:  # pragma: no cover - Windows fallback when tzdata is absent.
    BANGKOK_TZ = timezone(timedelta(hours=7), name="Asia/Bangkok")


SCHEDULE_TIME = time(16, 45)
TASK_NAME = "RiverAlpha-SET-PaperScan-1645"

EXIT_SUCCESS = 0
EXIT_SCANNER_FAILED = 10
EXIT_FRESHNESS_VALIDATION_FAILED = 11
EXIT_DUPLICATE_PROPOSAL = 12
EXIT_RUNNER_ERROR = 20

METADATA_PATH = Path("output") / "scan_metadata.json"
MANIFEST_PATH = Path("output") / "scan_run_manifest.json"
APPROVAL_QUEUE_PATH = Path("data") / "approval_queue.csv"
PAPER_BROKER_CONFIG_PATH = Path("config") / "paper_broker_config.json"

ROLLBACK_PATHS = (
    Path("data") / "approval_queue.csv",
    Path("data") / "approval_history.csv",
    Path("data") / "paper_portfolio.csv",
    Path("output") / "paper_trading_robot_proposals.csv",
    Path("output") / "paper_trading_robot_audit.csv",
    METADATA_PATH,
    MANIFEST_PATH,
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str = ""


@dataclass
class RuntimeSnapshot:
    files: dict[Path, bytes | None]

    @classmethod
    def capture(cls, project_root: Path) -> "RuntimeSnapshot":
        files: dict[Path, bytes | None] = {}
        for relative_path in ROLLBACK_PATHS:
            path = project_root / relative_path
            files[relative_path] = path.read_bytes() if path.exists() else None
        return cls(files=files)

    def restore(self, project_root: Path) -> None:
        for relative_path, content in self.files.items():
            path = project_root / relative_path
            if content is None:
                if path.exists():
                    path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.rollback.{os.getpid()}.tmp")
            temporary.write_bytes(content)
            os.replace(temporary, path)


class DailyRunLock:
    def __init__(self, path: Path, now: datetime, stale_after: timedelta = timedelta(hours=4)):
        self.path = path
        self.now = now
        self.stale_after = stale_after
        self.acquired = False

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "Pid": os.getpid(),
            "StartedAt": self.now.isoformat(),
        }
        for attempt in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                self.acquired = True
                return True
            except FileExistsError:
                if attempt > 0 or not self._is_stale():
                    return False
                self.path.unlink(missing_ok=True)
        return False

    def _is_stale(self) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            started_at = datetime.fromisoformat(str(payload.get("StartedAt", "")))
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=BANGKOK_TZ)
            return self.now - started_at.astimezone(BANGKOK_TZ) > self.stale_after
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            try:
                modified = datetime.fromtimestamp(self.path.stat().st_mtime, tz=BANGKOK_TZ)
                return self.now - modified > self.stale_after
            except OSError:
                return True

    def release(self) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False


ScannerRunner = Callable[[list[str], Path, logging.Logger, int], CommandResult]


def bangkok_now() -> datetime:
    return datetime.now(BANGKOK_TZ)


def is_scheduled_window(now: datetime) -> bool:
    local_now = now.astimezone(BANGKOK_TZ)
    return local_now.weekday() < 5 and local_now.time() >= SCHEDULE_TIME


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(dict(payload), indent=2), encoding="utf-8")
    os.replace(temporary, path)


def configure_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    logger = logging.getLogger(f"river_alpha_set_automation_{os.getpid()}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def close_logger(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def run_scanner_command(
    command: list[str],
    project_root: Path,
    logger: logging.Logger,
    timeout_seconds: int,
) -> CommandResult:
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(
            part for part in (exc.stdout or "", exc.stderr or "") if part
        )
        logger.error("Scanner timed out after %s seconds", timeout_seconds)
        return CommandResult(returncode=EXIT_SCANNER_FAILED, output=output)
    except OSError as exc:
        logger.error("Scanner process could not start: %s", exc)
        return CommandResult(returncode=EXIT_SCANNER_FAILED, output=str(exc))

    output = "\n".join(
        part for part in (completed.stdout, completed.stderr) if part
    )
    for line in output.splitlines():
        logger.info("[scanner] %s", line)
    return CommandResult(returncode=int(completed.returncode), output=output)


def validate_fresh_set_run(
    project_root: Path,
    previous_scan_run_id: str,
    run_started_epoch: float,
) -> tuple[bool, str, dict[str, Any]]:
    metadata_path = project_root / METADATA_PATH
    manifest_path = project_root / MANIFEST_PATH
    metadata = read_json(metadata_path)
    manifest = read_json(manifest_path)
    scan_run_id = str(metadata.get("ScanRunId", "")).strip()

    if not metadata or not manifest:
        return False, "Missing completion metadata or manifest", {}
    if not scan_run_id or scan_run_id == previous_scan_run_id:
        return False, "ScanRunId was not refreshed", metadata
    if str(manifest.get("ScanRunId", "")).strip() != scan_run_id:
        return False, "Manifest ScanRunId does not match metadata", metadata
    if metadata_path.stat().st_mtime + 2 < run_started_epoch:
        return False, "Completion metadata is older than this run", metadata
    if manifest_path.stat().st_mtime + 2 < run_started_epoch:
        return False, "Scan manifest is older than this run", metadata

    requested_mode = str(metadata.get("RequestedScanMode", "")).strip().upper()
    executed_mode = str(metadata.get("ExecutedScanMode", "")).strip().upper()
    executed_markets = {
        str(value).strip().upper()
        for value in metadata.get("ExecutedMarkets", [])
        if str(value).strip()
    }
    status = str(metadata.get("ScanStatus", "")).strip().upper()
    processed = int(float(metadata.get("SETSymbolsProcessed", 0) or 0))

    if requested_mode != "SET" or executed_mode != "SET":
        return False, f"Expected SET mode, got requested={requested_mode} executed={executed_mode}", metadata
    if executed_markets != {"SET"}:
        return False, f"Expected SET-only execution, got {sorted(executed_markets)}", metadata
    if status not in {"SUCCESS", "PARTIAL"} or processed <= 0:
        return False, f"SET scan did not produce usable fresh rows: status={status} rows={processed}", metadata
    if str(manifest.get("RequestedMode", "")).strip().upper() != "SET":
        return False, "Manifest is not for SET mode", metadata
    if manifest.get("ForceRefresh") is not True:
        return False, "Manifest does not confirm force refresh", metadata
    if {
        str(value).strip().upper()
        for value in manifest.get("CompletedMarkets", [])
        if str(value).strip()
    } != {"SET"}:
        return False, "Manifest does not confirm SET-only completion", metadata
    return True, "", metadata


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def validate_paper_only_config(project_root: Path) -> tuple[bool, str]:
    config = read_json(project_root / PAPER_BROKER_CONFIG_PATH)
    paper_only = config.get("paper_only", True)
    execution_mode = str(config.get("execution_mode", "MANUAL")).strip().upper()
    if paper_only is not True:
        return False, "Live broker execution is not supported: paper_only must be true"
    if execution_mode != "MANUAL":
        return False, "Live broker execution is not supported: execution_mode must be MANUAL"
    return True, ""


def new_pending_set_entries(project_root: Path, scan_run_id: str) -> pd.DataFrame:
    queue = load_csv(project_root / APPROVAL_QUEUE_PATH)
    if queue.empty:
        return queue
    for column in ("ScanRunId", "Symbol", "Market", "Action", "Status", "RobotKey"):
        if column not in queue.columns:
            queue[column] = ""
    entries = queue[
        (queue["ScanRunId"].astype(str) == scan_run_id)
        & (queue["Market"].astype(str).str.upper() == "SET")
        & (queue["Action"].astype(str).str.upper() == "BUY")
        & (queue["Status"].astype(str).str.upper() == "PENDING_APPROVAL")
        & (queue["RobotKey"].astype(str).str.strip() != "")
    ].copy()
    return entries


def validate_no_duplicate_proposals(entries: pd.DataFrame) -> tuple[bool, str]:
    if entries.empty:
        return True, ""
    duplicates = entries.duplicated(subset=["ScanRunId", "Symbol"], keep=False)
    if not duplicates.any():
        return True, ""
    symbols = sorted(entries.loc[duplicates, "Symbol"].astype(str).unique())
    return False, f"Duplicate Symbol + ScanRunId proposals: {', '.join(symbols)}"


def execute_automation(
    project_root: Path,
    *,
    now: datetime | None = None,
    run_now: bool = False,
    timeout_seconds: int = 7200,
    scanner_runner: ScannerRunner = run_scanner_command,
) -> int:
    project_root = project_root.resolve()
    current = (now or bangkok_now()).astimezone(BANGKOK_TZ)
    logs_dir = project_root / "logs"
    log_path = logs_dir / f"set_paper_scan_{current:%Y-%m-%d}.log"
    logger = configure_logger(log_path)
    lock = DailyRunLock(logs_dir / "run_set_paper_scan.lock", current)

    try:
        logger.info("River Alpha scheduled SET paper scan starting")
        logger.info("Bangkok time: %s", current.isoformat())
        logger.info("Project root: %s", project_root)

        if not run_now and not is_scheduled_window(current):
            logger.info("SKIPPED: outside Monday-Friday post-16:45 Asia/Bangkok window")
            return EXIT_SUCCESS

        if not lock.acquire():
            logger.info("DUPLICATE_RUN_SKIPPED: another SET paper scan is already running")
            return EXIT_SUCCESS

        state_path = logs_dir / "set_paper_scan_state.json"
        state = read_json(state_path)
        run_date = current.date().isoformat()
        if state.get("LastSuccessDate") == run_date:
            logger.info(
                "DUPLICATE_RUN_SKIPPED: successful run already recorded for %s (ScanRunId=%s)",
                run_date,
                state.get("ScanRunId", ""),
            )
            return EXIT_SUCCESS

        if not (project_root / "scanner.py").exists():
            logger.error("scanner.py not found under project root")
            return EXIT_RUNNER_ERROR

        paper_only, safety_reason = validate_paper_only_config(project_root)
        if not paper_only:
            logger.error(safety_reason)
            return EXIT_RUNNER_ERROR

        before_metadata = read_json(project_root / METADATA_PATH)
        previous_scan_run_id = str(before_metadata.get("ScanRunId", "")).strip()
        snapshot = RuntimeSnapshot.capture(project_root)
        transaction_committed = False
        run_started_epoch = datetime.now().timestamp()
        command = ["python", "scanner.py", "--mode", "SET", "--force-refresh"]
        logger.info("Running command: %s", " ".join(command))

        try:
            result = scanner_runner(command, project_root, logger, timeout_seconds)
            if result.returncode != 0:
                logger.error("Scanner failed with exit code %s", result.returncode)
                return EXIT_SCANNER_FAILED

            valid, reason, metadata = validate_fresh_set_run(
                project_root,
                previous_scan_run_id,
                run_started_epoch,
            )
            if not valid:
                logger.error("Fresh SET scan validation failed: %s", reason)
                return EXIT_FRESHNESS_VALIDATION_FAILED

            scan_run_id = str(metadata["ScanRunId"])
            entries = new_pending_set_entries(project_root, scan_run_id)
            unique, duplicate_reason = validate_no_duplicate_proposals(entries)
            if not unique:
                logger.error(duplicate_reason)
                return EXIT_DUPLICATE_PROPOSAL

            write_json_atomic(
                state_path,
                {
                    "LastSuccessDate": run_date,
                    "ScanRunId": scan_run_id,
                    "CompletedAt": bangkok_now().isoformat(),
                    "PendingProposalCount": int(len(entries)),
                    "Symbols": sorted(entries["Symbol"].astype(str).tolist()) if not entries.empty else [],
                },
            )
            transaction_committed = True

            if entries.empty:
                logger.info("No eligible SET candidates")
            else:
                logger.info(
                    "SUCCESS: created %s PENDING Approval Queue proposal(s): %s",
                    len(entries),
                    ", ".join(entries["Symbol"].astype(str).tolist()),
                )
            logger.info("ScanRunId: %s", scan_run_id)
            logger.info("No proposal was approved or filled automatically")
            return EXIT_SUCCESS
        finally:
            if not transaction_committed:
                snapshot.restore(project_root)
                logger.warning("Rolled back Approval Queue and paper runtime artifacts for failed run")
    except Exception:
        logger.exception("Runner failed unexpectedly")
        return EXIT_RUNNER_ERROR
    finally:
        lock.release()
        close_logger(logger)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the approval-only River Alpha SET paper scan automation."
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Manual test override for weekday/time validation; duplicate protection remains active.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=7200,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return execute_automation(
        args.project_root,
        run_now=args.run_now,
        timeout_seconds=max(int(args.timeout_seconds), 60),
    )


if __name__ == "__main__":
    raise SystemExit(main())
