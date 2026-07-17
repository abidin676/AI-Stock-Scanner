from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from config import MAX_FRESH_CROSS_DAYS
from fresh_cross_policy import (
    AUTHORITATIVE_CROSS_AGE_SOURCE,
    apply_fresh_cross_policy,
    evaluate_fresh_cross_policy,
)
from runtime_io import atomic_write_csv


FRESH_CROSS_CANDIDATES_FILE = Path("output") / "fresh_cross_candidates.csv"
CANDIDATE_RANKING_AUDIT_FILE = Path("output") / "candidate_ranking_audit.csv"
EXTENDED_TERMS = {"EXTENDED", "MOMENTUM EXTENDED", "CHASING"}

AUDIT_COLUMNS = [
    "Symbol",
    "Market",
    "LatestPriceDate",
    "CrossDate",
    "CrossAge",
    "CrossAgeSource",
    "EMA9",
    "EMA20",
    "PreviousEMA9",
    "PreviousEMA20",
    "EMA9AboveEMA20",
    "BullishCrossEvent",
    "RVOL",
    "RSI",
    "Extension",
    "FreshCrossEligible",
    "FreshCrossStatus",
    "FreshCrossStatusLabel",
    "Score",
    "PriorityScore",
    "Rank",
    "IncludedInTop5",
    "Top5EligibilityReason",
    "ExclusionReason",
]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _upper(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip().upper()


def is_candidate_extended(row: pd.Series | dict[str, Any]) -> bool:
    lifecycle = _upper(row.get("LifecycleState"))
    signal_text = " ".join(
        _upper(row.get(column))
        for column in (
            "StrategySignal",
            "Signal",
            "StrategySetup",
            "Setup",
            "RecommendedAction",
            "PriorityAction",
        )
    ).replace("NOT EXTENDED", "")
    expansion = _number(row.get("ExpansionScore"))
    distance_ema20 = _number(
        row.get(
            "DistanceEMA20Pct",
            row.get("DistanceFromEMA20Pct", 0),
        )
    )
    # ExpansionScore >= 70 already means the move is materially under way in
    # the opportunity engine.  It is therefore an EXTENDED hard-gate failure
    # even when a legacy lifecycle label still says WATCH/SEED.
    return (
        expansion >= 70
        or lifecycle == "EXTENDED"
        or any(term in signal_text for term in EXTENDED_TERMS)
        or distance_ema20 > 12
    )


def _ranking_score(row: pd.Series) -> float:
    for column in (
        "AIConfidence",
        "PriorityScore",
        "StrategyScore",
        "Score",
        "OpportunityScore",
    ):
        if column in row and not pd.isna(row.get(column)):
            return _number(row.get(column))
    return 0.0


def _extension_value(row: pd.Series) -> float:
    for column in (
        "ExtensionPct",
        "DistanceEMA20Pct",
        "DistanceFromEMA20Pct",
    ):
        if column in row and not pd.isna(row.get(column)):
            return _number(row.get(column))

    price = _number(row.get("Price"))
    ema9 = _number(row.get("EMA9"))
    if price > 0 and ema9 > 0:
        return (price / ema9 - 1) * 100
    return 0.0


def _hard_gate_exclusion_reason(row: pd.Series) -> str:
    policy = evaluate_fresh_cross_policy(row)

    if not policy.ema9_above_ema20:
        return "EMA9_NOT_ABOVE"
    if (
        not policy.latest_price_date
        or not policy.cross_date
        or policy.age is None
        or policy.cross_age_source != AUTHORITATIVE_CROSS_AGE_SOURCE
    ):
        return "NO_CROSS_EVENT"
    if policy.age == 0 and not policy.bullish_cross_event:
        return "NO_CROSS_EVENT"
    if policy.age > MAX_FRESH_CROSS_DAYS:
        return f"CROSS_AGE_{policy.age}"
    if not policy.eligible:
        return "NO_CROSS_EVENT"
    if is_candidate_extended(row):
        return "EXTENDED"
    return ""


def rank_candidate_universe(
    dataframe: pd.DataFrame | None,
    top_n: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if dataframe is None:
        empty = pd.DataFrame(columns=AUDIT_COLUMNS)
        return pd.DataFrame(), empty, pd.DataFrame()

    data = apply_fresh_cross_policy(dataframe)
    if data.empty:
        audit = pd.DataFrame(columns=AUDIT_COLUMNS)
        return data, audit, data.copy()

    for column, default in {
        "Symbol": "",
        "Market": "",
        "EMA9": pd.NA,
        "EMA20": pd.NA,
        "PreviousEMA9": pd.NA,
        "PreviousEMA20": pd.NA,
        "RVOL": 0,
        "RSI": 0,
        "PriorityScore": 0,
    }.items():
        if column not in data.columns:
            data[column] = default

    data["Symbol"] = data["Symbol"].astype(str).str.upper().str.strip()
    data["Market"] = data["Market"].astype(str).str.upper().str.strip()
    data["CrossAge"] = data["FreshCrossAge"]
    data["EMA9AboveEMA20"] = [
        evaluate_fresh_cross_policy(row).ema9_above_ema20
        for _, row in data.iterrows()
    ]
    data["Extension"] = [
        _extension_value(row)
        for _, row in data.iterrows()
    ]
    data["RankingScore"] = [
        _ranking_score(row)
        for _, row in data.iterrows()
    ]
    data["PriorityScore"] = pd.to_numeric(
        data["PriorityScore"],
        errors="coerce",
    ).fillna(0)
    data["_HardGateExclusion"] = [
        _hard_gate_exclusion_reason(row)
        for _, row in data.iterrows()
    ]
    data["FreshCrossEligible"] = data["_HardGateExclusion"].eq("")
    data["IsFreshEMA9Cross"] = data["FreshCrossEligible"]
    data["CanonicalRank"] = pd.Series(pd.NA, index=data.index, dtype="Int64")

    eligible = data[data["FreshCrossEligible"]].copy()
    ranked_markets = []
    for market, market_rows in eligible.groupby("Market", sort=True):
        ranked = market_rows.sort_values(
            [
                "CrossAge",
                "RankingScore",
                "PriorityScore",
                "Symbol",
            ],
            ascending=[
                True,
                False,
                False,
                True,
            ],
            kind="mergesort",
        ).copy()
        ranked["CanonicalRank"] = range(1, len(ranked) + 1)
        ranked_markets.append(ranked)

    if ranked_markets:
        eligible = pd.concat(ranked_markets, ignore_index=False)
        rank_map = eligible["CanonicalRank"]
        data.loc[rank_map.index, "CanonicalRank"] = rank_map.astype("Int64")

    data["IncludedInTop5"] = (
        data["FreshCrossEligible"]
        & data["CanonicalRank"].notna()
        & (data["CanonicalRank"] <= int(top_n))
    )
    data["Top5EligibilityReason"] = data["_HardGateExclusion"]
    data.loc[
        data["FreshCrossEligible"] & ~data["IncludedInTop5"],
        "Top5EligibilityReason",
    ] = "RANKED_BELOW_TOP5"
    data.loc[
        data["IncludedInTop5"],
        "Top5EligibilityReason",
    ] = "INCLUDED_IN_TOP5"
    data["ExclusionReason"] = data["Top5EligibilityReason"]

    fresh = data[data["FreshCrossEligible"]].sort_values(
        ["Market", "CanonicalRank", "Symbol"],
        ascending=[True, True, True],
        kind="mergesort",
    ).copy()

    audit = pd.DataFrame(
        {
            "Symbol": data["Symbol"],
            "Market": data["Market"],
            "LatestPriceDate": data["LatestPriceDate"],
            "CrossDate": data["CrossDate"],
            "CrossAge": data["CrossAge"],
            "CrossAgeSource": data["CrossAgeSource"],
            "EMA9": data["EMA9"],
            "EMA20": data["EMA20"],
            "PreviousEMA9": data["PreviousEMA9"],
            "PreviousEMA20": data["PreviousEMA20"],
            "EMA9AboveEMA20": data["EMA9AboveEMA20"],
            "BullishCrossEvent": data["BullishCrossEvent"],
            "RVOL": data["RVOL"],
            "RSI": data["RSI"],
            "Extension": data["Extension"],
            "FreshCrossEligible": data["FreshCrossEligible"],
            "FreshCrossStatus": data["FreshCrossStatus"],
            "FreshCrossStatusLabel": data["FreshCrossStatusLabel"],
            "Score": data["RankingScore"],
            "PriorityScore": data["PriorityScore"],
            "Rank": data["CanonicalRank"],
            "IncludedInTop5": data["IncludedInTop5"],
            "Top5EligibilityReason": data["Top5EligibilityReason"],
            "ExclusionReason": data["ExclusionReason"],
        }
    )
    audit = audit.sort_values(
        ["Market", "FreshCrossEligible", "Rank", "Symbol"],
        ascending=[True, False, True, True],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)
    return data, audit[AUDIT_COLUMNS], fresh


def fresh_cross_candidates(
    dataframe: pd.DataFrame | None,
    top_n: int = 5,
) -> pd.DataFrame:
    _, _, fresh = rank_candidate_universe(dataframe, top_n=top_n)
    return fresh


def top_five_candidates(
    dataframe: pd.DataFrame | None,
    market: str,
    limit: int = 5,
) -> pd.DataFrame:
    fresh = fresh_cross_candidates(dataframe, top_n=limit)
    if fresh.empty:
        return fresh
    return fresh[
        fresh["Market"].astype(str).str.upper() == str(market).upper()
    ].head(limit).copy()


def save_candidate_ranking_outputs(
    dataframe: pd.DataFrame | None,
    candidates_path: Path = FRESH_CROSS_CANDIDATES_FILE,
    audit_path: Path = CANDIDATE_RANKING_AUDIT_FILE,
) -> tuple[pd.DataFrame, pd.DataFrame, Path, Path]:
    _, audit, fresh = rank_candidate_universe(dataframe, top_n=5)
    candidates_file = atomic_write_csv(fresh, candidates_path, index=False)
    audit_file = atomic_write_csv(audit, audit_path, index=False)
    return fresh, audit, candidates_file, audit_file
