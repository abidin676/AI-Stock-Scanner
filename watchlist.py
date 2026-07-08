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
    "StrategyMode",
    "StrategySetup",
    "StrategyScore",
    "StrategySignal",
    "StopLoss",
    "Target",
    "Status",
    "Note",
]
NUMERIC_COLUMNS = [
    "Price",
    "Score",
    "StrategyScore",
    "StopLoss",
    "Target",
]


def _empty_watchlist():

    return pd.DataFrame(
        columns=WATCHLIST_COLUMNS
    )


def _normalize_watchlist(df):

    df = df.copy()
    missing_strategy_score = "StrategyScore" not in df.columns

    for column in WATCHLIST_COLUMNS:

        if column not in df.columns:
            df[column] = 0 if column in NUMERIC_COLUMNS else ""

    df = df[WATCHLIST_COLUMNS]

    df["Symbol"] = df["Symbol"].fillna("").astype(str).str.upper().str.strip()
    df["Market"] = df["Market"].fillna("").astype(str).str.upper().str.strip()
    df["AddedDate"] = df["AddedDate"].fillna("")
    df["Setup"] = df["Setup"].fillna("")
    df["Signal"] = df["Signal"].fillna("")
    df["StrategyMode"] = (
        df["StrategyMode"]
        .fillna("")
        .astype(str)
        .replace("", "Standard")
    )
    df["StrategySetup"] = df["StrategySetup"].fillna("")
    df["StrategySignal"] = df["StrategySignal"].fillna("")
    df.loc[df["StrategySetup"] == "", "StrategySetup"] = df["Setup"]
    df.loc[df["StrategySignal"] == "", "StrategySignal"] = df["Signal"]
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

    if missing_strategy_score:
        df["StrategyScore"] = df["Score"]

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
    strategy_mode="Standard",
    strategy_setup="",
    strategy_score=None,
    strategy_signal="",
    stop_loss=0,
    target=0,
    note="",
    status="WATCHING",
):

    df = load_watchlist()
    symbol = str(symbol).upper().strip()
    market = str(market).upper().strip()
    status = str(status).upper().strip() or "WATCHING"
    strategy_score = (
        score
        if strategy_score is None
        else strategy_score
    )

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
        df.loc[index, "StrategyMode"] = strategy_mode or "Standard"
        df.loc[index, "StrategySetup"] = strategy_setup or setup
        df.loc[index, "StrategyScore"] = float(strategy_score or 0)
        df.loc[index, "StrategySignal"] = strategy_signal or signal
        df.loc[index, "StopLoss"] = float(stop_loss or 0)
        df.loc[index, "Target"] = float(target or 0)
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
            "StrategyMode": strategy_mode or "Standard",
            "StrategySetup": strategy_setup or setup,
            "StrategyScore": float(strategy_score or 0),
            "StrategySignal": strategy_signal or signal,
            "StopLoss": float(stop_loss or 0),
            "Target": float(target or 0),
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


def update_watchlist_item(
    symbol,
    market,
    note=None,
    status=None,
    stop_loss=None,
    target=None,
):

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

    if stop_loss is not None:
        df.loc[mask, "StopLoss"] = float(stop_loss or 0)

    if target is not None:
        df.loc[mask, "Target"] = float(target or 0)

    save_watchlist(df)

    return load_watchlist()


def mark_bought(symbol, market):

    return update_watchlist_item(
        symbol,
        market,
        status="BOUGHT",
    )
