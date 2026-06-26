import pandas as pd
from metrics import calculate_metrics
from config import (
    START_CAPITAL,
    RISK_PER_TRADE,
)

START_CAPITAL = 100000
RISK_PER_TRADE = 1.0      # ลงเต็มพอร์ต

def build_equity(trades):

    capital = START_CAPITAL

    equity = []

    for _, row in trades.iterrows():

        capital *= (
            1 + row["Return"] / 100
        )

        equity.append({

            "ExitDate":
                row["ExitDate"],

            "Capital":
                round(capital,2),

            "Return":
                row["Return"]

        })

    return pd.DataFrame(equity)

from backtest_engine import run_backtest

trades,_ = run_backtest(
    "AAPL",
    "USA"
)

equity = build_equity(trades)

print(equity.tail())

equity.to_excel(
    "output/equity_curve.xlsx",
    index=False
)

equity["Peak"] = (
    equity["Capital"]
    .cummax()
)

equity["Drawdown"] = (
    equity["Capital"]
    /
    equity["Peak"]
    - 1
) * 100

print()

metrics = calculate_metrics(
    trades,
    equity,
    START_CAPITAL
)

print()

print("=" * 50)

print("RIVER ALPHA METRICS")

print("=" * 50)

for k, v in metrics.items():

    print(f"{k:20} : {v}")

print()

print("Saved")

print("output/equity_curve.xlsx")