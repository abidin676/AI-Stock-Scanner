from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
import hashlib
import json
import math

import pandas as pd

from approval_queue import mark_proposal_executed
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


PAPER_BROKER_VERSION = "2.0"
PAPER_CONFIG_FILE = Path("config") / "paper_broker_config.json"
PAPER_ORDERS_FILE = Path("data") / "paper_orders.csv"
PAPER_FILLS_FILE = Path("data") / "paper_fills.csv"
PAPER_TRADES_FILE = Path("data") / "paper_trades.csv"
PAPER_CASH_LEDGER_FILE = Path("data") / "paper_cash_ledger.csv"
PAPER_EXECUTION_HISTORY_FILE = Path("data") / "paper_execution_history.csv"
PAPER_ORDER_EVENTS_FILE = Path("data") / "paper_order_events.csv"
PAPER_DAILY_STATE_FILE = Path("data") / "paper_daily_state.csv"

ORDER_STATUSES = {"CREATED", "SUBMITTED", "FILLED", "REJECTED", "CANCELLED", "EXPIRED"}
TERMINAL_ORDER_STATUSES = {"FILLED", "REJECTED", "CANCELLED", "EXPIRED"}
VALID_ORDER_TRANSITIONS = {
    "CREATED": {"SUBMITTED", "REJECTED", "CANCELLED", "EXPIRED"},
    "SUBMITTED": {"FILLED", "REJECTED", "CANCELLED", "EXPIRED"},
    "FILLED": set(),
    "REJECTED": set(),
    "CANCELLED": set(),
    "EXPIRED": set(),
}

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
    "ReferencePrice",
    "OrderValue",
    "Status",
    "OrderStatus",
    "CreatedTime",
    "SubmittedTime",
    "FilledTime",
    "CancelledTime",
    "RejectedTime",
    "FillId",
    "FillPrice",
    "GrossValue",
    "Commission",
    "NetCashFlow",
    "RejectCode",
    "RejectReason",
    "CancelReason",
    "ExecutionKey",
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
    "RejectCode",
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
    "RejectCode",
    "RejectReason",
    "RequestedQty",
    "FilledQty",
    "ReferencePrice",
    "FillPrice",
    "ExecutionTime",
    "Message",
]

ORDER_EVENT_COLUMNS = [
    "EventId",
    "PaperOrderId",
    "ProposalId",
    "EventType",
    "PreviousStatus",
    "NewStatus",
    "EventTime",
    "Symbol",
    "Action",
    "Qty",
    "ReferencePrice",
    "FillPrice",
    "RejectCode",
    "Reason",
    "CashBefore",
    "CashAfter",
    "PositionQtyBefore",
    "PositionQtyAfter",
    "TriggeredBy",
]

DAILY_STATE_COLUMNS = [
    "TradingDate",
    "StartOfDayEquity",
    "CurrentEquity",
    "DailyPnL",
    "DailyPnLPct",
    "LossLimitTriggered",
    "UpdatedTime",
]

ACTION_TO_SIDE = {
    "BUY": "BUY",
    "ADD": "BUY",
    "REDUCE": "SELL",
    "EXIT": "SELL",
}

REJECT_REASON_COMPAT = {
    "PROPOSAL_NOT_APPROVED": "NOT_APPROVED",
    "RISK_NOT_APPROVED": "RISK_NOT_APPROVED",
    "PROPOSAL_EXPIRED": "EXPIRED_PROPOSAL",
    "DUPLICATE_EXECUTION": "DUPLICATE_EXECUTION",
    "INSUFFICIENT_CASH": "INSUFFICIENT_CASH",
    "MAX_OPEN_POSITIONS": "MAX_OPEN_POSITIONS",
    "MAX_POSITION_VALUE": "MAX_POSITION_VALUE",
    "MAX_ORDER_VALUE": "MAX_ORDER_VALUE",
    "DAILY_LOSS_LIMIT_EXCEEDED": "DAILY_LOSS_LIMIT_EXCEEDED",
    "POSITION_NOT_FOUND": "INSUFFICIENT_POSITION",
    "INSUFFICIENT_POSITION_QTY": "INSUFFICIENT_POSITION",
    "SHORT_SELL_NOT_ALLOWED": "INSUFFICIENT_POSITION",
    "INVALID_ORDER_TRANSITION": "INVALID_ORDER_TRANSITION",
    "INVALID_QUANTITY": "INVALID_QUANTITY",
    "INVALID_PRICE": "MISSING_PRICE",
    "CONFIG_ERROR": "CONFIG_ERROR",
    "PAPER_ONLY_REQUIRED": "Live broker execution is not supported",
    "MANUAL_EXECUTION_REQUIRED": "Live broker execution is not supported",
    "ROBOT_MARKET_NOT_ALLOWED": "ROBOT_MARKET_NOT_ALLOWED",
    "INVALID_ACTION": "INVALID_ACTION",
    "BELOW_BOARD_LOT": "BELOW_BOARD_LOT",
}


@dataclass(frozen=True)
class PaperBrokerConfig:
    paper_only: bool = True
    initial_cash: float = 100000.0
    starting_cash: float = 100000.0
    fill_policy: str = "FULL_FILL"
    price_source: str = "PROPOSAL_ENTRY"
    default_slippage_pct: float = 0.1
    slippage_pct: float = 0.1
    commission_pct: float = 0.157
    minimum_commission: float = 0.0
    allow_partial_fill: bool = False
    partial_fill_pct: float = 50.0
    reject_expired_proposal: bool = True
    reject_duplicate_execution: bool = True
    allow_negative_cash: bool = False
    allow_short_selling: bool = False
    allow_short: bool = False
    allow_fractional_usa: bool = False
    allow_add: bool = True
    allow_reduce: bool = True
    set_board_lot: int = 100
    max_open_positions: int = 5
    max_position_value_pct: float = 25.0
    max_order_value_pct: float = 20.0
    daily_loss_limit_pct: float = 3.0
    auto_mark_executed: bool = True
    require_approved_status: bool = True
    execution_mode: str = "MANUAL"
    trailing_stop_enabled: bool = True
    trailing_stop_pct: float = 5.0
    paper_broker_version: str = PAPER_BROKER_VERSION


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC).replace(tzinfo=None)).replace(microsecond=0).isoformat()


def today_key(now: datetime | None = None) -> str:
    return now_iso(now)[:10]


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

    # Missing/null configuration is always safe by default. Explicit false is
    # preserved so the UI and execution guards can refuse to run.
    data["paper_only"] = (
        True
        if data.get("paper_only") is None
        else safe_bool(data.get("paper_only"))
    )

    if "starting_cash" in data and "initial_cash" not in data:
        data["initial_cash"] = data["starting_cash"]
    if "initial_cash" in data:
        data["starting_cash"] = data["initial_cash"]
    if "slippage_pct" in data and "default_slippage_pct" not in data:
        data["default_slippage_pct"] = data["slippage_pct"]
    if "default_slippage_pct" in data:
        data["slippage_pct"] = data["default_slippage_pct"]
    if "allow_short" in data and "allow_short_selling" not in data:
        data["allow_short_selling"] = data["allow_short"]
    if "allow_short_selling" in data:
        data["allow_short"] = data["allow_short_selling"]

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


def stable_hash(*parts: Any, length: int = 8) -> str:
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
    for column in ["EntryPrice", "Price", "Close", "ReferencePrice", "RequestedPrice"]:
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
    return bool(expire and expire < (now or datetime.now(UTC).replace(tzinfo=None)))


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
    return data[columns].astype(object) if columns else data.astype(object)


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


def upsert_order(order: Mapping[str, Any]) -> None:
    orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
    row = dict(order)
    oid = safe_text(row.get("PaperOrderId"))
    if oid and not orders.empty and (orders["PaperOrderId"].astype(str) == oid).any():
        idx = orders.index[orders["PaperOrderId"].astype(str) == oid][0]
        for column in ORDER_COLUMNS:
            orders.at[idx, column] = row.get(column, "")
    else:
        orders = pd.concat([orders, pd.DataFrame([row])], ignore_index=True)
    save_csv(orders, PAPER_ORDERS_FILE, ORDER_COLUMNS)


def validate_order_transition(current_status: str, new_status: str) -> bool:
    current = safe_upper(current_status)
    new = safe_upper(new_status)
    return new in VALID_ORDER_TRANSITIONS.get(current, set())


def order_status(order: Mapping[str, Any]) -> str:
    return safe_upper(order.get("Status", order.get("OrderStatus", "")))


def set_order_status(order: Mapping[str, Any], status: str, now: str | None = None, reason: str = "", reject_code: str = "") -> dict[str, Any]:
    row = dict(order)
    status = safe_upper(status)
    stamp = now or now_iso()
    row["Status"] = status
    row["OrderStatus"] = status
    if status == "SUBMITTED":
        row["SubmittedTime"] = stamp
    elif status == "FILLED":
        row["FilledTime"] = stamp
    elif status == "CANCELLED":
        row["CancelledTime"] = stamp
        row["CancelReason"] = reason
    elif status == "REJECTED":
        row["RejectedTime"] = stamp
        row["RejectCode"] = reject_code or safe_text(row.get("RejectCode"), "CONFIG_ERROR")
        row["RejectReason"] = reason or reject_reason(row["RejectCode"])
    return row


def transition_order_data(order: Mapping[str, Any], new_status: str, reason: str = "", reject_code: str = "") -> dict[str, Any]:
    current = order_status(order)
    new = safe_upper(new_status)
    if current == new:
        return dict(order)
    if not validate_order_transition(current, new):
        raise ValueError(f"INVALID_ORDER_TRANSITION: {current} -> {new}")
    return set_order_status(order, new, reason=reason, reject_code=reject_code)


def transition_order(order_id: str, new_status: str, reason: str | None = None, triggered_by: str = "manual") -> dict[str, Any]:
    orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
    matches = orders.index[orders["PaperOrderId"].astype(str) == safe_text(order_id)].tolist()
    if not matches:
        raise ValueError("ORDER_NOT_FOUND")
    idx = matches[0]
    before = orders.loc[idx].to_dict()
    after = transition_order_data(before, new_status, reason or "")
    for column in ORDER_COLUMNS:
        orders.at[idx, column] = after.get(column, "")
    save_csv(orders, PAPER_ORDERS_FILE, ORDER_COLUMNS)
    append_order_event(
        after,
        event_type=f"ORDER_{safe_upper(new_status)}",
        previous_status=order_status(before),
        new_status=safe_upper(new_status),
        reason=reason or "",
        triggered_by=triggered_by,
    )
    return after


def reject_reason(code: str) -> str:
    return REJECT_REASON_COMPAT.get(safe_upper(code), safe_upper(code) or "REJECTED")


def successful_fills() -> pd.DataFrame:
    return load_csv(PAPER_FILLS_FILE, FILL_COLUMNS)


def execution_key_for(row: Mapping[str, Any], action: str | None = None, qty: float | None = None) -> str:
    action_value = action or proposal_action(row)
    qty_value = qty if qty is not None else proposal_quantity(row)
    return stable_hash(proposal_id(row), action_value, qty_value, length=16)


def existing_order_for(row: Mapping[str, Any], action: str | None = None, qty: float | None = None) -> dict[str, Any] | None:
    pid = proposal_id(row)
    key = execution_key_for(row, action, qty)
    linked_order_id = safe_text(row.get("PaperOrderId"))
    orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
    if orders.empty:
        return None

    matched = pd.DataFrame()
    if linked_order_id:
        matched = orders[orders["PaperOrderId"].astype(str) == linked_order_id]
    if matched.empty and pid:
        matched = orders[orders["ProposalId"].astype(str) == pid]
    if matched.empty and key:
        matched = orders[orders["ExecutionKey"].astype(str) == key]
    if matched.empty:
        return None
    return matched.iloc[-1].to_dict()


def already_executed(proposal: Mapping[str, Any]) -> bool:
    if approval_status(proposal) == "EXECUTED":
        return True
    existing = existing_order_for(proposal)
    if existing and order_status(existing) in TERMINAL_ORDER_STATUSES | {"CREATED", "SUBMITTED"}:
        return True
    return False


def paper_order_id(row: Mapping[str, Any], action: str, price: float, qty: float, when: str) -> str:
    symbol = safe_upper(row.get("Symbol"))
    market = safe_upper(row.get("Market"))
    return f"PO-{market}-{symbol}-{action}-{when[:10].replace('-', '')}-{stable_hash(proposal_id(row), action, qty, price)}"


def fill_id(order: Mapping[str, Any], fill_price: float, qty: float, when: str) -> str:
    return f"PF-{order['Market']}-{order['Symbol']}-{order['Action']}-{when[:10].replace('-', '')}-{stable_hash(order['PaperOrderId'], qty, fill_price)}"


def execution_id(order: Mapping[str, Any], status: str, when: str) -> str:
    return f"PE-{order['Market']}-{order['Symbol']}-{order['Action']}-{when[:10].replace('-', '')}-{stable_hash(order['PaperOrderId'], status)}"


def event_id(order: Mapping[str, Any], event_type: str, previous_status: str, new_status: str, when: str) -> str:
    return f"EV-{when[:10].replace('-', '')}-{stable_hash(order.get('PaperOrderId'), event_type, previous_status, new_status, when, length=12)}"


def reject_order(row: Mapping[str, Any], action: str, code: str, reference_price: float, qty: float, when: str) -> dict[str, Any]:
    symbol = safe_upper(row.get("Symbol"))
    market = safe_upper(row.get("Market"))
    side = ACTION_TO_SIDE.get(action, "")
    oid = paper_order_id(row, action or "NONE", reference_price, qty, when)
    reason = reject_reason(code)
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
        "ReferencePrice": reference_price,
        "OrderValue": 0,
        "Status": "REJECTED",
        "OrderStatus": "REJECTED",
        "CreatedTime": when,
        "SubmittedTime": "",
        "FilledTime": "",
        "CancelledTime": "",
        "RejectedTime": when,
        "FillId": "",
        "FillPrice": 0,
        "GrossValue": 0,
        "Commission": 0,
        "NetCashFlow": 0,
        "RejectCode": code,
        "RejectReason": reason,
        "CancelReason": "",
        "ExecutionKey": execution_key_for(row, action, qty),
        "StopPrice": safe_float(row.get("StopPrice")),
        "TargetPrice": safe_float(row.get("TargetPrice")),
        "AIConfidence": safe_float(row.get("AIConfidence")),
        "RiskScore": safe_float(row.get("RiskScore")),
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }


def paper_execution_safety_code(config: PaperBrokerConfig) -> str:
    if config.paper_only is not True:
        return "PAPER_ONLY_REQUIRED"
    if safe_upper(config.execution_mode) != "MANUAL":
        return "MANUAL_EXECUTION_REQUIRED"
    return "NONE"


def validate_proposal(row: Mapping[str, Any], cfg: PaperBrokerConfig, reference_price: float, qty: float, action: str, status: str) -> str:
    safety_code = paper_execution_safety_code(cfg)
    if safety_code != "NONE":
        return safety_code
    if safe_text(row.get("RobotKey")) and safe_upper(row.get("Market")) != "SET":
        return "ROBOT_MARKET_NOT_ALLOWED"
    if not proposal_id(row):
        return "CONFIG_ERROR"
    if cfg.require_approved_status and status != "APPROVED":
        if status == "EXECUTED":
            return "DUPLICATE_EXECUTION"
        return "PROPOSAL_NOT_APPROVED"
    if not safe_bool(row.get("RiskApproved", True)):
        return "RISK_NOT_APPROVED"
    if action not in ACTION_TO_SIDE:
        return "INVALID_ACTION"
    if qty <= 0:
        return "INVALID_QUANTITY"
    if reference_price <= 0:
        return "INVALID_PRICE"
    if cfg.reject_expired_proposal and is_expired(row):
        return "PROPOSAL_EXPIRED"
    if status in {"CANCELLED", "REJECTED", "EXPIRED", "EXECUTED"}:
        return "DUPLICATE_EXECUTION" if status == "EXECUTED" else "PROPOSAL_NOT_APPROVED"
    if cfg.reject_duplicate_execution and already_executed(row):
        return "DUPLICATE_EXECUTION"
    return "NONE"


def create_order(
    proposal,
    account=None,
    portfolio=None,
    config=None,
) -> dict[str, Any]:
    row = dict(proposal)
    cfg = normalize_config(config)
    when = now_iso()
    action = proposal_action(row)
    qty = proposal_quantity(row)
    reference_price = reference_price_from(row)
    status = approval_status(row)

    code = validate_proposal(row, cfg, reference_price, qty, action, status)
    if code != "NONE":
        return reject_order(row, action, code, reference_price, qty, when)

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
        "ReferencePrice": reference_price,
        "OrderValue": round(order_qty * reference_price, 6),
        "Status": "CREATED",
        "OrderStatus": "CREATED",
        "CreatedTime": when,
        "SubmittedTime": "",
        "FilledTime": "",
        "CancelledTime": "",
        "RejectedTime": "",
        "FillId": "",
        "FillPrice": 0,
        "GrossValue": 0,
        "Commission": 0,
        "NetCashFlow": 0,
        "RejectCode": "NONE",
        "RejectReason": "NONE",
        "CancelReason": "",
        "ExecutionKey": execution_key_for(row, action, order_qty),
        "StopPrice": safe_float(row.get("StopPrice")),
        "TargetPrice": safe_float(row.get("TargetPrice")),
        "AIConfidence": safe_float(row.get("AIConfidence")),
        "RiskScore": safe_float(row.get("RiskScore")),
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }


def create_paper_order(proposal, account=None, portfolio=None, config=None, triggered_by: str = "manual") -> dict[str, Any]:
    order = create_order(proposal, account=account, portfolio=portfolio, config=config)
    upsert_order(order)
    append_order_event(
        order,
        event_type="ORDER_REJECTED" if order_status(order) == "REJECTED" else "ORDER_CREATED",
        previous_status="",
        new_status=order_status(order),
        reject_code=safe_text(order.get("RejectCode")),
        reason=safe_text(order.get("RejectReason")),
        triggered_by=triggered_by,
    )
    return order


def estimated_buy_cash_required(order: Mapping[str, Any], cfg: PaperBrokerConfig) -> tuple[float, float, float]:
    qty = safe_float(order.get("RequestedQty"))
    reference = safe_float(order.get("ReferencePrice", order.get("RequestedPrice")))
    side = safe_upper(order.get("Side"))
    slippage_pct = cfg.default_slippage_pct / 100
    fill_price = reference * (1 + slippage_pct) if side == "BUY" else reference * (1 - slippage_pct)
    gross = fill_price * qty
    commission = max(gross * cfg.commission_pct / 100, cfg.minimum_commission) if gross > 0 else 0
    return gross, commission, fill_price


def current_position(portfolio_dataframe: pd.DataFrame, symbol: str, market: str) -> pd.Series | None:
    portfolio = normalize_paper_portfolio(portfolio_dataframe)
    matched = portfolio[
        (portfolio["Symbol"] == safe_upper(symbol))
        & (portfolio["Market"] == safe_upper(market))
        & (portfolio["PositionStatus"] == "OPEN")
    ]
    if matched.empty:
        return None
    return matched.iloc[0]


def current_equity(account: Mapping[str, Any]) -> float:
    equity = safe_float(account.get("TotalEquity"))
    if equity > 0:
        return equity
    return safe_float(account.get("Cash")) + safe_float(account.get("MarketValue"))


def load_daily_state(
    account: Mapping[str, Any] | None = None,
    config: PaperBrokerConfig | Mapping[str, Any] | None = None,
    persist: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    cfg = normalize_config(config)
    account_data = normalize_account(account if account is not None else load_paper_account(config=cfg), cfg.initial_cash)
    trading_date = today_key(now)
    equity = current_equity(account_data)
    if not persist and not PAPER_DAILY_STATE_FILE.exists():
        state = pd.DataFrame(columns=DAILY_STATE_COLUMNS)
    else:
        state = load_csv(PAPER_DAILY_STATE_FILE, DAILY_STATE_COLUMNS)
    for column in ["StartOfDayEquity", "CurrentEquity", "DailyPnL", "DailyPnLPct"]:
        if column in state.columns:
            state[column] = pd.to_numeric(state[column], errors="coerce").fillna(0).astype(float)
    if "LossLimitTriggered" in state.columns:
        state["LossLimitTriggered"] = state["LossLimitTriggered"].astype(object)

    if state.empty or trading_date not in set(state["TradingDate"].astype(str)):
        row = {
            "TradingDate": trading_date,
            "StartOfDayEquity": equity,
            "CurrentEquity": equity,
            "DailyPnL": 0,
            "DailyPnLPct": 0,
            "LossLimitTriggered": False,
            "UpdatedTime": now_iso(now),
        }
        if persist:
            state = pd.concat([state, pd.DataFrame([row])], ignore_index=True)
            save_csv(state, PAPER_DAILY_STATE_FILE, DAILY_STATE_COLUMNS)
        return row

    idx = state.index[state["TradingDate"].astype(str) == trading_date][-1]
    start = safe_float(state.at[idx, "StartOfDayEquity"], equity)
    pnl = equity - start
    pct = pnl / start * 100 if start > 0 else 0
    triggered = pct <= -abs(cfg.daily_loss_limit_pct)
    row = {
        "TradingDate": trading_date,
        "StartOfDayEquity": round(start, 6),
        "CurrentEquity": round(equity, 6),
        "DailyPnL": round(pnl, 6),
        "DailyPnLPct": round(pct, 6),
        "LossLimitTriggered": bool(triggered),
        "UpdatedTime": now_iso(now),
    }
    if persist:
        for column, value in row.items():
            state.at[idx, column] = value
        save_csv(state, PAPER_DAILY_STATE_FILE, DAILY_STATE_COLUMNS)
    return row


def run_portfolio_controls(order: Mapping[str, Any], account: Mapping[str, Any], portfolio_dataframe: pd.DataFrame, config: PaperBrokerConfig) -> str:
    safety_code = paper_execution_safety_code(config)
    if safety_code != "NONE":
        return safety_code

    action = safe_upper(order.get("Action"))
    side = safe_upper(order.get("Side"))
    symbol = safe_upper(order.get("Symbol"))
    market = safe_upper(order.get("Market"))
    qty = safe_float(order.get("RequestedQty"))
    portfolio = normalize_paper_portfolio(portfolio_dataframe)
    account_data = normalize_account(account, config.initial_cash)
    equity = max(current_equity(account_data), 0)
    gross, commission, _ = estimated_buy_cash_required(order, config)
    position = current_position(portfolio, symbol, market)
    has_position = position is not None and safe_float(position.get("PositionQty")) > 0

    daily_state = load_daily_state(account_data, config, persist=True)
    if action in {"BUY", "ADD"} and safe_bool(daily_state.get("LossLimitTriggered")):
        return "DAILY_LOSS_LIMIT_EXCEEDED"
    if action == "ADD" and not config.allow_add:
        return "CONFIG_ERROR"
    if action in {"REDUCE", "EXIT"} and not config.allow_reduce:
        return "CONFIG_ERROR"
    if side == "BUY":
        if action == "ADD" and not has_position:
            return "POSITION_NOT_FOUND"
        if action == "BUY" and has_position:
            return "INVALID_ACTION"
        projected_cash = safe_float(account_data.get("Cash")) - gross - commission
        if not config.allow_negative_cash and projected_cash < 0:
            return "INSUFFICIENT_CASH"

        open_positions = int((portfolio["PositionStatus"] == "OPEN").sum()) if not portfolio.empty else 0
        if action == "BUY" and not has_position and config.max_open_positions > 0 and open_positions >= config.max_open_positions:
            return "MAX_OPEN_POSITIONS"
        if config.max_order_value_pct > 0 and equity > 0 and gross > equity * config.max_order_value_pct / 100:
            return "MAX_ORDER_VALUE"

        current_value = safe_float(position.get("MarketValue")) if has_position else 0
        projected_position_value = current_value + gross
        if config.max_position_value_pct > 0 and equity > 0 and projected_position_value > equity * config.max_position_value_pct / 100:
            return "MAX_POSITION_VALUE"

    if side == "SELL":
        if not has_position:
            return "POSITION_NOT_FOUND"
        owned_qty = safe_float(position.get("PositionQty"))
        if not config.allow_short_selling and qty > owned_qty and action != "EXIT":
            return "INSUFFICIENT_POSITION_QTY"
        if not config.allow_short_selling and owned_qty <= 0:
            return "SHORT_SELL_NOT_ALLOWED"
    return "NONE"


def submit_order(order, account=None, portfolio=None, config=None, triggered_by: str = "paper_broker") -> dict[str, Any]:
    row = dict(order)
    cfg = normalize_config(config)
    account_data = normalize_account(account if account is not None else load_paper_account(config=cfg), cfg.initial_cash)
    portfolio_df = normalize_paper_portfolio(portfolio if portfolio is not None else load_paper_portfolio())
    current = order_status(row)
    if current == "REJECTED":
        return row

    try:
        transition_order_data(row, "SUBMITTED")
    except ValueError:
        return set_order_status(row, "REJECTED", reason=reject_reason("INVALID_ORDER_TRANSITION"), reject_code="INVALID_ORDER_TRANSITION")

    code = run_portfolio_controls(row, account_data, portfolio_df, cfg)
    if code != "NONE":
        return transition_order_data(row, "REJECTED", reject_reason(code), code)
    return transition_order_data(row, "SUBMITTED")


def submit_paper_order(
    proposal,
    account=None,
    portfolio=None,
    config=None,
) -> dict:
    order = create_order(proposal, account=account, portfolio=portfolio, config=config)
    if order_status(order) == "REJECTED":
        return order
    return submit_order(order, account=account, portfolio=portfolio, config=config)


def quantity_for_fill(order: Mapping[str, Any], config: PaperBrokerConfig, portfolio_dataframe: pd.DataFrame | None = None) -> float:
    qty = safe_float(order.get("RequestedQty"))
    action = safe_upper(order.get("Action"))
    symbol = safe_upper(order.get("Symbol"))
    market = safe_upper(order.get("Market"))

    if action == "EXIT" and portfolio_dataframe is not None:
        position = current_position(portfolio_dataframe, symbol, market)
        if position is not None:
            qty = safe_float(position.get("PositionQty"))

    if config.fill_policy.upper() == "PARTIAL_FILL" and config.allow_partial_fill:
        qty = qty * max(min(config.partial_fill_pct, 100), 0) / 100

    return round_quantity(qty, symbol, market, action, config)


def validate_fill(order: Mapping[str, Any], fill_qty: float, fill_price: float, gross: float, commission: float, account: Mapping[str, Any], portfolio_dataframe: pd.DataFrame, config: PaperBrokerConfig) -> str:
    safety_code = paper_execution_safety_code(config)
    if safety_code != "NONE":
        return safety_code

    action = safe_upper(order.get("Action"))
    side = safe_upper(order.get("Side"))
    symbol = safe_upper(order.get("Symbol"))
    market = safe_upper(order.get("Market"))

    if fill_qty <= 0:
        return "BELOW_BOARD_LOT" if is_set_market(symbol, market) else "INVALID_QUANTITY"
    if fill_price <= 0:
        return "INVALID_PRICE"
    if side == "BUY" and not config.allow_negative_cash:
        if safe_float(account.get("Cash")) < gross + commission:
            return "INSUFFICIENT_CASH"
    if side == "BUY":
        position = current_position(portfolio_dataframe, symbol, market)
        has_position = position is not None and safe_float(position.get("PositionQty")) > 0
        if action == "ADD" and not has_position:
            return "POSITION_NOT_FOUND"
        if action == "BUY" and has_position:
            return "INVALID_ACTION"
    if side == "SELL" and not config.allow_short_selling:
        position = current_position(portfolio_dataframe, symbol, market)
        if position is None:
            return "POSITION_NOT_FOUND"
        position_qty = safe_float(position.get("PositionQty"))
        if action != "EXIT" and fill_qty > position_qty:
            return "INSUFFICIENT_POSITION_QTY"
        if action == "EXIT" and position_qty <= 0:
            return "POSITION_NOT_FOUND"
    return "NONE"


def rejected_fill(order: Mapping[str, Any], code: str, reference_price: float, when: str) -> dict[str, Any]:
    fid = fill_id(order, 0, 0, when)
    reason = reject_reason(code)
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
        "RejectCode": code,
        "RejectReason": reason,
        "FillTime": when,
        "StopPrice": safe_float(order.get("StopPrice")),
        "TargetPrice": safe_float(order.get("TargetPrice")),
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }


def process_order(
    order,
    market_price=None,
    account=None,
    portfolio=None,
    config=None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = dict(order)
    cfg = normalize_config(config)
    when = now_iso()
    account_data = normalize_account(account, cfg.initial_cash)
    portfolio_df = normalize_paper_portfolio(portfolio)
    status = order_status(row)

    reference_price = safe_float(market_price) if market_price is not None and safe_float(market_price) > 0 else safe_float(row.get("ReferencePrice", row.get("RequestedPrice")))
    if status != "SUBMITTED":
        code = "INVALID_ORDER_TRANSITION" if status not in {"REJECTED", "CANCELLED", "EXPIRED"} else safe_text(row.get("RejectCode"), "PROPOSAL_NOT_APPROVED")
        return set_order_status(row, "REJECTED", reject_reason(code), code), rejected_fill(row, code, reference_price, when)
    if reference_price <= 0:
        code = "INVALID_PRICE"
        return transition_order_data(row, "REJECTED", reject_reason(code), code), rejected_fill(row, code, reference_price, when)

    side = safe_upper(row.get("Side"))
    fill_qty = quantity_for_fill(row, cfg, portfolio_df)
    slippage_pct = cfg.default_slippage_pct / 100
    fill_price = reference_price * (1 + slippage_pct) if side == "BUY" else reference_price * (1 - slippage_pct)
    gross = fill_price * fill_qty
    commission = max(gross * cfg.commission_pct / 100, cfg.minimum_commission) if gross > 0 else 0
    slippage_cost = abs(fill_price - reference_price) * fill_qty
    net_cash_flow = -(gross + commission) if side == "BUY" else gross - commission
    code = validate_fill(row, fill_qty, fill_price, gross, commission, account_data, portfolio_df, cfg)
    if code != "NONE":
        rejected_order = transition_order_data(row, "REJECTED", reject_reason(code), code)
        return rejected_order, rejected_fill(rejected_order, code, reference_price, when)

    requested_qty = safe_float(row.get("RequestedQty"))
    fill_status = "PARTIALLY_FILLED" if fill_qty < requested_qty else "FILLED"
    fid = fill_id(row, fill_price, fill_qty, when)
    fill = {
        "FillId": fid,
        "PaperOrderId": safe_text(row.get("PaperOrderId")),
        "ProposalId": safe_text(row.get("ProposalId")),
        "Symbol": safe_upper(row.get("Symbol")),
        "Market": safe_upper(row.get("Market")),
        "Action": safe_upper(row.get("Action")),
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
        "RejectCode": "NONE",
        "RejectReason": "NONE",
        "FillTime": when,
        "StopPrice": safe_float(row.get("StopPrice")),
        "TargetPrice": safe_float(row.get("TargetPrice")),
        "PaperBrokerVersion": PAPER_BROKER_VERSION,
    }
    filled_order = transition_order_data(row, "FILLED")
    filled_order.update(
        {
            "FillId": fid,
            "FillPrice": fill["FillPrice"],
            "GrossValue": fill["GrossValue"],
            "Commission": fill["Commission"],
            "NetCashFlow": fill["NetCashFlow"],
        }
    )
    return filled_order, fill


def execute_paper_order(
    order,
    market_price=None,
    account=None,
    portfolio=None,
    config=None,
) -> dict:
    row = dict(order)
    cfg = normalize_config(config)
    account_data = normalize_account(account, cfg.initial_cash)
    portfolio_df = normalize_paper_portfolio(portfolio)
    if order_status(row) == "CREATED":
        row = submit_order(row, account=account_data, portfolio=portfolio_df, config=cfg)
    final_order, fill = process_order(row, market_price=market_price, account=account_data, portfolio=portfolio_df, config=cfg)
    return fill


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
        "RejectCode": safe_text(fill.get("RejectCode"), "NONE") or "NONE",
        "RejectReason": safe_text(fill.get("RejectReason"), "NONE") or "NONE",
        "RequestedQty": safe_float(order.get("RequestedQty")),
        "FilledQty": safe_float(fill.get("FilledQty")),
        "ReferencePrice": safe_float(fill.get("ReferencePrice")),
        "FillPrice": safe_float(fill.get("FillPrice")),
        "ExecutionTime": when,
        "Message": message,
    }


def append_order_event(
    order: Mapping[str, Any],
    event_type: str,
    previous_status: str = "",
    new_status: str = "",
    fill: Mapping[str, Any] | None = None,
    reject_code: str = "",
    reason: str = "",
    account_before: Mapping[str, Any] | None = None,
    account_after: Mapping[str, Any] | None = None,
    position_qty_before: float = 0,
    position_qty_after: float = 0,
    triggered_by: str = "paper_broker",
) -> dict[str, Any]:
    when = now_iso()
    fill_data = fill or {}
    event = {
        "EventId": event_id(order, event_type, previous_status, new_status or order_status(order), when),
        "PaperOrderId": safe_text(order.get("PaperOrderId")),
        "ProposalId": safe_text(order.get("ProposalId")),
        "EventType": event_type,
        "PreviousStatus": safe_upper(previous_status),
        "NewStatus": safe_upper(new_status or order_status(order)),
        "EventTime": when,
        "Symbol": safe_upper(order.get("Symbol")),
        "Action": safe_upper(order.get("Action")),
        "Qty": safe_float(order.get("RequestedQty")),
        "ReferencePrice": safe_float(order.get("ReferencePrice", order.get("RequestedPrice"))),
        "FillPrice": safe_float(fill_data.get("FillPrice")),
        "RejectCode": safe_text(reject_code or fill_data.get("RejectCode") or order.get("RejectCode"), "NONE"),
        "Reason": safe_text(reason or fill_data.get("RejectReason") or order.get("RejectReason"), "NONE"),
        "CashBefore": safe_float((account_before or {}).get("Cash")),
        "CashAfter": safe_float((account_after or {}).get("Cash")),
        "PositionQtyBefore": safe_float(position_qty_before),
        "PositionQtyAfter": safe_float(position_qty_after),
        "TriggeredBy": triggered_by,
    }
    append_row(PAPER_ORDER_EVENTS_FILE, ORDER_EVENT_COLUMNS, event)
    return event


def position_qty_for(portfolio: pd.DataFrame, symbol: str, market: str) -> float:
    position = current_position(portfolio, symbol, market)
    return safe_float(position.get("PositionQty")) if position is not None else 0


def persist_rejection(order: Mapping[str, Any], fill: Mapping[str, Any], event_type: str = "ORDER_REJECTED") -> None:
    upsert_order(order)
    append_row(PAPER_FILLS_FILE, FILL_COLUMNS, fill)
    append_row(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS, execution_history_row(order, fill, safe_text(fill.get("RejectReason"))))
    append_order_event(
        order,
        event_type=event_type,
        previous_status="CREATED" if event_type == "CONTROL_BLOCKED" else "",
        new_status="REJECTED",
        fill=fill,
        reject_code=safe_text(fill.get("RejectCode")),
        reason=safe_text(fill.get("RejectReason")),
    )


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

    order = create_order(row, account=account_data, portfolio=portfolio_df, config=cfg)
    if order_status(order) == "REJECTED":
        fill = rejected_fill(order, safe_text(order.get("RejectCode"), "CONFIG_ERROR"), safe_float(order.get("ReferencePrice")), now_iso())
        if safe_text(order.get("RejectCode")) == "DUPLICATE_EXECUTION":
            append_order_event(order, "DUPLICATE_BLOCKED", new_status="REJECTED", fill=fill, reject_code="DUPLICATE_EXECUTION", reason=fill["RejectReason"])
        else:
            persist_rejection(order, fill)
        return {"order": order, "fill": fill, "trade": {}, "cash": {}, "portfolio": portfolio_df, "account": account_data, "execution": execution_history_row(order, fill)}

    append_order_event(order, "ORDER_CREATED", previous_status="", new_status="CREATED")
    submitted_order = submit_order(order, account=account_data, portfolio=portfolio_df, config=cfg)
    if order_status(submitted_order) == "REJECTED":
        fill = rejected_fill(submitted_order, safe_text(submitted_order.get("RejectCode"), "CONFIG_ERROR"), safe_float(submitted_order.get("ReferencePrice")), now_iso())
        persist_rejection(submitted_order, fill, event_type="CONTROL_BLOCKED")
        return {"order": submitted_order, "fill": fill, "trade": {}, "cash": {}, "portfolio": portfolio_df, "account": account_data, "execution": execution_history_row(submitted_order, fill)}

    append_order_event(submitted_order, "ORDER_SUBMITTED", previous_status="CREATED", new_status="SUBMITTED")
    before_qty = position_qty_for(portfolio_df, submitted_order["Symbol"], submitted_order["Market"])
    final_order, fill = process_order(submitted_order, market_price=market_price, account=account_data, portfolio=portfolio_df, config=cfg)
    if fill["FillStatus"] == "REJECTED":
        persist_rejection(final_order, fill)
        return {"order": final_order, "fill": fill, "trade": {}, "cash": {}, "portfolio": portfolio_df, "account": account_data, "execution": execution_history_row(final_order, fill)}

    updated_portfolio, updated_account, trade, cash_row = apply_fill_to_portfolio(fill, portfolio_df, account_data, cfg)
    fill = {**fill, "RealizedPnL": safe_float(trade.get("RealizedPnL"))}
    final_order = {**final_order, "FillId": fill["FillId"]}
    after_qty = position_qty_for(updated_portfolio, final_order["Symbol"], final_order["Market"])

    upsert_order(final_order)
    append_row(PAPER_FILLS_FILE, FILL_COLUMNS, fill)
    append_row(PAPER_TRADES_FILE, TRADE_COLUMNS, trade)
    append_row(PAPER_CASH_LEDGER_FILE, CASH_LEDGER_COLUMNS, cash_row)
    save_paper_portfolio(updated_portfolio)
    save_paper_account(updated_account)
    load_daily_state(updated_account, cfg, persist=True)
    execution = execution_history_row(final_order, fill, "paper execution completed")
    append_row(PAPER_EXECUTION_HISTORY_FILE, EXECUTION_HISTORY_COLUMNS, execution)
    append_order_event(
        final_order,
        event_type="ORDER_FILLED",
        previous_status="SUBMITTED",
        new_status="FILLED",
        fill=fill,
        account_before=account_data,
        account_after=updated_account,
        position_qty_before=before_qty,
        position_qty_after=after_qty,
    )

    if cfg.auto_mark_executed:
        mark_proposal_executed(
            final_order["ProposalId"],
            final_order["PaperOrderId"],
            fill["FillId"],
            changed_by="paper_broker",
        )

    return {"order": final_order, "fill": fill, "trade": trade, "cash": cash_row, "portfolio": updated_portfolio, "account": updated_account, "execution": execution}


def cancel_paper_order(order_id: str, reason: str = "manual_cancel", triggered_by: str = "manual") -> dict[str, Any]:
    orders = load_csv(PAPER_ORDERS_FILE, ORDER_COLUMNS)
    matches = orders.index[orders["PaperOrderId"].astype(str) == safe_text(order_id)].tolist()
    if not matches:
        raise ValueError("ORDER_NOT_FOUND")
    idx = matches[0]
    before = orders.loc[idx].to_dict()
    if order_status(before) not in {"CREATED", "SUBMITTED"}:
        raise ValueError("INVALID_ORDER_TRANSITION")
    after = transition_order_data(before, "CANCELLED", reason=reason)
    for column in ORDER_COLUMNS:
        orders.at[idx, column] = after.get(column, "")
    save_csv(orders, PAPER_ORDERS_FILE, ORDER_COLUMNS)
    append_order_event(
        after,
        "ORDER_CANCELLED",
        previous_status=order_status(before),
        new_status="CANCELLED",
        reason=reason,
        triggered_by=triggered_by,
    )
    return after


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
