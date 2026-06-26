import sys
from pathlib import Path

import pandas as pd

sys.path.append(
    str(Path(__file__).resolve().parent.parent)
)

from backtest_engine import run_backtest


symbols = [
    "AAPL",
    "MSFT",
    "NVDA",
    "META",
    "AMD",
]

for symbol in symbols:

    trades, scores = run_backtest(
        symbol,
        "USA"
    )

    print("=" * 60)
    print(symbol)

    print("\n========== SCORE ==========\n")

    print(
        scores["Score"].describe()
    )

    print("\n========== DISTRIBUTION ==========\n")

    bins = [0, 40, 50, 60, 70, 80, 90, 100]

    distribution = (
        scores.groupby(
            pd.cut(
                scores["Score"],
                bins=bins,
                include_lowest=True
            ),
            observed=False
        )
        .size()
    )

    print(distribution)

    print("\n========== TRADES ==========\n")

    print(f"Trades : {len(trades)}")

    if not trades.empty:

        print(
            trades[
                [
                    "EntryDate",
                    "ExitDate",
                    "Signal",
                    "Score",
                    "Return",
                ]
            ]
        )

    print("\n")