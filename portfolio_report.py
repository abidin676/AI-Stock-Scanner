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

    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    
    return round(float(close.iloc[-1]), 2)

portfolio = pd.read_csv(PORTFOLIO_FILE)
rows = []

for _, row in portfolio.iterrows():
    last_price = get_last_price(row["Symbol"], row["Market"])
    if last_price is None:
        print(f"Skipping symbol {row['Symbol']} as it was not found.")
        continue

    value = row["Qty"] * last_price
    cost = row["Qty"] * row["BuyPrice"]
    pnl = value - cost
    pnl_pct = pnl / cost * 100

    rows.append({
        "Symbol": row["Symbol"],
        "Qty": row["Qty"],
        "Buy": row["BuyPrice"],
        "Last": round(last_price,2),
        "Value": round(value,2),
        "PnL": round(pnl,2),
        "PnL %": round(pnl_pct,2)
    })

report = pd.DataFrame(rows)
print(report)

report.to_excel("output/portfolio_report.xlsx", index=False)

print()
print("Saved")
print("output/portfolio_report.xlsx")