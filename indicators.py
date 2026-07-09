from datetime import datetime
from pathlib import Path
import re

import pandas as pd
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator


INDICATOR_CACHE_DIR = Path("data") / "indicator_cache"
INDICATOR_VERSION = "v2_seed_expansion_20260709"
INDICATOR_COLUMNS = [
    "indicator_version",
    "ema9",
    "ema20",
    "ema50",
    "ema200",
    "rsi",
    "rsi_slope",
    "macd",
    "macd_signal",
    "macd_hist",
    "macd_hist_slope",
    "vol20",
    "rvol",
    "atr",
    "atr20",
    "atr_compression",
    "ema_spread",
    "ema_spread_pct",
    "compression_score",
    "ema_compression",
    "distance_ema20",
    "lowest_close_20",
    "price_above_low_close20_pct",
    "return_5d_pct",
    "return_10d_pct",
    "bullish_candle_streak",
    "wide_range_bullish",
    "wide_range_bullish_count_10",
    "momentum_established",
    "low90",
    "move_from_low90",
    "ema9_slope",
    "ema20_slope",
    "ema50_slope",
    "ema200_slope",
    "ema_alignment",
    "dry_volume",
    "vol5",
    "vol5_vol20",
    "dry_volume_days",
    "dry_volume_score",
    "higher_low",
    "higher_high",
    "trend_change",
    "base_days",
    "high_low_range_10",
    "high_low_range_20",
    "base_tightness_pct",
    "atr_percentile_60",
    "atr_compression_score",
    "days_since_ema20_slope_turn_positive",
    "days_since_ema9_cross_ema20",
    "days_since_breakout",
    "high20",
    "break20",
    "high55",
    "break55",
    "pivot20",
    "near_pivot",
    "strong_close",
    "close_above_prev_high",
    "pocket_pivot",
    "nr7",
    "inside_bar",
    "volume_breakout",
    "pivot_breakout",
]
BOOLEAN_COLUMNS = [
    "atr_compression",
    "ema_compression",
    "dry_volume",
    "higher_low",
    "higher_high",
    "trend_change",
    "break20",
    "break55",
    "near_pivot",
    "strong_close",
    "close_above_prev_high",
    "pocket_pivot",
    "nr7",
    "inside_bar",
    "volume_breakout",
    "pivot_breakout",
    "wide_range_bullish",
    "momentum_established",
]


def consecutive_count(condition):

    count = 0
    values = []

    for value in condition.fillna(False).astype(bool):
        count = count + 1 if value else 0
        values.append(count)

    return pd.Series(
        values,
        index=condition.index,
    )


def days_since_event(condition):

    days = []
    latest_event_index = None

    for index, value in enumerate(condition.fillna(False).astype(bool)):
        if value:
            latest_event_index = index

        if latest_event_index is None:
            days.append(float("nan"))
        else:
            days.append(index - latest_event_index)

    return pd.Series(
        days,
        index=condition.index,
        dtype="float64",
    )


def rolling_last_percentile(series, window=60):

    def percentile(values):
        current = values[-1]

        if pd.isna(current):
            return float("nan")

        valid = pd.Series(values).dropna()

        if valid.empty:
            return float("nan")

        return (
            (valid <= current).sum()
            / len(valid)
            * 100
        )

    return series.rolling(
        window,
        min_periods=20,
    ).apply(
        percentile,
        raw=True,
    )


def indicator_cache_path(
    symbol,
    market="USA",
    period="1y",
    interval="1d",
):

    key = "_".join(
        [
            str(market).upper().strip(),
            str(symbol).upper().strip(),
            str(period).strip(),
            str(interval).strip(),
        ]
    )
    filename = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        key,
    )

    return INDICATOR_CACHE_DIR / f"{filename}.pkl"


def is_indicator_cache_fresh(path):

    if not path.exists():
        return False

    modified_date = datetime.fromtimestamp(
        path.stat().st_mtime
    ).date()

    return modified_date == datetime.now().date()


def has_indicator_columns(df):

    return all(
        column in df.columns
        for column in INDICATOR_COLUMNS
    )


def normalize_indicator_cache(df):

    if df.empty:
        return df

    if "date" in df.columns:
        df["date"] = pd.to_datetime(
            df["date"],
            errors="coerce",
        )

    for column in (
        "symbol",
        "market",
    ):
        if column in df.columns:
            df[column] = df[column].astype(str).str.upper()

    for column in BOOLEAN_COLUMNS:
        if column not in df.columns:
            continue

        if df[column].dtype == bool:
            continue

        df[column] = (
            df[column]
            .astype(str)
            .str.lower()
            .isin(
                [
                    "true",
                    "1",
                    "yes",
                ]
            )
        )

    for column in df.columns:
        if column in (
            "date",
            "symbol",
            "market",
        ) or column in BOOLEAN_COLUMNS:
            continue

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    return df


def load_indicator_cache(path):

    try:
        df = pd.read_pickle(path)
    except Exception:
        return pd.DataFrame()

    if not has_indicator_columns(df):
        return pd.DataFrame()

    return normalize_indicator_cache(df)


def save_indicator_cache(path, df):

    INDICATOR_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    df.to_pickle(path)


def add_indicators_cached(
    df,
    symbol,
    market="USA",
    period="1y",
    interval="1d",
    force_refresh=False,
):

    if has_indicator_columns(df):
        return df, True

    path = indicator_cache_path(
        symbol,
        market,
        period,
        interval,
    )

    if not force_refresh and is_indicator_cache_fresh(path):
        cached = load_indicator_cache(path)

        if not cached.empty:
            return cached, True

    df = add_indicators(df)
    save_indicator_cache(
        path,
        df,
    )

    return df, False


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    เพิ่ม Indicators สำหรับ Scanner
    """

    df["indicator_version"] = INDICATOR_VERSION

    # EMA
    df["ema9"] = EMAIndicator(df["close"], window=9).ema_indicator()
    df["ema20"] = EMAIndicator(df["close"], window=20).ema_indicator()
    df["ema50"] = EMAIndicator(df["close"], window=50).ema_indicator()
    df["ema200"] = EMAIndicator(df["close"], window=200).ema_indicator()

    # RSI
    df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
    # RSI Slope
    df["rsi_slope"] = (
        df["rsi"]
        - df["rsi"].shift(5)
)

    # MACD
    macd = MACD(df["close"])

    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()
   
    # MACD Histogram Slope
    df["macd_hist_slope"] = (
        df["macd_hist"]
        - df["macd_hist"].shift(5)
)

    # Volume
    df["vol20"] = df["volume"].rolling(20).mean()
    df["rvol"] = df["volume"] / df["vol20"]
    df["vol5"] = df["volume"].rolling(5).mean()
    df["vol5_vol20"] = df["vol5"] / df["vol20"]
    # ==========================
    # ATR
    # ==========================

    atr = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14,
    )

    df["atr"] = atr.average_true_range()

    df["atr20"] = df["atr"].rolling(20).mean()

    df["atr_compression"] = df["atr"] < df["atr20"] * 0.85
    atr_low60 = df["atr"].rolling(60, min_periods=20).min()
    atr_high60 = df["atr"].rolling(60, min_periods=20).max()
    df["atr_percentile_60"] = (
        (df["atr"] - atr_low60)
        / (atr_high60 - atr_low60).replace(0, pd.NA)
        * 100
    )
    df["atr_compression_score"] = (
        100
        - df["atr_percentile_60"]
    ).clip(
        lower=0,
        upper=100,
    )

    # ==========================
    # EMA Compression
    # ==========================

    ema_max = df[["ema9", "ema20", "ema50"]].max(axis=1)
    ema_min = df[["ema9", "ema20", "ema50"]].min(axis=1)

    df["ema_spread"] = (
        (ema_max - ema_min)
        / df["close"]
        * 100
    )
    df["ema_spread_pct"] = df["ema_spread"]
    df["compression_score"] = (
        100
        - df["ema_spread_pct"] * 35
    ).clip(
        lower=0,
        upper=100,
    )

    df["ema_compression"] = df["ema_spread"] < 2

    # ==========================
    # Distance EMA20
    # ==========================

    df["distance_ema20"] = (
        (df["close"] - df["ema20"]).abs()
        / df["ema20"]
        * 100
    )
    df["lowest_close_20"] = (
        df["close"]
        .rolling(20)
        .min()
    )
    df["price_above_low_close20_pct"] = (
        (df["close"] - df["lowest_close_20"])
        / df["lowest_close_20"].replace(0, pd.NA)
        * 100
    )
    df["return_5d_pct"] = (
        df["close"]
        / df["close"].shift(5)
        - 1
    ) * 100
    df["return_10d_pct"] = (
        df["close"]
        / df["close"].shift(10)
        - 1
    ) * 100
    bullish_candle = df["close"] > df["open"]
    df["bullish_candle_streak"] = consecutive_count(
        bullish_candle
    )
    df["high_low_range_10"] = (
        (
            df["high"].rolling(10).max()
            - df["low"].rolling(10).min()
        )
        / df["close"].replace(0, pd.NA)
        * 100
    )
    df["high_low_range_20"] = (
        (
            df["high"].rolling(20).max()
            - df["low"].rolling(20).min()
        )
        / df["close"].replace(0, pd.NA)
        * 100
    )
    df["base_tightness_pct"] = df["high_low_range_20"]
    base_condition = (
        (df["high_low_range_20"] <= 18)
        &
        (df["distance_ema20"] <= 8)
        &
        (df["ema_spread_pct"] <= 6)
    )
    df["base_days"] = consecutive_count(base_condition)

    # ==========================
    # 90 Day Low
    # ==========================

    df["low90"] = (
        df["low"]
        .rolling(90)
        .min()
    )

    df["move_from_low90"] = (
        (df["close"] - df["low90"])
        / df["low90"]
        * 100
    )

    # ==========================
    # EMA Slope
    # ==========================
    df["ema9_slope"] = (
        df["ema9"]
        - df["ema9"].shift(5)
    )
    df["ema20_slope"] = (
        df["ema20"]
        - df["ema20"].shift(5)
    )

    df["ema50_slope"] = (
        df["ema50"]
        - df["ema50"].shift(5)
    )

    df["ema200_slope"] = (
        df["ema200"]
        - df["ema200"].shift(20)
    )
    ema20_slope_turn_positive = (
        (df["ema20_slope"] > 0)
        &
        (df["ema20_slope"].shift(1) <= 0)
    )
    df["days_since_ema20_slope_turn_positive"] = days_since_event(
        ema20_slope_turn_positive
    )
    ema9_cross_ema20 = (
        (df["ema9"] >= df["ema20"])
        &
        (df["ema9"].shift(1) < df["ema20"].shift(1))
    )
    df["days_since_ema9_cross_ema20"] = days_since_event(
        ema9_cross_ema20
    )
    # EMA Alignment
    df["ema_alignment"] = (
        (
            (df["ema9"] - df["ema20"]).abs()
            +
            (df["ema20"] - df["ema50"]).abs()
        )
        /
        df["close"].replace(0, pd.NA)
        * 100
    )
    # ==========================
    # Volume Dry Up
    # ==========================

    df["dry_volume"] = (
        df["volume"]
        .rolling(5)
        .mean()
        <
        df["vol20"] * 0.7
    )
    dry_session = df["volume"] < df["vol20"] * 0.75
    df["dry_volume_days"] = (
        dry_session
        .rolling(10)
        .sum()
        .fillna(0)
    )
    df["dry_volume_score"] = (
        df["dry_volume_days"]
        / 5
        * 100
    ).clip(
        lower=0,
        upper=100,
    )

    # ==========================
    # Higher Low
    # ==========================

    df["higher_low"] = (
    df["low"]
    >
    df["low"].rolling(5).min().shift(1)
)

    # ==========================
    # Higher High
    # ==========================

    df["higher_high"] = (
    df["high"]
    >
    df["high"].rolling(5).max().shift(1)
)

    # ==========================
    # Trend Change
    # ==========================

    df["trend_change"] = (
        df["higher_low"]
        &
        (df["ema20_slope"] > 0)
    )

    # ==========================
# Breakout 20 วัน
# ==========================

    df["high20"] = (
        df["high"]
        .rolling(20)
        .max()
        .shift(1)
    )

    df["break20"] = (
        df["close"] > df["high20"]
    )

# ==========================
# Breakout 55 วัน
# ==========================

    df["high55"] = (
        df["high"]
        .rolling(55)
        .max()
        .shift(1)
    )

    df["break55"] = (
        df["close"] > df["high55"]
    )
    df["days_since_breakout"] = days_since_event(
        df["break20"] | df["break55"]
    )

# ==========================
# Pivot High
# ==========================

    df["pivot20"] = (
        df["high"]
        .rolling(20)
        .max()
    )

    df["near_pivot"] = (
        (df["pivot20"] - df["close"])
        / df["pivot20"]
        < 0.03
    )

    # ==========================
# Strong Close
# ==========================

    df["strong_close"] = (
        df["close"]
        >=
        df["low"] + (df["high"] - df["low"]) * 0.75
    )
    candle_range = df["high"] - df["low"]
    avg_range_20 = candle_range.rolling(20).mean()
    df["wide_range_bullish"] = (
        bullish_candle
        &
        (
            candle_range
            >
            avg_range_20 * 1.30
        )
        &
        (
            df["close"]
            >=
            df["low"] + candle_range * 0.60
        )
    )
    df["wide_range_bullish_count_10"] = (
        df["wide_range_bullish"]
        .rolling(10)
        .sum()
        .fillna(0)
    )
    df["momentum_established"] = (
        (df["price_above_low_close20_pct"] > 12)
        |
        (df["return_5d_pct"] > 8)
        |
        (df["return_10d_pct"] > 15)
        |
        (df["bullish_candle_streak"] > 3)
        |
        (df["wide_range_bullish_count_10"] > 2)
        |
        (
            (df["rsi"] > 60)
            &
            (df["ema9"] > df["ema20"])
            &
            (df["close"] > df["ema20"] * 1.03)
        )
    )

# ==========================
# Close Above Previous High
# ==========================

    df["close_above_prev_high"] = (
        df["close"] > df["high"].shift(1)
    )

# ==========================
# Pocket Pivot
# ==========================

    red_day_volume = df["volume"].where(
        df["close"] < df["open"],
        0,
    )
    max_red_volume_10 = (
        red_day_volume
        .rolling(10)
        .max()
        .shift(1)
    )
    df["pocket_pivot"] = (
        (df["close"] > df["open"])
        &
        (df["volume"] > max_red_volume_10)
        &
        (
            (df["close"] > df["ema9"])
            |
            (df["close"] > df["ema20"])
        )
        &
        (
            df["ema20_slope"]
            >=
            -df["ema20"].abs() * 0.002
        )
    )


# ==========================
# NR7
# ==========================

    range_ = df["high"] - df["low"]

    df["nr7"] = (
        range_
        ==
        range_.rolling(7).min()
    )

# ==========================
# Inside Bar
# ==========================

    df["inside_bar"] = (
        (df["high"] < df["high"].shift(1))
        &
        (df["low"] > df["low"].shift(1))
    )

# ==========================
# Volume Breakout
# ==========================

    df["volume_breakout"] = (
        df["rvol"] > 2
    )

# ==========================
# Pivot Breakout
# ==========================

    df["pivot_breakout"] = (
        df["near_pivot"]
        &
        df["break20"]
    )

    return df
