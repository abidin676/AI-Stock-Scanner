from datetime import datetime
from pathlib import Path
import re

import pandas as pd
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator


INDICATOR_CACHE_DIR = Path("data") / "indicator_cache"
INDICATOR_COLUMNS = [
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
    "ema_compression",
    "distance_ema20",
    "low90",
    "move_from_low90",
    "ema9_slope",
    "ema20_slope",
    "ema50_slope",
    "ema200_slope",
    "ema_alignment",
    "dry_volume",
    "higher_low",
    "higher_high",
    "trend_change",
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
]


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

    df["ema_compression"] = df["ema_spread"] < 2

    # ==========================
    # Distance EMA20
    # ==========================

    df["distance_ema20"] = (
        (df["close"] - df["ema20"]).abs()
        / df["ema20"]
        * 100
    )

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

# ==========================
# Close Above Previous High
# ==========================

    df["close_above_prev_high"] = (
        df["close"] > df["high"].shift(1)
    )

# ==========================
# Pocket Pivot
# ==========================

    df["pocket_pivot"] = (
        (df["close"] > df["open"])
        &
        (df["volume"] > df["volume"].shift(1))
        &
        (df["close"] > df["ema20"])
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
