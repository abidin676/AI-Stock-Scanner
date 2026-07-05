import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from data import get_history
from indicators import add_indicators
from strategy import trend_start

symbols = [
    ("AAPL", "USA"),
    ("AOT.BK", "SET"),
    ("CPALL.BK", "SET"),
]

for symbol, market in symbols:

    print("=" * 60)
    print(symbol)

    df = get_history(symbol, market)

    if df.empty:
        print("No Data")
        continue

    df = add_indicators(df)

    result = trend_start(
        df,
        market=market,
    )

    print(f"Signal : {result['signal']}")
    print(f"Setup  : {result.get('setup', '-')}")
    print(f"Score  : {result['score']}")
    print(f"Price  : {result['price']}")
    print(f"RSI    : {result['rsi']}")
    print(f"RVOL   : {result['rvol']}")

    print("\nReasons")
    for reason in result["reasons"]:
        print(f" - {reason}")
