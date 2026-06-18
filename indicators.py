from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

def add_indicators(df):

    df = df.copy()

    df["EMA20"] = EMAIndicator(df["Close"], window=20).ema_indicator()
    df["EMA50"] = EMAIndicator(df["Close"], window=50).ema_indicator()
    df["EMA200"] = EMAIndicator(df["Close"], window=200).ema_indicator()

    df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

    # Average Volume 20 วัน
    df["VOL20"] = df["Volume"].rolling(20).mean()

    # Volume Ratio
    df["VOL_RATIO"] = df["Volume"] / df["VOL20"]

    return df