from data import get_history
from indicators import add_indicators
from strategy import trend_start

symbol = "ITC"      # เปลี่ยนเป็นหุ้นที่ต้องการ
market = "SET"

df = get_history(symbol, market)

if df.empty:
    print("No Data")
    exit()

df = add_indicators(df)

result = trend_start(
    df,
    market=market,
)

print("=" * 50)
print("Symbol :", symbol)
print("Signal :", result["signal"])
print("Score  :", result["score"])
print("Setup  :", result["setup"])
print("Price  :", result["price"])
print("RSI    :", result["rsi"])
print("RVOL   :", result["rvol"])

print("\nReasons")
for r in result["reasons"]:
    print("-", r)

print("\nScore Breakdown")
for k, v in result["score_breakdown"].items():
    print(f"{k}: {v}")
