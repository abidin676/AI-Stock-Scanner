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

    # MACD
    macd = MACD(df["close"])

    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

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
    return df
