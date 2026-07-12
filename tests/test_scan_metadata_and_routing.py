from pathlib import Path

import pandas as pd

import scanner
from runtime_io import atomic_write_csv
from scan_metadata import build_scan_metadata
from views.scanner import opportunity_score_diagnostics, scan_run_ids, scanner_debug_info


def test_all_mode_routes_to_set_and_usa():
    assert scanner.resolve_scan_plan("ALL") == [
        ("SET", "SET"),
        ("USA ALL", "USA"),
    ]


def test_all_mode_merges_set_and_usa_results(monkeypatch):
    captured = {}
    calls = []

    def fake_scan_market(index, market, **kwargs):
        calls.append((index, market))
        row = {
            "Symbol": "AOT.BK" if market == "SET" else "AAPL",
            "Market": market,
            "StrategyScore": 80,
            "Score": 80,
        }
        timing = {
            "Index": index,
            "Market": market,
            "Symbols": 1,
            "SymbolsRequested": 1,
            "LoadedCount": 1,
            "RowsProcessed": 1,
            "NoDataCount": 0,
            "FailedCount": 0,
            "CachedCount": 1,
            "DownloadedCount": 0,
            "ErrorCount": 0,
            "ProviderName": "mock",
            "Status": "OK",
            "Error": "",
            "Total Time": 0,
            "Download Time": 0,
            "Indicator Time": 0,
            "Decision Time": 0,
            "Processing Time": 0,
            "Indicator Cache Hits": 0,
        }
        return pd.DataFrame([row]), timing

    monkeypatch.setattr(scanner, "scan_market", fake_scan_market)
    monkeypatch.setattr(scanner, "update_lifecycle_from_scan", lambda df, strategy_mode: df)
    monkeypatch.setattr(scanner, "save_market_quality_summary", lambda df, seconds, last_scan, scan_run_id=None: (0, pd.DataFrame()))
    monkeypatch.setattr(scanner, "save_opportunity_summary", lambda df, quality: (df, 0))
    monkeypatch.setattr(scanner, "save_priority_summary", lambda df, quality: (df, 0))
    monkeypatch.setattr(scanner, "save_ai_decision_summary", lambda df: (df, 0))
    monkeypatch.setattr(scanner, "save_risk_manager_summary", lambda df: (0, pd.DataFrame(), pd.DataFrame()))
    monkeypatch.setattr(scanner, "run_watchlist_alerts", lambda df: 0)
    monkeypatch.setattr(scanner, "show_summary", lambda df: None)
    monkeypatch.setattr(scanner, "save_profile_report", lambda profile: None)
    monkeypatch.setattr(scanner, "show_performance_report", lambda profile: None)
    monkeypatch.setattr(scanner, "show_scan_duration", lambda timings, total: None)
    monkeypatch.setattr(scanner, "save_scan_metadata", lambda metadata: captured.setdefault("metadata", metadata))
    monkeypatch.setattr(scanner, "save_scan_failures", lambda failures: "output/scan_failures.csv")
    monkeypatch.setattr(scanner, "save_scan_manifest", lambda manifest: captured.setdefault("manifest", manifest))
    def fake_save_results(df):
        captured["results"] = df.copy()
        return 0

    monkeypatch.setattr(scanner, "save_results", fake_save_results)

    scanner.main(mode="ALL", workers=1)

    assert calls == [("SET", "SET"), ("USA ALL", "USA")]
    assert set(captured["results"]["Market"]) == {"SET", "USA"}
    assert captured["metadata"]["MarketDiagnostics"]["SET"]["Status"] == "OK"
    assert captured["metadata"]["MarketDiagnostics"]["USA"]["Status"] == "OK"


def test_all_metadata_reports_set_and_usa_success():
    metadata = build_scan_metadata(
        requested_mode="ALL",
        scan_timings=[
            {"Index": "SET", "Market": "SET", "SymbolsRequested": 931, "LoadedCount": 931, "RowsProcessed": 931, "Status": "OK"},
            {"Index": "USA ALL", "Market": "USA", "SymbolsRequested": 512, "LoadedCount": 512, "RowsProcessed": 512, "Status": "OK"},
        ],
        result_rows={"SET": 931, "USA": 512},
        symbol_counts={"SET": 931, "USA": 512},
        errors={},
        completed_at="2026-07-11 10:00:00",
        scan_run_id="scan-1",
    )

    assert metadata["RequestedScanMode"] == "ALL"
    assert metadata["ExecutedScanMode"] == "ALL"
    assert metadata["ExecutedMarkets"] == ["SET", "USA"]
    assert metadata["SETSymbolsProcessed"] == 931
    assert metadata["USASymbolsProcessed"] == 512
    assert metadata["ScanStatus"] == "SUCCESS"
    assert metadata["ScanRunId"] == "scan-1"
    assert metadata["MarketDiagnostics"]["USA"]["Status"] == "OK"
    assert metadata["Warnings"] == []


def test_all_metadata_warns_when_usa_has_zero_rows():
    metadata = build_scan_metadata(
        requested_mode="ALL",
        scan_timings=[
            {"Index": "SET", "Market": "SET", "SymbolsRequested": 931, "LoadedCount": 931, "RowsProcessed": 931, "Status": "OK"},
            {
                "Index": "USA ALL",
                "Market": "USA",
                "SymbolsRequested": 512,
                "LoadedCount": 0,
                "RowsProcessed": 0,
                "Status": "FAILED",
                "Error": "download timeout",
                "ErrorCount": 1,
            },
        ],
        result_rows={"SET": 931, "USA": 0},
        symbol_counts={"SET": 931, "USA": 512},
        errors={"USA": "download timeout"},
        completed_at="2026-07-11 10:00:00",
    )

    assert metadata["ScanStatus"] == "PARTIAL"
    assert metadata["USASymbolsRequested"] == 512
    assert metadata["USASymbolsProcessed"] == 0
    assert metadata["USAError"] == "download timeout"
    assert metadata["MarketDiagnostics"]["USA"]["Status"] == "FAILED"
    assert any("USA scan requested" in warning for warning in metadata["Warnings"])


def test_set_only_metadata_reports_usa_not_requested():
    metadata = build_scan_metadata(
        requested_mode="SET100",
        scan_timings=[
            {"Index": "SET100", "Market": "SET", "SymbolsRequested": 84, "LoadedCount": 84, "RowsProcessed": 84, "Status": "OK"},
        ],
        result_rows={"SET": 84},
        symbol_counts={"SET": 84},
        errors={},
        completed_at="2026-07-11 10:00:00",
        scan_run_id="set-only",
    )

    assert metadata["ScanStatus"] == "SUCCESS"
    assert metadata["MarketDiagnostics"]["SET"]["Status"] == "OK"
    assert metadata["MarketDiagnostics"]["USA"]["Status"] == "NOT_REQUESTED"


def test_dashboard_status_prefers_completed_scan_metadata_over_stale_columns(tmp_path):
    result_path = tmp_path / "scanner_results.csv"
    result_path.write_text("Symbol,Market,ScanMode\nAOT.BK,SET,SET100\n", encoding="utf-8")
    data = pd.DataFrame(
        [
            {"Symbol": "AOT.BK", "Market": "SET", "ScanMode": "SET100"},
            {"Symbol": "AAPL", "Market": "USA", "ScanMode": "SET100"},
        ]
    )
    metadata = {
        "RequestedScanMode": "ALL",
        "ExecutedScanMode": "ALL",
        "ExecutedMarkets": ["SET", "USA"],
        "SETSymbolsRequested": 931,
        "SETSymbolsProcessed": 1,
        "USASymbolsRequested": 512,
        "USASymbolsProcessed": 1,
        "ScanCompletedAt": "2026-07-11 10:00:00",
        "ScanStatus": "SUCCESS",
        "USAError": "",
        "ScanRunId": "scan-2",
        "Warnings": [],
    }

    info = scanner_debug_info(data, result_path, metadata)

    assert info["ScanMode"] == "ALL"
    assert info["RequestedScanMode"] == "ALL"
    assert info["ExecutedScanMode"] == "ALL"
    assert info["ExecutedMarkets"] == "SET, USA"
    assert info["Loaded rows"] == 2
    assert info["SET rows"] == 1
    assert info["USA rows"] == 1


def test_scan_run_id_mismatch_is_detectable():
    scanner_df = pd.DataFrame([{"ScanRunId": "scan-a"}])
    priority_df = pd.DataFrame([{"ScanRunId": "scan-b"}])

    assert scan_run_ids(scanner_df) == {"scan-a"}
    assert scan_run_ids(priority_df) != {"scan-a"}


def test_opportunity_score_scale_not_mixed():
    data = pd.DataFrame(
        {
            "OpportunityScore": [0, 10, 58.42, 100],
            "Market": ["SET", "SET", "USA", "USA"],
            "LifecycleState": ["SKIP", "WATCH", "SEED", "BREAKOUT"],
        }
    )

    diagnostics = opportunity_score_diagnostics(data)

    assert diagnostics["source"] == "OpportunityScore"
    assert diagnostics["max"] == 100
    assert diagnostics["zero_count"] == 1
    assert diagnostics["market_counts"] == {"SET": 2, "USA": 2}


def test_atomic_output_does_not_mix_runs(tmp_path):
    path = tmp_path / "scanner_results.csv"

    atomic_write_csv(
        pd.DataFrame([{"ScanRunId": "old-run", "Symbol": "OLD"}]),
        path,
        index=False,
    )
    atomic_write_csv(
        pd.DataFrame(
            [
                {"ScanRunId": "new-run", "Symbol": "NEW1"},
                {"ScanRunId": "new-run", "Symbol": "NEW2"},
            ]
        ),
        path,
        index=False,
    )

    written = pd.read_csv(path)

    assert set(written["ScanRunId"]) == {"new-run"}
    assert written["Symbol"].tolist() == ["NEW1", "NEW2"]


def test_scanner_source_does_not_execute_paper_orders():
    source = Path("scanner.py").read_text(encoding="utf-8")

    forbidden_calls = [
        "execute_approved_proposal(",
        "submit_paper_order(",
        "execute_paper_order(",
        "create_paper_order(",
        "cancel_paper_order(",
    ]

    for call in forbidden_calls:
        assert call not in source
