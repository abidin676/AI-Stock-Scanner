import yfinance as yf
import pandas as pd

from indicators import add_indicators
from scoring import calculate_score, signal


def load_watchlist(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]


def scan(symbol):

    try:

        df = yf.download(
            symbol,
            period="2y",
            interval="1d",
            auto_adjust=True,
            progress=False
        )

        if df.empty:
            return None

        # รองรับ yfinance รุ่นใหม่
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # เพิ่ม Indicator
        df = add_indicators(df)

        last = df.iloc[-1]

        score, reasons = calculate_score(last)

        return {
            "Symbol": symbol,
            "Close": round(float(last["Close"]), 2),
            "EMA20": round(float(last["EMA20"]), 2),
            "EMA50": round(float(last["EMA50"]), 2),
            "EMA200": round(float(last["EMA200"]), 2),
            "RSI": round(float(last["RSI"]), 2),
            "Score": score,
            "Signal": signal(score),
            "Reason": " | ".join(reasons)
        }

    except Exception as e:
        print(f"{symbol} : {e}")
        return None


def run_scanner():

    symbols = load_watchlist("watchlists/us100.txt")

    results = []

    print("\nScanning...\n")

    for symbol in symbols:

        result = scan(symbol)

        if result:
            results.append(result)

    df = pd.DataFrame(results)

    if df.empty:
        print("ไม่พบข้อมูล")
        return

    df = df.sort_values("Score", ascending=False)

    print(df.to_string(index=False))