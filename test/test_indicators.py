import os
import sys

# เพิ่ม Project Root เข้า Python Path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from data import get_history
from indicators import add_indicators


def main():

    symbol = "AOT"

    print(f"Testing Indicators : {symbol}")

    df = get_history(symbol, "SET")

    if df.empty:
        print("❌ No Data")
        return

    df = add_indicators(df)

    print("\n===== Last 5 Rows =====")

    print(
        df[
            [
                "date",
                "close",
                "ema9",
                "ema20",
                "ema50",
                "ema200",
                "rsi",
                "macd",
                "macd_signal",
                "macd_hist",
                "rvol",
            ]
        ].tail()
    )

    print("\n===== Check Columns =====")

    required = [
        "ema9",
        "ema20",
        "ema50",
        "ema200",
        "rsi",
        "macd",
        "macd_signal",
        "macd_hist",
        "rvol",
    ]

    for col in required:

        if col in df.columns:
            print(f"✅ {col}")
        else:
            print(f"❌ {col}")

    print("\nIndicators Test Passed ✅")


if __name__ == "__main__":
    main()