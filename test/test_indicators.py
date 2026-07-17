import pandas as pd
import pytest

from indicators import (
    INDICATOR_VERSION,
    add_indicators,
    days_since_bullish_ema_cross,
    days_since_event,
    indicator_cache_matches_source,
    normalize_indicator_cache,
)


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
        "ema9_bullish_cross",
        "days_since_ema9_cross_ema20",
        "ema9_cross_date",
    }

    assert expected_columns.issubset(result.columns)


def test_days_since_event_counts_trading_bars_not_calendar_days():
    trading_dates = pd.to_datetime(
        [
            "2026-07-02",  # Thursday
            "2026-07-03",  # Friday: cross
            "2026-07-06",  # Monday: one trading bar later
            "2026-07-07",  # Tuesday: two trading bars later
        ]
    )
    cross_event = pd.Series(
        [False, True, False, False],
        index=trading_dates,
    )

    result = days_since_event(cross_event)

    assert result.loc[pd.Timestamp("2026-07-03")] == 0
    assert result.loc[pd.Timestamp("2026-07-06")] == 1
    assert result.loc[pd.Timestamp("2026-07-07")] == 2


@pytest.mark.parametrize(
    ("row_index", "expected_age"),
    [
        (2, 0),
        (3, 1),
        (4, 2),
        (5, 3),
        (7, 5),
    ],
)
def test_days_since_bullish_ema_cross_uses_real_crossover_event(
    row_index,
    expected_age,
):
    ema9 = pd.Series([9, 9, 11, 11, 11, 11, 11, 11], dtype="float64")
    ema20 = pd.Series([10] * len(ema9), dtype="float64")

    ages = days_since_bullish_ema_cross(ema9, ema20)

    assert ages.iloc[row_index] == expected_age


def test_ema9_above_ema20_without_crossover_history_has_no_age():
    ema9 = pd.Series([11, 11, 11, 11], dtype="float64")
    ema20 = pd.Series([10, 10, 10, 10], dtype="float64")

    ages = days_since_bullish_ema_cross(ema9, ema20)

    assert ages.isna().all()
    assert not (ages == 0).any()


def test_never_crossed_ema_series_has_no_age():
    ema9 = pd.Series([9, 9, 9, 9], dtype="float64")
    ema20 = pd.Series([10, 10, 10, 10], dtype="float64")

    ages = days_since_bullish_ema_cross(ema9, ema20)

    assert ages.isna().all()
    assert not (ages == 0).any()


def test_indicator_cache_preserves_version_and_matches_exact_source():
    source = deterministic_ohlcv()
    cached = normalize_indicator_cache(add_indicators(source.copy()))

    assert cached["indicator_version"].iloc[-1] == INDICATOR_VERSION
    assert indicator_cache_matches_source(cached, source)


def test_indicator_cache_rejects_old_indicator_version():
    source = deterministic_ohlcv()
    cached = add_indicators(source.copy())
    cached["indicator_version"] = "old-version"

    assert not indicator_cache_matches_source(cached, source)


def test_indicator_cache_is_rejected_when_latest_provider_bar_changes():
    source = deterministic_ohlcv()
    cached = add_indicators(source.copy())
    changed_source = source.copy()
    changed_source.loc[changed_source.index[-1], "close"] += 1

    assert not indicator_cache_matches_source(cached, changed_source)


def test_indicator_cache_is_rejected_when_provider_revises_history():
    source = deterministic_ohlcv()
    cached = add_indicators(source.copy())
    changed_source = source.copy()
    changed_source.loc[changed_source.index[-2], "close"] += 1

    assert not indicator_cache_matches_source(cached, changed_source)
