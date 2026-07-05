import pandas as pd
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator


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
