from datetime import date
from pathlib import Path

import pandas as pd

from fee_engine import calculate_fee


PORTFOLIO_FILE = Path("data") / "portfolio.csv"
CURRENCY_BY_MARKET = {
    "SET": "THB",
    "USA": "USD",
}

BASE_COLUMNS = [
    "Symbol",
    "Market",
    "Currency",
    "EntryDate",
    "EntryPrice",
    "Shares",
    "Setup",
    "Score",
    "Status",
    "ExitDate",
    "ExitPrice",
]

FEE_COLUMNS = [
    "BuyAmount",
    "BuyCommission",
    "BuyVAT",
    "BuyFee",
    "NetCost",
    "SellAmount",
    "SellCommission",
    "SellVAT",
    "SellFee",
    "NetProceeds",
    "GrossPL",
    "NetPL",
    "NetPLPct",
]

PORTFOLIO_COLUMNS = BASE_COLUMNS + FEE_COLUMNS
NUMERIC_COLUMNS = [
    "EntryPrice",
    "Shares",
    "Score",
    "ExitPrice",
    *FEE_COLUMNS,
]


def _empty_portfolio():

    return pd.DataFrame(
        columns=PORTFOLIO_COLUMNS
    )


def _zero_fee():

    return {
        "commission": 0.0,
        "vat": 0.0,
        "total_fee": 0.0,
    }


def currency_for_market(market):

    market = str(market).upper().strip()

    return CURRENCY_BY_MARKET.get(
        market,
        "UNKNOWN",
    )


def _safe_float(value, default=0.0):

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_fee(amount, market, side):

    try:
        return calculate_fee(
            amount,
            market,
            side,
        )
    except ValueError:
        return _zero_fee()


def _round_money(value):

    return round(
        _safe_float(value),
        6,
    )


def _round_pct(value):

    return round(
        _safe_float(value),
        4,
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
            df[column] = 0 if column in NUMERIC_COLUMNS else ""

    df = df[PORTFOLIO_COLUMNS]

    df["Symbol"] = df["Symbol"].fillna("").astype(str).str.upper().str.strip()
    df["Market"] = df["Market"].fillna("").astype(str).str.upper().str.strip()
    df["Currency"] = df["Market"].apply(currency_for_market)
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

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0).astype(float)

    return _recalculate_portfolio(df)


def _recalculate_portfolio(df):

    df = df.copy()

    for index, row in df.iterrows():
        market = row["Market"]
        shares = _safe_float(row["Shares"])
        entry_price = _safe_float(row["EntryPrice"])
        exit_price = _safe_float(row["ExitPrice"])
        status = str(row["Status"]).upper().strip()

        buy_amount = entry_price * shares
        buy_fee = _safe_fee(
            buy_amount,
            market,
            "BUY",
        )
        net_cost = buy_amount + buy_fee["total_fee"]

        df.loc[index, "BuyAmount"] = _round_money(buy_amount)
        df.loc[index, "BuyCommission"] = _round_money(buy_fee["commission"])
        df.loc[index, "BuyVAT"] = _round_money(buy_fee["vat"])
        df.loc[index, "BuyFee"] = _round_money(buy_fee["total_fee"])
        df.loc[index, "NetCost"] = _round_money(net_cost)

        if status == "CLOSED" and exit_price > 0 and shares > 0:
            sell_amount = exit_price * shares
            sell_fee = _safe_fee(
                sell_amount,
                market,
                "SELL",
            )
            net_proceeds = sell_amount - sell_fee["total_fee"]
            gross_pl = sell_amount - buy_amount
            net_pl = net_proceeds - net_cost
            net_pl_pct = (
                net_pl / net_cost * 100
                if net_cost
                else 0
            )

            df.loc[index, "SellAmount"] = _round_money(sell_amount)
            df.loc[index, "SellCommission"] = _round_money(sell_fee["commission"])
            df.loc[index, "SellVAT"] = _round_money(sell_fee["vat"])
            df.loc[index, "SellFee"] = _round_money(sell_fee["total_fee"])
            df.loc[index, "NetProceeds"] = _round_money(net_proceeds)
            df.loc[index, "GrossPL"] = _round_money(gross_pl)
            df.loc[index, "NetPL"] = _round_money(net_pl)
            df.loc[index, "NetPLPct"] = _round_pct(net_pl_pct)
        else:
            df.loc[index, "SellAmount"] = 0.0
            df.loc[index, "SellCommission"] = 0.0
            df.loc[index, "SellVAT"] = 0.0
            df.loc[index, "SellFee"] = 0.0
            df.loc[index, "NetProceeds"] = 0.0
            df.loc[index, "GrossPL"] = 0.0
            df.loc[index, "NetPL"] = 0.0
            df.loc[index, "NetPLPct"] = 0.0

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

    market = str(market).upper().strip()
    entry_price = float(entry_price)
    shares = float(shares)
    buy_amount = entry_price * shares
    buy_fee = calculate_fee(
        buy_amount,
        market,
        "BUY",
    )
    net_cost = buy_amount + buy_fee["total_fee"]

    new_row = {
        "Symbol": str(symbol).upper().strip(),
        "Market": market,
        "Currency": currency_for_market(market),
        "EntryDate": date.today().isoformat(),
        "EntryPrice": entry_price,
        "Shares": shares,
        "Setup": setup,
        "Score": float(score),
        "Status": "OPEN",
        "ExitDate": "",
        "ExitPrice": 0,
        "BuyAmount": _round_money(buy_amount),
        "BuyCommission": _round_money(buy_fee["commission"]),
        "BuyVAT": _round_money(buy_fee["vat"]),
        "BuyFee": _round_money(buy_fee["total_fee"]),
        "NetCost": _round_money(net_cost),
        "SellAmount": 0,
        "SellCommission": 0,
        "SellVAT": 0,
        "SellFee": 0,
        "NetProceeds": 0,
        "GrossPL": 0,
        "NetPL": 0,
        "NetPLPct": 0,
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
    exit_price = float(exit_price)
    mask = (
        (df["Symbol"] == symbol)
        &
        (df["Status"] == "OPEN")
    )

    if not mask.any():
        return df

    for index in df[mask].index:
        shares = _safe_float(df.loc[index, "Shares"])
        market = df.loc[index, "Market"]
        buy_amount = _safe_float(df.loc[index, "BuyAmount"])
        net_cost = _safe_float(df.loc[index, "NetCost"])
        sell_amount = exit_price * shares
        sell_fee = calculate_fee(
            sell_amount,
            market,
            "SELL",
        )
        net_proceeds = sell_amount - sell_fee["total_fee"]
        gross_pl = sell_amount - buy_amount
        net_pl = net_proceeds - net_cost
        net_pl_pct = (
            net_pl / net_cost * 100
            if net_cost
            else 0
        )

        df.loc[index, "Status"] = "CLOSED"
        df.loc[index, "ExitDate"] = date.today().isoformat()
        df.loc[index, "ExitPrice"] = exit_price
        df.loc[index, "SellAmount"] = _round_money(sell_amount)
        df.loc[index, "SellCommission"] = _round_money(sell_fee["commission"])
        df.loc[index, "SellVAT"] = _round_money(sell_fee["vat"])
        df.loc[index, "SellFee"] = _round_money(sell_fee["total_fee"])
        df.loc[index, "NetProceeds"] = _round_money(net_proceeds)
        df.loc[index, "GrossPL"] = _round_money(gross_pl)
        df.loc[index, "NetPL"] = _round_money(net_pl)
        df.loc[index, "NetPLPct"] = _round_pct(net_pl_pct)

    save_portfolio(df)

    return load_portfolio()
