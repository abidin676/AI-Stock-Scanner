import pandas as pd

import scanner


def decision_result():
    return {
        "signal": "WATCH",
        "setup": "Test",
        "score": 80,
        "price": 10,
        "rsi": 55,
        "rvol": 1.2,
        "reasons": [],
    }


def strategy_result():
    return {
        "StrategyMode": "standard",
        "StrategySignal": "WATCH",
        "StrategyScore": 80,
        "StrategySetup": "Test",
        "StrategyReasons": [],
    }


def indicator_frame(cross_age, cross_date):
    return pd.DataFrame(
        [
            {
                "date": "2026-07-17",
                "close": 10,
                "ema9": 11,
                "ema20": 10,
                "ema9_cross_date": cross_date,
                "days_since_ema9_cross_ema20": cross_age,
            }
        ]
    )


def run_process(monkeypatch, frame):
    monkeypatch.setattr(
        scanner,
        "add_indicators_cached",
        lambda *args, **kwargs: (frame, False),
    )
    monkeypatch.setattr(scanner, "trend_start", lambda *args, **kwargs: decision_result())
    monkeypatch.setattr(
        scanner,
        "apply_strategy_mode",
        lambda *args, **kwargs: strategy_result(),
    )
    return scanner.process_symbol(
        "TEST.BK",
        "SET",
        pd.DataFrame([{"close": 10}]),
    )["row"]


def test_scanner_outputs_age_zero_only_for_authoritative_cross_event(monkeypatch):
    row = run_process(
        monkeypatch,
        indicator_frame(0.0, "2026-07-17"),
    )

    assert row["DaysSinceEMA9CrossEMA20"] == 0
    assert row["EMABullishCrossToday"] is True
    assert row["LatestPriceDate"] == "2026-07-17"
    assert row["CrossDate"] == "2026-07-17"


def test_scanner_does_not_fallback_to_today_when_cross_history_is_missing(
    monkeypatch,
):
    row = run_process(
        monkeypatch,
        indicator_frame(float("nan"), pd.NaT),
    )

    assert row["DaysSinceEMA9CrossEMA20"] is None
    assert row["DaysSinceEMACross"] is None
    assert row["EMABullishCrossToday"] is False
    assert row["IsFreshEMA9Cross"] is False
    assert row["CrossDate"] == ""


def test_scanner_marks_five_bar_cross_as_old(monkeypatch):
    row = run_process(
        monkeypatch,
        indicator_frame(5.0, "2026-07-10"),
    )

    assert row["DaysSinceEMA9CrossEMA20"] == 5
    assert row["EMABullishCrossToday"] is False
    assert row["IsFreshEMA9Cross"] is False
    assert row["FreshCrossStatus"] == "STALE_CROSS"
    assert row["CrossDate"] == "2026-07-10"
