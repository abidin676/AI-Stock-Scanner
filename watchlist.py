from datetime import date
from pathlib import Path

import pandas as pd


WATCHLIST_FILE = Path("data") / "watchlist.csv"
WATCHLIST_STATUSES = [
    "WATCHING",
    "READY",
    "WAIT",
    "PASS",
    "BOUGHT",
]
WATCHLIST_COLUMNS = [
    "Symbol",
    "Market",
    "AddedDate",
    "Price",
    "Setup",
    "Score",
    "Signal",
    "Status",
    "Note",
]
NUMERIC_COLUMNS = [
    "Price",
    "Score",
]


def _empty_watchlist():

    return pd.DataFrame(
        columns=WATCHLIST_COLUMNS
    )


def _normalize_watchlist(df):

    df = df.copy()

    for column in WATCHLIST_COLUMNS:

        if column not in df.columns:
            df[column] = 0 if column in NUMERIC_COLUMNS else ""

    df = df[WATCHLIST_COLUMNS]

    df["Symbol"] = df["Symbol"].fillna("").astype(str).str.upper().str.strip()
    df["Market"] = df["Market"].fillna("").astype(str).str.upper().str.strip()
    df["AddedDate"] = df["AddedDate"].fillna("")
    df["Setup"] = df["Setup"].fillna("")
    df["Signal"] = df["Signal"].fillna("")
    df["Note"] = df["Note"].fillna("")
    df["Status"] = (
        df["Status"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
        .replace("", "WATCHING")
    )

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0).astype(float)

    return df


def load_watchlist():

    WATCHLIST_FILE.parent.mkdir(
        exist_ok=True
    )

    if not WATCHLIST_FILE.exists():

        df = _empty_watchlist()
        save_watchlist(df)
        return df

    df = pd.read_csv(WATCHLIST_FILE)
    df = _normalize_watchlist(df)
    save_watchlist(df)

    return df


def save_watchlist(df):

    WATCHLIST_FILE.parent.mkdir(
        exist_ok=True
    )

    df = _normalize_watchlist(df)

    df.to_csv(
        WATCHLIST_FILE,
        index=False,
    )


def add_to_watchlist(
    symbol,
    market,
    price=0,
    setup="",
    score=0,
    signal="",
    note="",
    status="WATCHING",
):

    df = load_watchlist()
    symbol = str(symbol).upper().strip()
    market = str(market).upper().strip()
    status = str(status).upper().strip() or "WATCHING"

    mask = (
        (df["Symbol"] == symbol)
        &
        (df["Market"] == market)
    )

    if mask.any():
        index = df[mask].index[0]
        df.loc[index, "Price"] = float(price or 0)
        df.loc[index, "Setup"] = setup
        df.loc[index, "Score"] = float(score or 0)
        df.loc[index, "Signal"] = signal
        if note:
            df.loc[index, "Note"] = note
        if df.loc[index, "Status"] == "":
            df.loc[index, "Status"] = status
    else:
        new_row = {
            "Symbol": symbol,
            "Market": market,
            "AddedDate": date.today().isoformat(),
            "Price": float(price or 0),
            "Setup": setup,
            "Score": float(score or 0),
            "Signal": signal,
            "Status": status,
            "Note": note,
        }
        df = pd.concat(
            [
                df,
                pd.DataFrame([new_row]),
            ],
            ignore_index=True,
        )

    save_watchlist(df)

    return load_watchlist()


def update_watchlist_item(symbol, market, note=None, status=None):

    df = load_watchlist()
    symbol = str(symbol).upper().strip()
    market = str(market).upper().strip()
    mask = (
        (df["Symbol"] == symbol)
        &
        (df["Market"] == market)
    )

    if not mask.any():
        return df

    if note is not None:
        df.loc[mask, "Note"] = note

    if status is not None:
        df.loc[mask, "Status"] = str(status).upper().strip()

    save_watchlist(df)

    return load_watchlist()


def mark_bought(symbol, market):

    return update_watchlist_item(
        symbol,
        market,
        status="BOUGHT",
    )
