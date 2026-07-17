from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
import json

import pandas as pd

from config import rvol_action_for_market, rvol_thresholds_for_market
from fresh_cross_policy import evaluate_fresh_cross_policy
from fresh_cross_candidates import (
    fresh_cross_candidates,
    is_candidate_extended,
)


POLICY_CONFIG_FILE = Path("config") / "candidate_eligibility_config.json"
DEFAULT_POLICY_VERSION = "fresh_ema_cross_0_2_v1"
VALID_MARKETS = {"SET", "USA"}
SKIP_TERMS = {"SKIP", "NO DATA", "NO_DATA", "AVOID"}
RISK_REJECTED_STATUSES = {"REJECTED"}


@dataclass(frozen=True)
class EligibilityConfig:
    policy_version: str = DEFAULT_POLICY_VERSION
    buy_min_priority_score: float = 70.0
    buy_min_rr: float = 1.8
    prepare_min_seed_score: float = 80.0
    prepare_min_priority_score: float = 55.0
    prepare_min_rr: float = 1.5
    watch_min_opportunity_score: float = 45.0
    ai_confidence_warning_threshold: float = 55.0
    extended_is_hard_block: bool = True
    allowed_buy_lifecycle_states: tuple[str, ...] = (
        "SEED",
        "EARLY",
        "BREAKOUT",
        "MOMENTUM",
        "BUY",
    )
    allowed_prepare_lifecycle_states: tuple[str, ...] = (
        "SEED",
        "EARLY",
        "WATCH",
        "ACCUMULATION",
        "BASE",
        "BOTTOMING",
    )


@dataclass(frozen=True)
class EligibilityResult:
    queue_class: str
    eligible_for_buy_queue: bool
    eligible_for_watch_queue: bool
    base_eligible: bool
    blocking_reasons: list[str]
    warning_reasons: list[str]
    passed_gates: list[str]
    policy_version: str
    fresh_cross_eligible: bool
    fresh_cross_age: int | None
    fresh_cross_status: str
    fresh_cross_status_label: str
    fresh_cross_reason: str
    rvol_prepare_threshold: float
    rvol_buy_threshold: float
    rvol_action: str


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
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


def upper_text(value: Any, default: str = "") -> str:
    return safe_text(value, default).upper()


def first_value(row: pd.Series | Mapping[str, Any], *columns: str, default: Any = "") -> Any:
    for column in columns:
        if column in row:
            value = row.get(column)
            text = safe_text(value)
            if text != "":
                return value
    return default


def normalize_sequence(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values]
    return tuple(
        safe_text(value).upper()
        for value in values
        if safe_text(value)
    )


def normalize_config(config: EligibilityConfig | Mapping[str, Any] | None = None) -> EligibilityConfig:
    if isinstance(config, EligibilityConfig):
        return config

    values = asdict(EligibilityConfig())

    if config is None and POLICY_CONFIG_FILE.exists():
        try:
            config = json.loads(POLICY_CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            config = None

    if isinstance(config, Mapping):
        for key in values:
            if key in config:
                values[key] = config[key]

    values["allowed_buy_lifecycle_states"] = normalize_sequence(
        values["allowed_buy_lifecycle_states"]
    )
    values["allowed_prepare_lifecycle_states"] = normalize_sequence(
        values["allowed_prepare_lifecycle_states"]
    )
    return EligibilityConfig(**values)


def list_text(values: list[str]) -> str:
    return " | ".join(values)


def signal_text(row: pd.Series | Mapping[str, Any]) -> str:
    return " ".join(
        upper_text(first_value(row, column))
        for column in [
            "StrategySignal",
            "Signal",
            "StrategySetup",
            "Setup",
            "RecommendedAction",
            "PriorityAction",
        ]
    )


def is_extended(row: pd.Series | Mapping[str, Any]) -> bool:
    return is_candidate_extended(row)


def has_skip_signal(row: pd.Series | Mapping[str, Any]) -> bool:
    lifecycle = upper_text(row.get("LifecycleState"))
    text = signal_text(row)
    return lifecycle == "SKIP" or any(term in text for term in SKIP_TERMS)


def early_stage_exception(row: pd.Series | Mapping[str, Any], config: EligibilityConfig) -> bool:
    seed_score = safe_float(row.get("SeedScore"))
    priority_score = safe_float(row.get("PriorityScore"))
    rr = safe_float(first_value(row, "RiskRewardRatio", "RR", default=0))
    lifecycle = upper_text(row.get("LifecycleState"))
    pattern = upper_text(row.get("PatternName"))
    setup_text = signal_text(row)
    has_early_context = (
        lifecycle in {"SEED", "EARLY", "WATCH", "ACCUMULATION", "BASE", ""}
        or any(term in pattern for term in ["VCP", "BASE", "WYCKOFF", "ACCUMULATION", "BOTTOM"])
        or any(term in setup_text for term in ["SEED", "EARLY", "ACCUMULATION", "BASE", "WATCH"])
    )
    return (
        has_early_context
        and seed_score >= config.prepare_min_seed_score
        and priority_score >= config.prepare_min_priority_score
        and rr >= config.prepare_min_rr
        and not is_extended(row)
    )


def evaluate_candidate_eligibility(
    candidate: pd.Series | Mapping[str, Any],
    config: EligibilityConfig | Mapping[str, Any] | None = None,
) -> EligibilityResult:
    cfg = normalize_config(config)
    row = candidate if isinstance(candidate, Mapping) else candidate.to_dict()
    fresh_cross = evaluate_fresh_cross_policy(row)
    blocking: list[str] = []
    warnings: list[str] = []
    passed: list[str] = []

    symbol = safe_text(row.get("Symbol"))
    market = upper_text(row.get("Market"))
    lifecycle = upper_text(row.get("LifecycleState"))
    priority_score = safe_float(row.get("PriorityScore"))
    opportunity_score = safe_float(first_value(row, "OpportunityScore", "StrategyScore", "Score", default=0))
    seed_score = safe_float(row.get("SeedScore"))
    rr = safe_float(first_value(row, "RiskRewardRatio", "RR", default=0))
    entry = safe_float(first_value(row, "EntryPrice", "Price", "Close", default=0))
    stop = safe_float(first_value(row, "StopPrice", "StopLoss", default=0))
    target = safe_float(first_value(row, "TargetPrice", "Target", default=0))
    ai_confidence = safe_float(row.get("AIConfidence"), default=100)
    rvol = safe_float(row.get("RVOL"))
    rvol_thresholds = rvol_thresholds_for_market(market)
    rvol_action = rvol_action_for_market(market, rvol)
    proposal_status = upper_text(row.get("ProposalStatus"))
    risk_approved = upper_text(row.get("RiskApproved"))

    if not symbol:
        blocking.append("Missing symbol")
    else:
        passed.append("Symbol present")

    if market not in VALID_MARKETS:
        blocking.append("Invalid market")
    else:
        passed.append("Valid market")

    if entry <= 0:
        blocking.append("Missing or invalid entry price")
    else:
        passed.append("Valid entry price")

    if proposal_status in RISK_REJECTED_STATUSES or risk_approved == "FALSE":
        blocking.append("Risk Manager rejected")

    if cfg.extended_is_hard_block and is_extended(row):
        blocking.append("Extended or chasing setup")

    if has_skip_signal(row):
        blocking.append("Scanner/lifecycle SKIP")

    if fresh_cross.eligible:
        passed.append("Fresh EMA9-over-EMA20 cross within 0-2 trading days")
    else:
        blocking.append(
            f"Fresh EMA cross required: {fresh_cross.status_label}"
        )

    if rvol >= rvol_thresholds["BUY"]:
        passed.append(
            f"RVOL meets {market} BUY threshold {rvol_thresholds['BUY']:g}x"
        )
    elif rvol >= rvol_thresholds["PREPARE"]:
        passed.append(
            f"RVOL meets {market} PREPARE threshold {rvol_thresholds['PREPARE']:g}x"
        )
        warnings.append(
            f"RVOL {rvol:.2f}x below {market} BUY threshold {rvol_thresholds['BUY']:g}x"
        )
    else:
        blocking.append(
            f"RVOL {rvol:.2f}x below {market} PREPARE threshold {rvol_thresholds['PREPARE']:g}x"
        )

    buy_lifecycle_ok = (
        lifecycle in cfg.allowed_buy_lifecycle_states
        or any(term in signal_text(row) for term in ["BUY", "EARLY", "BREAKOUT", "MOMENTUM"])
    )
    prepare_lifecycle_ok = (
        lifecycle in cfg.allowed_prepare_lifecycle_states
        or early_stage_exception(row, cfg)
    )

    if buy_lifecycle_ok:
        passed.append("Buy lifecycle eligible")
    if prepare_lifecycle_ok:
        passed.append("Prepare lifecycle eligible")

    if ai_confidence < cfg.ai_confidence_warning_threshold:
        warnings.append(f"AI confidence below {cfg.ai_confidence_warning_threshold:g}")
    else:
        passed.append("AI confidence acceptable")

    if priority_score >= cfg.buy_min_priority_score:
        passed.append("Priority score meets BUY threshold")
    elif priority_score >= cfg.prepare_min_priority_score:
        passed.append("Priority score meets PREPARE threshold")
    else:
        warnings.append("Priority score below PREPARE threshold")

    if rr >= cfg.buy_min_rr:
        passed.append("RR meets BUY threshold")
    elif rr >= cfg.prepare_min_rr:
        passed.append("RR meets PREPARE threshold")
    elif rr > 0:
        blocking.append(f"RR below hard minimum {cfg.prepare_min_rr:g}")
    else:
        warnings.append("RR missing")

    has_valid_order_prices = stop > 0 and target > entry
    if has_valid_order_prices:
        passed.append("Valid stop and target")
    else:
        warnings.append("Stop/target not valid for actionable order")

    hard_blocked = bool(blocking)
    base_eligible = not hard_blocked
    queue_class = "IGNORE"
    eligible_buy = False
    eligible_watch = False

    if not hard_blocked and buy_lifecycle_ok:
        if (
            priority_score >= cfg.buy_min_priority_score
            and rr >= cfg.buy_min_rr
            and has_valid_order_prices
            and rvol_action == "BUY"
        ):
            queue_class = "BUY"
            eligible_buy = True

    if (
        queue_class == "IGNORE"
        and not hard_blocked
        and (prepare_lifecycle_ok or buy_lifecycle_ok)
    ):
        if (
            (
                seed_score >= cfg.prepare_min_seed_score
                or priority_score >= cfg.buy_min_priority_score
            )
            and priority_score >= cfg.prepare_min_priority_score
            and rr >= cfg.prepare_min_rr
            and rvol_action in {"PREPARE", "BUY"}
        ):
            queue_class = "PREPARE"
            eligible_watch = True

    if queue_class == "IGNORE" and not hard_blocked:
        if (
            opportunity_score >= cfg.watch_min_opportunity_score
            or seed_score >= cfg.prepare_min_seed_score * 0.75
            or "WATCH" in signal_text(row)
        ):
            queue_class = "WATCH"
            eligible_watch = True

    if queue_class == "BUY":
        passed.append("Queue class BUY")
    elif queue_class == "PREPARE":
        passed.append("Queue class PREPARE")
    elif queue_class == "WATCH":
        passed.append("Queue class WATCH")

    return EligibilityResult(
        queue_class=queue_class,
        eligible_for_buy_queue=eligible_buy,
        eligible_for_watch_queue=eligible_watch,
        base_eligible=base_eligible,
        blocking_reasons=blocking,
        warning_reasons=warnings,
        passed_gates=passed,
        policy_version=cfg.policy_version,
        fresh_cross_eligible=fresh_cross.eligible,
        fresh_cross_age=fresh_cross.age,
        fresh_cross_status=fresh_cross.status,
        fresh_cross_status_label=fresh_cross.status_label,
        fresh_cross_reason=fresh_cross.reason,
        rvol_prepare_threshold=rvol_thresholds["PREPARE"],
        rvol_buy_threshold=rvol_thresholds["BUY"],
        rvol_action=rvol_action,
    )


def merge_by_symbol_market(base: pd.DataFrame, extra: pd.DataFrame | None, prefix: str) -> pd.DataFrame:
    if extra is None or extra.empty:
        return base
    if "Symbol" not in extra.columns or "Market" not in extra.columns:
        return base

    extra_data = extra.copy()
    extra_data["Symbol"] = extra_data["Symbol"].astype(str).str.upper().str.strip()
    extra_data["Market"] = extra_data["Market"].astype(str).str.upper().str.strip()
    extra_data = extra_data.drop_duplicates(
        subset=["Symbol", "Market"],
        keep="last",
    )
    rename = {
        column: f"{prefix}{column}"
        for column in extra_data.columns
        if column not in {"Symbol", "Market"}
    }
    extra_data = extra_data.rename(columns=rename)
    return base.merge(extra_data, on=["Symbol", "Market"], how="left")


def normalize_candidates(
    ranked: pd.DataFrame | None,
    ai_decisions: pd.DataFrame | None = None,
    risk_proposals: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if ranked is None or ranked.empty:
        return pd.DataFrame()

    data = ranked.copy()
    if "Symbol" not in data.columns:
        data["Symbol"] = ""
    if "Market" not in data.columns:
        data["Market"] = ""
    data["Symbol"] = data["Symbol"].astype(str).str.upper().str.strip()
    data["Market"] = data["Market"].astype(str).str.upper().str.strip()
    data = merge_by_symbol_market(data, ai_decisions, "_AI_")
    data = merge_by_symbol_market(data, risk_proposals, "_Risk_")

    fill_pairs = {
        "AIDecision": "_AI_AIDecision",
        "AIConfidence": "_AI_AIConfidence",
        "ProposalStatus": "_Risk_ProposalStatus",
        "RiskApproved": "_Risk_RiskApproved",
        "RiskRewardRatio": "_Risk_RiskRewardRatio",
        "EntryPrice": "_Risk_EntryPrice",
        "StopPrice": "_Risk_StopPrice",
        "TargetPrice": "_Risk_TargetPrice",
    }
    for column, prefixed in fill_pairs.items():
        if column not in data.columns:
            data[column] = data.get(prefixed, "")
        elif prefixed in data.columns:
            data[column] = data[column].where(
                data[column].notna() & (data[column].astype(str).str.strip() != ""),
                data[prefixed],
            )

    if "RiskRewardRatio" in data.columns and "RR" not in data.columns:
        data["RR"] = data["RiskRewardRatio"]
    if "EntryPrice" not in data.columns:
        data["EntryPrice"] = data.get("Price", 0)

    return apply_eligibility_policy(data)


def apply_eligibility_policy(
    dataframe: pd.DataFrame | None,
    config: EligibilityConfig | Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    if dataframe is None or dataframe.empty:
        return pd.DataFrame() if dataframe is None else dataframe.copy()

    data = dataframe.copy()
    results = [
        evaluate_candidate_eligibility(row, config)
        for _, row in data.iterrows()
    ]

    data["QueueClass"] = [result.queue_class for result in results]
    data["EligibleForBuyQueue"] = [result.eligible_for_buy_queue for result in results]
    data["EligibleForWatchQueue"] = [result.eligible_for_watch_queue for result in results]
    data["BaseEligible"] = [result.base_eligible for result in results]
    data["BlockingReasons"] = [list_text(result.blocking_reasons) for result in results]
    data["WarningReasons"] = [list_text(result.warning_reasons) for result in results]
    data["PassedGates"] = [list_text(result.passed_gates) for result in results]
    data["EligibilityPolicyVersion"] = [result.policy_version for result in results]
    data["FreshCrossEligible"] = [
        result.fresh_cross_eligible
        for result in results
    ]
    data["IsFreshEMA9Cross"] = data["FreshCrossEligible"]
    data["FreshCrossAge"] = [result.fresh_cross_age for result in results]
    data["CrossAgeLabel"] = [
        "Today"
        if result.fresh_cross_age == 0
        else (
            f"{result.fresh_cross_age}D"
            if result.fresh_cross_age is not None
            else "-"
        )
        for result in results
    ]
    data["FreshCrossStatus"] = [
        result.fresh_cross_status
        for result in results
    ]
    data["FreshCrossStatusLabel"] = [
        result.fresh_cross_status_label
        for result in results
    ]
    data["FreshCrossReason"] = [
        result.fresh_cross_reason
        for result in results
    ]
    data["RVOLPrepareThreshold"] = [
        result.rvol_prepare_threshold
        for result in results
    ]
    data["RVOLBuyThreshold"] = [
        result.rvol_buy_threshold
        for result in results
    ]
    data["RVOLAction"] = [result.rvol_action for result in results]
    if "CrossAgeSource" not in data.columns:
        data["CrossAgeSource"] = ""
    else:
        data["CrossAgeSource"] = data["CrossAgeSource"].fillna("")
    data["EligibilityReasons"] = data["BlockingReasons"]
    data["BuyQueueEligible"] = data["EligibleForBuyQueue"]
    data["WatchQueueEligible"] = data["EligibleForWatchQueue"]
    return data


def candidate_rejection_reasons(row: pd.Series, config: EligibilityConfig | None = None) -> list[str]:
    return evaluate_candidate_eligibility(row, config).blocking_reasons


def is_buy_queue_candidate(row: pd.Series, config: EligibilityConfig | None = None) -> bool:
    return evaluate_candidate_eligibility(row, config).eligible_for_buy_queue


def is_watch_queue_candidate(row: pd.Series, config: EligibilityConfig | None = None) -> bool:
    return evaluate_candidate_eligibility(row, config).eligible_for_watch_queue


def split_candidate_queues(
    ranked: pd.DataFrame | None,
    ai_decisions: pd.DataFrame | None = None,
    risk_proposals: pd.DataFrame | None = None,
    config: EligibilityConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = normalize_candidates(ranked, ai_decisions, risk_proposals)
    if data.empty:
        return data, data, data

    rank_column = "PriorityRank" if "PriorityRank" in data.columns else "OpportunityRank"
    score_column = "PriorityScore" if "PriorityScore" in data.columns else "OpportunityScore"
    if rank_column not in data.columns:
        data[rank_column] = range(1, len(data) + 1)
    if score_column not in data.columns:
        data[score_column] = 0

    data[rank_column] = pd.to_numeric(data[rank_column], errors="coerce").fillna(999999)
    data[score_column] = pd.to_numeric(data[score_column], errors="coerce").fillna(0)
    data = data.sort_values([rank_column, score_column], ascending=[True, False]).reset_index(drop=True)

    canonical = fresh_cross_candidates(data)
    canonical_keys = set(zip(canonical["Symbol"], canonical["Market"]))
    data["CanonicalFreshCrossEligible"] = pd.Series(
        list(zip(data["Symbol"], data["Market"])),
        index=data.index,
    ).isin(canonical_keys)
    data["EligibleForBuyQueue"] = (
        data["EligibleForBuyQueue"]
        & data["CanonicalFreshCrossEligible"]
    )
    data["EligibleForWatchQueue"] = (
        data["EligibleForWatchQueue"]
        & data["CanonicalFreshCrossEligible"]
    )

    buy_queue = data[data["EligibleForBuyQueue"]].copy()
    watch_queue = data[data["EligibleForWatchQueue"]].copy()
    return data, buy_queue, watch_queue
