import yfinance as yf
import pandas as pd
from indicators import add_indicators

def load_watchlist(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]


def scan(symbol):
    try:
        df = yf.download(
            symbol,
            period="6mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="column"
        )

        if df.empty:
            print(f"{symbol} : ไม่มีข้อมูล")
            return None

            df = add_indicators(df)

        # รองรับ yfinance เวอร์ชันใหม่
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df["EMA20"] = df["Close"].ewm(span=20).mean()

        last = df.iloc[-1]

        return {
    "Symbol": symbol,
    "Close": round(float(last["Close"]), 2),
    "EMA20": round(float(last["EMA20"]), 2),
    "EMA50": round(float(last["EMA50"]), 2),
    "EMA200": round(float(last["EMA200"]), 2),
    "RSI": round(float(last["RSI"]), 2),
    "Above EMA20": last["Close"] > last["EMA20"]
}

    except Exception as e:
        print(f"ERROR {symbol}: {e}")
        return None


def main():

    symbols = load_watchlist("watchlists/us100.txt")

    results = []

    for symbol in symbols:
        print(f"Scanning {symbol}...")

        r = scan(symbol)

        if r:
            results.append(r)

    df = pd.DataFrame(results)

    print("\n========== RESULT ==========\n")

    if df.empty:
        print("ไม่พบข้อมูล")
    else:
        print(df)


if __name__ == "__main__":
    main()