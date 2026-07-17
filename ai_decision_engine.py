from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from config import rvol_action_for_market, rvol_thresholds_for_market
from runtime_io import atomic_write_csv


AI_DECISIONS_FILE = Path("output") / "ai_decisions.csv"
AIDECISION_VERSION = "1.0"

AI_COLUMNS = [
    "AIDecision",
    "AIAction",
    "AIConfidence",
    "AIConviction",
    "AIPositionIntent",
    "AIEntryReadiness",
    "AIRiskLevel",
    "AIReason",
    "AIPositiveFactors",
    "AINegativeFactors",
    "AIBlockers",
    "AISuggestedAction",
    "AIReviewPriority",
    "AIRequiresApproval",
    "AIDecisionVersion",
    "AIDecisionTime",
]

DECISION_ACTIONS = {
    "BUY": "Enter New Position",
    "PREPARE": "Prepare Entry",
    "WATCH": "Watch Closely",
    "HOLD": "Hold Position",
    "ADD": "Add to Position",
    "REDUCE": "Reduce Position",
    "EXIT": "Exit Position",
    "AVOID": "Avoid Entry",
    "NO_ACTION": "No Action",
}

POSITION_INTENTS = {
    "BUY": "OPEN",
    "PREPARE": "OPEN",
    "WATCH": "NONE",
    "HOLD": "HOLD",
    "ADD": "ADD",
    "REDUCE": "REDUCE",
    "EXIT": "CLOSE",
    "AVOID": "NONE",
    "NO_ACTION": "NONE",
}

ENTRY_READINESS = {
    "BUY": "READY",
    "PREPARE": "NEAR_READY",
    "WATCH": "NOT_READY",
    "HOLD": "NOT_APPLICABLE",
    "ADD": "READY",
    "REDUCE": "NOT_APPLICABLE",
    "EXIT": "NOT_APPLICABLE",
    "AVOID": "BLOCKED",
    "NO_ACTION": "NOT_APPLICABLE",
}

APPROVAL_DECISIONS = {
    "BUY",
    "ADD",
    "REDUCE",
    "EXIT",
}

SUGGESTED_ACTIONS = {
    "BUY": "BUY_SUPPORT",
    "PREPARE": "PREPARE",
    "WATCH": "WATCH",
    "AVOID": "AVOID",
    "NO_ACTION": "NO_ACTION",
    "HOLD": "NO_ACTION",
    "ADD": "BUY_SUPPORT",
    "REDUCE": "NO_ACTION",
    "EXIT": "AVOID",
}

SEVERE_BLOCKERS = {
    "EXTENDED",
    "LOW_RR",
    "HIGH_RISK",
    "INVALID_STOP",
    "MISSING_PRICE",
    "CONFLICTING_SIGNAL",
    "SETUP_INVALIDATED",
    "BELOW_STOP",
    "INSUFFICIENT_DATA",
}


@dataclass(frozen=True)
class AIDecisionConfig:
    """Tunable thresholds for the deterministic AI decision layer."""

    buy_priority_score: float = 80
    buy_opportunity_score: float = 70
    prepare_priority_score: float = 65
    prepare_opportunity_score: float = 55
    watch_priority_score: float = 45
    watch_opportunity_score: float = 40
    max_buy_risk_pct: float = 8
    min_buy_rr: float = 2
    min_rr: float = 1.5
    market_avoid_score: float = 20
    high_distance_ema20_pct: float = 10
    hot_rsi: float = 75


def safe_float(value: Any, default: float = 0.0) -> float:
    """Return a float without raising for missing or malformed values."""

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_text(value: Any, default: str = "") -> str:
    """Return a stripped string without raising for missing values."""

    if pd.isna(value):
        return default

    return str(value).strip()


def safe_bool(value: Any) -> bool:
    """Parse booleans from bools, numbers, and common string values."""

    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    text = safe_text(value).upper()

    return text in {
        "TRUE",
        "YES",
        "Y",
        "1",
    }


def clamp(value: Any, low: float = 0, high: float = 100) -> float:
    """Clamp a numeric value into a fixed range."""

    return max(
        low,
        min(
            high,
            safe_float(value),
        ),
    )


def row_to_dict(row: Any) -> dict[str, Any]:
    """Normalize a dict-like row or pandas Series into a plain dict."""

    if isinstance(row, pd.Series):
        return row.to_dict()

    if isinstance(row, Mapping):
        return dict(row)

    return {}


def get_value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    """Fetch the first available value from a row using multiple names."""

    for name in names:
        if name in row and not pd.isna(row[name]):
            return row[name]

    return default


def has_numeric(row: Mapping[str, Any], *names: str) -> bool:
    """Check whether any named field is present and numeric."""

    for name in names:
        if name not in row:
            continue

        value = row[name]

        try:
            if not pd.isna(value):
                float(value)
                return True
        except (TypeError, ValueError):
            continue

    return False


def contains_any(text: Any, values: set[str]) -> bool:
    """Case-insensitive containment test for decision keywords."""

    data = safe_text(text).upper()

    return any(value in data for value in values)


def normalize_symbol(symbol: Any, market: Any = "") -> str:
    """Normalize symbols for matching scanner rows with portfolio rows."""

    value = safe_text(symbol).upper()
    market_value = safe_text(market).upper()

    if market_value == "SET" and value and not value.endswith(".BK"):
        return f"{value}.BK"

    return value


def normalize_config(config: AIDecisionConfig | Mapping[str, Any] | None) -> AIDecisionConfig:
    """Return a config dataclass from None, a dataclass, or a mapping."""

    if isinstance(config, AIDecisionConfig):
        return config

    if isinstance(config, Mapping):
        values = {
            field: config.get(field)
            for field in AIDecisionConfig.__dataclass_fields__
            if field in config
        }
        return AIDecisionConfig(**values)

    return AIDecisionConfig()


def normalize_portfolio_context(
    row: Mapping[str, Any],
    portfolio: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge row-level and optional portfolio context into one structure."""

    portfolio = dict(portfolio or {})
    position_qty = safe_float(
        get_value(
            portfolio,
            "qty",
            "PositionQty",
            "Shares",
            default=get_value(row, "PositionQty", "Shares", default=0),
        )
    )
    portfolio_status = safe_text(
        get_value(
            portfolio,
            "PortfolioStatus",
            "Status",
            default=get_value(row, "PortfolioStatus", "Status", default=""),
        )
    ).upper()
    has_position = bool(
        portfolio.get(
            "has_position",
            portfolio_status == "OPEN" or position_qty > 0,
        )
    )

    return {
        "has_position": has_position,
        "qty": position_qty,
        "average_cost": safe_float(
            get_value(
                portfolio,
                "average_cost",
                "AverageCost",
                "EntryPrice",
                default=get_value(row, "AverageCost", "EntryPrice", default=0),
            )
        ),
        "unrealized_return_pct": safe_float(
            get_value(
                portfolio,
                "unrealized_return_pct",
                "UnrealizedReturnPct",
                default=get_value(row, "UnrealizedReturnPct", default=0),
            )
        ),
        "stop_price": safe_float(
            get_value(
                portfolio,
                "stop_price",
                "Stop",
                "StopLoss",
                default=get_value(row, "Stop", "StopLoss", default=0),
            )
        ),
        "current_price": safe_float(
            get_value(
                portfolio,
                "current_price",
                "CurrentPrice",
                "Price",
                "Close",
                default=get_value(row, "CurrentPrice", "Price", "Close", default=0),
            )
        ),
    }


def collect_inputs(row: Mapping[str, Any]) -> dict[str, Any]:
    """Extract normalized fields used by the AI decision layer."""

    price = safe_float(
        get_value(row, "Price", "Close", "CurrentPrice", default=0)
    )
    strategy_score = safe_float(
        get_value(row, "StrategyScore", "Score", default=0)
    )

    return {
        "symbol": safe_text(get_value(row, "Symbol", default="")).upper(),
        "market": safe_text(get_value(row, "Market", default="")).upper(),
        "strategy_signal": safe_text(get_value(row, "StrategySignal", "Signal", default="")).upper(),
        "signal": safe_text(get_value(row, "Signal", "StrategySignal", default="")).upper(),
        "setup": safe_text(get_value(row, "Setup", "StrategySetup", default="")),
        "strategy_score": strategy_score,
        "lifecycle": safe_text(get_value(row, "LifecycleState", default="")).upper(),
        "days_in_state": safe_float(get_value(row, "DaysInState", default=0)),
        "state_changed": safe_bool(get_value(row, "StateChanged", default=False)),
        "state_changed_recently": safe_bool(
            get_value(row, "StateChangedRecently", "StateChanged", default=False)
        ),
        "opportunity_score": safe_float(get_value(row, "OpportunityScore", default=0)),
        "recommended_action": safe_text(get_value(row, "RecommendedAction", default="")).upper(),
        "opportunity_grade": safe_text(get_value(row, "OpportunityGrade", default="")),
        "priority_score": safe_float(get_value(row, "PriorityScore", default=0)),
        "priority_rank": safe_float(get_value(row, "PriorityRank", default=999999)),
        "priority_action": safe_text(get_value(row, "PriorityAction", default="")).upper(),
        "priority_mode": safe_text(get_value(row, "PriorityMode", default="")),
        "priority_reasons": safe_text(get_value(row, "PriorityReasons", default="")),
        "market_quality_score": safe_float(get_value(row, "MarketQualityScore", default=0)),
        "market_quality_label": safe_text(get_value(row, "MarketQualityLabel", default="")).upper(),
        "price": price,
        "entry": safe_float(get_value(row, "Entry", "EntryPrice", default=0)),
        "stop": safe_float(get_value(row, "Stop", "StopLoss", default=0)),
        "target": safe_float(get_value(row, "Target", default=0)),
        "risk_pct": safe_float(get_value(row, "RiskPct", default=0)),
        "reward_pct": safe_float(get_value(row, "RewardPct", default=0)),
        "rr": safe_float(get_value(row, "RR", default=0)),
        "rsi": safe_float(get_value(row, "RSI", default=0)),
        "rvol": safe_float(get_value(row, "RVOL", default=0)),
        "distance_ema20": safe_float(get_value(row, "DistanceEMA20", "DistanceEMA20Pct", default=0)),
        "pattern_name": safe_text(get_value(row, "PatternName", default="")),
        "pattern_score": safe_float(get_value(row, "PatternScore", default=0)),
        "freshness_score": safe_float(get_value(row, "FreshnessScore", default=0)),
        "seed_score": safe_float(get_value(row, "SeedScore", default=0)),
        "confidence": safe_float(get_value(row, "Confidence", default=0)),
        "has_rr": has_numeric(row, "RR"),
        "has_risk_pct": has_numeric(row, "RiskPct"),
        "has_price": price > 0,
    }


def is_market_avoid(inputs: Mapping[str, Any], config: AIDecisionConfig) -> bool:
    """Detect weak market context without changing market quality scoring."""

    label = safe_text(inputs["market_quality_label"]).upper()

    return "AVOID" in label or safe_float(inputs["market_quality_score"]) <= config.market_avoid_score


def classify_risk(
    inputs: Mapping[str, Any],
    blockers: list[str],
    config: AIDecisionConfig,
) -> str:
    """Classify AI risk from existing scanner risk fields."""

    if "MISSING_PRICE" in blockers:
        return "UNKNOWN"

    if (
        "HIGH_RISK" in blockers
        or "EXTENDED" in blockers
        or "LOW_RR" in blockers
    ):
        return "HIGH"

    risk_pct = safe_float(inputs["risk_pct"])
    rr = safe_float(inputs["rr"])

    if inputs["has_risk_pct"] and risk_pct <= 3.5 and (not inputs["has_rr"] or rr >= 2):
        return "LOW"

    if inputs["has_risk_pct"] and risk_pct <= config.max_buy_risk_pct:
        return "MEDIUM"

    return "UNKNOWN"


def detect_blockers(
    inputs: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    config: AIDecisionConfig,
) -> list[str]:
    """Detect deterministic blockers from existing scanner and portfolio fields."""

    blockers: list[str] = []
    signal_text = " ".join(
        [
            safe_text(inputs["signal"]),
            safe_text(inputs["strategy_signal"]),
            safe_text(inputs["recommended_action"]),
            safe_text(inputs["setup"]),
        ]
    ).upper()

    if not inputs["symbol"]:
        blockers.append("INSUFFICIENT_DATA")

    if not inputs["has_price"]:
        blockers.append("MISSING_PRICE")

    if contains_any(signal_text, {"EXTENDED"}) or inputs["lifecycle"] == "EXTENDED":
        blockers.append("EXTENDED")

    if inputs["has_rr"] and safe_float(inputs["rr"]) < config.min_rr:
        blockers.append("LOW_RR")

    if (
        (inputs["has_risk_pct"] and safe_float(inputs["risk_pct"]) > config.max_buy_risk_pct)
        or abs(safe_float(inputs["distance_ema20"])) > config.high_distance_ema20_pct
        or (safe_float(inputs["rsi"]) >= config.hot_rsi and "EXTENDED" in blockers)
    ):
        blockers.append("HIGH_RISK")

    if inputs["has_price"] and safe_float(inputs["stop"]) > 0 and safe_float(inputs["stop"]) >= safe_float(inputs["price"]):
        blockers.append("INVALID_STOP")

    if is_market_avoid(inputs, config):
        blockers.append("MARKET_AVOID")

    if contains_any(signal_text, {"SKIP"}) and (
        safe_float(inputs["priority_score"]) >= config.buy_priority_score
        or safe_float(inputs["opportunity_score"]) >= config.buy_opportunity_score
        or contains_any(signal_text, {"BUY"})
    ):
        blockers.append("CONFLICTING_SIGNAL")

    if portfolio["has_position"]:
        if safe_float(portfolio["stop_price"]) > 0 and safe_float(portfolio["current_price"]) <= safe_float(portfolio["stop_price"]):
            blockers.append("BELOW_STOP")

        if contains_any(signal_text, {"SKIP", "FAILED", "INVALIDATED"}):
            blockers.append("SETUP_INVALIDATED")
    else:
        if contains_any(signal_text, {"EXIT", "REDUCE"}):
            blockers.append("NO_POSITION")

    return list(dict.fromkeys(blockers))


def positive_factors(inputs: Mapping[str, Any], portfolio: Mapping[str, Any]) -> list[str]:
    """Build readable positive factors from existing fields."""

    factors: list[str] = []

    if safe_float(inputs["priority_score"]) >= 80:
        factors.append("High PriorityScore")
    elif safe_float(inputs["priority_score"]) >= 65:
        factors.append("Constructive PriorityScore")

    if safe_float(inputs["opportunity_score"]) >= 70:
        factors.append("High OpportunityScore")
    elif safe_float(inputs["opportunity_score"]) >= 55:
        factors.append("Opportunity is developing")

    if inputs["lifecycle"] in {"SEED", "EARLY"}:
        factors.append(f"{inputs['lifecycle']} lifecycle")

    if safe_float(inputs["freshness_score"]) >= 70:
        factors.append("Fresh setup")

    if safe_float(inputs["pattern_score"]) >= 70:
        pattern = safe_text(inputs["pattern_name"], "pattern")
        factors.append(f"Strong {pattern} pattern")

    if inputs["has_rr"] and safe_float(inputs["rr"]) >= 2:
        factors.append("Risk/reward is acceptable")

    if portfolio["has_position"] and safe_float(portfolio["unrealized_return_pct"]) >= 0:
        factors.append("Position is not losing")

    return factors


def negative_factors(inputs: Mapping[str, Any], blockers: list[str]) -> list[str]:
    """Build readable negative factors from blockers and weak fields."""

    factors: list[str] = []

    if "MARKET_AVOID" in blockers:
        factors.append("Market quality is weak")

    if "LOW_RR" in blockers:
        factors.append("Risk/reward is below threshold")

    if "HIGH_RISK" in blockers:
        factors.append("Risk is elevated")

    if "EXTENDED" in blockers:
        factors.append("Move is extended")

    rvol = safe_float(inputs["rvol"])
    thresholds = rvol_thresholds_for_market(inputs["market"])
    if rvol < thresholds["PREPARE"]:
        factors.append(
            f"RVOL {rvol:.2f}x is below {inputs['market']} PREPARE threshold "
            f"{thresholds['PREPARE']:g}x"
        )
    elif rvol < thresholds["BUY"]:
        factors.append(
            f"RVOL {rvol:.2f}x is below {inputs['market']} BUY threshold "
            f"{thresholds['BUY']:g}x"
        )

    if safe_float(inputs["rsi"]) >= 70:
        factors.append("RSI is hot")

    if safe_float(inputs["priority_score"]) < 45 and safe_float(inputs["opportunity_score"]) < 40:
        factors.append("Scores are not yet strong")

    return list(dict.fromkeys(factors))


def calculate_confidence(
    inputs: Mapping[str, Any],
    risk_level: str,
    blockers: list[str],
) -> float:
    """Calculate AI confidence from existing scores without copying any one score."""

    confidence = (
        safe_float(inputs["priority_score"]) * 0.30
        + safe_float(inputs["opportunity_score"]) * 0.25
        + safe_float(inputs["strategy_score"]) * 0.15
        + safe_float(inputs["pattern_score"]) * 0.10
        + safe_float(inputs["freshness_score"]) * 0.10
        + safe_float(inputs["market_quality_score"]) * 0.10
    )

    rr = safe_float(inputs["rr"])

    if inputs["has_rr"] and rr >= 3:
        confidence += 5
    elif inputs["has_rr"] and rr >= 2:
        confidence += 3

    if inputs["lifecycle"] in {"SEED", "EARLY"}:
        confidence += 4

    if inputs["state_changed_recently"]:
        confidence += 3

    if risk_level == "LOW":
        confidence += 3

    if "EXTENDED" in blockers:
        confidence -= 25

    if "MARKET_AVOID" in blockers:
        confidence -= 15

    if "LOW_RR" in blockers:
        confidence -= 15

    if "HIGH_RISK" in blockers:
        confidence -= 15

    if "CONFLICTING_SIGNAL" in blockers:
        confidence -= 10

    if "INSUFFICIENT_DATA" in blockers or "MISSING_PRICE" in blockers:
        confidence -= 10

    return round(
        clamp(confidence),
        2,
    )


def classify_conviction(confidence: float, blockers: list[str], decision: str) -> str:
    """Classify decision conviction from confidence and blockers."""

    severe = any(blocker in SEVERE_BLOCKERS for blocker in blockers)

    if confidence >= 80 and not blockers:
        return "HIGH"

    if decision in {"EXIT", "REDUCE"} and confidence >= 60:
        return "MEDIUM"

    if severe and decision in {"AVOID", "NO_ACTION"}:
        return "NONE"

    if confidence >= 60:
        return "MEDIUM"

    if confidence >= 35:
        return "LOW"

    return "NONE"


def priority_action_is_buyable(priority_action: str) -> bool:
    """Treat review-first style priority actions as equivalent buy review flags."""

    text = safe_text(priority_action).upper()

    return contains_any(
        text,
        {
            "REVIEW FIRST",
            "HIGH PRIORITY",
            "TOP PICK",
            "BUY",
        },
    )


def recommended_action_is_buyable(recommended_action: str, strategy_signal: str) -> bool:
    """Detect buy-like recommended actions without changing original values."""

    text = f"{recommended_action} {strategy_signal}".upper()

    return contains_any(
        text,
        {
            "STRONG BUY",
            "BUY",
            "SEED BUY",
        },
    )


def has_severe_entry_blocker(blockers: list[str]) -> bool:
    """Return True when new entries should be blocked."""

    return any(
        blocker in blockers
        for blocker in {
            "EXTENDED",
            "LOW_RR",
            "HIGH_RISK",
            "INVALID_STOP",
            "MISSING_PRICE",
            "CONFLICTING_SIGNAL",
            "INSUFFICIENT_DATA",
        }
    )


def choose_new_position_decision(
    inputs: Mapping[str, Any],
    blockers: list[str],
    config: AIDecisionConfig,
) -> str:
    """Choose a decision for symbols not currently held."""

    priority_score = safe_float(inputs["priority_score"])
    opportunity_score = safe_float(inputs["opportunity_score"])
    lifecycle = safe_text(inputs["lifecycle"]).upper()
    volume_action = rvol_action_for_market(inputs["market"], inputs["rvol"])
    signal_text = " ".join(
        [
            safe_text(inputs["signal"]),
            safe_text(inputs["strategy_signal"]),
            safe_text(inputs["recommended_action"]),
        ]
    ).upper()

    market_avoid = "MARKET_AVOID" in blockers
    severe_entry_blocker = has_severe_entry_blocker(blockers)

    if severe_entry_blocker:
        if priority_score >= config.prepare_priority_score and opportunity_score >= config.prepare_opportunity_score and lifecycle in {"SEED", "EARLY"} and blockers == ["MARKET_AVOID"]:
            return "PREPARE"
        return "AVOID"

    if (
        priority_score >= config.buy_priority_score
        and opportunity_score >= config.buy_opportunity_score
        and priority_action_is_buyable(inputs["priority_action"])
        and recommended_action_is_buyable(inputs["recommended_action"], inputs["strategy_signal"])
        and lifecycle in {"SEED", "EARLY", "BREAKOUT"}
        and not market_avoid
        and (not inputs["has_risk_pct"] or safe_float(inputs["risk_pct"]) <= config.max_buy_risk_pct)
        and (not inputs["has_rr"] or safe_float(inputs["rr"]) >= config.min_buy_rr)
        and volume_action == "BUY"
    ):
        return "BUY"

    if (
        lifecycle in {"SEED", "EARLY"}
        and priority_score >= config.prepare_priority_score
        and opportunity_score >= config.prepare_opportunity_score
        and volume_action in {"PREPARE", "BUY"}
    ):
        return "PREPARE"

    if contains_any(signal_text, {"SKIP"}):
        has_special_watch_reason = (
            lifecycle in {"SEED", "EARLY"}
            or opportunity_score >= config.watch_opportunity_score
            or priority_score >= config.prepare_priority_score
            or contains_any(signal_text, {"WATCH", "SEED WATCH", "EARLY WATCH"})
        )

        if not has_special_watch_reason:
            return "AVOID"

    if (
        priority_score >= config.watch_priority_score
        or opportunity_score >= config.watch_opportunity_score
        or contains_any(signal_text, {"WATCH", "SEED WATCH", "EARLY WATCH"})
    ):
        return "WATCH"

    if contains_any(signal_text, {"SKIP", "EXTENDED"}) or lifecycle == "EXTENDED":
        return "AVOID"

    if "NO_POSITION" in blockers:
        return "NO_ACTION"

    return "NO_ACTION"


def choose_portfolio_decision(
    inputs: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    blockers: list[str],
    config: AIDecisionConfig,
) -> str:
    """Choose a decision for symbols already in the portfolio."""

    priority_score = safe_float(inputs["priority_score"])
    opportunity_score = safe_float(inputs["opportunity_score"])
    unrealized_return = safe_float(portfolio["unrealized_return_pct"])
    lifecycle = safe_text(inputs["lifecycle"]).upper()

    if "BELOW_STOP" in blockers or "SETUP_INVALIDATED" in blockers:
        return "EXIT"

    if "EXTENDED" in blockers or lifecycle in {"MOMENTUM", "EXTENDED"}:
        if unrealized_return >= 5 or "HIGH_RISK" in blockers:
            return "REDUCE"

    if (
        priority_score >= 85
        and opportunity_score >= 75
        and lifecycle in {"SEED", "EARLY", "BREAKOUT"}
        and unrealized_return >= -3
        and not has_severe_entry_blocker(blockers)
    ):
        return "ADD"

    if "HIGH_RISK" in blockers and unrealized_return < -5:
        return "EXIT"

    if priority_score >= 35 or opportunity_score >= 35 or not has_severe_entry_blocker(blockers):
        return "HOLD"

    return "REDUCE"


def review_priority(decision: str, confidence: float) -> int:
    """Return review priority where 1 is the most urgent."""

    if decision in {"BUY", "EXIT"}:
        return 1

    if decision in {"PREPARE", "ADD", "REDUCE"}:
        return 2

    if decision in {"WATCH", "HOLD"}:
        return 3 if confidence >= 35 else 4

    if decision == "AVOID":
        return 4

    return 5


def build_reason(
    decision: str,
    inputs: Mapping[str, Any],
    positives: list[str],
    negatives: list[str],
    blockers: list[str],
) -> str:
    """Build a compact, readable reason without promising returns."""

    lifecycle = safe_text(inputs["lifecycle"], "UNKNOWN") or "UNKNOWN"
    priority_score = safe_float(inputs["priority_score"])
    opportunity_score = safe_float(inputs["opportunity_score"])

    if decision == "BUY":
        prefix = "Entry candidate"
    elif decision == "PREPARE":
        prefix = "Prepare entry"
    elif decision == "WATCH":
        prefix = "Watch setup"
    elif decision == "HOLD":
        prefix = "Hold position"
    elif decision == "ADD":
        prefix = "Add candidate"
    elif decision == "REDUCE":
        prefix = "Reduce exposure"
    elif decision == "EXIT":
        prefix = "Exit candidate"
    elif decision == "AVOID":
        prefix = "Avoid entry"
    else:
        prefix = "No action"

    reason_parts = [
        f"{prefix}: {lifecycle} context with Priority {priority_score:.0f} and Opportunity {opportunity_score:.0f}."
    ]

    if positives:
        reason_parts.append(f"Supports: {positives[0]}.")

    if negatives:
        reason_parts.append(f"Watch: {negatives[0]}.")

    if blockers:
        reason_parts.append(f"Blockers: {', '.join(blockers[:3])}.")

    return " ".join(reason_parts)


def make_ai_decision(
    row: Any,
    portfolio: Mapping[str, Any] | None = None,
    config: AIDecisionConfig | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one deterministic AI decision from one scanner row.

    This function is a support layer only. It never mutates scanner scores,
    sends orders, or calls an external AI/API service.
    """

    cfg = normalize_config(config)
    row_data = row_to_dict(row)
    inputs = collect_inputs(row_data)
    portfolio_context = normalize_portfolio_context(
        row_data,
        portfolio,
    )
    blockers = detect_blockers(
        inputs,
        portfolio_context,
        cfg,
    )
    risk_level = classify_risk(
        inputs,
        blockers,
        cfg,
    )
    confidence = calculate_confidence(
        inputs,
        risk_level,
        blockers,
    )
    positives = positive_factors(
        inputs,
        portfolio_context,
    )
    negatives = negative_factors(
        inputs,
        blockers,
    )

    if portfolio_context["has_position"]:
        decision = choose_portfolio_decision(
            inputs,
            portfolio_context,
            blockers,
            cfg,
        )
    else:
        decision = choose_new_position_decision(
            inputs,
            blockers,
            cfg,
        )

    volume_action = rvol_action_for_market(inputs["market"], inputs["rvol"])
    if not portfolio_context["has_position"]:
        if decision == "BUY" and volume_action != "BUY":
            decision = "PREPARE" if volume_action == "PREPARE" else "WATCH"
        elif decision == "PREPARE" and volume_action == "WATCH":
            decision = "WATCH"

    queue_class = safe_text(row_data.get("QueueClass")).upper()
    if not portfolio_context["has_position"] and queue_class:
        if queue_class == "BUY":
            decision = (
                "BUY"
                if volume_action == "BUY"
                else "PREPARE"
                if volume_action == "PREPARE"
                else "WATCH"
            )
        elif queue_class == "PREPARE":
            decision = "PREPARE" if volume_action != "WATCH" else "WATCH"
        elif queue_class == "WATCH":
            decision = "WATCH"
        elif queue_class == "IGNORE" and decision in {"BUY", "PREPARE"}:
            decision = "AVOID"

    conviction = classify_conviction(
        confidence,
        blockers,
        decision,
    )

    return {
        "Symbol": inputs["symbol"],
        "Market": inputs["market"],
        "AIDecision": decision,
        "AIAction": DECISION_ACTIONS[decision],
        "AIConfidence": confidence,
        "AIConviction": conviction,
        "AIPositionIntent": POSITION_INTENTS[decision],
        "AIEntryReadiness": ENTRY_READINESS[decision],
        "AIRiskLevel": risk_level,
        "AIReason": build_reason(
            decision,
            inputs,
            positives,
            negatives,
            blockers,
        ),
        "AIPositiveFactors": "; ".join(positives),
        "AINegativeFactors": "; ".join(negatives),
        "AIBlockers": "; ".join(blockers),
        "AISuggestedAction": SUGGESTED_ACTIONS.get(
            decision,
            "NO_ACTION",
        ),
        "AIReviewPriority": review_priority(
            decision,
            confidence,
        ),
        "AIRequiresApproval": decision in APPROVAL_DECISIONS,
        "AIDecisionVersion": AIDECISION_VERSION,
        "AIDecisionTime": datetime.now().isoformat(timespec="seconds"),
    }


def build_portfolio_lookup(portfolio_dataframe: pd.DataFrame | None) -> dict[tuple[str, str], dict[str, Any]]:
    """Build a symbol/market lookup from an optional portfolio DataFrame."""

    if portfolio_dataframe is None or portfolio_dataframe.empty:
        return {}

    data = portfolio_dataframe.copy()

    for column in [
        "Symbol",
        "Market",
        "Status",
        "Shares",
        "AverageCost",
        "EntryPrice",
        "NetCost",
        "UnrealizedReturnPct",
        "Stop",
        "StopLoss",
        "CurrentPrice",
        "Price",
    ]:
        if column not in data.columns:
            data[column] = 0 if column not in {"Symbol", "Market", "Status"} else ""

    lookup: dict[tuple[str, str], dict[str, Any]] = {}

    for _, row in data.iterrows():
        market = safe_text(row.get("Market")).upper()
        symbol = normalize_symbol(
            row.get("Symbol"),
            market,
        )
        status = safe_text(row.get("Status"), "OPEN").upper()
        shares = safe_float(row.get("Shares"))
        average_cost = safe_float(row.get("AverageCost"))
        entry_price = safe_float(row.get("EntryPrice"))
        net_cost = safe_float(row.get("NetCost"))

        if average_cost <= 0 and shares > 0 and net_cost > 0:
            average_cost = net_cost / shares

        if average_cost <= 0:
            average_cost = entry_price

        lookup[(symbol, market)] = {
            "has_position": status == "OPEN" and shares > 0,
            "qty": shares,
            "average_cost": average_cost,
            "unrealized_return_pct": safe_float(row.get("UnrealizedReturnPct")),
            "stop_price": safe_float(get_value(row, "Stop", "StopLoss", default=0)),
            "current_price": safe_float(get_value(row, "CurrentPrice", "Price", default=0)),
            "PortfolioStatus": status,
        }

    return lookup


def portfolio_for_row(
    row: Mapping[str, Any],
    lookup: Mapping[tuple[str, str], Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Find portfolio context for a scanner row if one exists."""

    market = safe_text(row.get("Market")).upper()
    symbol = normalize_symbol(
        row.get("Symbol"),
        market,
    )

    return lookup.get((symbol, market)) or lookup.get((safe_text(row.get("Symbol")).upper(), market))


def build_ai_decisions(
    dataframe: pd.DataFrame,
    portfolio_dataframe: pd.DataFrame | None = None,
    config: AIDecisionConfig | Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Build AI decisions for a DataFrame without mutating the input."""

    if dataframe is None:
        base = pd.DataFrame()
    else:
        base = dataframe.copy(deep=True)

    for column in AI_COLUMNS:
        if column not in base.columns:
            base[column] = pd.Series(dtype="object")

    if base.empty:
        return base

    portfolio_lookup = build_portfolio_lookup(portfolio_dataframe)
    decisions = []

    for _, row in base.drop(columns=AI_COLUMNS, errors="ignore").iterrows():
        row_data = row.to_dict()
        decisions.append(
            make_ai_decision(
                row_data,
                portfolio=portfolio_for_row(
                    row_data,
                    portfolio_lookup,
                ),
                config=config,
            )
        )

    decision_df = pd.DataFrame(decisions)
    output = base.drop(columns=AI_COLUMNS, errors="ignore").reset_index(drop=True)
    output = pd.concat(
        [
            output,
            decision_df[AI_COLUMNS].reset_index(drop=True),
        ],
        axis=1,
    )

    sort_columns = [
        column
        for column in [
            "AIReviewPriority",
            "AIConfidence",
            "PriorityRank",
        ]
        if column in output.columns
    ]

    if sort_columns:
        ascending = [
            True if column != "AIConfidence" else False
            for column in sort_columns
        ]
        output = output.sort_values(
            by=sort_columns,
            ascending=ascending,
            kind="mergesort",
        ).reset_index(drop=True)

    return output


def save_ai_decisions(
    decisions: pd.DataFrame,
    path: Path = AI_DECISIONS_FILE,
) -> Path:
    """Save AI decisions to a runtime CSV output."""

    path.parent.mkdir(
        exist_ok=True
    )
    atomic_write_csv(
        decisions,
        path,
        index=False,
    )

    return path
