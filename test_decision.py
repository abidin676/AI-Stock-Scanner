from data import get_history
from indicators import add_indicators
from strategy_engine.decision_engine import make_decision
from strategy import ema_cross_within

symbols = ["NVDA", "MSFT", "AAPL", "AMD"]

for symbol in symbols:

    df = get_history(symbol, "USA")

    if df.empty:
        continue

    df = add_indicators(df)

    decision = make_decision(
        df=df,
        ema_cross_func=ema_cross_within,
        symbol=symbol,
        market="USA",
    )

    print("=" * 60)
    print(symbol)

    print(
        f"Score : {decision['total_score']} / {decision['max_score']}"
    )

    print(
        f"Signal: {decision['signal']}"
    )

    print()

    for engine in (
        "trend",
        "momentum",
        "volume",
        "base",
        "price",
        "stage",
    ):
        e = decision[engine]

        print(
            f"{engine:<10}"
            f"{e['score']:>3}/{e['max_score']}"
            f"   {e['quality']}"
        )

    print("\nReasons")

    for r in decision["reasons"]:
        print("-", r)

    print()