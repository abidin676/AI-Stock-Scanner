import pandas as pd

from backtest_engine import run_backtest


# ==========================================
# SETTINGS
# ==========================================

SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "META",
    "AMD",
]

MARKET = "USA"

START_CAPITAL = 100000


# ==========================================
# LOAD TRADES
# ==========================================

all_trades = []

for symbol in SYMBOLS:

    print(f"Backtesting {symbol}...")

    trades, scores = run_backtest(
        symbol,
        MARKET
    )

    if trades.empty:
        continue

    trades = trades.copy()
    trades["Symbol"] = symbol

    all_trades.append(trades)

if len(all_trades) == 0:
    raise Exception("No Trades Found")


# ==========================================
# MERGE TRADES
# ==========================================

portfolio = pd.concat(
    all_trades,
    ignore_index=True
)

portfolio["ExitDate"] = pd.to_datetime(
    portfolio["ExitDate"]
)

portfolio = portfolio.sort_values(
    "ExitDate"
).reset_index(drop=True)


# ==========================================
# BUILD EQUITY
# ==========================================

capital = START_CAPITAL

equity = []

for _, row in portfolio.iterrows():

    capital *= (
        1 + row["Return"] / 100
    )

    equity.append({

        "Date":
            row["ExitDate"],

        "Capital":
            round(capital, 2),

        "Return":
            row["Return"],

        "Symbol":
            row["Symbol"]

    })

equity = pd.DataFrame(equity)


# ==========================================
# DRAWDOWN
# ==========================================

equity["Peak"] = (
    equity["Capital"]
    .cummax()
)

equity["Drawdown"] = (
    equity["Capital"]
    / equity["Peak"]
    - 1
) * 100


# ==========================================
# SUMMARY
# ==========================================

ending = equity["Capital"].iloc[-1]

total_return = (
    ending / START_CAPITAL - 1
) * 100

print()
print("=" * 60)
print("PORTFOLIO BACKTEST")
print("=" * 60)

print()
print(f"Starting Capital : {START_CAPITAL:,.2f}")

print(f"Ending Capital   : {ending:,.2f}")

print(f"Total Return     : {total_return:.2f}%")

print(f"Trades           : {len(portfolio)}")

print(
    f"Max Drawdown     : "
    f"{equity['Drawdown'].min():.2f}%"
)


# ==========================================
# EXPORT
# ==========================================

equity.to_excel(
    "output/portfolio_equity.xlsx",
    index=False
)

portfolio.to_excel(
    "output/portfolio_trades.xlsx",
    index=False
)

print()
print("Saved")
print("output/portfolio_equity.xlsx")
print("output/portfolio_trades.xlsx")