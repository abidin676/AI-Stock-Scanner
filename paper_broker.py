from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
import hashlib
import json
import math

import pandas as pd

from approval_queue import ApprovalQueueError, mark_proposal_executed
from paper_portfolio import (
    apply_fill_to_portfolio,
    atomic_write_csv,
    load_paper_account,
    load_paper_portfolio,
    normalize_account,
    normalize_paper_portfolio,
    save_paper_account,
    save_paper_portfolio,
    safe_float,
    safe_text,
)


PAPER_BROKER_VERSION = "1.0"
PAPER_CONFIG_FILE = Path("config") / "paper_broker_config.json"
PAPER_ORDERS_FILE = Path("data") / "paper_orders.csv"
PAPER_FILLS_FILE = Path("data") / "paper_fills.csv"
PAPER_TRADES_FILE = Path("data") / "paper_trades.csv"
PAPER_CASH_LEDGER_FILE = Path("data") / "paper_cash_ledger.csv"
PAPER_EXECUTION_HISTORY_FILE = Path("data") / "paper_execution_history.csv"

ORDER_COLUMNS = [
    "PaperOrderId",
    "ProposalId",
    "Symbol",
    "Market",
    "Action",
    "Side",
    "OrderType",
    "RequestedQty",
    "RequestedPrice",
    "OrderValue",
    "OrderStatus",
    "RejectReason",
    "SubmittedTime",
    "StopPrice",
    "TargetPrice",
    "AIConfidence",
    "RiskScore",
    "PaperBrokerVersion",
]

FILL_COLUMNS = [
    "FillId",
    "PaperOrderId",
    "ProposalId",
    "Symbol",
    "Market",
    "Action",
    "Side",
    "RequestedQty",
    "FilledQty",
    "UnfilledQty",
    "ReferencePrice",
    "FillPrice",
    "GrossValue",
    "Commission",
    "SlippageCost",
    "NetCashFlow",
    "RealizedPnL",
    "FillStatus",
    "RejectReason",
    "FillTime",
    "StopPrice",
    "TargetPrice",
    "PaperBrokerVersion",
]

TRADE_COLUMNS = [
    "TradeId",
    "ProposalId",
    "PaperOrderId",
    "FillId",
    "Symbol",
    "Market",
    "Action",
    "Side",
    "Quantity",
    "ReferencePrice",
    "FillPrice",
    "GrossValue",
    "Commission",
    "NetCashFlow",
    "AverageCostBefore",
    "AverageCostAfter",
    "PositionQtyBefore",
    "PositionQtyAfter",
    "RealizedPnL",
    "CashBefore",
    "CashAfter",
    "TradeTime",
    "PaperBrokerVersion",
]

CASH_LEDGER_COLUMNS = [
    "CashTransactionId",
    "TradeId",
    "ProposalId",
    "TransactionType",
    "Symbol",
    "Market",
    "Amount",
    "CashBefore",
    "CashAfter",
    "Description",
    "TransactionTime",
]

EXECUTION_HISTORY_COLUMNS = [
    "ExecutionId",
    "ProposalId",
    "PaperOrderId",
    "FillId",
    "Symbol",
    "Market",
    "Action",
    "ExecutionStatus",
    "RejectReason",
    "RequestedQty",
    "FilledQty",
    "ReferencePrice",
    "FillPrice",
    "ExecutionTime",
    "Message",
]

ACTION_TO_SIDE = {
    "BUY": "BUY",
    "ADD": "BUY",
    "REDUCE": "SELL",
    "EXIT": "SELL",
}


@dataclass(frozen=True)
class PaperBrokerConfig:
    initial_cash: float = 100000.0
    fill_policy: str = "FULL_FILL"
    price_source: str = "PROPOSAL_ENTRY"
    default_slippage_pct: float = 0.1
    commission_pct: float = 0.157
    minimum_commission: float = 0.0
    allow_partial_fill: bool = False
    partial_fill_pct: float = 50.0
    reject_expired_proposal: bool = True
    reject_duplicate_execution: bool = True
    allow_negative_cash: bool = False
    allow_short_selling: bool = False
    allow_fractional_usa: bool = False
    set_board_lot: int = 100
    auto_mark_executed: bool = True
    require_approved_status: bool = True
    execution_mode: str = "MANUAL"
    paper_broker_version: str = PAPER_BROKER_VERSION


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def safe_upper(value: Any, default: str = "") -> str:
    return safe_text(value, default).upper()


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return safe_upper(value) in {"TRUE", "YES", "Y", "1"}


def normalize_config(config: PaperBrokerConfig | Mapping[str, Any] | None = None) -> PaperBrokerConfig:
    if isinstance(config, PaperBrokerConfig):
        return config

    data: dict[str, Any] = {}
    if PAPER_CONFIG_FILE.exists():
        try:
            data.update(json.loads(PAPER_CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            data = {}

    if isinstance(config, Mapping):
        data.update(dict(config))

    allowed = PaperBrokerConfig.__dataclass_fields__
    values = {key: value for key, value in data.items() if key in allowed}
    return PaperBrokerConfig(**values)


def load_paper_broker_config(path: Path = PAPER_CONFIG_FILE, overrides: Mapping[str, Any] | None = None) -> PaperBrokerConfig:
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            data = {}
    if overrides:
        data.update(dict(overrides))
    return normalize_config(data)


def save_default_paper_broker_config(path: Path = PAPER_CONFIG_FILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(asdict(PaperBrokerConfig()), indent=2), encoding="utf-8")
    return path


def stable_hash(*parts: Any, length: int = 6) -> str:
    text = "|".join(safe_text(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def is_set_market(symbol: str, market: str) -> bool:
    return safe_upper(market) in {"SET", "TH", "THAI"} or safe_upper(symbol).endswith(".BK")


def proposal_id(row: Mapping[str, Any]) -> str:
    return safe_text(row.get("ProposalId"))


def proposal_action(row: Mapping[str, Any]) -> str:
    for column in ["ProposalAction", "Action", "SourceDecision"]:
        action = safe_upper(row.get(column))
        if action in ACTION_TO_SIDE:
            return action
    return ""


def approval_status(row: Mapping[str, Any]) -> str:
    for column in ["Status", "ApprovalStatus", "ProposalStatus"]:
        status = safe_upper(row.get(column))
        if status:
            return status
    return ""


def proposal_quantity(row: Mapping[str, Any]) -> float:
    return safe_float(row.get("ProposedQty", row.get("Quantity", 0)))


def reference_price_from(row: Mapping[str, Any], market_price: float | None = None) -> float:
    if market_price is not None and safe_float(market_price) > 0:
        return safe_float(market_price)
    for column in ["EntryPrice", "Price", "Close"]:
        price = safe_float(row.get(column))
        if price > 0:
            return price
    return 0


def parse_time(value: Any) -> datetime | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def is_expired(row: Mapping[str, Any], now: datetime | None = None) -> bool:
    expire = parse_time(row.get("ExpireTime"))
    return bool(expire and expire < (now or datetime.now()))


def round_quantity(qty: float, symbol: str, market: str, action: str, config: PaperBrokerConfig) -> float:
    if qty <= 0:
        return 0
    if is_set_market(symbol, market):
        if action == "EXIT":
            return round(qty, 6)
        lot = max(int(config.set_board_lot), 1)
        return math.floor(qty / lot) * lot
    if safe_upper(market) == "USA" and not config.allow_fractional_usa:
        return math.floor(qty)
    return round(qty, 4)


def load_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        save_csv(pd.DataFrame(columns=columns), path, columns)
        return pd.DataFrame(columns=columns)
    try:
        data = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in data.columns:
            data[column] = ""
    return data[columns]


def save_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    data = df.copy()
    for column in columns:
        if column not in data.columns:
            data[column] = ""
    atomic_write_csv(data[columns], path)


def append_row(path: Path, columns: list[str], row: Mapping[str, Any]) -> None:
    data = load_csv(path, columns)
    data = pd.concat([data, pd.DataFrame([dict(row)])], ignore_index=True)
    save_csv(data, path, columns)


def successful_fills() -> pd.DataFrame:
    return load_csv(PAPER_FILLS_FILE, FILL_COLUMNS)


def already_executed(proposal: Mapping[str, Any]) -> bool:
    pid = proposal_id(proposal)
    if not pid:
        return False

    fills = load_csv(PAPER_FILLS_FILE, FILL_COLUMNS)
    if not fills.empty:
        matched = fills[
            (fills["ProposalId"].astype(str) == pid)
            & (fills["FillStatus"].astype(str).str.upper().isin(["FILLED", "PARTIALLY_FILLED"]))
        ]
        if not matched.empty:
            return True

    history = load_csv(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS)
    if not history.empty:
        matched = history[
            (history["ProposalId"].astype(str) == pid)
            & (history["ExecutionStatus"].astype(str).str.upper().isin(["FILLED", "PARTIALLY_FILLED", "EXECUTED", "SUCCESS"]))
        ]
        if not matched.empty:
            return True

    orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
    if not orders.empty:
        matched = orders[
            (orders["ProposalId"].astype(str) == pid)
            & (orders["OrderStatus"].astype(str).str.upper().isin(["FILLED", "PARTIALLY_FILLED"]))
        ]
        return not matched.empty

    return False


def paper_order_id(row: Mapping[str, Any], action: str, price: float, qty: float, when: str) -> str:
    symbol = safe_upper(row.get("Symbol"))
    market = safe_upper(row.get("Market"))
    return f"PO-{market}-{symbol}-{action}-{when[:10].replace('-', '')}-{stable_hash(proposal_id(row), symbol, market, action, qty, price)}"


def fill_id(order: Mapping[str, Any], fill_price: float, qty: float, when: str) -> str:
    return f"PF-{order['Market']}-{order['Symbol']}-{order['Action']}-{when[:10].replace('-', '')}-{stable_hash(order['PaperOrderId'], qty, fill_price)}"


def execution_id(order: Mapping[str, Any], status: str, when: str) -> str:
    return f"PE-{order['Market']}-{order['Symbol']}-{order['Action']}-{when[:10].replace('-', '')}-{stable_hash(order['PaperOrderId'], status)}"


def reject_order(row: Mapping[str, Any], action: str, reason: str, reference_price: float, qty: float, when: str) -> dict[str, Any]:
    symbol = safe_upper(row.get("Symbol"))
    market = safe_upper(row.get("Market"))
    side = ACTION_TO_SIDE.get(action, "")
    oid = paper_order_id(row, action or "NONE", reference_price, qty, when)
    return {
        "PaperOrderId": oid,
        "ProposalId": proposal_id(row),
        "Symbol": symbol,
        "Market": market,
        "Action": action,
        "Side": side,
        "OrderType": "MARKET_SIMULATED",
        "RequestedQty": qty,
        "RequestedPrice": reference_price,
        "OrderValue": 0,
        "OrderStatus": "REJECTED",
        "RejectReason": reason,
        "SubmittedTime": when,
        "StopPrice": safe_float(row.get("StopPrice")),
        "TargetPrice": safe_float(row.get("TargetPrice")),
        "AIConfidence": safe_float(row.get("AIConfidence")),
        "RiskScore": safe_float(row.get("RiskScore")),
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }


def submit_paper_order(
    proposal,
    account=None,
    portfolio=None,
    config=None,
) -> dict:
    row = dict(proposal)
    cfg = normalize_config(config)
    when = now_iso()
    action = proposal_action(row)
    qty = proposal_quantity(row)
    reference_price = reference_price_from(row)
    status = approval_status(row)

    reason = validate_proposal(row, cfg, reference_price, qty, action, status)
    if reason != "NONE":
        return reject_order(row, action, reason, reference_price, qty, when)

    symbol = safe_upper(row.get("Symbol"))
    market = safe_upper(row.get("Market"))
    side = ACTION_TO_SIDE[action]
    order_qty = round_quantity(qty, symbol, market, action, cfg)

    if order_qty <= 0:
        return reject_order(row, action, "BELOW_BOARD_LOT" if is_set_market(symbol, market) else "INVALID_QUANTITY", reference_price, qty, when)

    oid = paper_order_id(row, action, reference_price, order_qty, when)
    return {
        "PaperOrderId": oid,
        "ProposalId": proposal_id(row),
        "Symbol": symbol,
        "Market": market,
        "Action": action,
        "Side": side,
        "OrderType": "MARKET_SIMULATED",
        "RequestedQty": order_qty,
        "RequestedPrice": reference_price,
        "OrderValue": round(order_qty * reference_price, 6),
        "OrderStatus": "SUBMITTED",
        "RejectReason": "NONE",
        "SubmittedTime": when,
        "StopPrice": safe_float(row.get("StopPrice")),
        "TargetPrice": safe_float(row.get("TargetPrice")),
        "AIConfidence": safe_float(row.get("AIConfidence")),
        "RiskScore": safe_float(row.get("RiskScore")),
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }


def validate_proposal(row: Mapping[str, Any], cfg: PaperBrokerConfig, reference_price: float, qty: float, action: str, status: str) -> str:
    if not proposal_id(row):
        return "MISSING_PROPOSAL_ID"
    if cfg.require_approved_status and status != "APPROVED":
        return "NOT_APPROVED"
    if not safe_bool(row.get("RiskApproved", True)):
        return "RISK_NOT_APPROVED"
    if action not in ACTION_TO_SIDE:
        return "INVALID_ACTION"
    if qty <= 0:
        return "INVALID_QUANTITY"
    if reference_price <= 0:
        return "MISSING_PRICE"
    if cfg.reject_expired_proposal and is_expired(row):
        return "EXPIRED_PROPOSAL"
    if status in {"CANCELLED", "REJECTED", "EXPIRED", "EXECUTED"}:
        return "NOT_APPROVED"
    if cfg.reject_duplicate_execution and already_executed(row):
        return "DUPLICATE_EXECUTION"
    return "NONE"


def quantity_for_fill(order: Mapping[str, Any], config: PaperBrokerConfig, portfolio_dataframe: pd.DataFrame | None = None) -> float:
    qty = safe_float(order.get("RequestedQty"))
    action = safe_upper(order.get("Action"))
    symbol = safe_upper(order.get("Symbol"))
    market = safe_upper(order.get("Market"))

    if action == "EXIT" and portfolio_dataframe is not None:
        portfolio = normalize_paper_portfolio(portfolio_dataframe)
        matched = portfolio[
            (portfolio["Symbol"] == symbol)
            & (portfolio["Market"] == market)
            & (portfolio["PositionStatus"] == "OPEN")
        ]
        if not matched.empty:
            qty = safe_float(matched.iloc[0]["PositionQty"])

    if config.fill_policy.upper() == "PARTIAL_FILL" and config.allow_partial_fill:
        qty = qty * max(min(config.partial_fill_pct, 100), 0) / 100

    return round_quantity(qty, symbol, market, action, config)


def validate_fill(order: Mapping[str, Any], fill_qty: float, fill_price: float, gross: float, commission: float, account: Mapping[str, Any], portfolio_dataframe: pd.DataFrame, config: PaperBrokerConfig) -> str:
    action = safe_upper(order.get("Action"))
    side = safe_upper(order.get("Side"))
    symbol = safe_upper(order.get("Symbol"))
    market = safe_upper(order.get("Market"))

    if fill_qty <= 0:
        return "BELOW_BOARD_LOT" if is_set_market(symbol, market) else "INVALID_QUANTITY"
    if fill_price <= 0:
        return "MISSING_PRICE"
    if side == "BUY" and not config.allow_negative_cash:
        if safe_float(account.get("Cash")) < gross + commission:
            return "INSUFFICIENT_CASH"
    if side == "BUY":
        portfolio = normalize_paper_portfolio(portfolio_dataframe)
        matched = portfolio[
            (portfolio["Symbol"] == symbol)
            & (portfolio["Market"] == market)
            & (portfolio["PositionStatus"] == "OPEN")
        ]
        has_position = not matched.empty and safe_float(matched.iloc[0]["PositionQty"]) > 0
        if action == "ADD" and not has_position:
            return "INSUFFICIENT_POSITION"
        if action == "BUY" and has_position:
            return "INVALID_ACTION"
    if side == "SELL" and not config.allow_short_selling:
        portfolio = normalize_paper_portfolio(portfolio_dataframe)
        matched = portfolio[
            (portfolio["Symbol"] == symbol)
            & (portfolio["Market"] == market)
            & (portfolio["PositionStatus"] == "OPEN")
        ]
        if matched.empty:
            return "INSUFFICIENT_POSITION"
        position_qty = safe_float(matched.iloc[0]["PositionQty"])
        if action != "EXIT" and fill_qty > position_qty:
            return "INSUFFICIENT_POSITION"
        if action == "EXIT" and position_qty <= 0:
            return "INSUFFICIENT_POSITION"
    return "NONE"


def rejected_fill(order: Mapping[str, Any], reason: str, reference_price: float, when: str) -> dict[str, Any]:
    fid = fill_id(order, 0, 0, when)
    return {
        "FillId": fid,
        "PaperOrderId": safe_text(order.get("PaperOrderId")),
        "ProposalId": safe_text(order.get("ProposalId")),
        "Symbol": safe_upper(order.get("Symbol")),
        "Market": safe_upper(order.get("Market")),
        "Action": safe_upper(order.get("Action")),
        "Side": safe_upper(order.get("Side")),
        "RequestedQty": safe_float(order.get("RequestedQty")),
        "FilledQty": 0,
        "UnfilledQty": safe_float(order.get("RequestedQty")),
        "ReferencePrice": reference_price,
        "FillPrice": 0,
        "GrossValue": 0,
        "Commission": 0,
        "SlippageCost": 0,
        "NetCashFlow": 0,
        "RealizedPnL": 0,
        "FillStatus": "REJECTED",
        "RejectReason": reason,
        "FillTime": when,
        "StopPrice": safe_float(order.get("StopPrice")),
        "TargetPrice": safe_float(order.get("TargetPrice")),
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }


def execute_paper_order(
    order,
    market_price=None,
    account=None,
    portfolio=None,
    config=None,
) -> dict:
    row = dict(order)
    cfg = normalize_config(config)
    when = now_iso()
    account_data = normalize_account(account, cfg.initial_cash)
    portfolio_df = normalize_paper_portfolio(portfolio)

    reference_price = safe_float(market_price) if market_price is not None and safe_float(market_price) > 0 else safe_float(row.get("RequestedPrice"))
    if safe_upper(row.get("OrderStatus")) == "REJECTED":
        return rejected_fill(row, safe_text(row.get("RejectReason"), "REJECTED"), reference_price, when)
    if reference_price <= 0:
        return rejected_fill(row, "MISSING_PRICE", reference_price, when)

    side = safe_upper(row.get("Side"))
    action = safe_upper(row.get("Action"))
    fill_qty = quantity_for_fill(row, cfg, portfolio_df)
    slippage_pct = cfg.default_slippage_pct / 100
    fill_price = reference_price * (1 + slippage_pct) if side == "BUY" else reference_price * (1 - slippage_pct)
    gross = fill_price * fill_qty
    commission = max(gross * cfg.commission_pct / 100, cfg.minimum_commission) if gross > 0 else 0
    slippage_cost = abs(fill_price - reference_price) * fill_qty
    net_cash_flow = -(gross + commission) if side == "BUY" else gross - commission
    reason = validate_fill(row, fill_qty, fill_price, gross, commission, account_data, portfolio_df, cfg)
    if reason != "NONE":
        return rejected_fill(row, reason, reference_price, when)

    requested_qty = safe_float(row.get("RequestedQty"))
    fill_status = "PARTIALLY_FILLED" if fill_qty < requested_qty else "FILLED"
    fid = fill_id(row, fill_price, fill_qty, when)
    return {
        "FillId": fid,
        "PaperOrderId": safe_text(row.get("PaperOrderId")),
        "ProposalId": safe_text(row.get("ProposalId")),
        "Symbol": safe_upper(row.get("Symbol")),
        "Market": safe_upper(row.get("Market")),
        "Action": action,
        "Side": side,
        "RequestedQty": requested_qty,
        "FilledQty": round(fill_qty, 6),
        "UnfilledQty": round(max(requested_qty - fill_qty, 0), 6),
        "ReferencePrice": round(reference_price, 6),
        "FillPrice": round(fill_price, 6),
        "GrossValue": round(gross, 6),
        "Commission": round(commission, 6),
        "SlippageCost": round(slippage_cost, 6),
        "NetCashFlow": round(net_cash_flow, 6),
        "RealizedPnL": 0,
        "FillStatus": fill_status,
        "RejectReason": "NONE",
        "FillTime": when,
        "StopPrice": safe_float(row.get("StopPrice")),
        "TargetPrice": safe_float(row.get("TargetPrice")),
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }


def execution_history_row(order: Mapping[str, Any], fill: Mapping[str, Any], message: str = "") -> dict[str, Any]:
    when = safe_text(fill.get("FillTime")) or now_iso()
    status = safe_upper(fill.get("FillStatus"))
    return {
        "ExecutionId": execution_id(order, status, when),
        "ProposalId": safe_text(order.get("ProposalId")),
        "PaperOrderId": safe_text(order.get("PaperOrderId")),
        "FillId": safe_text(fill.get("FillId")),
        "Symbol": safe_upper(order.get("Symbol")),
        "Market": safe_upper(order.get("Market")),
        "Action": safe_upper(order.get("Action")),
        "ExecutionStatus": status,
        "RejectReason": safe_text(fill.get("RejectReason"), "NONE") or "NONE",
        "RequestedQty": safe_float(order.get("RequestedQty")),
        "FilledQty": safe_float(fill.get("FilledQty")),
        "ReferencePrice": safe_float(fill.get("ReferencePrice")),
        "FillPrice": safe_float(fill.get("FillPrice")),
        "ExecutionTime": when,
        "Message": message,
    }


def persist_rejection(order: Mapping[str, Any], fill: Mapping[str, Any]) -> None:
    append_row(PAPER_ORDERS_FILE, ORDER_COLUMNS, order)
    append_row(PAPER_FILLS_FILE, FILL_COLUMNS, fill)
    append_row(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS, execution_history_row(order, fill, safe_text(fill.get("RejectReason"))))


def execute_approved_proposal(
    proposal,
    market_price=None,
    account=None,
    portfolio=None,
    config=None,
) -> dict:
    row = dict(proposal)
    cfg = normalize_config(config)
    account_data = normalize_account(account if account is not None else load_paper_account(config=cfg), cfg.initial_cash)
    portfolio_df = normalize_paper_portfolio(portfolio if portfolio is not None else load_paper_portfolio())

    order = submit_paper_order(row, account=account_data, portfolio=portfolio_df, config=cfg)
    if order["OrderStatus"] == "REJECTED":
        fill = rejected_fill(order, order["RejectReason"], safe_float(order.get("RequestedPrice")), now_iso())
        persist_rejection(order, fill)
        return {"order": order, "fill": fill, "trade": {}, "cash": {}, "portfolio": portfolio_df, "account": account_data, "execution": execution_history_row(order, fill)}

    fill = execute_paper_order(order, market_price=market_price, account=account_data, portfolio=portfolio_df, config=cfg)
    if fill["FillStatus"] == "REJECTED":
        order = {**order, "OrderStatus": "REJECTED", "RejectReason": fill["RejectReason"]}
        persist_rejection(order, fill)
        return {"order": order, "fill": fill, "trade": {}, "cash": {}, "portfolio": portfolio_df, "account": account_data, "execution": execution_history_row(order, fill)}

    updated_portfolio, updated_account, trade, cash_row = apply_fill_to_portfolio(fill, portfolio_df, account_data, cfg)
    order = {**order, "OrderStatus": fill["FillStatus"]}
    fill = {**fill, "RealizedPnL": safe_float(trade.get("RealizedPnL"))}

    append_row(PAPER_ORDERS_FILE, ORDER_COLUMNS, order)
    append_row(PAPER_FILLS_FILE, FILL_COLUMNS, fill)
    append_row(PAPER_TRADES_FILE, TRADE_COLUMNS, trade)
    append_row(PAPER_CASH_LEDGER_FILE, CASH_LEDGER_COLUMNS, cash_row)
    save_paper_portfolio(updated_portfolio)
    save_paper_account(updated_account)
    execution = execution_history_row(order, fill, "paper execution completed")
    append_row(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS, execution)

    if cfg.auto_mark_executed:
        mark_proposal_executed(
            order["ProposalId"],
            order["PaperOrderId"],
            fill["FillId"],
            changed_by="paper_broker",
        )

    return {"order": order, "fill": fill, "trade": trade, "cash": cash_row, "portfolio": updated_portfolio, "account": updated_account, "execution": execution}


def batch_sort_key(row: Mapping[str, Any]) -> tuple[float, int]:
    action_order = {"EXIT": 1, "REDUCE": 2, "BUY": 3, "ADD": 4}
    return safe_float(row.get("ProposalPriority"), 5), action_order.get(proposal_action(row), 9)


def execute_approved_batch(
    proposals_dataframe,
    market_prices=None,
    account=None,
    portfolio_dataframe=None,
    config=None,
) -> tuple:
    cfg = normalize_config(config)
    proposals = pd.DataFrame(proposals_dataframe).copy() if proposals_dataframe is not None else pd.DataFrame()
    if proposals.empty:
        return (
            pd.DataFrame(columns=ORDER_COLUMNS),
            pd.DataFrame(columns=FILL_COLUMNS),
            pd.DataFrame(columns=TRADE_COLUMNS),
            normalize_paper_portfolio(portfolio_dataframe),
            normalize_account(account, cfg.initial_cash),
            {"Total": 0, "Filled": 0, "Rejected": 0},
        )

    proposals["_Sort"] = proposals.apply(lambda row: batch_sort_key(row.to_dict()), axis=1)
    proposals = proposals.sort_values("_Sort", kind="mergesort").drop(columns=["_Sort"])
    current_account = normalize_account(account if account is not None else load_paper_account(config=cfg), cfg.initial_cash)
    current_portfolio = normalize_paper_portfolio(portfolio_dataframe if portfolio_dataframe is not None else load_paper_portfolio())
    orders: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []

    for _, proposal in proposals.iterrows():
        row = proposal.to_dict()
        if approval_status(row) != "APPROVED":
            continue
        symbol = safe_upper(row.get("Symbol"))
        price = market_prices.get(symbol) if isinstance(market_prices, Mapping) else None
        result = execute_approved_proposal(
            row,
            market_price=price,
            account=current_account,
            portfolio=current_portfolio,
            config=cfg,
        )
        orders.append(result["order"])
        fills.append(result["fill"])
        if result["trade"]:
            trades.append(result["trade"])
        current_account = result["account"]
        current_portfolio = result["portfolio"]

    filled_count = sum(1 for fill in fills if fill.get("FillStatus") in {"FILLED", "PARTIALLY_FILLED"})
    rejected_count = sum(1 for fill in fills if fill.get("FillStatus") == "REJECTED")
    summary = {"Total": len(fills), "Filled": filled_count, "Rejected": rejected_count}

    return (
        pd.DataFrame(orders, columns=ORDER_COLUMNS),
        pd.DataFrame(fills, columns=FILL_COLUMNS),
        pd.DataFrame(trades, columns=TRADE_COLUMNS),
        current_portfolio,
        current_account,
        summary,
    )
