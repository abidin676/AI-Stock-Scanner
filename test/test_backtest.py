from inspect import signature

import pandas as pd

import backtest_engine as backtest


def fixed_history():
    dates = pd.date_range("2026-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [10.0, 10.4, 10.8, 11.1, 10.9],
            "high": [10.5, 10.9, 11.2, 11.3, 11.0],
            "low": [9.8, 10.2, 10.6, 10.7, 10.5],
            "close": [10.2, 10.8, 11.0, 10.7, 10.6],
            "volume": [1000, 1100, 1200, 900, 850],
            "symbol": ["TEST"] * 5,
            "market": ["USA"] * 5,
        }
    )


def install_backtest_fixtures(monkeypatch, history):
    decisions = [
        {"signal": "BUY", "setup": "Seed", "score": 80},
        {"signal": "BUY", "setup": "Seed", "score": 82},
        {"signal": "WATCH", "setup": "Seed", "score": 65},
        {"signal": "SKIP", "setup": "-", "score": 20},
        {"signal": "SKIP", "setup": "-", "score": 20},
    ]

    def fake_prepare_history(symbol, market, start_date, end_date):
        return history.copy()

    def fake_evaluate_day(day_history, market):
        index = min(len(day_history) - 1, len(decisions) - 1)
        return decisions[index]

    monkeypatch.setattr(backtest, "prepare_history", fake_prepare_history)
    monkeypatch.setattr(backtest, "evaluate_day", fake_evaluate_day)
    monkeypatch.setattr(backtest, "save_results", lambda *args, **kwargs: None)


def test_run_backtest_current_signature():
    params = signature(backtest.run_backtest).parameters

    assert list(params)[:4] == [
        "symbol",
        "market",
        "start_date",
        "end_date",
    ]
    assert "min_score" in params


def test_run_backtest_empty_history_schema(monkeypatch):
    install_backtest_fixtures(
        monkeypatch,
        pd.DataFrame(),
    )

    trades, summary, equity_curve, monthly = backtest.run_backtest(
        "TEST",
        "USA",
        "2026-01-01",
        "2026-01-05",
        min_score=70,
    )

    assert trades.empty
    assert trades.columns.tolist() == backtest.TRADE_COLUMNS
    assert summary.columns.tolist() == backtest.SUMMARY_COLUMNS
    assert equity_curve.columns.tolist() == [
        "Trade",
        "ExitDate",
        "Equity",
        "PeakEquity",
        "DrawdownPct",
        "IsNewHigh",
    ]
    assert monthly.columns.tolist() == backtest.MONTHLY_COLUMNS
    assert summary.iloc[0]["Total Trades"] == 0


def test_run_backtest_deterministic_trade_output(monkeypatch):
    install_backtest_fixtures(
        monkeypatch,
        fixed_history(),
    )

    trades, summary, equity_curve, monthly = backtest.run_backtest(
        "TEST",
        "USA",
        "2026-01-01",
        "2026-01-05",
        min_score=70,
    )

    assert trades.columns.tolist() == backtest.TRADE_COLUMNS
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["Symbol"] == "TEST"
    assert trade["EntrySignal"] == "BUY"
    assert trade["ExitSignal"] == "WATCH"
    assert trade["ExitReason"] == "Signal Changed: BUY -> WATCH"
    assert trade["EntryPrice"] == 10.2
    assert trade["ExitPrice"] == 11.0
    assert trade["HoldingDays"] == 2
    assert summary.iloc[0]["Total Trades"] == 1
    assert len(equity_curve) == 1
    assert monthly[["Year", "Month"]].iloc[0].to_dict() == {
        "Year": 2026,
        "Month": 1,
    }
