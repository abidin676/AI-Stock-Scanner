import pandas as pd

from strategy import ema_cross_within, trend_start


def test_ema_cross_within_detects_recent_cross():
    data = pd.DataFrame(
        {
            "ema9": [9.4, 9.5, 9.8, 10.2, 10.4],
            "ema20": [10.0, 10.0, 10.0, 10.0, 10.1],
        }
    )

    assert ema_cross_within(data, days=3) is True


def test_ema_cross_within_returns_false_without_enough_data():
    data = pd.DataFrame(
        {
            "ema9": [10.2],
            "ema20": [10.0],
        }
    )

    assert ema_cross_within(data, days=3) is False


def test_trend_start_no_data_response_is_stable():
    data = pd.DataFrame(
        {
            "close": [10.0] * 20,
            "ema9": [10.0] * 20,
            "ema20": [10.0] * 20,
            "ema50": [10.0] * 20,
            "ema200": [10.0] * 20,
            "rsi": [50.0] * 20,
            "rvol": [1.0] * 20,
        }
    )

    result = trend_start(data, market="SET")

    assert result == {
        "signal": "NO DATA",
        "setup": "-",
        "passed": False,
        "score": 0,
        "price": None,
        "rsi": None,
        "rvol": None,
        "score_breakdown": {},
        "reasons": ["Not enough data"],
    }
