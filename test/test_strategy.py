import os
import sys

# เพิ่มโฟลเดอร์หลักของโปรเจกต์เข้า Python Path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from data import get_history
from indicators import add_indicators
from strategy import trend_start

symbol = "AOT"

print(f"Testing {symbol}")

df = get_history(symbol, "SET")

if df.empty:
    print("No data")
    exit()

df = add_indicators(df)

result = trend_start(
    df,
    market="SET",
)

print("\n===== RESULT =====")
print(result)

print("\n===== LAST ROW =====")
print(
    df[[
        "date",
        "close",
        "ema9",
        "ema20",
        "ema50",
        "ema200",
        "rsi",
        "rvol",
        "macd",
        "macd_signal",
    ]].tail(1)
)
