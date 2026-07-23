from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
import hashlib

import pandas as pd

from approval_queue import (
    APPROVAL_HISTORY_FILE,
    APPROVAL_QUEUE_FILE,
    load_approval_queue,
    sync_approval_queue,
)
from config import (
    INTERVAL,
    MAX_FRESH_CROSS_DAYS,
    PERIOD,
    rvol_action_for_market,
    rvol_thresholds_for_market,
)
from data import is_price_cache_fresh, load_price_cache, price_cache_path
from fresh_cross_candidates import is_candidate_extended
from fresh_cross_policy import evaluate_fresh_cross_policy
from paper_broker import PaperBrokerConfig, load_paper_broker_config
from paper_portfolio import (
    PAPER_PORTFOLIO_FILE,
    calculate_portfolio_summary,
    load_paper_account,
    load_paper_portfolio,
    normalize_paper_portfolio,
    refresh_position_marks,
    save_paper_portfolio,
)
from risk_manager import (
    RiskConfig,
    SEVERE_AI_BLOCKERS,
    evaluate_risk,
    load_risk_config,
)
from runtime_io import atomic_write_csv


PAPER_TRADING_ROBOT_VERSION = "1.0"
ROBOT_PROPOSALS_FILE = Path("output") / "paper_trading_robot_proposals.csv"
ROBOT_AUDIT_FILE = Path("output") / "paper_trading_robot_audit.csv"
THREE_RED_DAYS_EXIT_REASON = "THREE_RED_DAYS"
EXIT_REASON_LABELS = {
    THREE_RED_DAYS_EXIT_REASON: "ปิดแดงต่อเนื่อง 3 วัน",
}

AUDIT_COLUMNS = [
    "ScanRunId",
    "Symbol",
    "Market",
    "AutomationType",
    "LatestPriceDate",
    "CrossDate",
    "CrossAge",
    "CrossAgeSource",
    "EMA9",
    "EMA20",
    "RVOL",
    "AIDecision",
    "QueueClass",
    "FreshCrossEligible",
    "HardGateEligible",
    "RiskApproved",
    "ProposalStatus",
    "ProposalId",
    "RobotKey",
    "ExclusionReason",
    "AutomationReason",
    "AuditTime",
    "RobotVersion",
]


@dataclass(frozen=True)
class PaperRobotResult:
    proposals: pd.DataFrame
    audit: pd.DataFrame
    queue: pd.DataFrame
    portfolio: pd.DataFrame


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def safe_upper(value: Any, default: str = "") -> str:
    return safe_text(value, default).upper()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return safe_upper(value) in {"TRUE", "YES", "Y", "1"}


def exit_reason_label(value: Any) -> str:
    reason = safe_upper(value)
    return EXIT_REASON_LABELS.get(reason, safe_text(value))


def consecutive_red_days(history: pd.DataFrame | None) -> int:
    if history is None or history.empty:
        return 0

    columns = {str(column).strip().lower(): column for column in history.columns}
    open_column = columns.get("open")
    close_column = columns.get("close")
    if open_column is None or close_column is None:
        return 0

    frame = history.copy()
    date_column = columns.get("date")
    if date_column is not None:
        frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
        frame = frame.sort_values(date_column, kind="mergesort")
    frame[open_column] = pd.to_numeric(frame[open_column], errors="coerce")
    frame[close_column] = pd.to_numeric(frame[close_column], errors="coerce")

    count = 0
    for _, candle in frame.iloc[::-1].iterrows():
        open_price = candle[open_column]
        close_price = candle[close_column]
        if (
            pd.isna(open_price)
            or pd.isna(close_price)
            or float(open_price) <= 0
            or float(close_price) <= 0
            or float(close_price) >= float(open_price)
        ):
            break
        count += 1
    return count


def _history_for_symbol(
    histories: Mapping[str, pd.DataFrame] | None,
    symbol: str,
) -> pd.DataFrame:
    if not histories:
        return pd.DataFrame()
    lookup = [symbol, symbol.removesuffix(".BK"), f"{symbol.removesuffix('.BK')}.SET"]
    normalized = {safe_upper(key): value for key, value in histories.items()}
    for key in lookup:
        history = normalized.get(safe_upper(key))
        if isinstance(history, pd.DataFrame):
            return history
    return pd.DataFrame()


def load_fresh_position_daily_histories(
    portfolio_dataframe: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    portfolio = normalize_paper_portfolio(portfolio_dataframe)
    histories: dict[str, pd.DataFrame] = {}
    if portfolio.empty:
        return histories

    open_set_positions = portfolio[
        (portfolio["Market"].astype(str).str.upper() == "SET")
        & (portfolio["PositionStatus"].astype(str).str.upper() == "OPEN")
        & (pd.to_numeric(portfolio["PositionQty"], errors="coerce").fillna(0) > 0)
    ]
    for symbol_value in open_set_positions["Symbol"].drop_duplicates():
        symbol = safe_upper(symbol_value)
        cache_path = price_cache_path(symbol, "SET", PERIOD, INTERVAL)
        if not is_price_cache_fresh(cache_path):
            continue
        history = load_price_cache(cache_path)
        if history.empty:
            continue
        histories[symbol] = history
        histories[symbol.removesuffix(".BK")] = history
    return histories


def parse_blockers(value: Any) -> set[str]:
    return {
        part.strip()
        for part in safe_upper(value).replace(",", ";").split(";")
        if part.strip()
    }


def stable_id(*parts: Any, length: int = 12) -> str:
    raw = "|".join(safe_text(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def proposal_identity(symbol: str, scan_run_id: str, automation_type: str) -> tuple[str, str]:
    symbol_key = safe_upper(symbol)
    scan_key = safe_text(scan_run_id)
    automation_key = safe_upper(automation_type, "ENTRY")
    robot_key = f"SET|{symbol_key}|{scan_key}"
    proposal_id = f"PTR-SET-{symbol_key.replace('.', '')}-{automation_key}-{stable_id(robot_key, automation_key)}"
    return robot_key, proposal_id


def _entry_gate(row: Mapping[str, Any]) -> tuple[bool, str, Any]:
    market = safe_upper(row.get("Market"))
    if market != "SET":
        return False, "EXECUTION_SCOPE_SET_ONLY", evaluate_fresh_cross_policy(row)

    if not safe_text(row.get("ScanRunId")):
        return False, "MISSING_SCAN_RUN_ID", evaluate_fresh_cross_policy(row)

    policy = evaluate_fresh_cross_policy(row)
    if not policy.ema9_above_ema20:
        return False, "EMA9_NOT_ABOVE_EMA20", policy
    if not policy.cross_date or policy.age is None:
        return False, "NO_BULLISH_CROSS_EVENT", policy
    if policy.age > MAX_FRESH_CROSS_DAYS:
        return False, f"CROSS_AGE_{policy.age}", policy
    if not policy.eligible:
        return False, "NO_BULLISH_CROSS_EVENT", policy

    if is_candidate_extended(dict(row)):
        return False, "EXTENDED", policy

    signal = " ".join(
        safe_upper(row.get(column))
        for column in ("StrategySignal", "Signal", "LifecycleState")
    )
    if "SKIP" in signal:
        return False, "SCANNER_SKIP", policy
    if "BUY" not in signal:
        return False, "SCANNER_SIGNAL_NOT_BUY", policy
    if safe_upper(row.get("AIDecision")) != "BUY":
        return False, "AI_DECISION_NOT_BUY", policy
    if safe_upper(row.get("QueueClass")) != "BUY":
        return False, "QUEUE_CLASS_NOT_BUY", policy
    if not safe_bool(row.get("EligibleForBuyQueue")):
        return False, "BUY_QUEUE_FLAG_FALSE", policy
    if "BaseEligible" in row and not safe_bool(row.get("BaseEligible")):
        return False, "CANDIDATE_ELIGIBILITY_FAILED", policy

    rvol = safe_float(row.get("RVOL"))
    if rvol_action_for_market("SET", rvol) != "BUY":
        threshold = rvol_thresholds_for_market("SET")["BUY"]
        return False, f"RVOL_BELOW_SET_BUY_{threshold:g}X", policy

    blockers = parse_blockers(row.get("AIBlockers"))
    severe = sorted(blockers & SEVERE_AI_BLOCKERS)
    if severe:
        return False, f"AI_BLOCKER_{severe[0]}", policy

    market_quality = safe_upper(row.get("MarketQualityLabel"))
    if market_quality in {"AVOID", "POOR", "UNSAFE"}:
        return False, "MARKET_QUALITY_FAILED", policy

    blocking_reasons = safe_text(row.get("BlockingReasons"))
    if blocking_reasons and blocking_reasons.upper() not in {"NONE", "NAN"}:
        return False, "CANDIDATE_ELIGIBILITY_FAILED", policy

    return True, "PASSED_ALL_HARD_GATES", policy


def _portfolio_context(portfolio: pd.DataFrame, symbol: str, market: str = "SET") -> dict[str, Any]:
    if portfolio.empty:
        return {
            "has_position": False,
            "qty": 0.0,
            "average_cost": 0.0,
            "current_value": 0.0,
            "unrealized_return_pct": 0.0,
        }

    match = portfolio[
        (portfolio["Symbol"].astype(str).str.upper() == safe_upper(symbol))
        & (portfolio["Market"].astype(str).str.upper() == safe_upper(market))
        & (portfolio["PositionStatus"].astype(str).str.upper() == "OPEN")
    ]
    if match.empty:
        return {
            "has_position": False,
            "qty": 0.0,
            "average_cost": 0.0,
            "current_value": 0.0,
            "unrealized_return_pct": 0.0,
        }

    item = match.iloc[0]
    return {
        "has_position": safe_float(item.get("PositionQty")) > 0,
        "qty": safe_float(item.get("PositionQty")),
        "average_cost": safe_float(item.get("AverageCost")),
        "current_value": safe_float(item.get("MarketValue")),
        "unrealized_return_pct": safe_float(item.get("UnrealizedReturnPct")),
    }


def _risk_account(account: Mapping[str, Any], portfolio: pd.DataFrame) -> dict[str, Any]:
    summary = calculate_portfolio_summary(portfolio, account)
    return {
        "AccountEquity": safe_float(summary.get("TotalEquity")),
        "AvailableCash": safe_float(summary.get("Cash")),
        "TotalExposure": safe_float(summary.get("MarketValue")),
        "OpenPositions": int(safe_float(summary.get("OpenPositions"))),
    }


def _audit_row(
    row: Mapping[str, Any],
    *,
    policy: Any,
    hard_gate: bool,
    exclusion_reason: str,
    audit_time: str,
    proposal: Mapping[str, Any] | None = None,
    automation_type: str = "ENTRY",
    automation_reason: str = "",
) -> dict[str, Any]:
    proposal = dict(proposal or {})
    return {
        "ScanRunId": safe_text(row.get("ScanRunId")),
        "Symbol": safe_upper(row.get("Symbol")),
        "Market": safe_upper(row.get("Market")),
        "AutomationType": safe_upper(automation_type),
        "LatestPriceDate": safe_text(getattr(policy, "latest_price_date", row.get("LatestPriceDate", ""))),
        "CrossDate": safe_text(getattr(policy, "cross_date", row.get("CrossDate", ""))),
        "CrossAge": getattr(policy, "age", row.get("DaysSinceEMA9CrossEMA20", pd.NA)),
        "CrossAgeSource": safe_text(getattr(policy, "cross_age_source", row.get("CrossAgeSource", ""))),
        "EMA9": safe_float(row.get("EMA9")),
        "EMA20": safe_float(row.get("EMA20")),
        "RVOL": safe_float(row.get("RVOL")),
        "AIDecision": safe_upper(row.get("AIDecision")),
        "QueueClass": safe_upper(row.get("QueueClass")),
        "FreshCrossEligible": bool(getattr(policy, "eligible", False)),
        "HardGateEligible": bool(hard_gate),
        "RiskApproved": safe_bool(proposal.get("RiskApproved")),
        "ProposalStatus": safe_upper(proposal.get("ProposalStatus")),
        "ProposalId": safe_text(proposal.get("ProposalId")),
        "RobotKey": safe_text(proposal.get("RobotKey")),
        "ExclusionReason": exclusion_reason,
        "AutomationReason": automation_reason,
        "AuditTime": audit_time,
        "RobotVersion": PAPER_TRADING_ROBOT_VERSION,
    }


def update_exit_tracking(
    portfolio_dataframe: pd.DataFrame,
    prices: Mapping[str, Any],
    config: PaperBrokerConfig | Mapping[str, Any] | None = None,
    now: datetime | None = None,
    daily_histories: Mapping[str, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    cfg = config if isinstance(config, PaperBrokerConfig) else load_paper_broker_config(overrides=config)
    required_red_days = max(int(safe_float(cfg.three_red_days_required, 3)), 1)
    portfolio = normalize_paper_portfolio(portfolio_dataframe)
    triggers: list[dict[str, Any]] = []
    stamp = (now or datetime.now()).isoformat(timespec="seconds")

    for idx, position in portfolio.iterrows():
        if (
            safe_upper(position.get("Market")) != "SET"
            or safe_upper(position.get("PositionStatus")) != "OPEN"
            or safe_float(position.get("PositionQty")) <= 0
        ):
            continue

        symbol = safe_upper(position.get("Symbol"))
        lookup = [
            symbol,
            symbol.removesuffix(".BK"),
            f"{symbol.removesuffix('.BK')}.SET",
        ]
        daily_history = _history_for_symbol(daily_histories, symbol)
        current = next((safe_float(prices.get(key)) for key in lookup if safe_float(prices.get(key)) > 0), 0.0)
        if current <= 0 and not daily_history.empty:
            close_columns = {
                str(column).strip().lower(): column
                for column in daily_history.columns
            }
            close_column = close_columns.get("close")
            if close_column is not None:
                closes = pd.to_numeric(daily_history[close_column], errors="coerce").dropna()
                if not closes.empty:
                    current = safe_float(closes.iloc[-1])
        if current <= 0:
            continue

        highest = max(safe_float(position.get("HighestPrice")), safe_float(position.get("LastPrice")), current)
        stop = safe_float(position.get("StopPrice"))
        target = safe_float(position.get("TargetPrice"))
        old_trailing = safe_float(position.get("TrailingStopPrice"))
        trailing = 0.0
        if cfg.trailing_stop_enabled and cfg.trailing_stop_pct > 0:
            trailing = highest * (1 - cfg.trailing_stop_pct / 100)
        active_trailing = max(old_trailing, stop, trailing)

        portfolio.at[idx, "LastPrice"] = current
        portfolio.at[idx, "HighestPrice"] = round(highest, 6)
        portfolio.at[idx, "TrailingStopPrice"] = round(active_trailing, 6)
        refreshed = refresh_position_marks(portfolio.loc[idx].to_dict())
        for column, value in refreshed.items():
            portfolio.at[idx, column] = value

        reason = ""
        if stop > 0 and current <= stop:
            reason = "STOP_LOSS"
        elif active_trailing > 0 and current <= active_trailing:
            reason = "TRAILING_STOP"
        elif target > 0 and current >= target:
            reason = "TARGET_REACHED"
        elif (
            cfg.three_red_days_exit_enabled
            and consecutive_red_days(daily_history) >= required_red_days
        ):
            reason = THREE_RED_DAYS_EXIT_REASON

        if reason:
            portfolio.at[idx, "ExitReason"] = reason
            portfolio.at[idx, "ExitTriggeredTime"] = stamp
            triggers.append({**portfolio.loc[idx].to_dict(), "CurrentPrice": current, "ExitReason": reason})

    return normalize_paper_portfolio(portfolio), triggers


def _latest_prices(ai_decisions: pd.DataFrame) -> dict[str, float]:
    prices: dict[str, float] = {}
    if ai_decisions is None or ai_decisions.empty:
        return prices
    for _, row in ai_decisions.iterrows():
        symbol = safe_upper(row.get("Symbol"))
        price = safe_float(row.get("Price", row.get("Close", 0)))
        if symbol and price > 0:
            prices[symbol] = price
            prices[symbol.removesuffix(".BK")] = price
    return prices


def run_paper_trading_robot(
    ai_decisions: pd.DataFrame | None,
    *,
    scan_run_id: str | None = None,
    paper_account: Mapping[str, Any] | None = None,
    paper_portfolio: pd.DataFrame | None = None,
    risk_config: RiskConfig | Mapping[str, Any] | None = None,
    paper_config: PaperBrokerConfig | Mapping[str, Any] | None = None,
    queue_path: Path = APPROVAL_QUEUE_FILE,
    history_path: Path = APPROVAL_HISTORY_FILE,
    proposals_path: Path = ROBOT_PROPOSALS_FILE,
    audit_path: Path = ROBOT_AUDIT_FILE,
    portfolio_path: Path = PAPER_PORTFOLIO_FILE,
    daily_histories: Mapping[str, pd.DataFrame] | None = None,
    now: datetime | None = None,
    persist: bool = True,
) -> PaperRobotResult:
    source = ai_decisions.copy(deep=True) if ai_decisions is not None else pd.DataFrame()
    cfg = risk_config if isinstance(risk_config, RiskConfig) else load_risk_config(overrides=risk_config)
    broker_cfg = paper_config if isinstance(paper_config, PaperBrokerConfig) else load_paper_broker_config(overrides=paper_config)
    if not broker_cfg.paper_only or safe_upper(broker_cfg.execution_mode) != "MANUAL":
        raise ValueError("PAPER_ONLY_MANUAL_EXECUTION_REQUIRED")

    account = dict(paper_account) if paper_account is not None else load_paper_account(config=broker_cfg)
    portfolio = normalize_paper_portfolio(paper_portfolio if paper_portfolio is not None else load_paper_portfolio())
    stamp = (now or datetime.now()).isoformat(timespec="seconds")

    if scan_run_id:
        if "ScanRunId" not in source.columns:
            source["ScanRunId"] = scan_run_id
        else:
            source["ScanRunId"] = source["ScanRunId"].fillna("").replace("", scan_run_id)

    max_positions = min(max(int(cfg.max_open_positions), 0), max(int(broker_cfg.max_open_positions), 0))
    cfg = replace(cfg, max_open_positions=max_positions, require_manual_approval=True)
    risk_account = _risk_account(account, portfolio)
    reserve_floor = risk_account["AccountEquity"] * max(100 - cfg.max_total_exposure_pct, 0) / 100
    existing_queue = load_approval_queue(queue_path)
    active_queue = existing_queue[
        existing_queue["Status"].astype(str).str.upper().isin({"PENDING_APPROVAL", "APPROVED"})
        & (existing_queue["RobotKey"].astype(str).str.strip() != "")
        & (existing_queue["Market"].astype(str).str.upper() == "SET")
    ].copy()
    active_entries = active_queue[
        active_queue["Action"].astype(str).str.upper().isin({"BUY", "ADD"})
    ].copy()
    active_exits = active_queue[
        active_queue["Action"].astype(str).str.upper().isin({"REDUCE", "EXIT"})
    ].copy()
    active_entry_symbols = set(active_entries["Symbol"].astype(str).str.upper())
    active_exit_symbols = set(active_exits["Symbol"].astype(str).str.upper())
    pending_cost = safe_float(
        pd.to_numeric(active_entries.get("EstimatedTotalCost", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    )
    pending_exposure = safe_float(
        pd.to_numeric(active_entries.get("ProposedOrderValue", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    )
    reserved_cash = max(risk_account["AvailableCash"] - pending_cost, 0)
    reserved_exposure = risk_account["TotalExposure"] + pending_exposure
    reserved_positions = risk_account["OpenPositions"] + len(active_entry_symbols)

    proposals: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []

    sort_columns = [column for column in ("PriorityScore", "AIConfidence", "Symbol") if column in source.columns]
    if sort_columns:
        ascending = [False if column != "Symbol" else True for column in sort_columns]
        source = source.sort_values(sort_columns, ascending=ascending, kind="mergesort")

    for _, candidate in source.iterrows():
        row = candidate.to_dict()
        eligible, reason, policy = _entry_gate(row)
        if not eligible:
            audits.append(_audit_row(row, policy=policy, hard_gate=False, exclusion_reason=reason, audit_time=stamp))
            continue

        symbol = safe_upper(row.get("Symbol"))
        if symbol in active_entry_symbols:
            audits.append(
                _audit_row(
                    row,
                    policy=policy,
                    hard_gate=True,
                    exclusion_reason="ACTIVE_ENTRY_PROPOSAL_EXISTS",
                    audit_time=stamp,
                )
            )
            continue
        if _portfolio_context(portfolio, symbol)["has_position"]:
            audits.append(
                _audit_row(
                    row,
                    policy=policy,
                    hard_gate=True,
                    exclusion_reason="ALREADY_OWNED",
                    audit_time=stamp,
                )
            )
            continue
        run_id = safe_text(row.get("ScanRunId"))
        robot_key, proposal_id = proposal_identity(symbol, run_id, "ENTRY")
        sequential_account = {
            "AccountEquity": risk_account["AccountEquity"],
            "AvailableCash": reserved_cash,
            "TotalExposure": reserved_exposure,
            "OpenPositions": reserved_positions,
        }
        proposal = evaluate_risk(
            row,
            portfolio=_portfolio_context(portfolio, symbol),
            account=sequential_account,
            config=cfg,
        )
        proposal.update(
            {
                "ScanRunId": run_id,
                "RobotKey": robot_key,
                "AutomationType": "ENTRY",
                "AutomationReason": "PASSED_ALL_HARD_GATES",
                "ProposalId": proposal_id,
                "PaperOnly": True,
                "RobotVersion": PAPER_TRADING_ROBOT_VERSION,
            }
        )

        risk_reason = safe_text(proposal.get("RejectReason"), "NONE") or "NONE"
        if safe_bool(proposal.get("RiskApproved")):
            total_cost = safe_float(proposal.get("EstimatedTotalCost"))
            proposed_value = safe_float(proposal.get("ProposedOrderValue"))
            cash_after = reserved_cash - total_cost
            exposure_after = reserved_exposure + proposed_value
            exposure_limit = risk_account["AccountEquity"] * cfg.max_total_exposure_pct / 100

            if reserved_positions >= max_positions:
                risk_reason = "MAX_OPEN_POSITIONS"
            elif cash_after < reserve_floor:
                risk_reason = "CASH_RESERVE_LIMIT"
            elif exposure_after > exposure_limit:
                risk_reason = "MAX_TOTAL_EXPOSURE"

            if risk_reason != "NONE":
                proposal["RiskApproved"] = False
                proposal["ProposalStatus"] = "REJECTED"
                proposal["RejectReason"] = risk_reason
            else:
                reserved_cash = cash_after
                reserved_exposure = exposure_after
                reserved_positions += 1

        proposals.append(proposal)
        audits.append(
            _audit_row(
                row,
                policy=policy,
                hard_gate=True,
                exclusion_reason="" if safe_bool(proposal.get("RiskApproved")) else safe_text(proposal.get("RejectReason")),
                audit_time=stamp,
                proposal=proposal,
                automation_reason="PASSED_ALL_HARD_GATES",
            )
        )

    prices = _latest_prices(source)
    position_histories = (
        load_fresh_position_daily_histories(portfolio)
        if daily_histories is None
        else daily_histories
    )
    portfolio, exit_triggers = update_exit_tracking(
        portfolio,
        prices,
        broker_cfg,
        now=now,
        daily_histories=position_histories,
    )
    exit_run_id = scan_run_id or (
        safe_text(source.iloc[0].get("ScanRunId")) if not source.empty else stamp.replace(":", "").replace("-", "")
    )
    for trigger in exit_triggers:
        symbol = safe_upper(trigger.get("Symbol"))
        if symbol in active_exit_symbols:
            exit_row = {
                "Symbol": symbol,
                "Market": "SET",
                "ScanRunId": exit_run_id,
                "AIDecision": "EXIT",
            }
            audits.append(
                _audit_row(
                    exit_row,
                    policy=None,
                    hard_gate=True,
                    exclusion_reason="ACTIVE_EXIT_PROPOSAL_EXISTS",
                    audit_time=stamp,
                    automation_type="EXIT",
                    automation_reason=safe_text(trigger.get("ExitReason")),
                )
            )
            continue
        robot_key, proposal_id = proposal_identity(symbol, exit_run_id, "EXIT")
        exit_row = {
            "Symbol": symbol,
            "Market": "SET",
            "ScanRunId": exit_run_id,
            "AIDecision": "EXIT",
            "Price": safe_float(trigger.get("CurrentPrice")),
            "Stop": safe_float(trigger.get("StopPrice")),
            "Target": safe_float(trigger.get("TargetPrice")),
            "AIBlockers": "BELOW_STOP" if safe_text(trigger.get("ExitReason")) in {"STOP_LOSS", "TRAILING_STOP"} else "",
            "AIReason": exit_reason_label(trigger.get("ExitReason")),
            "AIConfidence": 100,
        }
        proposal = evaluate_risk(
            exit_row,
            portfolio=_portfolio_context(portfolio, symbol),
            account=_risk_account(account, portfolio),
            config=cfg,
        )
        proposal.update(
            {
                "ScanRunId": exit_run_id,
                "RobotKey": robot_key,
                "AutomationType": "EXIT",
                "AutomationReason": safe_text(trigger.get("ExitReason")),
                "AIReason": exit_reason_label(trigger.get("ExitReason")),
                "ProposalId": proposal_id,
                "PaperOnly": True,
                "RobotVersion": PAPER_TRADING_ROBOT_VERSION,
            }
        )
        proposals.append(proposal)
        audits.append(
            _audit_row(
                exit_row,
                policy=None,
                hard_gate=True,
                exclusion_reason="" if safe_bool(proposal.get("RiskApproved")) else safe_text(proposal.get("RejectReason")),
                audit_time=stamp,
                proposal=proposal,
                automation_type="EXIT",
                automation_reason=safe_text(trigger.get("ExitReason")),
            )
        )

    proposal_df = pd.DataFrame(proposals)
    audit_df = pd.DataFrame(audits)
    for column in AUDIT_COLUMNS:
        if column not in audit_df.columns:
            audit_df[column] = pd.Series(dtype="object")
    audit_df = audit_df[AUDIT_COLUMNS]

    if persist:
        atomic_write_csv(proposal_df, proposals_path)
        atomic_write_csv(audit_df, audit_path)
        save_paper_portfolio(portfolio, portfolio_path)
        queue_input = proposal_df[
            proposal_df.get("RiskApproved", pd.Series(dtype=bool)).map(safe_bool)
            & (proposal_df.get("ProposalStatus", pd.Series(dtype=str)).astype(str).str.upper() == "PENDING_APPROVAL")
        ].copy()
        queue, _ = sync_approval_queue(queue_input, queue_path=queue_path, history_path=history_path, now=now)
    else:
        queue_input = proposal_df[
            proposal_df.get("RiskApproved", pd.Series(dtype=bool)).map(safe_bool)
            & (proposal_df.get("ProposalStatus", pd.Series(dtype=str)).astype(str).str.upper() == "PENDING_APPROVAL")
        ].copy()
        queue, _ = sync_approval_queue(queue_input, queue_path=queue_path, history_path=history_path, now=now)

    return PaperRobotResult(proposals=proposal_df, audit=audit_df, queue=queue, portfolio=portfolio)
