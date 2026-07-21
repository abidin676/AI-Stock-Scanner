from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
import json
import math

import pandas as pd

from runtime_io import atomic_write_csv


RISK_MANAGER_VERSION = "1.0"
RISK_CONFIG_FILE = Path("config") / "risk_config.json"
ORDER_PROPOSALS_FILE = Path("output") / "order_proposals.csv"
RISK_SUMMARY_FILE = Path("output") / "risk_summary.csv"

PROPOSAL_COLUMNS = [
    "Symbol",
    "Market",
    "SourceDecision",
    "ProposalAction",
    "ProposalStatus",
    "RiskApproved",
    "ApprovalRequired",
    "RejectReason",
    "RiskWarnings",
    "EntryPrice",
    "StopPrice",
    "TargetPrice",
    "StopDistancePct",
    "RewardDistancePct",
    "RiskRewardRatio",
    "RiskBudget",
    "MaxPositionValue",
    "ProposedOrderValue",
    "EstimatedCommission",
    "EstimatedSlippage",
    "EstimatedTotalCost",
    "CurrentPositionQty",
    "ProposedQty",
    "FinalPositionQty",
    "CurrentExposurePct",
    "ProjectedExposurePct",
    "PortfolioExposureAfterPct",
    "CashAfterOrder",
    "PositionSizeMethod",
    "RiskLevel",
    "RiskScore",
    "ProposalPriority",
    "ProposalId",
    "RiskManagerVersion",
    "ProposalTime",
]

SUMMARY_COLUMNS = [
    "RunTime",
    "AccountEquity",
    "AvailableCash",
    "CurrentExposure",
    "CurrentExposurePct",
    "ProjectedExposure",
    "ProjectedExposurePct",
    "OpenPositions",
    "PendingProposals",
    "ApprovedProposals",
    "RejectedProposals",
    "BuyProposals",
    "AddProposals",
    "ReduceProposals",
    "ExitProposals",
    "TotalProposedBuyValue",
    "TotalProposedSellValue",
    "EstimatedCommission",
    "EstimatedSlippage",
    "EstimatedCashAfter",
    "MaxSinglePositionPct",
    "AverageRiskScore",
    "HighRiskProposalCount",
    "RiskManagerVersion",
]

ACTIONABLE_DECISIONS = {"BUY", "ADD", "REDUCE", "EXIT"}
SEVERE_AI_BLOCKERS = {
    "EXTENDED",
    "MARKET_AVOID",
    "HIGH_RISK",
    "SETUP_INVALIDATED",
    "BELOW_STOP",
    "MISSING_PRICE",
    "INVALID_STOP",
}


@dataclass(frozen=True)
class RiskConfig:
    account_equity: float = 100000.0
    available_cash: float = 100000.0
    risk_per_trade_pct: float = 1.0
    max_position_pct: float = 15.0
    max_total_exposure_pct: float = 80.0
    max_sector_exposure_pct: float = 25.0
    max_open_positions: int = 10
    min_order_value: float = 1000.0
    max_order_value: float = 15000.0
    min_rr: float = 1.5
    default_stop_loss_pct: float = 7.0
    max_stop_loss_pct: float = 12.0
    allow_add_position: bool = True
    allow_reduce_position: bool = True
    require_manual_approval: bool = True
    set_board_lot: int = 100
    usa_fractional_shares: bool = False
    commission_pct: float = 0.157
    minimum_commission: float = 0.0
    slippage_pct: float = 0.1


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_text(value: Any, default: str = "") -> str:
    if pd.isna(value):
        return default

    return str(value).strip()


def safe_bool(value: Any) -> bool:
    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    return safe_text(value).upper() in {"TRUE", "YES", "Y", "1"}


def clamp(value: Any, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, safe_float(value)))


def row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, pd.Series):
        return row.to_dict()

    if isinstance(row, Mapping):
        return dict(row)

    return {}


def get_value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and not pd.isna(row[name]):
            return row[name]

    return default


def normalize_symbol(symbol: Any, market: Any = "") -> str:
    value = safe_text(symbol).upper()
    market_value = safe_text(market).upper()

    if market_value in {"SET", "TH", "THAI"} and value and not value.endswith(".BK"):
        return f"{value}.BK"

    return value


def is_set_market(symbol: Any, market: Any) -> bool:
    return safe_text(market).upper() in {"SET", "TH", "THAI"} or safe_text(symbol).upper().endswith(".BK")


def normalize_config(config: RiskConfig | Mapping[str, Any] | None = None) -> RiskConfig:
    if isinstance(config, RiskConfig):
        return config

    data: dict[str, Any] = {}

    if RISK_CONFIG_FILE.exists():
        try:
            data.update(json.loads(RISK_CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            data = {}

    if isinstance(config, Mapping):
        data.update(dict(config))

    allowed = RiskConfig.__dataclass_fields__

    values = {
        key: value
        for key, value in data.items()
        if key in allowed
    }

    return RiskConfig(**values)


def load_risk_config(path: Path = RISK_CONFIG_FILE, overrides: Mapping[str, Any] | None = None) -> RiskConfig:
    data: dict[str, Any] = {}

    if path.exists():
        try:
            data.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            data = {}

    if overrides:
        data.update(dict(overrides))

    return normalize_config(data)


def save_default_risk_config(path: Path = RISK_CONFIG_FILE) -> Path:
    path.parent.mkdir(exist_ok=True)

    if not path.exists():
        path.write_text(
            json.dumps(asdict(RiskConfig()), indent=2),
            encoding="utf-8",
        )

    return path


def normalize_account(row: Mapping[str, Any], account: Mapping[str, Any] | None, config: RiskConfig) -> dict[str, float]:
    account = dict(account or {})
    equity = safe_float(
        account.get("AccountEquity", account.get("account_equity", get_value(row, "AccountEquity", default=config.account_equity))),
        config.account_equity,
    )
    available_cash = safe_float(
        account.get("AvailableCash", account.get("available_cash", get_value(row, "AvailableCash", default=config.available_cash))),
        config.available_cash,
    )
    total_exposure = safe_float(
        account.get("TotalExposure", account.get("total_exposure", get_value(row, "TotalExposure", default=0))),
        0,
    )
    open_positions = safe_int(
        account.get("OpenPositions", account.get("open_positions", get_value(row, "OpenPositions", default=0))),
        0,
    )
    sector_exposure = safe_float(
        account.get("SectorExposure", account.get("sector_exposure", get_value(row, "SectorExposure", "SectorExposureValue", default=0))),
        0,
    )

    return {
        "account_equity": max(equity, 0),
        "available_cash": max(available_cash, 0),
        "total_exposure": max(total_exposure, 0),
        "open_positions": max(open_positions, 0),
        "sector_exposure": max(sector_exposure, 0),
    }


def normalize_portfolio_context(row: Mapping[str, Any], portfolio: Mapping[str, Any] | None) -> dict[str, Any]:
    portfolio = dict(portfolio or {})
    status = safe_text(
        portfolio.get("PortfolioStatus", portfolio.get("Status", get_value(row, "PortfolioStatus", "Status", default=""))),
    ).upper()
    qty = safe_float(
        portfolio.get("PositionQty", portfolio.get("Shares", portfolio.get("qty", get_value(row, "PositionQty", "Shares", default=0)))),
        0,
    )
    current_value = safe_float(
        portfolio.get("CurrentValue", portfolio.get("current_value", get_value(row, "CurrentValue", default=0))),
        0,
    )
    average_cost = safe_float(
        portfolio.get("AverageCost", portfolio.get("EntryPrice", portfolio.get("average_cost", get_value(row, "AverageCost", "EntryPrice", default=0)))),
        0,
    )

    return {
        "has_position": bool(portfolio.get("has_position", status == "OPEN" or qty > 0)),
        "qty": qty,
        "average_cost": average_cost,
        "current_value": current_value,
        "unrealized_return_pct": safe_float(
            portfolio.get("UnrealizedReturnPct", portfolio.get("unrealized_return_pct", get_value(row, "UnrealizedReturnPct", default=0))),
            0,
        ),
    }


def select_entry_price(row: Mapping[str, Any]) -> float:
    for column in ("EntryPrice", "Entry", "Price", "Close"):
        value = safe_float(get_value(row, column, default=0))

        if value > 0:
            return value

    return 0


def select_stop_price(row: Mapping[str, Any], entry: float, action: str, config: RiskConfig) -> tuple[float, str]:
    if action not in {"BUY", "ADD"} or entry <= 0:
        return 0, "not_applicable"

    raw_stop = safe_float(
        get_value(row, "StopPrice", "Stop", "StopLoss", default=0)
    )

    if raw_stop > 0:
        if raw_stop >= entry:
            return raw_stop, "invalid_stop"
        return raw_stop, "provided"

    risk_pct = safe_float(get_value(row, "RiskPct", default=0))

    if risk_pct > 0:
        return entry * (1 - risk_pct / 100), "risk_pct"

    atr = safe_float(get_value(row, "ATR", default=0))

    if atr > 0 and entry - (2 * atr) > 0:
        return entry - (2 * atr), "atr"

    return entry * (1 - config.default_stop_loss_pct / 100), "default"


def select_target_price(row: Mapping[str, Any], entry: float, stop: float, action: str, config: RiskConfig) -> tuple[float, str]:
    if action not in {"BUY", "ADD"} or entry <= 0 or stop <= 0:
        return 0, "not_applicable"

    raw_target = safe_float(
        get_value(row, "TargetPrice", "Target", default=0)
    )

    if raw_target > 0:
        return raw_target, "provided"

    reward_pct = safe_float(get_value(row, "RewardPct", default=0))

    if reward_pct > 0:
        return entry * (1 + reward_pct / 100), "reward_pct"

    risk_per_share = entry - stop

    planned_rr = safe_float(
        get_value(row, "RR", "RiskRewardRatio", default=0)
    )
    if planned_rr > 0:
        return entry + (risk_per_share * planned_rr), "planned_rr"

    return entry + (risk_per_share * config.min_rr), "minimum_rr"


def indicative_risk_levels(
    row: Mapping[str, Any],
    config: RiskConfig | Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Return reusable BUY planning levels without creating an order proposal."""

    cfg = normalize_config(config)
    entry = select_entry_price(row)
    stop, _ = select_stop_price(row, entry, "BUY", cfg)
    target, _ = select_target_price(row, entry, stop, "BUY", cfg)
    stop_distance_pct = (
        (entry - stop) / entry * 100
        if entry > 0 and 0 < stop < entry
        else 0
    )
    reward_distance_pct = (
        (target - entry) / entry * 100
        if entry > 0 and target > entry
        else 0
    )
    rr = (
        (target - entry) / (entry - stop)
        if entry > 0 and target > entry and 0 < stop < entry
        else 0
    )
    return {
        "EntryPrice": round(entry, 6),
        "StopPrice": round(stop, 6),
        "TargetPrice": round(target, 6),
        "StopDistancePct": round(stop_distance_pct, 4),
        "RewardDistancePct": round(reward_distance_pct, 4),
        "RiskRewardRatio": round(rr, 4),
    }


def add_indicative_risk_levels(
    dataframe: pd.DataFrame | None,
    config: RiskConfig | Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Fill missing planning levels using the Risk Manager's existing rules."""

    if dataframe is None:
        return pd.DataFrame()

    data = dataframe.copy()
    if data.empty:
        return data

    levels = pd.DataFrame(
        [
            indicative_risk_levels(row.to_dict(), config=config)
            for _, row in data.iterrows()
        ],
        index=data.index,
    )
    for column in levels.columns:
        if column not in data.columns:
            data[column] = levels[column]
            continue

        existing = pd.to_numeric(data[column], errors="coerce")
        data[column] = existing.where(existing > 0, levels[column])

    return data


def round_quantity(qty: float, symbol: str, market: str, config: RiskConfig, allow_set_fractional_exit: bool = False) -> float:
    if qty <= 0:
        return 0

    if is_set_market(symbol, market) and not allow_set_fractional_exit:
        lot = max(int(config.set_board_lot), 1)
        return math.floor(qty / lot) * lot

    if safe_text(market).upper() == "USA" and not config.usa_fractional_shares:
        return math.floor(qty)

    return round(qty, 4)


def estimate_commission(value: float, config: RiskConfig) -> float:
    if value <= 0:
        return 0

    return round(max(value * config.commission_pct / 100, config.minimum_commission), 6)


def estimate_slippage(value: float, config: RiskConfig) -> float:
    if value <= 0:
        return 0

    return round(value * config.slippage_pct / 100, 6)


def order_cost(value: float, config: RiskConfig) -> tuple[float, float, float]:
    commission = estimate_commission(value, config)
    slippage = estimate_slippage(value, config)

    return commission, slippage, round(value + commission + slippage, 6)


def order_proceeds(value: float, config: RiskConfig) -> tuple[float, float, float]:
    commission = estimate_commission(value, config)
    slippage = estimate_slippage(value, config)

    return commission, slippage, round(max(value - commission - slippage, 0), 6)


def parse_ai_blockers(value: Any) -> set[str]:
    text = safe_text(value).upper()

    if not text:
        return set()

    return {
        part.strip()
        for part in text.replace(",", ";").split(";")
        if part.strip()
    }


def proposal_id(symbol: str, market: str, action: str, proposal_time: str) -> str:
    date = proposal_time[:10].replace("-", "")
    clean_symbol = symbol.replace(".", "")

    return f"RM-{market or 'NA'}-{clean_symbol or 'UNKNOWN'}-{action}-{date}"


def risk_score(
    row: Mapping[str, Any],
    action: str,
    ai_blockers: set[str],
    stop_distance_pct: float,
    rr: float,
    projected_exposure_pct: float,
    portfolio_exposure_after_pct: float,
    below_stop: bool,
) -> float:
    ai_risk = safe_text(get_value(row, "AIRiskLevel", default="UNKNOWN")).upper()
    score = {
        "LOW": 20,
        "MEDIUM": 50,
        "HIGH": 80,
        "UNKNOWN": 60,
    }.get(ai_risk, 60)

    if stop_distance_pct > 10:
        score += 15
    elif stop_distance_pct >= 7:
        score += 8

    if rr > 0 and rr < 1.5:
        score += 20
    elif 1.5 <= rr < 2:
        score += 8

    if projected_exposure_pct > 12:
        score += 15

    if portfolio_exposure_after_pct > 70:
        score += 15

    if safe_float(get_value(row, "AIConfidence", default=0)) < 50:
        score += 10

    if ai_blockers & SEVERE_AI_BLOCKERS:
        score += 25

    if action == "ADD":
        score += 5

    if action == "EXIT" and below_stop:
        score = max(score, 90)

    return round(clamp(score), 2)


def risk_level_from_score(score: float) -> str:
    if score < 35:
        return "LOW"

    if score < 65:
        return "MEDIUM"

    return "HIGH"


def proposal_priority(action: str, status: str, confidence: float, below_stop: bool) -> int:
    if action == "EXIT" or below_stop:
        return 1

    if action == "REDUCE" or (action == "BUY" and confidence >= 80):
        return 2

    if action in {"BUY", "ADD"}:
        return 3

    if status == "REJECTED":
        return 4

    return 5


def base_result(
    row: Mapping[str, Any],
    action: str,
    status: str,
    risk_approved: bool,
    reject_reason: str,
    warnings: list[str],
    entry: float,
    stop: float,
    target: float,
    stop_distance_pct: float,
    reward_distance_pct: float,
    rr: float,
    risk_budget: float,
    max_position_value: float,
    proposed_value: float,
    commission: float,
    slippage: float,
    total_cost: float,
    current_qty: float,
    proposed_qty: float,
    final_qty: float,
    current_exposure_pct: float,
    projected_exposure_pct: float,
    portfolio_exposure_after_pct: float,
    cash_after: float,
    method: str,
    risk_level: str,
    score: float,
    priority: int,
    proposal_time: str,
) -> dict[str, Any]:
    symbol = safe_text(get_value(row, "Symbol", default="")).upper()
    market = safe_text(get_value(row, "Market", default="")).upper()

    return {
        "Symbol": symbol,
        "Market": market,
        "SourceDecision": safe_text(get_value(row, "AIDecision", default="NO_ACTION")).upper(),
        "ProposalAction": action,
        "ProposalStatus": status,
        "RiskApproved": bool(risk_approved),
        "ApprovalRequired": action in {"BUY", "ADD", "REDUCE", "EXIT"},
        "RejectReason": reject_reason or "NONE",
        "RiskWarnings": "; ".join(warnings) if warnings else "NONE",
        "EntryPrice": round(entry, 6),
        "StopPrice": round(stop, 6),
        "TargetPrice": round(target, 6),
        "StopDistancePct": round(stop_distance_pct, 4),
        "RewardDistancePct": round(reward_distance_pct, 4),
        "RiskRewardRatio": round(rr, 4),
        "RiskBudget": round(risk_budget, 6),
        "MaxPositionValue": round(max_position_value, 6),
        "ProposedOrderValue": round(proposed_value, 6),
        "EstimatedCommission": round(commission, 6),
        "EstimatedSlippage": round(slippage, 6),
        "EstimatedTotalCost": round(total_cost, 6),
        "CurrentPositionQty": round(current_qty, 6),
        "ProposedQty": round(proposed_qty, 6),
        "FinalPositionQty": round(final_qty, 6),
        "CurrentExposurePct": round(current_exposure_pct, 4),
        "ProjectedExposurePct": round(projected_exposure_pct, 4),
        "PortfolioExposureAfterPct": round(portfolio_exposure_after_pct, 4),
        "CashAfterOrder": round(cash_after, 6),
        "PositionSizeMethod": method,
        "RiskLevel": risk_level,
        "RiskScore": round(score, 2),
        "ProposalPriority": int(priority),
        "ProposalId": proposal_id(symbol, market, action, proposal_time),
        "RiskManagerVersion": RISK_MANAGER_VERSION,
        "ProposalTime": proposal_time,
    }


def no_proposal(
    row: Mapping[str, Any],
    action: str,
    config: RiskConfig,
    proposal_time: str,
    reason: str = "NONE",
) -> dict[str, Any]:
    return base_result(
        row=row,
        action=action,
        status="NO_PROPOSAL",
        risk_approved=False,
        reject_reason=reason,
        warnings=[],
        entry=select_entry_price(row),
        stop=0,
        target=0,
        stop_distance_pct=0,
        reward_distance_pct=0,
        rr=0,
        risk_budget=config.account_equity * config.risk_per_trade_pct / 100,
        max_position_value=config.account_equity * config.max_position_pct / 100,
        proposed_value=0,
        commission=0,
        slippage=0,
        total_cost=0,
        current_qty=safe_float(get_value(row, "PositionQty", "Shares", default=0)),
        proposed_qty=0,
        final_qty=safe_float(get_value(row, "PositionQty", "Shares", default=0)),
        current_exposure_pct=0,
        projected_exposure_pct=0,
        portfolio_exposure_after_pct=0,
        cash_after=config.available_cash,
        method="no_proposal",
        risk_level="UNKNOWN",
        score=0,
        priority=5,
        proposal_time=proposal_time,
    )


def reject(
    row: Mapping[str, Any],
    action: str,
    reason: str,
    warnings: list[str],
    entry: float,
    stop: float,
    target: float,
    risk_budget: float,
    max_position_value: float,
    current_qty: float,
    account_data: Mapping[str, float],
    risk_score_value: float,
    proposal_time: str,
) -> dict[str, Any]:
    equity = max(account_data["account_equity"], 1)
    current_value = current_qty * entry
    current_exposure_pct = current_value / equity * 100 if entry > 0 else 0
    risk_level = risk_level_from_score(risk_score_value)

    return base_result(
        row=row,
        action=action,
        status="REJECTED",
        risk_approved=False,
        reject_reason=reason,
        warnings=warnings,
        entry=entry,
        stop=stop,
        target=target,
        stop_distance_pct=((entry - stop) / entry * 100) if entry > 0 and stop > 0 and entry > stop else 0,
        reward_distance_pct=((target - entry) / entry * 100) if entry > 0 and target > entry else 0,
        rr=((target - entry) / (entry - stop)) if entry > 0 and target > entry and stop > 0 and entry > stop else 0,
        risk_budget=risk_budget,
        max_position_value=max_position_value,
        proposed_value=0,
        commission=0,
        slippage=0,
        total_cost=0,
        current_qty=current_qty,
        proposed_qty=0,
        final_qty=current_qty,
        current_exposure_pct=current_exposure_pct,
        projected_exposure_pct=current_exposure_pct,
        portfolio_exposure_after_pct=account_data["total_exposure"] / equity * 100,
        cash_after=account_data["available_cash"],
        method="rejected",
        risk_level=risk_level,
        score=risk_score_value,
        priority=proposal_priority(action, "REJECTED", safe_float(get_value(row, "AIConfidence", default=0)), reason == "BELOW_STOP"),
        proposal_time=proposal_time,
    )


def buy_or_add_proposal(
    row: Mapping[str, Any],
    action: str,
    portfolio: Mapping[str, Any],
    account_data: Mapping[str, float],
    config: RiskConfig,
    proposal_time: str,
) -> dict[str, Any]:
    warnings: list[str] = []
    symbol = safe_text(get_value(row, "Symbol", default="")).upper()
    market = safe_text(get_value(row, "Market", default="")).upper()
    entry = select_entry_price(row)
    risk_budget = account_data["account_equity"] * config.risk_per_trade_pct / 100
    max_position_value = account_data["account_equity"] * config.max_position_pct / 100
    current_qty = safe_float(portfolio["qty"])
    current_position_value = safe_float(portfolio["current_value"]) or current_qty * entry
    ai_blockers = parse_ai_blockers(get_value(row, "AIBlockers", default=""))
    severe_ai_blockers = ai_blockers & SEVERE_AI_BLOCKERS

    if entry <= 0:
        return reject(row, action, "MISSING_PRICE", warnings, entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 85, proposal_time)

    if action == "BUY" and portfolio["has_position"]:
        return reject(row, action, "ALREADY_OWNED", warnings, entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 75, proposal_time)

    if action == "ADD":
        if not portfolio["has_position"]:
            return reject(row, action, "NO_EXISTING_POSITION", warnings, entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 75, proposal_time)

        if not config.allow_add_position:
            return reject(row, action, "ADD_DISABLED", warnings, entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 70, proposal_time)

    if severe_ai_blockers:
        reason = "AI_BLOCKED"

        if "MISSING_PRICE" in severe_ai_blockers:
            reason = "MISSING_PRICE"
        elif "INVALID_STOP" in severe_ai_blockers:
            reason = "INVALID_STOP"

        return reject(row, action, reason, [f"AI blocker: {', '.join(sorted(severe_ai_blockers))}"], entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 90, proposal_time)

    stop, stop_method = select_stop_price(row, entry, action, config)

    if stop_method == "invalid_stop" or stop >= entry:
        return reject(row, action, "INVALID_STOP", warnings, entry, stop, 0, risk_budget, max_position_value, current_qty, account_data, 85, proposal_time)

    stop_distance_pct = (entry - stop) / entry * 100

    if stop_distance_pct <= 0:
        return reject(row, action, "INVALID_STOP", warnings, entry, stop, 0, risk_budget, max_position_value, current_qty, account_data, 85, proposal_time)

    if stop_distance_pct > config.max_stop_loss_pct:
        return reject(row, action, "STOP_TOO_WIDE", warnings, entry, stop, 0, risk_budget, max_position_value, current_qty, account_data, 85, proposal_time)

    target, _ = select_target_price(row, entry, stop, action, config)

    if target <= entry:
        return reject(row, action, "LOW_RR", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 75, proposal_time)

    reward_distance_pct = (target - entry) / entry * 100
    rr = (target - entry) / (entry - stop)

    if rr < config.min_rr:
        return reject(row, action, "LOW_RR", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 75, proposal_time)

    if action == "BUY" and account_data["open_positions"] >= config.max_open_positions:
        return reject(row, action, "MAX_OPEN_POSITIONS", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 70, proposal_time)

    remaining_position_value = max_position_value - (current_position_value if action == "ADD" else 0)

    if remaining_position_value <= 0:
        return reject(row, action, "MAX_POSITION_EXCEEDED", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 75, proposal_time)

    risk_per_share = entry - stop
    risk_based_qty = risk_budget / risk_per_share if risk_per_share > 0 else 0
    position_cap_qty = remaining_position_value / entry
    max_order_qty = config.max_order_value / entry if config.max_order_value > 0 else position_cap_qty
    cash_qty = account_data["available_cash"] / (entry * (1 + (config.commission_pct + config.slippage_pct) / 100))
    exposure_room_value = max(account_data["account_equity"] * config.max_total_exposure_pct / 100 - account_data["total_exposure"], 0)
    exposure_qty = exposure_room_value / entry
    sector_room_value = max(account_data["account_equity"] * config.max_sector_exposure_pct / 100 - account_data["sector_exposure"], 0)
    sector_qty = sector_room_value / entry if account_data["sector_exposure"] > 0 else position_cap_qty

    raw_qty = min(risk_based_qty, position_cap_qty, max_order_qty, cash_qty, exposure_qty, sector_qty)
    proposed_qty = round_quantity(raw_qty, symbol, market, config)

    if proposed_qty <= 0 and is_set_market(symbol, market):
        return reject(row, action, "BELOW_BOARD_LOT", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 70, proposal_time)

    if proposed_qty <= 0 and exposure_room_value <= 0:
        return reject(row, action, "MAX_TOTAL_EXPOSURE", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 80, proposal_time)

    if proposed_qty <= 0 and account_data["sector_exposure"] > 0 and sector_room_value <= 0:
        return reject(row, action, "MAX_SECTOR_EXPOSURE", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 75, proposal_time)

    if proposed_qty <= 0:
        return reject(row, action, "INVALID_QUANTITY", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 70, proposal_time)

    proposed_value = proposed_qty * entry
    commission, slippage, total_cost = order_cost(proposed_value, config)

    while proposed_qty > 0 and total_cost > account_data["available_cash"]:
        reduced_qty = proposed_qty - (config.set_board_lot if is_set_market(symbol, market) else 1)
        proposed_qty = round_quantity(reduced_qty, symbol, market, config)
        proposed_value = proposed_qty * entry
        commission, slippage, total_cost = order_cost(proposed_value, config)

    if proposed_qty <= 0:
        return reject(row, action, "INSUFFICIENT_CASH", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 80, proposal_time)

    if proposed_value < config.min_order_value:
        return reject(row, action, "BELOW_MIN_ORDER", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, 60, proposal_time)

    final_qty = current_qty + proposed_qty
    final_position_value = final_qty * entry
    current_exposure_pct = current_position_value / account_data["account_equity"] * 100 if account_data["account_equity"] else 0
    projected_exposure_pct = final_position_value / account_data["account_equity"] * 100 if account_data["account_equity"] else 0
    portfolio_exposure_after_pct = (account_data["total_exposure"] + proposed_value) / account_data["account_equity"] * 100 if account_data["account_equity"] else 0
    score = risk_score(row, action, ai_blockers, stop_distance_pct, rr, projected_exposure_pct, portfolio_exposure_after_pct, False)
    level = risk_level_from_score(score)

    if level == "HIGH":
        return reject(row, action, "HIGH_RISK", warnings, entry, stop, target, risk_budget, max_position_value, current_qty, account_data, score, proposal_time)

    status = "PENDING_APPROVAL" if config.require_manual_approval else "APPROVED_FOR_PAPER"

    return base_result(
        row=row,
        action=action,
        status=status,
        risk_approved=True,
        reject_reason="NONE",
        warnings=warnings + ([f"Stop from {stop_method}"] if stop_method else []),
        entry=entry,
        stop=stop,
        target=target,
        stop_distance_pct=stop_distance_pct,
        reward_distance_pct=reward_distance_pct,
        rr=rr,
        risk_budget=risk_budget,
        max_position_value=max_position_value,
        proposed_value=proposed_value,
        commission=commission,
        slippage=slippage,
        total_cost=total_cost,
        current_qty=current_qty,
        proposed_qty=proposed_qty,
        final_qty=final_qty,
        current_exposure_pct=current_exposure_pct,
        projected_exposure_pct=projected_exposure_pct,
        portfolio_exposure_after_pct=portfolio_exposure_after_pct,
        cash_after=account_data["available_cash"] - total_cost,
        method="risk_based_min_cap",
        risk_level=level,
        score=score,
        priority=proposal_priority(action, status, safe_float(get_value(row, "AIConfidence", default=0)), False),
        proposal_time=proposal_time,
    )


def reduce_or_exit_proposal(
    row: Mapping[str, Any],
    action: str,
    portfolio: Mapping[str, Any],
    account_data: Mapping[str, float],
    config: RiskConfig,
    proposal_time: str,
) -> dict[str, Any]:
    warnings: list[str] = []
    symbol = safe_text(get_value(row, "Symbol", default="")).upper()
    market = safe_text(get_value(row, "Market", default="")).upper()
    entry = select_entry_price(row)
    current_qty = safe_float(portfolio["qty"])
    current_value = safe_float(portfolio["current_value"]) or (current_qty * entry)
    risk_budget = account_data["account_equity"] * config.risk_per_trade_pct / 100
    max_position_value = account_data["account_equity"] * config.max_position_pct / 100
    ai_blockers = parse_ai_blockers(get_value(row, "AIBlockers", default=""))
    below_stop = "BELOW_STOP" in ai_blockers or (
        safe_float(get_value(row, "Stop", "StopLoss", default=0)) > 0
        and entry > 0
        and entry <= safe_float(get_value(row, "Stop", "StopLoss", default=0))
    )

    if entry <= 0:
        return reject(row, action, "MISSING_PRICE", warnings, entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 85, proposal_time)

    if not portfolio["has_position"] or current_qty <= 0:
        return reject(row, action, "NO_EXISTING_POSITION", warnings, entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 75, proposal_time)

    if action == "REDUCE" and not config.allow_reduce_position:
        return reject(row, action, "REDUCE_DISABLED", warnings, entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 70, proposal_time)

    if action == "EXIT":
        proposed_qty = current_qty
    else:
        ai_risk = safe_text(get_value(row, "AIRiskLevel", default="UNKNOWN")).upper()
        lifecycle = safe_text(get_value(row, "LifecycleState", default="")).upper()
        reduce_pct = 0.5 if ai_risk == "HIGH" or lifecycle == "EXTENDED" else 0.25 if ai_risk == "MEDIUM" else 0.2
        proposed_qty = current_qty * reduce_pct
        proposed_qty = min(proposed_qty, current_qty)
        proposed_qty = round_quantity(proposed_qty, symbol, market, config)

        if proposed_qty <= 0:
            return reject(row, action, "BELOW_BOARD_LOT" if is_set_market(symbol, market) else "INVALID_QUANTITY", warnings, entry, 0, 0, risk_budget, max_position_value, current_qty, account_data, 65, proposal_time)

    proposed_value = min(proposed_qty, current_qty) * entry
    commission, slippage, proceeds = order_proceeds(proposed_value, config)
    final_qty = max(current_qty - proposed_qty, 0)
    final_position_value = final_qty * entry
    current_exposure_pct = current_value / account_data["account_equity"] * 100 if account_data["account_equity"] else 0
    projected_exposure_pct = final_position_value / account_data["account_equity"] * 100 if account_data["account_equity"] else 0
    portfolio_exposure_after_pct = max(account_data["total_exposure"] - proposed_value, 0) / account_data["account_equity"] * 100 if account_data["account_equity"] else 0
    score = risk_score(row, action, ai_blockers, 0, safe_float(get_value(row, "RR", default=0)), projected_exposure_pct, portfolio_exposure_after_pct, below_stop)
    level = risk_level_from_score(score)
    status = "PENDING_APPROVAL" if config.require_manual_approval else "APPROVED_FOR_PAPER"

    return base_result(
        row=row,
        action=action,
        status=status,
        risk_approved=True,
        reject_reason="NONE",
        warnings=warnings,
        entry=entry,
        stop=safe_float(get_value(row, "Stop", "StopLoss", default=0)),
        target=safe_float(get_value(row, "Target", default=0)),
        stop_distance_pct=0,
        reward_distance_pct=0,
        rr=safe_float(get_value(row, "RR", default=0)),
        risk_budget=risk_budget,
        max_position_value=max_position_value,
        proposed_value=proposed_value,
        commission=commission,
        slippage=slippage,
        total_cost=commission + slippage,
        current_qty=current_qty,
        proposed_qty=proposed_qty,
        final_qty=final_qty,
        current_exposure_pct=current_exposure_pct,
        projected_exposure_pct=projected_exposure_pct,
        portfolio_exposure_after_pct=portfolio_exposure_after_pct,
        cash_after=account_data["available_cash"] + proceeds,
        method="full_exit" if action == "EXIT" else "risk_trim",
        risk_level=level,
        score=score,
        priority=proposal_priority(action, status, safe_float(get_value(row, "AIConfidence", default=0)), below_stop),
        proposal_time=proposal_time,
    )


def evaluate_risk(
    row: Any,
    portfolio: Mapping[str, Any] | None = None,
    account: Mapping[str, Any] | None = None,
    config: RiskConfig | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row_data = row_to_dict(row)
    cfg = normalize_config(config)
    proposal_time = datetime.now().isoformat(timespec="seconds")
    action = safe_text(get_value(row_data, "AIDecision", default="NO_ACTION")).upper()
    queue_class = safe_text(get_value(row_data, "QueueClass", default="")).upper()
    eligible_for_buy = str(
        get_value(row_data, "EligibleForBuyQueue", default="")
    ).strip().upper() in {"TRUE", "1", "YES", "Y"}

    if queue_class in {"PREPARE", "WATCH"}:
        return no_proposal(
            row_data,
            "NONE",
            cfg,
            proposal_time,
            reason=f"QUEUE_CLASS_{queue_class}",
        )

    if queue_class == "IGNORE":
        return no_proposal(
            row_data,
            "NONE",
            cfg,
            proposal_time,
            reason="QUEUE_CLASS_IGNORE",
        )

    if queue_class == "BUY" and action not in {"ADD", "REDUCE", "EXIT"}:
        action = "BUY"

    if queue_class and queue_class != "BUY" and action in {"BUY", "ADD"}:
        return no_proposal(
            row_data,
            "NONE",
            cfg,
            proposal_time,
            reason="NOT_BUY_QUEUE_ELIGIBLE",
        )

    if action == "BUY" and queue_class == "BUY" and not eligible_for_buy:
        return no_proposal(
            row_data,
            "NONE",
            cfg,
            proposal_time,
            reason="BUY_QUEUE_FLAG_FALSE",
        )

    if action not in {"BUY", "ADD", "REDUCE", "EXIT", "HOLD", "WATCH", "PREPARE", "AVOID", "NO_ACTION"}:
        account_data = normalize_account(row_data, account, cfg)
        portfolio_data = normalize_portfolio_context(row_data, portfolio)
        return reject(row_data, "NONE", "UNSUPPORTED_ACTION", [], select_entry_price(row_data), 0, 0, account_data["account_equity"] * cfg.risk_per_trade_pct / 100, account_data["account_equity"] * cfg.max_position_pct / 100, portfolio_data["qty"], account_data, 70, proposal_time)

    if action not in ACTIONABLE_DECISIONS:
        proposal_action = "HOLD" if action == "HOLD" else "NONE"
        return no_proposal(
            row_data,
            proposal_action,
            cfg,
            proposal_time,
            reason=f"ACTION_{action}_NOT_ACTIONABLE",
        )

    account_data = normalize_account(row_data, account, cfg)
    portfolio_data = normalize_portfolio_context(row_data, portfolio)

    if action in {"BUY", "ADD"}:
        return buy_or_add_proposal(row_data, action, portfolio_data, account_data, cfg, proposal_time)

    return reduce_or_exit_proposal(row_data, action, portfolio_data, account_data, cfg, proposal_time)


def build_portfolio_lookup(portfolio_dataframe: pd.DataFrame | None) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]], dict[str, float]]:
    if portfolio_dataframe is None or portfolio_dataframe.empty:
        return {}, {}, {"total_exposure": 0.0, "open_positions": 0.0}

    data = portfolio_dataframe.copy()

    for column in ["Symbol", "Market", "Status", "Shares", "PositionQty", "AverageCost", "EntryPrice", "CurrentPrice", "LastPrice", "CurrentValue", "UnrealizedReturnPct"]:
        if column not in data.columns:
            data[column] = "" if column in {"Symbol", "Market", "Status"} else pd.NA

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}
    total_exposure = 0.0
    open_positions = 0

    for _, row in data.iterrows():
        status = safe_text(row.get("Status"), "OPEN").upper()
        qty = safe_float(get_value(row, "PositionQty", "Shares", default=0))
        market = safe_text(row.get("Market")).upper()
        symbol = normalize_symbol(row.get("Symbol"), market)
        entry = safe_float(get_value(row, "CurrentPrice", "LastPrice", "EntryPrice", "AverageCost", default=0))
        current_value = safe_float(row.get("CurrentValue")) or qty * entry
        has_position = status == "OPEN" and qty > 0

        if has_position:
            total_exposure += current_value
            open_positions += 1

        item = {
            "has_position": has_position,
            "qty": qty,
            "average_cost": safe_float(get_value(row, "AverageCost", "EntryPrice", default=0)),
            "current_value": current_value,
            "unrealized_return_pct": safe_float(row.get("UnrealizedReturnPct")),
            "PortfolioStatus": status,
        }
        by_key[(symbol, market)] = item
        by_symbol[safe_text(row.get("Symbol")).upper()] = item
        by_symbol[symbol] = item

    return by_key, by_symbol, {"total_exposure": total_exposure, "open_positions": float(open_positions)}


def portfolio_for_row(row: Mapping[str, Any], by_key: Mapping[tuple[str, str], Mapping[str, Any]], by_symbol: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    market = safe_text(row.get("Market")).upper()
    raw_symbol = safe_text(row.get("Symbol")).upper()
    symbol = normalize_symbol(raw_symbol, market)

    return by_key.get((symbol, market)) or by_symbol.get(raw_symbol) or by_symbol.get(symbol)


def account_for_row(
    row: Mapping[str, Any],
    base_account: Mapping[str, Any],
    portfolio_totals: Mapping[str, float],
) -> dict[str, Any]:
    account = dict(base_account)

    if "TotalExposure" not in account and "total_exposure" not in account:
        account["TotalExposure"] = portfolio_totals.get("total_exposure", 0)

    if "OpenPositions" not in account and "open_positions" not in account:
        account["OpenPositions"] = portfolio_totals.get("open_positions", 0)

    for source, target in [
        ("AccountEquity", "AccountEquity"),
        ("AvailableCash", "AvailableCash"),
        ("TotalExposure", "TotalExposure"),
        ("OpenPositions", "OpenPositions"),
    ]:
        if source in row and not pd.isna(row[source]):
            account[target] = row[source]

    return account


def build_order_proposals(
    ai_decisions_dataframe: pd.DataFrame,
    portfolio_dataframe: pd.DataFrame | None = None,
    account: Mapping[str, Any] | None = None,
    config: RiskConfig | Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    cfg = normalize_config(config)
    base = ai_decisions_dataframe.copy(deep=True) if ai_decisions_dataframe is not None else pd.DataFrame()

    for column in PROPOSAL_COLUMNS:
        if column not in base.columns:
            base[column] = pd.Series(dtype="object")

    if base.empty:
        return base

    generated_columns = [
        column
        for column in PROPOSAL_COLUMNS
        if column not in {"Symbol", "Market"}
    ]
    proposal_input = base.drop(columns=generated_columns, errors="ignore").copy()
    by_key, by_symbol, portfolio_totals = build_portfolio_lookup(portfolio_dataframe)
    base_account = dict(account or {})

    proposals = []

    for _, row in proposal_input.iterrows():
        row_data = row.to_dict()
        proposals.append(
            evaluate_risk(
                row_data,
                portfolio=portfolio_for_row(row_data, by_key, by_symbol),
                account=account_for_row(row_data, base_account, portfolio_totals),
                config=cfg,
            )
        )

    proposal_df = pd.DataFrame(proposals)
    output = proposal_input.reset_index(drop=True)
    append_columns = [
        column
        for column in PROPOSAL_COLUMNS
        if column not in output.columns
    ]
    output = pd.concat([output, proposal_df[append_columns].reset_index(drop=True)], axis=1)
    output = output.sort_values(
        by=[
            "ProposalPriority",
            "RiskApproved",
            "AIConfidence" if "AIConfidence" in output.columns else "RiskScore",
            "AIReviewPriority" if "AIReviewPriority" in output.columns else "ProposalPriority",
        ],
        ascending=[True, False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)

    for column in PROPOSAL_COLUMNS:
        if column in output.columns:
            default_value = "NONE" if column in {"RejectReason", "RiskWarnings"} else ""
            if column in {"RejectReason", "RiskWarnings", "ProposalId"}:
                output[column] = output[column].fillna(default_value)
            else:
                output[column] = output[column].fillna(0)

    return output


def build_risk_summary(
    proposals_dataframe: pd.DataFrame,
    account: Mapping[str, Any] | None = None,
    config: RiskConfig | Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    cfg = normalize_config(config)
    account_data = normalize_account({}, account, cfg)
    proposals = proposals_dataframe.copy() if proposals_dataframe is not None else pd.DataFrame()

    for column in PROPOSAL_COLUMNS:
        if column not in proposals.columns:
            proposals[column] = 0 if column not in {"ProposalStatus", "ProposalAction", "RiskLevel"} else ""

    actionable = proposals[proposals["ProposalStatus"].isin(["PENDING_APPROVAL", "APPROVED_FOR_PAPER"])].copy()
    buy_value = safe_float(actionable[actionable["ProposalAction"].isin(["BUY", "ADD"])]["ProposedOrderValue"].sum())
    sell_value = safe_float(actionable[actionable["ProposalAction"].isin(["REDUCE", "EXIT"])]["ProposedOrderValue"].sum())
    commission = safe_float(actionable["EstimatedCommission"].sum())
    slippage = safe_float(actionable["EstimatedSlippage"].sum())
    current_exposure = account_data["total_exposure"]
    projected_exposure = max(buy_value - sell_value, 0)
    equity = max(account_data["account_equity"], 1)
    estimated_cash_after = account_data["available_cash"] - safe_float(actionable[actionable["ProposalAction"].isin(["BUY", "ADD"])]["EstimatedTotalCost"].sum())
    estimated_cash_after += sell_value - safe_float(actionable[actionable["ProposalAction"].isin(["REDUCE", "EXIT"])]["EstimatedTotalCost"].sum())

    summary = {
        "RunTime": datetime.now().isoformat(timespec="seconds"),
        "AccountEquity": account_data["account_equity"],
        "AvailableCash": account_data["available_cash"],
        "CurrentExposure": current_exposure,
        "CurrentExposurePct": round(current_exposure / equity * 100, 4),
        "ProjectedExposure": round(projected_exposure, 6),
        "ProjectedExposurePct": round(projected_exposure / equity * 100, 4),
        "OpenPositions": int(account_data["open_positions"]),
        "PendingProposals": int((proposals["ProposalStatus"] == "PENDING_APPROVAL").sum()),
        "ApprovedProposals": int((proposals["ProposalStatus"] == "APPROVED_FOR_PAPER").sum()),
        "RejectedProposals": int((proposals["ProposalStatus"] == "REJECTED").sum()),
        "BuyProposals": int((proposals["ProposalAction"] == "BUY").sum()),
        "AddProposals": int((proposals["ProposalAction"] == "ADD").sum()),
        "ReduceProposals": int((proposals["ProposalAction"] == "REDUCE").sum()),
        "ExitProposals": int((proposals["ProposalAction"] == "EXIT").sum()),
        "TotalProposedBuyValue": round(buy_value, 6),
        "TotalProposedSellValue": round(sell_value, 6),
        "EstimatedCommission": round(commission, 6),
        "EstimatedSlippage": round(slippage, 6),
        "EstimatedCashAfter": round(estimated_cash_after, 6),
        "MaxSinglePositionPct": round(
            safe_float(actionable["ProjectedExposurePct"].max())
            if not actionable.empty
            else 0,
            4,
        ),
        "AverageRiskScore": round(safe_float(pd.to_numeric(proposals["RiskScore"], errors="coerce").mean()), 2),
        "HighRiskProposalCount": int((proposals["RiskLevel"] == "HIGH").sum()),
        "RiskManagerVersion": RISK_MANAGER_VERSION,
    }

    return pd.DataFrame([summary], columns=SUMMARY_COLUMNS)


def save_order_proposals(proposals: pd.DataFrame, path: Path = ORDER_PROPOSALS_FILE) -> Path:
    path.parent.mkdir(exist_ok=True)
    atomic_write_csv(proposals, path, index=False)

    return path


def save_risk_summary(summary: pd.DataFrame, path: Path = RISK_SUMMARY_FILE) -> Path:
    path.parent.mkdir(exist_ok=True)
    atomic_write_csv(summary, path, index=False)

    return path
