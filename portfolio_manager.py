from pathlib import Path
import pandas as pd

PORTFOLIO_FILE = Path("data") / "portfolio.csv"


def load_portfolio():

    if not PORTFOLIO_FILE.exists():
        return pd.DataFrame(
            columns=[
                "Symbol",
                "Qty",
                "BuyPrice",
                "BuyDate",
                "StopLoss",
                "Target",
                "Market"
            ]
        )

    return pd.read_csv(PORTFOLIO_FILE)


def save_portfolio(df):

    PORTFOLIO_FILE.parent.mkdir(exist_ok=True)

    df.to_csv(
        PORTFOLIO_FILE,
        index=False
    )


def add_position(
    symbol,
    qty,
    buy_price,
    buy_date,
    stop_loss,
    target,
    market
):

    df = load_portfolio()

    if symbol.upper() in df["Symbol"].values:
        print(f"{symbol} already exists")
        return

    new_row = {
        "Symbol": symbol.upper(),
        "Qty": qty,
        "BuyPrice": buy_price,
        "BuyDate": buy_date,
        "StopLoss": stop_loss,
        "Target": target,
        "Market": market
    }

    df = pd.concat(
        [df, pd.DataFrame([new_row])],
        ignore_index=True
    )

    save_portfolio(df)

    print(f"Added {symbol}")

def show_portfolio():

    df = load_portfolio()

    if df.empty:
        print("Portfolio Empty")
        return

    print(df)

def sell_position(symbol):

    df = load_portfolio()

    symbol = symbol.upper()

    if symbol not in df["Symbol"].values:
        print(f"{symbol} not found")
        return

    df = df[df["Symbol"] != symbol]

    save_portfolio(df)

    print(f"Sold {symbol}")

def show_portfolio():

    df = load_portfolio()

    if df.empty:
        print("\nPortfolio Empty\n")
        return

    print("\nCurrent Portfolio\n")
    print(df)

    print(f"\nTotal Positions : {len(df)}")