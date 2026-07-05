from datetime import date
from pathlib import Path

import pandas as pd


PORTFOLIO_FILE = Path("data") / "portfolio.csv"
PORTFOLIO_COLUMNS = [
    "Symbol",
    "Market",
    "EntryDate",
    "EntryPrice",
    "Shares",
    "Setup",
    "Score",
    "Status",
    "ExitDate",
    "ExitPrice",
]


def _empty_portfolio():

    return pd.DataFrame(
        columns=PORTFOLIO_COLUMNS
    )


def _normalize_portfolio(df):

    df = df.copy()

    legacy_map = {
        "Qty": "Shares",
        "BuyPrice": "EntryPrice",
        "BuyDate": "EntryDate",
    }

    for old_column, new_column in legacy_map.items():

        if old_column in df.columns and new_column not in df.columns:
            df[new_column] = df[old_column]

    for column in PORTFOLIO_COLUMNS:

        if column not in df.columns:
            df[column] = ""

    df = df[PORTFOLIO_COLUMNS]

    df["Symbol"] = df["Symbol"].fillna("").astype(str).str.upper().str.strip()
    df["Market"] = df["Market"].fillna("").astype(str).str.upper().str.strip()
    df["Setup"] = df["Setup"].fillna("")
    df["EntryDate"] = df["EntryDate"].fillna("")
    df["ExitDate"] = df["ExitDate"].fillna("")
    df["Status"] = (
        df["Status"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
        .replace("", "OPEN")
    )

    for column in (
        "EntryPrice",
        "Shares",
        "Score",
        "ExitPrice",
    ):
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    return df


def load_portfolio():

    PORTFOLIO_FILE.parent.mkdir(
        exist_ok=True
    )

    if not PORTFOLIO_FILE.exists():

        df = _empty_portfolio()
        save_portfolio(df)
        return df

    df = pd.read_csv(PORTFOLIO_FILE)
    df = _normalize_portfolio(df)
    save_portfolio(df)

    return df


def save_portfolio(df):

    PORTFOLIO_FILE.parent.mkdir(
        exist_ok=True
    )

    df = _normalize_portfolio(df)

    df.to_csv(
        PORTFOLIO_FILE,
        index=False,
    )


def add_position(
    symbol,
    market,
    entry_price,
    shares,
    setup,
    score,
):

    df = load_portfolio()

    new_row = {
        "Symbol": str(symbol).upper().strip(),
        "Market": str(market).upper().strip(),
        "EntryDate": date.today().isoformat(),
        "EntryPrice": float(entry_price),
        "Shares": float(shares),
        "Setup": setup,
        "Score": float(score),
        "Status": "OPEN",
        "ExitDate": "",
        "ExitPrice": "",
    }

    df = pd.concat(
        [
            df,
            pd.DataFrame([new_row]),
        ],
        ignore_index=True,
    )

    save_portfolio(df)

    return load_portfolio()


def close_position(symbol, exit_price):

    df = load_portfolio()
    symbol = str(symbol).upper().strip()
    mask = (
        (df["Symbol"] == symbol)
        &
        (df["Status"] == "OPEN")
    )

    if not mask.any():
        return df

    df.loc[mask, "Status"] = "CLOSED"
    df.loc[mask, "ExitDate"] = date.today().isoformat()
    df.loc[mask, "ExitPrice"] = float(exit_price)

    save_portfolio(df)

    return load_portfolio()
