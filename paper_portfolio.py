from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
import hashlib
import json

import pandas as pd


PAPER_BROKER_VERSION = "1.0"
PAPER_ACCOUNT_FILE = Path("data") / "paper_account.json"
PAPER_PORTFOLIO_FILE = Path("data") / "paper_portfolio.csv"

ACCOUNT_COLUMNS = [
    "InitialCash",
    "Cash",
    "BuyingPower",
    "MarketValue",
    "TotalEquity",
    "RealizedPnL",
    "UnrealizedPnL",
    "TotalCommission",
    "TotalOrders",
    "TotalFills",
    "OpenPositions",
    "LastUpdated",
    "PaperBrokerVersion",
]

PORTFOLIO_COLUMNS = [
    "Symbol",
    "Market",
    "PositionQty",
    "AverageCost",
    "LastPrice",
    "MarketValue",
    "CostBasis",
    "UnrealizedPnL",
    "UnrealizedReturnPct",
    "RealizedPnL",
    "TotalCommission",
    "StopPrice",
    "TargetPrice",
    "HighestPrice",
    "TrailingStopPrice",
    "ExitReason",
    "ExitTriggeredTime",
    "LastProposalId",
    "LastOrderId",
    "LastFillId",
    "PositionStatus",
    "OpenedTime",
    "UpdatedTime",
    "ClosedTime",
]


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def short_hash(*parts: Any, length: int = 8) -> str:
    text = "|".join(safe_text(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def atomic_write_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
    tmp_path.replace(path)
    return path


def atomic_write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        df.to_csv(handle, index=False)
        handle.flush()
    tmp_path.replace(path)
    return path


def default_account(initial_cash: float = 100000.0) -> dict[str, Any]:
    cash = float(initial_cash)
    return {
        "InitialCash": cash,
        "Cash": cash,
        "BuyingPower": cash,
        "MarketValue": 0.0,
        "TotalEquity": cash,
        "RealizedPnL": 0.0,
        "UnrealizedPnL": 0.0,
        "TotalCommission": 0.0,
        "TotalOrders": 0,
        "TotalFills": 0,
        "OpenPositions": 0,
        "LastUpdated": "",
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }


def normalize_account(account: Mapping[str, Any] | None, initial_cash: float = 100000.0) -> dict[str, Any]:
    data = default_account(initial_cash)
    if account:
        data.update(dict(account))

    for column in [
        "InitialCash",
        "Cash",
        "BuyingPower",
        "MarketValue",
        "TotalEquity",
        "RealizedPnL",
        "UnrealizedPnL",
        "TotalCommission",
    ]:
        data[column] = safe_float(data.get(column), safe_float(default_account(initial_cash).get(column)))

    for column in ["TotalOrders", "TotalFills", "OpenPositions"]:
        data[column] = safe_int(data.get(column))

    data["PaperBrokerVersion"] = safe_text(data.get("PaperBrokerVersion"), PAPER_BROKER_VERSION)
    data["LastUpdated"] = safe_text(data.get("LastUpdated"))
    return data


def load_paper_account(path: Path = PAPER_ACCOUNT_FILE, config: Any | None = None) -> dict[str, Any]:
    initial_cash = safe_float(getattr(config, "initial_cash", 100000.0), 100000.0)
    if not path.exists():
        account = default_account(initial_cash)
        save_paper_account(account, path)
        return account

    try:
        with path.open("r", encoding="utf-8") as handle:
            return normalize_account(json.load(handle), initial_cash)
    except (json.JSONDecodeError, OSError):
        return default_account(initial_cash)


def save_paper_account(account: Mapping[str, Any], path: Path = PAPER_ACCOUNT_FILE) -> None:
    data = normalize_account(account, safe_float(account.get("InitialCash", 100000.0)))
    atomic_write_text(json.dumps(data, indent=2), path)


def normalize_paper_portfolio(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)

    data = df.copy()
    for column in PORTFOLIO_COLUMNS:
        if column not in data.columns:
            data[column] = 0 if column in numeric_portfolio_columns() else ""

    for column in numeric_portfolio_columns():
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).astype(float)

    for column in PORTFOLIO_COLUMNS:
        if column not in numeric_portfolio_columns():
            data[column] = data[column].fillna("").astype(str).str.strip()

    data["Symbol"] = data["Symbol"].str.upper()
    data["Market"] = data["Market"].str.upper()
    data["PositionStatus"] = data["PositionStatus"].str.upper().replace("", "OPEN")
    return data[PORTFOLIO_COLUMNS]


def numeric_portfolio_columns() -> set[str]:
    return {
        "PositionQty",
        "AverageCost",
        "LastPrice",
        "MarketValue",
        "CostBasis",
        "UnrealizedPnL",
        "UnrealizedReturnPct",
        "RealizedPnL",
        "TotalCommission",
        "StopPrice",
        "TargetPrice",
        "HighestPrice",
        "TrailingStopPrice",
    }


def load_paper_portfolio(path: Path = PAPER_PORTFOLIO_FILE) -> pd.DataFrame:
    if not path.exists():
        save_paper_portfolio(pd.DataFrame(columns=PORTFOLIO_COLUMNS), path)
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)

    try:
        return normalize_paper_portfolio(pd.read_csv(path))
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)


def save_paper_portfolio(portfolio_dataframe: pd.DataFrame, path: Path = PAPER_PORTFOLIO_FILE) -> None:
    atomic_write_csv(normalize_paper_portfolio(portfolio_dataframe), path)


def find_position_index(portfolio: pd.DataFrame, symbol: str, market: str) -> int | None:
    if portfolio.empty:
        return None

    matches = portfolio.index[
        (portfolio["Symbol"].astype(str).str.upper() == symbol.upper())
        & (portfolio["Market"].astype(str).str.upper() == market.upper())
        & (portfolio["PositionStatus"].astype(str).str.upper() == "OPEN")
    ].tolist()
    return matches[0] if matches else None


def position_template(symbol: str, market: str, now: str) -> dict[str, Any]:
    return {
        "Symbol": symbol.upper(),
        "Market": market.upper(),
        "PositionQty": 0.0,
        "AverageCost": 0.0,
        "LastPrice": 0.0,
        "MarketValue": 0.0,
        "CostBasis": 0.0,
        "UnrealizedPnL": 0.0,
        "UnrealizedReturnPct": 0.0,
        "RealizedPnL": 0.0,
        "TotalCommission": 0.0,
        "StopPrice": 0.0,
        "TargetPrice": 0.0,
        "HighestPrice": 0.0,
        "TrailingStopPrice": 0.0,
        "ExitReason": "",
        "ExitTriggeredTime": "",
        "LastProposalId": "",
        "LastOrderId": "",
        "LastFillId": "",
        "PositionStatus": "OPEN",
        "OpenedTime": now,
        "UpdatedTime": now,
        "ClosedTime": "",
    }


def refresh_position_marks(row: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    qty = safe_float(item.get("PositionQty"))
    avg = safe_float(item.get("AverageCost"))
    last = safe_float(item.get("LastPrice"))
    market_value = qty * last
    cost_basis = qty * avg
    unrealized = (last - avg) * qty if qty > 0 else 0
    return_pct = unrealized / cost_basis * 100 if cost_basis > 0 else 0

    item["MarketValue"] = round(market_value, 6)
    item["CostBasis"] = round(cost_basis, 6)
    item["UnrealizedPnL"] = round(unrealized, 6)
    item["UnrealizedReturnPct"] = round(return_pct, 6)
    return item


def update_account_totals(account: Mapping[str, Any], portfolio: pd.DataFrame, now: str | None = None) -> dict[str, Any]:
    data = normalize_account(account)
    pf = normalize_paper_portfolio(portfolio)
    open_pf = pf[pf["PositionStatus"] == "OPEN"].copy()
    market_value = safe_float(open_pf["MarketValue"].sum()) if not open_pf.empty else 0
    unrealized = safe_float(open_pf["UnrealizedPnL"].sum()) if not open_pf.empty else 0

    data["MarketValue"] = round(market_value, 6)
    data["UnrealizedPnL"] = round(unrealized, 6)
    data["TotalEquity"] = round(safe_float(data["Cash"]) + market_value, 6)
    data["BuyingPower"] = round(safe_float(data["Cash"]), 6)
    data["OpenPositions"] = int(len(open_pf))
    data["LastUpdated"] = now or now_iso()
    data["PaperBrokerVersion"] = PAPER_BROKER_VERSION
    return data


def update_paper_market_prices(portfolio_dataframe: pd.DataFrame, prices: Mapping[str, Any]) -> pd.DataFrame:
    data = normalize_paper_portfolio(portfolio_dataframe)
    if data.empty:
        return data

    for idx, row in data.iterrows():
        symbol = safe_text(row["Symbol"]).upper()
        market = safe_text(row["Market"]).upper()
        price = safe_float(prices.get(symbol, prices.get(f"{symbol}.{market}", 0))) if prices else 0
        if price <= 0:
            continue

        data.at[idx, "LastPrice"] = price
        refreshed = refresh_position_marks(data.loc[idx].to_dict())
        for column, value in refreshed.items():
            data.at[idx, column] = value

    return normalize_paper_portfolio(data)


def calculate_portfolio_summary(
    portfolio_dataframe: pd.DataFrame,
    account: Mapping[str, Any],
    market_prices: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    portfolio = normalize_paper_portfolio(portfolio_dataframe)
    if market_prices:
        portfolio = update_paper_market_prices(portfolio, market_prices)

    account_data = update_account_totals(account, portfolio)
    open_pf = portfolio[portfolio["PositionStatus"] == "OPEN"].copy()

    market_value = safe_float(open_pf["MarketValue"].sum()) if not open_pf.empty else 0
    realized = safe_float(portfolio["RealizedPnL"].sum()) if not portfolio.empty else 0
    unrealized = safe_float(open_pf["UnrealizedPnL"].sum()) if not open_pf.empty else 0
    total_pnl = realized + unrealized
    initial_cash = safe_float(account_data.get("InitialCash"), 100000)
    total_equity = safe_float(account_data.get("Cash")) + market_value
    largest_position_pct = 0

    if total_equity > 0 and not open_pf.empty:
        largest_position_pct = safe_float(open_pf["MarketValue"].max()) / total_equity * 100

    return {
        "Cash": round(safe_float(account_data.get("Cash")), 6),
        "MarketValue": round(market_value, 6),
        "TotalEquity": round(total_equity, 6),
        "RealizedPnL": round(realized, 6),
        "UnrealizedPnL": round(unrealized, 6),
        "TotalPnL": round(total_pnl, 6),
        "TotalReturnPct": round((total_equity - initial_cash) / initial_cash * 100, 6) if initial_cash > 0 else 0,
        "OpenPositions": int(len(open_pf)),
        "WinningPositions": int((open_pf["UnrealizedPnL"] > 0).sum()) if not open_pf.empty else 0,
        "LosingPositions": int((open_pf["UnrealizedPnL"] < 0).sum()) if not open_pf.empty else 0,
        "LargestPositionPct": round(largest_position_pct, 6),
        "TotalCommission": round(safe_float(account_data.get("TotalCommission")), 6),
    }


def apply_fill_to_portfolio(
    fill: Mapping[str, Any],
    portfolio_dataframe: pd.DataFrame,
    account: Mapping[str, Any],
    config: Any | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any], dict[str, Any]]:
    fill_status = safe_text(fill.get("FillStatus")).upper()
    if fill_status not in {"FILLED", "PARTIALLY_FILLED"}:
        return normalize_paper_portfolio(portfolio_dataframe), normalize_account(account), {}, {}

    now = safe_text(fill.get("FillTime")) or now_iso()
    portfolio = normalize_paper_portfolio(portfolio_dataframe)
    account_data = normalize_account(account, safe_float(getattr(config, "initial_cash", 100000.0), 100000.0))

    symbol = safe_text(fill.get("Symbol")).upper()
    market = safe_text(fill.get("Market")).upper()
    side = safe_text(fill.get("Side")).upper()
    action = safe_text(fill.get("Action", side)).upper()
    qty = safe_float(fill.get("FilledQty"))
    fill_price = safe_float(fill.get("FillPrice"))
    commission = safe_float(fill.get("Commission"))
    net_cash_flow = safe_float(fill.get("NetCashFlow"))
    proposal_id = safe_text(fill.get("ProposalId"))
    order_id = safe_text(fill.get("PaperOrderId"))
    fill_id = safe_text(fill.get("FillId"))
    stop = safe_float(fill.get("StopPrice"))
    target = safe_float(fill.get("TargetPrice"))

    idx = find_position_index(portfolio, symbol, market)
    cash_before = safe_float(account_data.get("Cash"))

    if side == "BUY":
        if idx is None:
            item = position_template(symbol, market, now)
            portfolio = pd.concat([portfolio, pd.DataFrame([item])], ignore_index=True)
            idx = len(portfolio) - 1

        before = portfolio.loc[idx].to_dict()
        old_qty = safe_float(before.get("PositionQty"))
        old_avg = safe_float(before.get("AverageCost"))
        new_qty = old_qty + qty
        new_avg = ((old_qty * old_avg) + (qty * fill_price) + commission) / new_qty if new_qty > 0 else 0
        realized = 0.0

        portfolio.at[idx, "PositionQty"] = round(new_qty, 6)
        portfolio.at[idx, "AverageCost"] = round(new_avg, 6)
        portfolio.at[idx, "LastPrice"] = fill_price
        portfolio.at[idx, "StopPrice"] = stop or safe_float(before.get("StopPrice"))
        portfolio.at[idx, "TargetPrice"] = target or safe_float(before.get("TargetPrice"))
        highest = max(safe_float(before.get("HighestPrice")), fill_price)
        trailing_enabled = bool(getattr(config, "trailing_stop_enabled", True))
        trailing_pct = max(safe_float(getattr(config, "trailing_stop_pct", 5.0)), 0)
        trailing = highest * (1 - trailing_pct / 100) if trailing_enabled and trailing_pct > 0 else 0
        portfolio.at[idx, "HighestPrice"] = round(highest, 6)
        portfolio.at[idx, "TrailingStopPrice"] = round(
            max(
                safe_float(before.get("TrailingStopPrice")),
                stop,
                trailing,
            ),
            6,
        )
        portfolio.at[idx, "ExitReason"] = ""
        portfolio.at[idx, "ExitTriggeredTime"] = ""
        portfolio.at[idx, "PositionStatus"] = "OPEN"
        portfolio.at[idx, "ClosedTime"] = ""

    else:
        if idx is None:
            raise ValueError("INSUFFICIENT_POSITION")

        before = portfolio.loc[idx].to_dict()
        old_qty = safe_float(before.get("PositionQty"))
        old_avg = safe_float(before.get("AverageCost"))
        sell_qty = min(qty, old_qty)
        new_qty = max(old_qty - sell_qty, 0)
        realized = (fill_price - old_avg) * sell_qty - commission

        portfolio.at[idx, "PositionQty"] = round(new_qty, 6)
        portfolio.at[idx, "AverageCost"] = round(old_avg if new_qty > 0 else 0, 6)
        portfolio.at[idx, "LastPrice"] = fill_price
        portfolio.at[idx, "RealizedPnL"] = round(safe_float(before.get("RealizedPnL")) + realized, 6)
        portfolio.at[idx, "StopPrice"] = stop or safe_float(before.get("StopPrice"))
        portfolio.at[idx, "TargetPrice"] = target or safe_float(before.get("TargetPrice"))
        if new_qty <= 0:
            portfolio.at[idx, "PositionStatus"] = "CLOSED"
            portfolio.at[idx, "ClosedTime"] = now

    portfolio.at[idx, "TotalCommission"] = round(safe_float(portfolio.at[idx, "TotalCommission"]) + commission, 6)
    portfolio.at[idx, "LastProposalId"] = proposal_id
    portfolio.at[idx, "LastOrderId"] = order_id
    portfolio.at[idx, "LastFillId"] = fill_id
    portfolio.at[idx, "UpdatedTime"] = now

    refreshed = refresh_position_marks(portfolio.loc[idx].to_dict())
    for column, value in refreshed.items():
        portfolio.at[idx, column] = value

    cash_after = cash_before + net_cash_flow
    account_data["Cash"] = round(cash_after, 6)
    account_data["RealizedPnL"] = round(safe_float(account_data.get("RealizedPnL")) + realized, 6)
    account_data["TotalCommission"] = round(safe_float(account_data.get("TotalCommission")) + commission, 6)
    account_data["TotalOrders"] = safe_int(account_data.get("TotalOrders")) + 1
    account_data["TotalFills"] = safe_int(account_data.get("TotalFills")) + 1
    account_data = update_account_totals(account_data, portfolio, now=now)

    after = portfolio.loc[idx].to_dict()
    trade_id = f"PT-{market}-{symbol}-{action}-{now[:10].replace('-', '')}-{short_hash(proposal_id, order_id, fill_id, qty, fill_price)}"
    cash_id = f"PC-{market}-{symbol}-{action}-{now[:10].replace('-', '')}-{short_hash(trade_id, net_cash_flow)}"

    trade = {
        "TradeId": trade_id,
        "ProposalId": proposal_id,
        "PaperOrderId": order_id,
        "FillId": fill_id,
        "Symbol": symbol,
        "Market": market,
        "Action": action,
        "Side": side,
        "Quantity": qty,
        "ReferencePrice": safe_float(fill.get("ReferencePrice")),
        "FillPrice": fill_price,
        "GrossValue": safe_float(fill.get("GrossValue")),
        "Commission": commission,
        "NetCashFlow": net_cash_flow,
        "AverageCostBefore": safe_float(before.get("AverageCost")),
        "AverageCostAfter": safe_float(after.get("AverageCost")),
        "PositionQtyBefore": safe_float(before.get("PositionQty")),
        "PositionQtyAfter": safe_float(after.get("PositionQty")),
        "RealizedPnL": round(realized, 6),
        "CashBefore": round(cash_before, 6),
        "CashAfter": round(cash_after, 6),
        "TradeTime": now,
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }
    cash_row = {
        "CashTransactionId": cash_id,
        "TradeId": trade_id,
        "ProposalId": proposal_id,
        "TransactionType": "BUY" if side == "BUY" else "SELL",
        "Symbol": symbol,
        "Market": market,
        "Amount": round(net_cash_flow, 6),
        "CashBefore": round(cash_before, 6),
        "CashAfter": round(cash_after, 6),
        "Description": f"{action} {qty:g} {symbol} @ {fill_price:g}",
        "TransactionTime": now,
    }

    return normalize_paper_portfolio(portfolio), account_data, trade, cash_row
