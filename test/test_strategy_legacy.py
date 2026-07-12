import pandas as pd

from strategy import ema_cross_within, trend_start


def test_legacy_strategy_import_targets_production_module():
    assert trend_start.__module__ == "strategy"
    assert ema_cross_within.__module__ == "strategy"


def test_ema_cross_within_ignores_old_cross_outside_window():
    data = pd.DataFrame(
        {
            "ema9": [9.5, 10.2, 10.4, 10.5, 10.6, 10.7],
            "ema20": [10.0, 10.0, 10.1, 10.2, 10.3, 10.4],
        }
    )

    assert ema_cross_within(data, days=3) is False


def test_trend_start_empty_frame_returns_no_data():
    result = trend_start(pd.DataFrame(), market="SET")

    assert result["signal"] == "NO DATA"
    assert result["passed"] is False
    assert result["reasons"] == ["Not enough data"]
