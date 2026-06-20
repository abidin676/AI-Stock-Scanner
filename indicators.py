import pandas as pd
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

    return df