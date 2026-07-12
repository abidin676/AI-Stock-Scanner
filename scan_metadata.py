from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

from runtime_io import atomic_write_json


SCAN_METADATA_FILE = Path("output") / "scan_metadata.json"
SCAN_MANIFEST_FILE = Path("output") / "scan_run_manifest.json"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_mode(mode: str | None) -> str:
    return safe_text(mode, "ALL").upper().replace("_", " ").strip()


def expected_markets_for_mode(mode: str | None) -> list[str]:
    normalized = normalize_mode(mode)
    if normalized == "ALL":
        return ["SET", "USA"]
    if normalized.startswith("SET"):
        return ["SET"]
    if normalized.startswith("USA"):
        return ["USA"]
    return []


def market_values(values: Iterable[Any]) -> list[str]:
    seen = []
    for value in values:
        market = safe_text(value).upper()
        if market and market not in seen:
            seen.append(market)
    return seen


def default_market_diagnostic(market: str, status: str = "NOT_REQUESTED") -> dict[str, Any]:
    return {
        "Market": market,
        "ProviderName": "",
        "RequestedSymbols": 0,
        "LoadedSymbols": 0,
        "ProcessedRows": 0,
        "FailedSymbols": 0,
        "NoDataSymbols": 0,
        "CachedSymbols": 0,
        "DownloadedSymbols": 0,
        "ErrorCount": 0,
        "ElapsedSeconds": 0.0,
        "Status": status,
        "ErrorSummary": "",
    }


def diagnostic_from_timing(timing: Mapping[str, Any]) -> dict[str, Any]:
    market = safe_text(timing.get("Market")).upper()
    requested = safe_int(timing.get("SymbolsRequested", timing.get("Symbols")))
    loaded = safe_int(timing.get("LoadedCount"))
    processed = safe_int(timing.get("RowsProcessed"))
    no_data = safe_int(timing.get("NoDataCount"))
    error = safe_text(timing.get("Error"))
    error_count = safe_int(timing.get("ErrorCount"), 1 if error else 0)
    status = safe_text(timing.get("Status")).upper()

    if not status:
        if requested <= 0:
            status = "FAILED"
        elif error_count > 0 and loaded <= 0:
            status = "FAILED"
        elif loaded <= 0:
            status = "FAILED"
        elif no_data > 0:
            status = "PARTIAL"
        else:
            status = "OK"

    return {
        "Market": market,
        "ProviderName": safe_text(timing.get("ProviderName")),
        "RequestedSymbols": requested,
        "LoadedSymbols": loaded,
        "ProcessedRows": processed,
        "FailedSymbols": safe_int(timing.get("FailedCount")),
        "NoDataSymbols": no_data,
        "CachedSymbols": safe_int(timing.get("CachedCount")),
        "DownloadedSymbols": safe_int(timing.get("DownloadedCount")),
        "ErrorCount": error_count,
        "ElapsedSeconds": float(timing.get("Total Time", 0) or 0),
        "Status": status,
        "ErrorSummary": error,
    }


def build_scan_metadata(
    requested_mode: str,
    scan_timings: list[Mapping[str, Any]] | None = None,
    result_rows: Mapping[str, int] | None = None,
    symbol_counts: Mapping[str, int] | None = None,
    errors: Mapping[str, str] | None = None,
    completed_at: str | None = None,
    scan_run_id: str | None = None,
) -> dict[str, Any]:
    timings = list(scan_timings or [])
    rows = {
        "SET": safe_int((result_rows or {}).get("SET")),
        "USA": safe_int((result_rows or {}).get("USA")),
    }
    symbols = {
        "SET": safe_int((symbol_counts or {}).get("SET")),
        "USA": safe_int((symbol_counts or {}).get("USA")),
    }
    errors = {
        "SET": safe_text((errors or {}).get("SET")),
        "USA": safe_text((errors or {}).get("USA")),
    }
    requested = normalize_mode(requested_mode)
    expected = expected_markets_for_mode(requested)
    executed = market_values(timing.get("Market") for timing in timings)
    diagnostics = {
        "SET": default_market_diagnostic("SET"),
        "USA": default_market_diagnostic("USA"),
    }

    for timing in timings:
        diagnostic = diagnostic_from_timing(timing)
        market = diagnostic["Market"]
        if market in diagnostics:
            diagnostics[market] = diagnostic

    for market in expected:
        if diagnostics[market]["Status"] == "NOT_REQUESTED":
            diagnostics[market]["Status"] = "FAILED"

    warnings = []
    for market in expected:
        market_status = diagnostics[market]["Status"]
        if market_status == "FAILED":
            warnings.append(
                f"{market} scan requested but no valid {market} results were produced. "
                "Check provider, symbol universe, download errors, or cache."
            )
        elif market_status == "PARTIAL":
            warnings.append(
                f"{market} scan completed partially. "
                f"Loaded {diagnostics[market]['LoadedSymbols']} of "
                f"{diagnostics[market]['RequestedSymbols']} requested symbols."
            )
        elif symbols.get(market, 0) <= 0:
            warnings.append(f"{market} provider returned zero requested symbols.")
        elif rows.get(market, 0) <= 0:
            message = (
                f"{market} scan produced zero valid rows. "
                f"Requested symbols: {symbols.get(market, 0)}"
            )
            if errors.get(market):
                message += f". Provider/download error: {errors[market]}"
            warnings.append(message)

    processed_expected = sum(rows.get(market, 0) for market in expected)
    failed_markets = [
        market
        for market in expected
        if diagnostics[market]["Status"] == "FAILED"
        or symbols.get(market, 0) <= 0
        or rows.get(market, 0) <= 0
    ]
    partial_markets = [
        market
        for market in expected
        if diagnostics[market]["Status"] == "PARTIAL"
    ]

    if failed_markets and processed_expected <= 0:
        status = "FAILED"
    elif failed_markets or partial_markets:
        status = "PARTIAL"
    else:
        status = "SUCCESS"

    return {
        "ScanRunId": scan_run_id or datetime.now().strftime("%Y%m%d%H%M%S"),
        "RequestedScanMode": requested,
        "ExecutedScanMode": requested,
        "ExpectedMarkets": expected,
        "ExecutedMarkets": executed,
        "SETSymbolsRequested": symbols["SET"],
        "SETSymbolsProcessed": rows["SET"],
        "USASymbolsRequested": symbols["USA"],
        "USASymbolsProcessed": rows["USA"],
        "ScanCompletedAt": completed_at or now_text(),
        "ScanStatus": status,
        "SETError": errors["SET"],
        "USAError": errors["USA"],
        "MarketDiagnostics": diagnostics,
        "Warnings": warnings,
    }


def save_scan_metadata(metadata: Mapping[str, Any], path: Path = SCAN_METADATA_FILE) -> Path:
    return atomic_write_json(metadata, path)


def save_scan_manifest(manifest: Mapping[str, Any], path: Path = SCAN_MANIFEST_FILE) -> Path:
    return atomic_write_json(manifest, path)


def load_scan_metadata(path: Path = SCAN_METADATA_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_scan_manifest(path: Path = SCAN_MANIFEST_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
