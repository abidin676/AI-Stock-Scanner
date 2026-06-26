from pathlib import Path

import pandas as pd
import yfinance as yf

PORTFOLIO_FILE = Path("data") / "portfolio.csv"


def get_last_price(symbol, market):

    ticker = symbol + ".BK" if market == "SET" else symbol

    df = yf.download(
        ticker,
        period="5d",
        auto_adjust=True,
        progress=False
    )

    if df.empty:
        return None

    close = df["Close"]

    # รองรับ yfinance เวอร์ชันใหม่
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    return float(close.iloc[-1])


portfolio = pd.read_csv(PORTFOLIO_FILE)

rows = []

for _, row in portfolio.iterrows():

    last = get_last_price(
        row["Symbol"],
        row["Market"]
    )

    if last is None:
        continue

    value = row["Qty"] * last

    cost = row["Qty"] * row["BuyPrice"]

    pnl = value - cost

    pnl_pct = pnl / cost * 100

    rows.append({

        "Symbol": row["Symbol"],

        "Qty": row["Qty"],

        "Buy": row["BuyPrice"],

        "Last": round(last,2),

        "Value": round(value,2),

        "PnL": round(pnl,2),

        "PnL %": round(pnl_pct,2)

    })

report = pd.DataFrame(rows)

print(report)

report.to_excel(
    "output/portfolio_report.xlsx",
    index=False
)

print()

print("Saved")

print("output/portfolio_report.xlsx")