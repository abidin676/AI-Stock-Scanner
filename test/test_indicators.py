import pandas as pd

from indicators import add_indicators


def deterministic_ohlcv(rows=240):
    index = pd.RangeIndex(rows)
    base = pd.Series(index, dtype="float64")
    close = 100 + base * 0.08 + ((base % 9) - 4) * 0.18
    open_ = close - ((base % 5) - 2) * 0.05
    spread = 0.8 + (base % 7) * 0.04
    high = pd.concat(
        [
            open_,
            close,
        ],
        axis=1,
    ).max(axis=1) + spread
    low = pd.concat(
        [
            open_,
            close,
        ],
        axis=1,
    ).min(axis=1) - spread * 0.75
    volume = 1000 + (base % 13) * 25

    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=rows, freq="D"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_add_indicators_preserves_length_and_index_alignment():
    raw = deterministic_ohlcv()
    original_index = raw.index.copy()

    result = add_indicators(raw.copy())

    assert len(result) == len(raw)
    assert result.index.equals(original_index)
    assert result["date"].equals(raw["date"])


def test_atr_columns_are_finite_after_warmup_period():
    result = add_indicators(deterministic_ohlcv())
    warm = result.iloc[80:]

    for column in [
        "atr",
        "atr20",
        "atr_percentile_60",
        "atr_compression_score",
    ]:
        values = pd.to_numeric(
            warm[column],
            errors="coerce",
        )
        assert values.notna().all(), column
        assert values.map(pd.notna).all(), column

    assert warm["atr"].gt(0).all()
    assert warm["atr_compression_score"].between(0, 100).all()


def test_indicator_columns_needed_by_scanner_exist():
    result = add_indicators(deterministic_ohlcv())

    expected_columns = {
        "ema9",
        "ema20",
        "ema50",
        "ema200",
        "rsi",
        "rvol",
        "atr",
        "atr20",
        "atr_compression",
        "ema_compression",
        "base_days",
        "dry_volume_days",
        "pocket_pivot",
    }

    assert expected_columns.issubset(result.columns)
