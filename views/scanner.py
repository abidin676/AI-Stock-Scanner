from pathlib import Path
from datetime import datetime
import html
import subprocess
import sys

import pandas as pd
import streamlit as st

from candidate_eligibility import split_candidate_queues
from config import MAX_FRESH_CROSS_DAYS, MAX_WORKERS
from data import PRICE_CACHE_DIR
from fresh_cross_policy import (
    cross_age_label as policy_cross_age_label,
    evaluate_fresh_cross_policy,
    fresh_cross_reason_for_age,
)
from fresh_cross_candidates import (
    CANDIDATE_RANKING_AUDIT_FILE,
    FRESH_CROSS_CANDIDATES_FILE,
    fresh_cross_candidates as canonical_fresh_cross_candidates,
    rank_candidate_universe,
    top_five_candidates,
)
from market_quality import (
    calculate_market_quality,
    latest_market_quality_with_trend,
    load_market_quality,
)
from opportunity_engine import (
    OPPORTUNITY_COLUMNS,
    calculate_opportunities,
)
from priority_engine import (
    PRIORITY_COLUMNS,
    PRIORITY_FILE,
    PRIORITY_UI_OPTIONS,
    apply_priority_mode,
    load_priority_results,
    recommend_priority_mode,
)
from approval_queue import load_approval_queue
from risk_manager import build_risk_summary
from scan_metadata import SCAN_METADATA_FILE, load_scan_manifest, load_scan_metadata
from strategy_lifecycle import (
    get_state_transitions,
    load_lifecycle,
)
from watchlist import add_to_watchlist


RESULT_CSV_FILE = Path("output") / "scanner_results.csv"
RESULT_XLSX_FILE = Path("output") / "scanner_results.xlsx"
OPPORTUNITY_RESULT_FILE = Path("output") / "opportunity_results.csv"
PRIORITY_RESULT_FILE = PRIORITY_FILE
AI_DECISION_RESULT_FILE = Path("output") / "ai_decisions.csv"
ORDER_PROPOSALS_FILE = Path("output") / "order_proposals.csv"
RISK_SUMMARY_FILE = Path("output") / "risk_summary.csv"
FRESH_CROSS_RESULT_FILE = FRESH_CROSS_CANDIDATES_FILE
CANDIDATE_RANKING_AUDIT_RESULT_FILE = CANDIDATE_RANKING_AUDIT_FILE
RESULT_FILES = [
    RESULT_CSV_FILE,
    RESULT_XLSX_FILE,
]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_MODE_OPTIONS = [
    "ALL",
    "SET50",
    "SET100",
    "SET All",
    "USA Watchlist",
    "USA All",
]
STRATEGY_MODE_OPTIONS = [
    "Standard",
    "Early",
    "Pure Early",
    "Breakout",
    "Momentum",
]
STRATEGY_MODE_CLI_ARGS = {
    "STANDARD": "standard",
    "EARLY": "early",
    "PURE EARLY": "pure_early",
    "PURE_EARLY": "pure_early",
    "PURE-EARLY": "pure_early",
    "SEED": "pure_early",
    "BREAKOUT": "breakout",
    "MOMENTUM": "momentum",
}
SIGNAL_ORDER = {
    "BUY": 0,
    "WATCH": 1,
    "EARLY": 2,
    "EXTENDED": 3,
    "SKIP": 4,
    "OTHER": 5,
}
SIGNAL_GROUPS = set(SIGNAL_ORDER.keys())
LIFECYCLE_STATES = [
    "ALL",
    "SEED",
    "EARLY",
    "BREAKOUT",
    "MOMENTUM",
    "EXTENDED",
    "WATCH",
    "SKIP",
    "UNKNOWN",
]
DISPLAY_COLUMNS = [
    "Symbol",
    "Market",
    "PriorityRank",
    "PriorityScore",
    "PriorityMode",
    "PriorityAction",
    "OpportunityRank",
    "OpportunityScore",
    "OpportunityGrade",
    "Confidence",
    "RecommendedAction",
    "LifecycleState",
    "SeedScore",
    "SeedProbability",
    "FreshnessScore",
    "PatternName",
    "PatternScore",
    "VCPProbability",
    "BaseQuality",
    "AccumulationScore",
    "ExpansionScore",
    "BottomingSeedScore",
    "DowntrendDecelerationScore",
    "SellingPressureScore",
    "SmallCandleScore",
    "PreviousLifecycleState",
    "DaysInState",
    "StateChanged",
    "StrategyMode",
    "StrategySignal",
    "StrategySetup",
    "StrategyScore",
    "LatestPriceDate",
    "CrossDate",
    "DaysSinceEMA9CrossEMA20",
    "BaseDays",
    "BaseTightnessPct",
    "HighLowRange10",
    "HighLowRange20",
    "DryVolumeDays",
    "DryVolumeScore",
    "Vol5ToVol20",
    "EMACompressionPct",
    "ATRPercentile60",
    "ATRCompressionScore",
    "PocketPivot",
    "PriceAboveLowClose20Pct",
    "Return5DPct",
    "Return10DPct",
    "BullishCandleStreak",
    "WideRangeBullishCount",
    "MomentumEstablished",
    "LowerLowsStopped",
    "FirstHigherLow",
    "EMA9CurlUp",
    "EMA20Improving",
    "FirstIgnition",
    "DistanceFromHigh60Pct",
    "NearLow60Pct",
    "EMA9EMA20SpreadPct",
    "Signal",
    "Setup",
    "Score",
    "Price",
    "RSI",
    "RVOL",
]
OPPORTUNITY_DISPLAY_COLUMNS = [
    "PriorityRank",
    "PriorityScore",
    "PriorityMode",
    "PriorityAction",
    "PriorityReasons",
    "OpportunityRank",
    "Symbol",
    "Market",
    "OpportunityScore",
    "OpportunityGrade",
    "Confidence",
    "RecommendedAction",
    "LifecycleState",
    "DaysInState",
    "SeedScore",
    "FreshnessScore",
    "PatternName",
    "PatternScore",
    "VCPProbability",
    "BaseQuality",
    "AccumulationScore",
    "ExpansionScore",
    "BottomingSeedScore",
    "DowntrendDecelerationScore",
    "BaseDays",
    "BaseTightnessPct",
    "DryVolumeDays",
    "DryVolumeScore",
    "Vol5ToVol20",
    "EMACompressionPct",
    "ATRPercentile60",
    "PriceAboveLowClose20Pct",
    "Return5DPct",
    "Return10DPct",
    "EMA9EMA20SpreadPct",
    "StrategyMode",
    "StrategySignal",
    "StrategyScore",
    "LatestPriceDate",
    "CrossDate",
    "DaysSinceEMA9CrossEMA20",
    "Price",
    "RSI",
    "RVOL",
    "RiskPct",
    "RewardPct",
    "RR",
]
OPPORTUNITY_OVERVIEW_COLUMNS = [
    "PriorityRank",
    "PriorityScore",
    "PriorityAction",
    "PriorityMode",
    "PriorityReasons",
    "OpportunityRank",
    "Symbol",
    "Market",
    "OpportunityScore",
    "RecommendedAction",
    "LifecycleState",
    "DaysInState",
    "SeedScore",
    "FreshnessScore",
    "PatternName",
    "PatternScore",
    "VCPProbability",
    "BaseQuality",
    "AccumulationScore",
    "ExpansionScore",
    "BottomingSeedScore",
    "DowntrendDecelerationScore",
    "BaseDays",
    "BaseTightnessPct",
    "DryVolumeDays",
    "DryVolumeScore",
    "EMACompressionPct",
    "PriceAboveLowClose20Pct",
    "Return5DPct",
    "Return10DPct",
    "EMA9EMA20SpreadPct",
    "StrategySignal",
    "StrategyScore",
    "RSI",
    "RVOL",
    "RiskPct",
    "RewardPct",
    "RR",
]
SEED_DETAIL_COLUMNS = [
    "Rank",
    "Symbol",
    "RecommendedAction",
    "LifecycleState",
    "SeedScore",
    "FreshnessScore",
    "ExpansionScore",
    "PatternName",
    "BaseDays",
    "DryVolumeDays",
    "EMACompressionPct",
    "RiskPct",
    "PriorityScore",
    "PriorityAction",
]
OPPORTUNITY_ACTIONS = [
    "ALL",
    "Strong Buy",
    "Buy",
    "Watch Closely",
    "Watch",
    "Early Watch",
    "Ignore",
]
ROW_COLORS = {
    "BUY": "#dcfce7",
    "WATCH": "#dbeafe",
    "EARLY": "#fef9c3",
    "EXTENDED": "#ffedd5",
    "SKIP": "#f3f4f6",
}
LIFECYCLE_ROW_COLORS = {
    "EARLY": "#dcfce7",
    "BREAKOUT": "#ffedd5",
    "MOMENTUM": "#dbeafe",
    "EXTENDED": "#fed7aa",
    "WATCH": "#e0f2fe",
    "SKIP": "#f3f4f6",
    "UNKNOWN": "#f9fafb",
}
QUALITY_DISPLAY_COLUMNS = [
    "Market",
    "StrategyMode",
    "QualityScore",
    "QualityLabel",
    "Trend",
    "TotalStocks",
    "BuyCount",
    "AvgBuyScore",
    "BreakoutCount",
    "ScanTimeSeconds",
    "LastScanTime",
]


def signal_group(signal):

    signal = str(signal)

    if "BUY" in signal:
        return "BUY"

    if "WATCH" in signal:
        return "WATCH"

    if "EARLY" in signal:
        return "EARLY"

    if "EXTENDED" in signal:
        return "EXTENDED"

    if "SKIP" in signal:
        return "SKIP"

    return "OTHER"


def result_file_modified_time(path):

    return datetime.fromtimestamp(
        path.stat().st_mtime
    )


def result_file_display_time(path):

    return result_file_modified_time(path).strftime(
        "%d/%m/%Y %H:%M:%S"
    )


def select_scanner_result_file():

    if RESULT_CSV_FILE.exists():
        return RESULT_CSV_FILE

    if RESULT_XLSX_FILE.exists():
        return RESULT_XLSX_FILE

    return None


def load_scanner_results_from_disk():

    path = select_scanner_result_file()

    if path is None:
        return pd.DataFrame(), None

    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path), path

        return pd.read_excel(path), path

    except Exception as exc:
        st.warning(
            f"Could not load scanner results: {exc}"
        )
        return pd.DataFrame(), path


def load_opportunity_results_from_disk(scanner_df=None):

    if OPPORTUNITY_RESULT_FILE.exists():
        try:
            return (
                pd.read_csv(OPPORTUNITY_RESULT_FILE),
                OPPORTUNITY_RESULT_FILE,
                False,
            )
        except pd.errors.EmptyDataError:
            return (
                pd.DataFrame(),
                OPPORTUNITY_RESULT_FILE,
                False,
            )
        except Exception as exc:
            st.warning(
                f"Could not load opportunity results: {exc}"
            )

    if scanner_df is not None and not scanner_df.empty:
        return (
            scanner_df.copy(),
            None,
            True,
        )

    return (
        pd.DataFrame(),
        None,
        True,
    )


def load_priority_results_from_disk():

    if not PRIORITY_RESULT_FILE.exists():
        return pd.DataFrame(), PRIORITY_RESULT_FILE, True

    try:
        return (
            load_priority_results(PRIORITY_RESULT_FILE),
            PRIORITY_RESULT_FILE,
            False,
        )
    except Exception as exc:
        st.warning(
            f"Could not load priority results: {exc}"
        )
        return pd.DataFrame(), PRIORITY_RESULT_FILE, True


def load_ai_decisions_from_disk():

    if not AI_DECISION_RESULT_FILE.exists():
        return pd.DataFrame(), AI_DECISION_RESULT_FILE, True

    try:
        return (
            pd.read_csv(AI_DECISION_RESULT_FILE),
            AI_DECISION_RESULT_FILE,
            False,
        )
    except pd.errors.EmptyDataError:
        return (
            pd.DataFrame(),
            AI_DECISION_RESULT_FILE,
            False,
        )
    except Exception as exc:
        st.warning(
            f"Could not load AI decisions: {exc}"
        )
        return pd.DataFrame(), AI_DECISION_RESULT_FILE, True


def load_candidate_ranking_outputs_from_disk():

    fresh_missing = not FRESH_CROSS_RESULT_FILE.exists()
    audit_missing = not CANDIDATE_RANKING_AUDIT_RESULT_FILE.exists()

    try:
        fresh = (
            pd.read_csv(FRESH_CROSS_RESULT_FILE)
            if not fresh_missing
            else pd.DataFrame()
        )
    except pd.errors.EmptyDataError:
        fresh = pd.DataFrame()
    except Exception as exc:
        st.warning(f"Could not load canonical Fresh Cross candidates: {exc}")
        fresh = pd.DataFrame()
        fresh_missing = True

    try:
        audit = (
            pd.read_csv(CANDIDATE_RANKING_AUDIT_RESULT_FILE)
            if not audit_missing
            else pd.DataFrame()
        )
    except pd.errors.EmptyDataError:
        audit = pd.DataFrame()
    except Exception as exc:
        st.warning(f"Could not load candidate ranking audit: {exc}")
        audit = pd.DataFrame()
        audit_missing = True

    return fresh, audit, fresh_missing, audit_missing


def load_order_proposals_from_disk():

    if not ORDER_PROPOSALS_FILE.exists():
        return pd.DataFrame(), ORDER_PROPOSALS_FILE, True

    try:
        return (
            pd.read_csv(ORDER_PROPOSALS_FILE),
            ORDER_PROPOSALS_FILE,
            False,
        )
    except pd.errors.EmptyDataError:
        return (
            pd.DataFrame(),
            ORDER_PROPOSALS_FILE,
            False,
        )
    except Exception as exc:
        st.warning(
            f"Could not load order proposals: {exc}"
        )
        return pd.DataFrame(), ORDER_PROPOSALS_FILE, True


def load_risk_summary_from_disk(proposals=None):

    if RISK_SUMMARY_FILE.exists():
        try:
            return (
                pd.read_csv(RISK_SUMMARY_FILE),
                RISK_SUMMARY_FILE,
                False,
            )
        except pd.errors.EmptyDataError:
            return (
                pd.DataFrame(),
                RISK_SUMMARY_FILE,
                False,
            )
        except Exception as exc:
            st.warning(
                f"Could not load risk summary: {exc}"
            )

    if proposals is not None and not proposals.empty:
        try:
            return (
                build_risk_summary(proposals),
                None,
                True,
            )
        except Exception as exc:
            st.warning(
                f"Could not build fallback risk summary: {exc}"
            )

    return pd.DataFrame(), RISK_SUMMARY_FILE, True


def ensure_strategy_columns(df):

    data = df.copy()

    if "Symbol" not in data.columns:
        data["Symbol"] = ""

    if "Market" not in data.columns:
        data["Market"] = ""

    if "Signal" not in data.columns:
        data["Signal"] = ""

    if "Setup" not in data.columns:
        data["Setup"] = ""

    if "Score" not in data.columns:
        data["Score"] = 0

    if "StrategyMode" not in data.columns:
        data["StrategyMode"] = "Standard"

    if "StrategySignal" not in data.columns:
        data["StrategySignal"] = data["Signal"]

    if "StrategySetup" not in data.columns:
        data["StrategySetup"] = data["Setup"]

    if "StrategyScore" not in data.columns:
        data["StrategyScore"] = data["Score"]

    data["StrategyScore"] = pd.to_numeric(
        data["StrategyScore"],
        errors="coerce",
    ).fillna(0)
    data["Score"] = pd.to_numeric(
        data["Score"],
        errors="coerce",
    ).fillna(0)
    data["Symbol"] = (
        data["Symbol"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    data["Market"] = (
        data["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    return data


def ensure_lifecycle_columns(df):

    data = df.copy()

    if "LifecycleState" not in data.columns:
        data["LifecycleState"] = "UNKNOWN"

    if "PreviousLifecycleState" not in data.columns:
        data["PreviousLifecycleState"] = "UNKNOWN"

    if "DaysInState" not in data.columns:
        data["DaysInState"] = 0

    if "StateChanged" not in data.columns:
        data["StateChanged"] = False

    data["LifecycleState"] = (
        data["LifecycleState"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .replace("", "UNKNOWN")
    )
    data["PreviousLifecycleState"] = (
        data["PreviousLifecycleState"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .replace("", "UNKNOWN")
    )
    data["DaysInState"] = pd.to_numeric(
        data["DaysInState"],
        errors="coerce",
    ).fillna(0).astype(int)
    data["StateChanged"] = data["StateChanged"].apply(
        lambda value: str(value).strip().upper()
        in {
            "TRUE",
            "1",
            "YES",
            "Y",
        }
        if not isinstance(value, bool)
        else value
    )

    return data


def ensure_opportunity_columns(df):

    data = df.copy()

    if not set(OPPORTUNITY_COLUMNS).issubset(data.columns):
        data = calculate_opportunities(
            data,
            lifecycle=load_lifecycle(),
            market_quality=load_market_quality(),
        )

    if "OpportunityScore" not in data.columns:
        data["OpportunityScore"] = 0

    if "OpportunityRank" not in data.columns:
        data["OpportunityRank"] = range(
            1,
            len(data) + 1,
        )

    if "OpportunityGrade" not in data.columns:
        data["OpportunityGrade"] = "★☆☆☆☆ Ignore"

    if "Confidence" not in data.columns:
        data["Confidence"] = 0

    if "RecommendedAction" not in data.columns:
        data["RecommendedAction"] = "Ignore"

    if "OpportunityReasons" not in data.columns:
        data["OpportunityReasons"] = ""

    for column in [
        "RiskPct",
        "RewardPct",
        "RR",
    ]:
        if column not in data.columns:
            data[column] = 0

    data["OpportunityScore"] = pd.to_numeric(
        data["OpportunityScore"],
        errors="coerce",
    ).fillna(0)
    data["OpportunityRank"] = pd.to_numeric(
        data["OpportunityRank"],
        errors="coerce",
    ).fillna(0).astype(int)
    data["Confidence"] = pd.to_numeric(
        data["Confidence"],
        errors="coerce",
    ).fillna(0)
    for column in [
        "RiskPct",
        "RewardPct",
        "RR",
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        ).fillna(0)

    return data


def ensure_priority_columns(
    df,
    priority_mode="Seed First",
    quality=None,
    lifecycle=None,
    ai_recommendation=None,
):

    data = df.copy()
    ai_recommendation = ai_recommendation or {
        "AIRecommendedPriority": priority_mode,
        "AIRecommendationReason": "",
    }

    if not set(PRIORITY_COLUMNS).issubset(data.columns):
        data = apply_priority_mode(
            data,
            priority_mode,
            market_quality_df=quality,
            lifecycle_df=lifecycle,
            ai_recommended_priority=ai_recommendation.get(
                "AIRecommendedPriority",
                priority_mode,
            ),
            ai_recommendation_reason=ai_recommendation.get(
                "AIRecommendationReason",
                "",
            ),
        )

    if "PriorityScore" not in data.columns:
        data["PriorityScore"] = data.get(
            "OpportunityScore",
            data.get("StrategyScore", data.get("Score", 0)),
        )

    if "PriorityRank" not in data.columns:
        data = data.sort_values(
            "PriorityScore",
            ascending=False,
        ).reset_index(drop=True)
        data["PriorityRank"] = range(
            1,
            len(data) + 1,
        )

    if "PriorityMode" not in data.columns:
        data["PriorityMode"] = priority_mode

    if "PriorityAction" not in data.columns:
        data["PriorityAction"] = ""

    if "PriorityReasons" not in data.columns:
        data["PriorityReasons"] = ""

    if "AIRecommendedPriority" not in data.columns:
        data["AIRecommendedPriority"] = ai_recommendation.get(
            "AIRecommendedPriority",
            priority_mode,
        )

    if "AIRecommendationReason" not in data.columns:
        data["AIRecommendationReason"] = ai_recommendation.get(
            "AIRecommendationReason",
            "",
        )

    data["PriorityScore"] = pd.to_numeric(
        data["PriorityScore"],
        errors="coerce",
    ).fillna(0)
    data["PriorityRank"] = pd.to_numeric(
        data["PriorityRank"],
        errors="coerce",
    ).fillna(0).astype(int)

    return data


def prepare_data(df):

    df = ensure_strategy_columns(df)
    df = ensure_lifecycle_columns(df)
    df = ensure_opportunity_columns(df)
    df["_signal_group"] = df["StrategySignal"].apply(signal_group)
    df["_signal_rank"] = df["_signal_group"].map(
        SIGNAL_ORDER
    ).fillna(
        SIGNAL_ORDER["OTHER"]
    )

    return df


def sort_results(df):

    return df.sort_values(
        [
            "_signal_rank",
            "OpportunityScore",
            "StrategyScore",
            "RVOL",
            "RSI",
        ],
        ascending=[
            True,
            False,
            False,
            False,
            True,
        ],
    )


def visible_columns(df):

    return [
        column
        for column in DISPLAY_COLUMNS
        if column in df.columns
    ]


def safe_number(value):

    if pd.isna(value):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_quality_number(value, suffix=""):

    return f"{safe_number(value):,.2f}{suffix}"


def latest_quality_from_results(df, last_scan):

    quality = calculate_market_quality(
        df,
        scan_time_seconds={},
        last_scan_time=last_scan,
    )
    quality["Trend"] = "N/A"

    return quality


def load_quality_for_dashboard(df, last_scan):

    history = load_market_quality()

    if history.empty:
        return latest_quality_from_results(
            df,
            last_scan,
        )

    latest = latest_market_quality_with_trend(history)

    if latest.empty:
        return latest_quality_from_results(
            df,
            last_scan,
        )

    current_mode = current_strategy_mode(df)
    latest = latest[
        latest["StrategyMode"].fillna("Standard").astype(str)
        == current_mode
    ]

    if latest.empty:
        return latest_quality_from_results(
            df,
            last_scan,
        )

    return latest


def current_strategy_mode(df):

    if "StrategyMode" not in df.columns or df.empty:
        return "Standard"

    modes = (
        df["StrategyMode"]
        .fillna("Standard")
        .astype(str)
        .replace("", "Standard")
    )

    if modes.empty:
        return "Standard"

    return modes.mode().iloc[0]


def watchlist_label(row):

    return (
        f"{row['Symbol']} | {row['Market']} | "
        f"{row['StrategySignal']} | {row['StrategySetup']} | "
        f"Score {row['StrategyScore']}"
    )


def first_existing_number(row, columns):

    for column in columns:
        if column in row:
            return safe_number(row.get(column, 0.0))

    return 0.0


def selected_candidate_row(candidates, selected):

    symbol, market = [
        part.strip()
        for part in selected.split("|")[:2]
    ]

    return candidates[
        (candidates["Symbol"] == symbol)
        &
        (candidates["Market"] == market)
    ].iloc[0]


def apply_filters(
    df,
    market_filter,
    signal_filter,
    symbol_search,
    lifecycle_filter=None,
    state_changed_only=False,
):

    data = df.copy()

    if market_filter != "ALL":
        data = data[data["Market"] == market_filter]

    if signal_filter and "ALL" not in signal_filter:
        grouped_filters = [
            signal
            for signal in signal_filter
            if signal in SIGNAL_GROUPS
        ]
        exact_filters = [
            signal.upper()
            for signal in signal_filter
            if signal not in SIGNAL_GROUPS
        ]
        group_mask = data["_signal_group"].isin(
            grouped_filters
        )
        exact_mask = data["StrategySignal"].astype(str).str.upper().isin(
            exact_filters
        )
        data = data[
            group_mask
            |
            exact_mask
        ]

    lifecycle_filter = lifecycle_filter or [
        "ALL",
    ]

    if lifecycle_filter and "ALL" not in lifecycle_filter:
        data = data[
            data["LifecycleState"].isin(lifecycle_filter)
        ]

    if state_changed_only:
        data = data[data["StateChanged"]]

    symbol_search = symbol_search.strip().upper()

    if symbol_search:
        data = data[
            data["Symbol"].astype(str).str.upper().str.contains(
                symbol_search,
                regex=False,
            )
        ]

    return sort_results(data)


def metadata_text(metadata, key, default="N/A"):

    if not metadata:
        return default

    value = metadata.get(key, default)

    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else default

    if value is None or str(value).strip() == "":
        return default

    return str(value)


def scanner_debug_info(df, result_path, metadata=None):

    if result_path is None:
        modified_time = "N/A"
        loaded_path = "N/A"
    else:
        modified_time = result_file_display_time(result_path)
        loaded_path = str(result_path)

    scan_mode = "N/A"

    for column in (
        "ScanMode",
        "Mode",
        "Index",
    ):
        if column in df.columns:
            values = (
                df[column]
                .dropna()
                .astype(str)
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )
            if values:
                scan_mode = ", ".join(
                    sorted(values)
                )
                break

    return {
        "Loaded file path": loaded_path,
        "File modified time": modified_time,
        "Scan metadata file": str(SCAN_METADATA_FILE)
        if SCAN_METADATA_FILE.exists()
        else "N/A",
        "Loaded rows": int(len(df)),
        "SET rows": int((df["Market"] == "SET").sum())
        if "Market" in df.columns
        else 0,
        "USA rows": int((df["Market"] == "USA").sum())
        if "Market" in df.columns
        else 0,
        "StrategyMode values found": ", ".join(
            sorted(
                df["StrategyMode"]
                .fillna("Standard")
                .astype(str)
                .replace("", "Standard")
                .unique()
                .tolist()
            )
        )
        if "StrategyMode" in df.columns
        else "Standard",
        "ScanMode": metadata_text(metadata, "ExecutedScanMode", scan_mode),
        "RequestedScanMode": metadata_text(metadata, "RequestedScanMode"),
        "ExecutedScanMode": metadata_text(metadata, "ExecutedScanMode", scan_mode),
        "ExecutedMarkets": metadata_text(metadata, "ExecutedMarkets"),
        "SETSymbolsRequested": metadata_text(metadata, "SETSymbolsRequested", "0"),
        "SETSymbolsProcessed": metadata_text(metadata, "SETSymbolsProcessed", "0"),
        "USASymbolsRequested": metadata_text(metadata, "USASymbolsRequested", "0"),
        "USASymbolsProcessed": metadata_text(metadata, "USASymbolsProcessed", "0"),
        "ScanCompletedAt": metadata_text(metadata, "ScanCompletedAt"),
        "ScanStatus": metadata_text(metadata, "ScanStatus"),
        "USAError": metadata_text(metadata, "USAError", ""),
        "SET diagnostics": metadata_text(
            metadata.get("MarketDiagnostics", {}) if metadata else {},
            "SET",
            "",
        ),
        "USA diagnostics": metadata_text(
            metadata.get("MarketDiagnostics", {}) if metadata else {},
            "USA",
            "",
        ),
        "Warnings": metadata_text(metadata, "Warnings", ""),
    }


def dataframe_values(df, column, default="N/A"):

    if column not in df.columns:
        return default

    values = (
        df[column]
        .dropna()
        .astype(str)
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

    if not values:
        return default

    return ", ".join(
        sorted(values)
    )


def score_diagnostics(df, column):

    if df is None or df.empty or column not in df.columns:
        return {
            "source": column,
            "min": 0,
            "median": 0,
            "mean": 0,
            "p90": 0,
            "max": 0,
            "null_count": 0,
            "zero_count": 0,
        }

    values = pd.to_numeric(
        df[column],
        errors="coerce",
    )
    non_null = values.dropna()

    if non_null.empty:
        return {
            "source": column,
            "min": 0,
            "median": 0,
            "mean": 0,
            "p90": 0,
            "max": 0,
            "null_count": int(values.isna().sum()),
            "zero_count": 0,
        }

    return {
        "source": column,
        "min": round(float(non_null.min()), 2),
        "median": round(float(non_null.median()), 2),
        "mean": round(float(non_null.mean()), 2),
        "p90": round(float(non_null.quantile(0.90)), 2),
        "max": round(float(non_null.max()), 2),
        "null_count": int(values.isna().sum()),
        "zero_count": int((non_null == 0).sum()),
    }


def opportunity_score_diagnostics(df):

    score_column = (
        "OpportunityScore"
        if df is not None and "OpportunityScore" in df.columns
        else "PriorityScore"
        if df is not None and "PriorityScore" in df.columns
        else "StrategyScore"
        if df is not None and "StrategyScore" in df.columns
        else "Score"
    )
    diagnostics = score_diagnostics(df, score_column)

    if df is None or df.empty:
        diagnostics.update({
            "market_counts": {},
            "lifecycle_counts": {},
        })
        return diagnostics

    diagnostics.update({
        "market_counts": df["Market"].value_counts().to_dict()
        if "Market" in df.columns
        else {},
        "lifecycle_counts": df["LifecycleState"].value_counts().head(10).to_dict()
        if "LifecycleState" in df.columns
        else {},
    })
    return diagnostics


def opportunity_debug_info(df, result_path, is_fallback=False):

    if result_path is None:
        loaded_path = (
            "Fallback: scanner_results"
            if is_fallback
            else "N/A"
        )
        modified_time = "N/A"
    else:
        loaded_path = str(result_path)
        modified_time = result_file_display_time(result_path)

    diagnostics = opportunity_score_diagnostics(df)

    return {
        "Loaded opportunity file path": loaded_path,
        "Modified time": modified_time,
        "Loaded rows": int(len(df)),
        "SET rows": int((df["Market"] == "SET").sum())
        if "Market" in df.columns
        else 0,
        "USA rows": int((df["Market"] == "USA").sum())
        if "Market" in df.columns
        else 0,
        "StrategyMode values": dataframe_values(
            df,
            "StrategyMode",
            "Standard",
        ),
        "ScanMode values": dataframe_values(
            df,
            "ScanMode",
            "N/A",
        ),
        "Score source column": diagnostics["source"],
        "Score min": diagnostics["min"],
        "Score median": diagnostics["median"],
        "Score mean": diagnostics["mean"],
        "Score p90": diagnostics["p90"],
        "Score max": diagnostics["max"],
        "Score null count": diagnostics["null_count"],
        "Score zero count": diagnostics["zero_count"],
        "Score count by Market": diagnostics["market_counts"],
        "Score count by LifecycleState": diagnostics["lifecycle_counts"],
    }


def render_scanner_status(df, result_path, last_scan, metadata=None):

    info = scanner_debug_info(
        df,
        result_path,
        metadata,
    )
    cols = st.columns(4)
    cols[0].metric(
        "Scan Mode",
        info["ExecutedScanMode"],
    )
    cols[1].metric(
        "Scan Status",
        info["ScanStatus"],
    )
    cols[2].metric(
        "Rows Loaded",
        int(len(df)),
    )
    cols[3].metric(
        "Last Scan Time",
        info["ScanCompletedAt"]
        if info["ScanCompletedAt"] != "N/A"
        else last_scan,
    )

    warnings = metadata.get("Warnings", []) if metadata else []
    for warning in warnings:
        st.warning(str(warning))


def render_debug_info(df, result_path, metadata=None):

    info = scanner_debug_info(
        df,
        result_path,
        metadata,
    )

    with st.expander("Debug Info"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Metric": key,
                        "Value": str(value),
                    }
                    for key, value in info.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def scan_run_ids(dataframe):

    if dataframe is None or dataframe.empty or "ScanRunId" not in dataframe.columns:
        return set()

    return {
        str(value).strip()
        for value in dataframe["ScanRunId"].dropna().tolist()
        if str(value).strip()
    }


def market_status(metadata, market):

    diagnostics = metadata.get("MarketDiagnostics", {}) if metadata else {}
    item = diagnostics.get(market, {})
    return item.get("Status", "N/A")


def render_pipeline_health(df, opportunity_df, metadata):

    manifest = load_scan_manifest()
    priority_df, _, priority_missing = load_priority_results_from_disk()
    ai_df, _, ai_missing = load_ai_decisions_from_disk()
    risk_df, _, risk_missing = load_order_proposals_from_disk()

    ranked = (
        priority_df
        if not priority_missing and not priority_df.empty
        else opportunity_df
    )
    ai_for_queue = None
    risk_for_queue = None

    if not ai_missing and not ai_df.empty:
        ai_for_queue = normalize_ai_decision_frame(ai_df)
    if not risk_missing and not risk_df.empty:
        risk_for_queue = normalize_order_proposals_frame(risk_df)

    ranked, buy_queue, watch_queue = split_candidate_queues(
        ranked,
        ai_decisions=ai_for_queue,
        risk_proposals=risk_for_queue,
    )
    prepare_count = int((ranked.get("QueueClass", pd.Series(dtype=str)) == "PREPARE").sum())
    watch_count = int((ranked.get("QueueClass", pd.Series(dtype=str)) == "WATCH").sum())

    pending_approvals = 0
    try:
        approval_queue = load_approval_queue()
        if not approval_queue.empty and "Status" in approval_queue.columns:
            pending_approvals = int((approval_queue["Status"] == "PENDING_APPROVAL").sum())
    except Exception:
        pending_approvals = 0

    risk_proposals = 0
    if not risk_missing and not risk_df.empty and "ProposalStatus" in risk_df.columns:
        risk_proposals = int(
            risk_df["ProposalStatus"].isin(["PENDING_APPROVAL", "APPROVED_FOR_PAPER", "REJECTED"]).sum()
        )

    st.subheader("Pipeline Health")
    cols = st.columns(6)
    cols[0].metric("SET Scan", market_status(metadata, "SET"))
    cols[1].metric("USA Scan", market_status(metadata, "USA"))
    cols[2].metric("Scanner Rows", int(len(df)))
    cols[3].metric("Priority Rows", int(0 if priority_missing else len(priority_df)))
    cols[4].metric("BUY Queue", int(len(buy_queue)))
    cols[5].metric("PREPARE", prepare_count)

    cols = st.columns(6)
    cols[0].metric("Opportunity Rows", int(len(opportunity_df)))
    cols[1].metric("AI Rows", int(0 if ai_missing else len(ai_df)))
    cols[2].metric("WATCH", watch_count)
    cols[3].metric("Risk Proposals", risk_proposals)
    cols[4].metric("Pending Approvals", pending_approvals)
    cols[5].metric("ScanRunId", metadata.get("ScanRunId", "N/A") if metadata else "N/A")

    if manifest:
        completed_markets = manifest.get("CompletedMarkets", [])
        st.caption(
            "Completed Markets: "
            + (", ".join(completed_markets) if completed_markets else "None")
            + f" | Manifest Status: {manifest.get('Status', 'N/A')}"
        )

    expected_scan_run = metadata.get("ScanRunId") if metadata else ""
    output_ids = {
        "scanner": scan_run_ids(df),
        "opportunity": scan_run_ids(opportunity_df),
        "priority": scan_run_ids(priority_df),
        "ai": scan_run_ids(ai_df),
        "risk": scan_run_ids(risk_df),
    }
    mismatched = [
        name
        for name, values in output_ids.items()
        if expected_scan_run and values and values != {expected_scan_run}
    ]
    if mismatched:
        st.warning(
            "ScanRunId mismatch detected in: "
            + ", ".join(mismatched)
            + ". Outputs may be from different scanner runs."
        )

    requested = set(metadata.get("ExpectedMarkets", [])) if metadata else set()
    if "USA" in requested and market_status(metadata, "USA") in {"FAILED", "N/A"}:
        st.warning(
            "USA scan requested but no USA results were produced. "
            "Check provider, symbol universe, download errors, or cache."
        )

    if len(df) > 0:
        for name, frame, missing in [
            ("Opportunity", opportunity_df, False),
            ("Priority", priority_df, priority_missing),
            ("AI decision", ai_df, ai_missing),
        ]:
            if missing or frame.empty:
                st.warning(f"{name} output is missing or empty while scanner rows exist.")

    render_funnel_summary(
        ranked,
        buy_queue,
        watch_queue,
        ai_df if not ai_missing else pd.DataFrame(),
        risk_df if not risk_missing else pd.DataFrame(),
        pending_approvals,
    )


def reason_counts(series):

    counts = {}

    for value in series.fillna("").astype(str):
        for reason in value.split("|"):
            reason = reason.strip()
            if not reason:
                continue
            counts[reason] = counts.get(reason, 0) + 1

    return counts


def render_funnel_summary(ranked, buy_queue, watch_queue, ai_df, risk_df, pending_approvals):

    if ranked is None or ranked.empty:
        return

    lifecycle_eligible = int(ranked.get("BaseEligible", pd.Series(False, index=ranked.index)).fillna(False).astype(bool).sum())
    opportunity_score = pd.to_numeric(
        ranked.get("OpportunityScore", pd.Series(0, index=ranked.index)),
        errors="coerce",
    ).fillna(0)
    priority_score = pd.to_numeric(
        ranked.get("PriorityScore", pd.Series(0, index=ranked.index)),
        errors="coerce",
    ).fillna(0)
    rr = pd.to_numeric(
        ranked.get("RiskRewardRatio", ranked.get("RR", pd.Series(0, index=ranked.index))),
        errors="coerce",
    ).fillna(0)
    entry = pd.to_numeric(
        ranked.get("EntryPrice", ranked.get("Price", pd.Series(0, index=ranked.index))),
        errors="coerce",
    ).fillna(0)
    stop = pd.to_numeric(
        ranked.get("StopPrice", ranked.get("StopLoss", pd.Series(0, index=ranked.index))),
        errors="coerce",
    ).fillna(0)
    target = pd.to_numeric(
        ranked.get("TargetPrice", ranked.get("Target", pd.Series(0, index=ranked.index))),
        errors="coerce",
    ).fillna(0)

    ai_actionable = 0
    if ai_df is not None and not ai_df.empty and "AIDecision" in ai_df.columns:
        ai_actionable = int(ai_df["AIDecision"].isin(["BUY", "PREPARE", "WATCH"]).sum())

    risk_passed = 0
    if risk_df is not None and not risk_df.empty and "ProposalStatus" in risk_df.columns:
        risk_passed = int(risk_df["ProposalStatus"].isin(["PENDING_APPROVAL", "APPROVED_FOR_PAPER"]).sum())

    funnel = pd.DataFrame(
        [
            {"Stage": "Scanner candidates", "Input": len(ranked), "Passed": len(ranked), "Rejected": 0},
            {"Stage": "Lifecycle/Base eligible", "Input": len(ranked), "Passed": lifecycle_eligible, "Rejected": len(ranked) - lifecycle_eligible},
            {"Stage": "Opportunity score > 0", "Input": len(ranked), "Passed": int((opportunity_score > 0).sum()), "Rejected": int((opportunity_score <= 0).sum())},
            {"Stage": "Priority score >= 55", "Input": len(ranked), "Passed": int((priority_score >= 55).sum()), "Rejected": int((priority_score < 55).sum())},
            {"Stage": "AI BUY/PREPARE/WATCH", "Input": len(ai_df) if ai_df is not None else 0, "Passed": ai_actionable, "Rejected": max((len(ai_df) if ai_df is not None else 0) - ai_actionable, 0)},
            {"Stage": "RR >= 1.5", "Input": len(ranked), "Passed": int((rr >= 1.5).sum()), "Rejected": int((rr < 1.5).sum())},
            {"Stage": "Price/Stop/Target valid", "Input": len(ranked), "Passed": int(((entry > 0) & (stop > 0) & (target > entry)).sum()), "Rejected": int(((entry <= 0) | (stop <= 0) | (target <= entry)).sum())},
            {"Stage": "Risk passed", "Input": len(risk_df) if risk_df is not None else 0, "Passed": risk_passed, "Rejected": max((len(risk_df) if risk_df is not None else 0) - risk_passed, 0)},
            {"Stage": "Buy Queue", "Input": len(ranked), "Passed": len(buy_queue), "Rejected": len(ranked) - len(buy_queue)},
            {"Stage": "Pending Approval", "Input": len(risk_df) if risk_df is not None else 0, "Passed": pending_approvals, "Rejected": max((len(risk_df) if risk_df is not None else 0) - pending_approvals, 0)},
        ]
    )

    with st.expander("Funnel Summary", expanded=False):
        st.dataframe(
            funnel,
            use_container_width=True,
            hide_index=True,
        )
        reasons = reason_counts(
            ranked.get("BlockingReasons", pd.Series("", index=ranked.index))
        )
        if reasons:
            reason_df = pd.DataFrame(
                [
                    {"Reason": reason, "Count": count}
                    for reason, count in sorted(
                        reasons.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )[:10]
                ]
            )
            st.caption("Top rejection reasons")
            st.dataframe(reason_df, use_container_width=True, hide_index=True)

        if buy_queue.empty:
            st.info("Buy Queue is empty because no candidate passed every actionable gate.")
        if watch_queue.empty and ai_df is not None and not ai_df.empty:
            watch_ai = int(ai_df.get("AIDecision", pd.Series(dtype=str)).isin(["WATCH"]).sum())
            if watch_ai:
                st.info(
                    f"AI produced {watch_ai} WATCH rows, but central eligibility did not admit them into Watch Queue. "
                    "Check BlockingReasons and WarningReasons above."
                )


def render_opportunity_debug(df, result_path, is_fallback=False):

    info = opportunity_debug_info(
        df,
        result_path,
        is_fallback=is_fallback,
    )

    with st.expander("Opportunity Debug"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Metric": key,
                        "Value": str(value),
                    }
                    for key, value in info.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def priority_debug_info(
    df,
    selected_mode,
    ai_recommendation,
    priority_path=PRIORITY_RESULT_FILE,
):

    signal = (
        df["StrategySignal"].astype(str).str.upper()
        if "StrategySignal" in df.columns
        else pd.Series("", index=df.index)
    )
    setup = (
        df["StrategySetup"].astype(str).str.upper()
        if "StrategySetup" in df.columns
        else pd.Series("", index=df.index)
    )
    state = (
        df["LifecycleState"].astype(str).str.upper()
        if "LifecycleState" in df.columns
        else pd.Series("", index=df.index)
    )

    return {
        "Selected PriorityMode": selected_mode,
        "AI Recommended Priority": ai_recommendation.get(
            "AIRecommendedPriority",
            "N/A",
        ),
        "Priority file path": str(priority_path),
        "Priority file exists": priority_path.exists(),
        "Rows loaded": int(len(df)),
        "Top PriorityScore": safe_number(
            df["PriorityScore"].max()
        )
        if "PriorityScore" in df.columns and not df.empty
        else 0,
        "Number of Seed candidates": int(
            (
                signal.str.contains("SEED|EARLY", regex=True, na=False)
                | setup.str.contains(
                    "SEED|EARLY|ACCUMULATION|EMA20 TURN",
                    regex=True,
                    na=False,
                )
                | (state == "SEED")
                | (
                    pd.to_numeric(
                        df.get(
                            "SeedScore",
                            pd.Series(0, index=df.index),
                        ),
                        errors="coerce",
                    ).fillna(0) >= 82
                )
            ).sum()
        ),
        "Number of Breakout candidates": int(
            (
                signal.str.contains("BREAKOUT", regex=True, na=False)
                | setup.str.contains(
                    "BREAKOUT|POCKET PIVOT",
                    regex=True,
                    na=False,
                )
                | (state == "BREAKOUT")
            ).sum()
        ),
        "Number of Momentum candidates": int(
            (
                signal.str.contains("MOMENTUM", regex=True, na=False)
                | (state == "MOMENTUM")
            ).sum()
        ),
    }


def render_priority_debug(df, selected_mode, ai_recommendation):

    info = priority_debug_info(
        df,
        selected_mode,
        ai_recommendation,
    )

    with st.expander("Priority Debug"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Metric": key,
                        "Value": str(value),
                    }
                    for key, value in info.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_lifecycle_section(df):

    st.subheader("Strategy Lifecycle")

    changed = df[df["StateChanged"]]
    metric_cols = st.columns(6)

    metrics = [
        (
            "New Seed",
            int(
                (
                    (changed["LifecycleState"] == "SEED")
                ).sum()
            ),
        ),
        (
            "New Early",
            int(
                (
                    (changed["LifecycleState"] == "EARLY")
                ).sum()
            ),
        ),
        (
            "New Breakout",
            int(
                (
                    (changed["LifecycleState"] == "BREAKOUT")
                ).sum()
            ),
        ),
        (
            "New Momentum",
            int(
                (
                    (changed["LifecycleState"] == "MOMENTUM")
                ).sum()
            ),
        ),
        (
            "Extended Count",
            int(
                (
                    df["LifecycleState"] == "EXTENDED"
                ).sum()
            ),
        ),
        (
            "State Changes Today",
            int(len(changed)),
        ),
    ]

    for column, (label, value) in zip(metric_cols, metrics):
        column.metric(
            label,
            value,
        )

    transitions = get_state_transitions(
        limit=25,
    )

    with st.expander("Recent State Transitions"):
        if transitions.empty:
            st.info("No recent state transitions")
        else:
            st.dataframe(
                transitions,
                use_container_width=True,
                hide_index=True,
            )


def market_quality_recommendation(score):

    score = safe_number(score)

    if score >= 80:
        return (
            "Strong",
            "Market is supportive. Focus on the cleanest seed and breakout setups.",
        )

    if score >= 60:
        return (
            "Healthy",
            "Review quality accumulation setups. Avoid low-conviction chasing.",
        )

    if score >= 40:
        return (
            "Selective",
            "Market is mixed. Review only clean early accumulation.",
        )

    if score >= 20:
        return (
            "Defensive",
            "Review early accumulation only. Avoid chasing breakouts.",
        )

    return (
        "Defensive",
        "Review early accumulation only. Avoid chasing breakouts.",
    )


def market_quality_color(score):

    score = safe_number(score)

    if score >= 80:
        return "#22c55e"

    if score >= 60:
        return "#60a5fa"

    if score >= 40:
        return "#facc15"

    if score >= 20:
        return "#fb923c"

    return "#f87171"


def render_market_quality_style():

    st.markdown(
        """
        <style>
        .ra-market-card {
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 10px;
            padding: 12px 14px;
            background: rgba(15, 23, 42, 0.18);
            margin-bottom: 8px;
        }
        .ra-market-name {
            font-size: 0.78rem;
            opacity: 0.72;
            text-transform: uppercase;
        }
        .ra-market-tone {
            font-size: 1.05rem;
            font-weight: 800;
            margin-top: 3px;
        }
        .ra-market-dot {
            color: var(--market-color);
            margin-right: 6px;
        }
        .ra-market-note {
            font-size: 0.84rem;
            opacity: 0.86;
            margin-top: 5px;
            line-height: 1.35;
        }
        .ra-market-meta {
            font-size: 0.72rem;
            opacity: 0.58;
            margin-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_market_quality_cards(df, last_scan):

    quality = load_quality_for_dashboard(
        df,
        last_scan,
    )

    scan_metadata = load_scan_metadata()

    st.subheader("Today's Market")
    render_market_quality_style()

    cards = st.columns(2)

    for index, market in enumerate(("SET", "USA")):
        row = quality[
            quality["Market"].astype(str).str.upper() == market
        ]

        with cards[index]:
            if row.empty:
                st.info(f"No {market} market quality")
                continue

            data = row.iloc[0]
            trend = data.get(
                "Trend",
                "N/A",
            )
            label = data.get(
                "QualityLabel",
                "",
            )
            score = safe_number(
                data.get(
                    "QualityScore",
                    0,
                )
            )
            status = market_status(scan_metadata, market)
            total_stocks = safe_number(data.get("TotalStocks", 0))

            if status == "NOT_REQUESTED":
                tone = "Not Requested"
                recommendation = "This market was not part of the latest completed scan."
                color = "#94a3b8"
            elif status in {"FAILED", "N/A"} and total_stocks == 0:
                tone = "No Data"
                recommendation = "Scan requested but no market data was produced. Check provider, download, or cache."
                color = "#f87171"
            else:
                tone, recommendation = market_quality_recommendation(score)
                color = market_quality_color(score)

            st.markdown(
                f"""
                <div class="ra-market-card" style="--market-color: {color};">
                    <div class="ra-market-name">{market}</div>
                    <div class="ra-market-tone"><span class="ra-market-dot">●</span>{html.escape(tone)}</div>
                    <div class="ra-market-note">{html.escape(recommendation)}</div>
                    <div class="ra-market-meta">Status {html.escape(str(status))}</div>
                    <div class="ra-market-meta">Quality {score:.1f} · {html.escape(str(label))} · Trend {html.escape(str(trend))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("Market Quality Details"):
        display_columns = [
            column
            for column in QUALITY_DISPLAY_COLUMNS
            if column in quality.columns
        ]
        st.dataframe(
            quality[display_columns],
            use_container_width=True,
            hide_index=True,
        )


def render_table(df):

    columns = visible_columns(df)

    header = "".join(
        f"<th>{html.escape(column)}</th>"
        for column in columns
    )

    rows = []

    for _, row in df.iterrows():

        lifecycle_state = str(
            row.get(
                "LifecycleState",
                "",
            )
        ).upper()
        group = row.get(
            "_signal_group",
            "OTHER",
        )
        background = LIFECYCLE_ROW_COLORS.get(
            lifecycle_state,
            ROW_COLORS.get(
                group,
                "#ffffff",
            ),
        )

        cell_style = (
            f"background-color: {background}; "
            "color: #111827 !important; "
            "font-weight: 700; "
            "padding: 9px 12px; "
            "border-top: 1px solid rgba(17, 24, 39, 0.12); "
            "white-space: nowrap;"
        )

        cells = "".join(
            f"<td style='{cell_style}'>{html.escape(str(row[column]))}</td>"
            for column in columns
        )

        rows.append(
            f"<tr style='background-color: {background}; color: #111827;'>"
            f"{cells}</tr>"
        )

    st.markdown(
        """
        <style>
        .ra-table-wrap {
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 6px;
            max-height: 680px;
            overflow: auto;
        }
        .ra-table {
            border-collapse: collapse;
            width: 100%;
            min-width: 760px;
            font-size: 14px;
        }
        .ra-table th {
            background-color: #111827;
            color: #f9fafb;
            font-weight: 700;
            padding: 10px 12px;
            position: sticky;
            top: 0;
            text-align: left;
            z-index: 1;
        }
        .ra-table td {
            border-top: 1px solid rgba(17, 24, 39, 0.12);
            color: #111827;
            font-weight: 650;
            padding: 9px 12px;
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='ra-table-wrap'>"
        "<table class='ra-table'>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>",
        unsafe_allow_html=True,
    )


def opportunity_display_columns(df):

    return [
        column
        for column in OPPORTUNITY_DISPLAY_COLUMNS
        if column in df.columns
    ]


def opportunity_overview_columns(df):

    return [
        column
        for column in OPPORTUNITY_OVERVIEW_COLUMNS
        if column in df.columns
    ]


def format_opportunity_value(value, column):

    if pd.isna(value):
        return ""

    if column in {
        "PriorityRank",
        "OpportunityRank",
        "DaysInState",
    }:
        return f"{int(safe_number(value))}"

    if column in {
        "PriorityScore",
        "OpportunityScore",
        "SeedScore",
        "SeedProbability",
        "FreshnessScore",
        "PatternScore",
        "VCPProbability",
        "BaseQuality",
        "AccumulationScore",
        "ExpansionScore",
        "BottomingSeedScore",
        "DowntrendDecelerationScore",
        "SellingPressureScore",
        "SmallCandleScore",
        "DistanceFromHigh60Pct",
        "NearLow60Pct",
        "EMA9EMA20SpreadPct",
        "PriceAboveLowClose20Pct",
        "Return5DPct",
        "Return10DPct",
        "EMACompressionPct",
        "BaseTightnessPct",
        "HighLowRange10",
        "HighLowRange20",
        "DryVolumeScore",
        "Vol5ToVol20",
        "ATRPercentile60",
        "ATRCompressionScore",
        "Confidence",
        "RSI",
        "RVOL",
        "Price",
        "RiskPct",
        "RewardPct",
        "RR",
    }:
        return f"{safe_number(value):.2f}"

    if column == "StrategyScore":
        return f"{safe_number(value):.0f}"

    if column in {
        "BaseDays",
        "DryVolumeDays",
        "DaysSinceEMA20SlopeTurnPositive",
        "DaysSinceEMA9CrossEMA20",
        "DaysSinceBreakout",
        "BullishCandleStreak",
        "WideRangeBullishCount",
    }:
        return f"{int(safe_number(value))}"

    return str(value)


def render_opportunity_overview_table(opportunities):

    columns = opportunity_overview_columns(opportunities)

    if not columns:
        st.info("No opportunity columns available")
        return

    header = "".join(
        f"<th>{html.escape(column)}</th>"
        for column in columns
    )

    rows = []

    for _, row in opportunities.iterrows():
        action = str(
            row.get(
                "PriorityAction",
                row.get(
                    "RecommendedAction",
                    "",
                ),
            )
        )
        recommended_action = str(
            row.get(
                "RecommendedAction",
                "",
            )
        )
        background = {
            "Review First": "#dcfce7",
            "High Priority": "#e0f2fe",
            "Strong Buy": "#dcfce7",
            "Buy": "#e0f2fe",
            "Watch Closely": "#fef9c3",
            "Watch": "#fef9c3",
            "Early Watch": "#ffedd5",
            "Monitor": "#ffedd5",
            "Low Priority": "#f3f4f6",
            "Ignore": "#f3f4f6",
        }.get(
            action,
            {
                "Strong Buy": "#dcfce7",
                "Buy": "#e0f2fe",
                "Watch Closely": "#fef9c3",
                "Watch": "#fef9c3",
                "Early Watch": "#ffedd5",
                "Ignore": "#f3f4f6",
            }.get(
                recommended_action,
                "#ffffff",
            ),
        )
        cells = "".join(
            "<td>"
            f"{html.escape(format_opportunity_value(row[column], column))}"
            "</td>"
            for column in columns
        )
        rows.append(
            f"<tr style='background-color: {background};'>{cells}</tr>"
        )

    st.markdown(
        """
        <style>
        .opportunity-table-wrap {
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 6px;
            overflow-x: auto;
            margin-top: 0.5rem;
        }
        .opportunity-table {
            border-collapse: collapse;
            width: 100%;
            min-width: 960px;
            font-size: 13px;
        }
        .opportunity-table th {
            background-color: #111827;
            color: #f9fafb;
            font-weight: 700;
            padding: 9px 10px;
            text-align: left;
            white-space: nowrap;
        }
        .opportunity-table td {
            color: #111827;
            font-weight: 650;
            padding: 8px 10px;
            border-top: 1px solid rgba(17, 24, 39, 0.12);
            white-space: nowrap;
        }
        @media print {
            .opportunity-table-wrap {
                overflow: visible;
            }
            .opportunity-table {
                min-width: 0;
                font-size: 10px;
            }
            .opportunity-table th,
            .opportunity-table td {
                padding: 5px 6px;
                white-space: normal;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='opportunity-table-wrap'>"
        "<table class='opportunity-table'>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>",
        unsafe_allow_html=True,
    )


def risk_reward_details(row):

    price = safe_number(
        row.get(
            "Price",
            0,
        )
    )
    stop_loss = first_existing_number(
        row,
        [
            "StopLoss",
            "Stop Loss",
            "SL",
        ],
    )
    target = first_existing_number(
        row,
        [
            "Target",
            "TakeProfit",
            "Take Profit",
            "TP",
        ],
    )
    risk = None
    reward = None

    if price > 0 and stop_loss > 0:
        risk = price - stop_loss

    if price > 0 and target > 0:
        reward = target - price

    return risk, reward


def selected_opportunity_row(opportunities, selected):

    rank = int(
        str(selected)
        .split("|")[0]
        .strip()
        .replace("#", "")
    )
    rank_column = (
        "PriorityRank"
        if "PriorityRank" in opportunities.columns
        else "OpportunityRank"
    )

    return opportunities[
        opportunities[rank_column] == rank
    ].iloc[0]


def market_quality_for_row(row, quality):

    if quality.empty:
        return 0

    market = str(
        row.get(
            "Market",
            "",
        )
    ).upper()
    match = quality[
        quality["Market"].astype(str).str.upper() == market
    ]

    if match.empty:
        return 0

    return safe_number(
        match.iloc[0].get(
            "QualityScore",
            0,
        )
    )


def split_reason_text(value, exclude=None):

    exclude = set(exclude or [])

    return [
        reason.strip()
        for reason in str(value or "").split(";")
        if reason.strip()
        and reason.strip() not in exclude
    ]


def render_reason_block(title, reasons):

    if not reasons:
        return

    st.markdown(f"**{title}**")
    st.markdown(
        "\n".join(
            f"- {reason}"
            for reason in reasons
        )
    )


BUY_CHECKLIST_LABELS = {
    "ema9_above_ema20": "EMA9 อยู่เหนือ EMA20",
    "ema_cross_fresh": (
        f"EMA9 เพิ่งตัดขึ้นภายใน {MAX_FRESH_CROSS_DAYS} วันทำการ"
    ),
    "ema20_rising": "EMA20 กำลังขึ้น",
    "rsi_zone": "RSI อยู่ในโซน",
    "rvol_ready": "RVOL >= 1.5x",
    "breakout_ready": "Breakout / Pivot ยืนยัน",
    "volume_normal": "Volume ไม่ผิดปกติ",
    "risk_passed": "Risk ผ่าน",
}


def row_value(row, *names, default=None):

    for name in names:
        if not hasattr(row, "get"):
            continue

        try:
            if name not in row:
                continue
        except TypeError:
            pass

        value = row.get(name, default)

        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass

        if value is not None:
            return value

    return default


def row_number_or_none(row, *names):

    value = row_value(row, *names, default=None)

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_text(row, *names):

    value = row_value(row, *names, default="")
    return str(value or "").strip()


def row_bool(row, *names):

    value = row_value(row, *names, default=False)

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    return str(value or "").strip().upper() in {
        "TRUE",
        "YES",
        "Y",
        "1",
    }


def combined_decision_text(row):

    fields = [
        "AIReason",
        "AIPositiveFactors",
        "AINegativeFactors",
        "AIBlockers",
        "AISuggestedAction",
        "OpportunityReasons",
        "PriorityReasons",
        "SeedReasons",
        "BottomingReasons",
        "ExpansionReasons",
        "StrategySignal",
        "StrategySetup",
        "Signal",
        "Setup",
        "RecommendedAction",
        "PriorityAction",
        "ChartReaderSummary",
    ]

    return " ".join(
        row_text(row, field)
        for field in fields
        if row_text(row, field)
    ).upper()


def has_any_text(text, terms):

    return any(
        term.upper() in text
        for term in terms
    )


def ema_check_context(row):

    fresh_cross = evaluate_fresh_cross_policy(row)
    ema9 = row_number_or_none(row, "EMA9", "ema9")
    ema20 = row_number_or_none(row, "EMA20", "ema20")
    days_since_cross = fresh_cross.age

    above_field = row_value(row, "EMA9AboveEMA20", default=None)
    if ema9 is not None and ema20 is not None:
        ema9_above_ema20 = ema9 > ema20
        field_used = "EMA9/EMA20"
    elif above_field is not None:
        ema9_above_ema20 = row_bool(row, "EMA9AboveEMA20")
        field_used = "EMA9AboveEMA20"
    else:
        ema9_above_ema20 = False
        field_used = "unavailable"

    ema9_above_ema20 = fresh_cross.ema9_above_ema20

    bullish_cross_today = (
        days_since_cross == 0
        and fresh_cross.ema9_above_ema20
    )

    cross_age_is_valid = (
        days_since_cross is not None
        and days_since_cross >= 0
    )
    cross_within_fresh_days = (
        cross_age_is_valid
        and days_since_cross <= MAX_FRESH_CROSS_DAYS
    )
    is_fresh_ema9_cross = fresh_cross.eligible

    return {
        "LatestPriceDate": fresh_cross.latest_price_date,
        "CrossDate": fresh_cross.cross_date,
        "EMA9": ema9,
        "EMA20": ema20,
        "EMA9AboveEMA20": bool(ema9_above_ema20),
        "EMABullishCrossToday": bool(bullish_cross_today),
        "EMACrossWithinFreshDays": bool(cross_within_fresh_days),
        "IsFreshEMA9Cross": bool(is_fresh_ema9_cross),
        "DaysSinceEMACross": days_since_cross,
        "FreshCrossStatus": fresh_cross.status,
        "FreshCrossStatusLabel": fresh_cross.status_label,
        "FreshCrossReason": fresh_cross.reason,
        "CrossAgeSource": fresh_cross.cross_age_source,
        "BullishCrossEvent": fresh_cross.bullish_cross_event,
        "PreviousEMA9": row_number_or_none(
            row,
            "PreviousEMA9",
            "previous_ema9",
        ),
        "PreviousEMA20": row_number_or_none(
            row,
            "PreviousEMA20",
            "previous_ema20",
        ),
        "RVOL": row_number_or_none(row, "RVOL", "rvol"),
        "ChecklistEMAFieldUsed": field_used,
    }


def checklist_debug_fields(row):

    return ema_check_context(row)


def format_cross_age(value):

    return policy_cross_age_label(value)


def fresh_cross_reason(value):

    return fresh_cross_reason_for_age(value)


def build_buy_checklist(row):

    text = combined_decision_text(row)
    ema_context = ema_check_context(row)

    rsi = row_value(row, "RSI")
    rvol = row_value(row, "RVOL")
    expansion = row_value(row, "ExpansionScore")
    rr = row_value(row, "RR", "RiskRewardRatio")
    risk_pct = row_value(row, "RiskPct", "StopDistancePct")

    ema9_above_ema20 = ema_context["EMA9AboveEMA20"]
    ema_cross_fresh = ema_context["IsFreshEMA9Cross"]

    ema20_rising = (
        row_bool(row, "EMA20Improving")
        or safe_number(row_value(row, "DaysSinceEMA20SlopeTurnPositive")) > 0
        or has_any_text(
            text,
            {
                "EMA20 RISING",
                "EMA20 IMPROVING",
                "EMA20 TURNING UP",
                "EMA20 SLOPE TURNED POSITIVE",
            },
        )
    )

    rsi_zone = (
        45 <= safe_number(rsi) <= 65
        if rsi is not None
        else has_any_text(
            text,
            {
                "HEALTHY RSI",
                "RSI ACCUMULATION",
                "RSI อยู่ในโซน",
            },
        )
    )

    rvol_ready = (
        safe_number(rvol) >= 1.5
        if rvol is not None
        else has_any_text(
            text,
            {
                "HIGH RVOL",
                "RVOL IS EXPANDING",
                "VOLUME EXPANSION",
            },
        )
    )

    breakout_ready = (
        row_bool(row, "PocketPivot")
        or has_any_text(
            text,
            {
                "BREAKOUT",
                "POCKET PIVOT",
                "PIVOT POINT",
                "FIRST IGNITION",
            },
        )
    ) and not has_any_text(
        text,
        {
            "WAIT FOR BREAKOUT",
            "NEED BREAKOUT",
            "NO BREAKOUT",
            "NOT BREAKOUT",
            "ยังไม่ BREAKOUT",
        },
    )

    volume_normal = False
    if expansion is not None:
        volume_normal = safe_number(expansion) <= 60
    elif rvol is not None or text:
        volume_normal = not has_any_text(
            text,
            {
                "VOLUME SPIKE AWAY",
                "EXPANSION RISK",
                "ABNORMAL VOLUME",
            },
        )
    if rvol is not None and safe_number(rvol) > 4:
        volume_normal = False

    if "RiskApproved" in row:
        risk_passed = row_bool(row, "RiskApproved")
    elif has_any_text(
        text,
        {
            "HIGH_RISK",
            "LOW_RR",
            "INVALID_STOP",
            "RISK ยังไม่ผ่าน",
        },
    ):
        risk_passed = False
    elif row_text(row, "AIRiskLevel").upper() == "HIGH":
        risk_passed = False
    elif rr is not None and risk_pct is not None:
        risk_passed = safe_number(rr) >= 1.5 and safe_number(risk_pct) <= 8
    else:
        risk_passed = False

    values = {
        "ema9_above_ema20": bool(ema9_above_ema20),
        "ema_cross_fresh": bool(ema_cross_fresh),
        "ema20_rising": bool(ema20_rising),
        "rsi_zone": bool(rsi_zone),
        "rvol_ready": bool(rvol_ready),
        "breakout_ready": bool(breakout_ready),
        "volume_normal": bool(volume_normal),
        "risk_passed": bool(risk_passed),
    }

    return [
        {
            "key": key,
            "label": label,
            "passed": values[key],
        }
        for key, label in BUY_CHECKLIST_LABELS.items()
    ]


def buy_checklist_summary(items):

    total = len(items)
    passed = sum(
        1
        for item in items
        if item.get("passed")
    )

    return f"ผ่านแล้ว {passed}/{total} เงื่อนไข"


def next_action_priority(row):

    actions = [
        ai_action_key(row_text(row, field))
        for field in [
            "AIDecision",
            "RecommendedAction",
            "PriorityAction",
            "StrategySignal",
            "Signal",
        ]
        if row_text(row, field)
    ]
    text = combined_decision_text(row)

    def has_action(values):
        return any(
            action in values
            for action in actions
        )

    if has_action(
        {
            "EXIT",
            "REDUCE",
        }
    ) or has_any_text(
        text,
        {
            "BELOW_STOP",
            "SETUP_INVALIDATED",
            "EXIT",
        },
    ):
        return "EXIT"

    if has_action(
        {
            "BUY",
            "ADD",
            "STRONG BUY",
            "SEED BUY",
        }
    ):
        return "BUY"

    if has_action(
        {
            "PREPARE",
            "WATCH CLOSELY",
            "EARLY WATCH",
            "SEED WATCH",
        }
    ):
        return "PREPARE"

    return "WATCH"


def next_action_message(row, checklist=None):

    checklist = checklist or build_buy_checklist(row)
    priority = next_action_priority(row)
    ema_context = ema_check_context(row)
    by_key = {
        item["key"]: bool(item["passed"])
        for item in checklist
    }

    if priority == "EXIT":
        if "BELOW_STOP" in combined_decision_text(row):
            return "แนวโน้มเสียแล้ว"
        return "ควรขาย"

    if priority == "BUY" and all(by_key.values()):
        return "ผ่านเงื่อนไข เตรียมประเมิน Entry / Stop / Target"

    if not by_key.get("ema9_above_ema20", False):
        return "รอ EMA9 ตัดขึ้นเหนือ EMA20"

    if not by_key.get("ema_cross_fresh", False):
        days_since_cross = ema_context.get("DaysSinceEMACross")
        if days_since_cross is None:
            return "ยังไม่มีประวัติ EMA9 ตัด EMA20"
        return (
            f"EMA9 Cross เกิน {MAX_FRESH_CROSS_DAYS} วันทำการแล้ว"
        )

    if not by_key.get("rvol_ready", False):
        return "รอ Volume ยืนยัน โดย RVOL >= 1.5x"

    days_since_cross = ema_context.get("DaysSinceEMACross")
    expansion = safe_number(row_value(row, "ExpansionScore", default=0))

    if (
        days_since_cross is not None
        and days_since_cross > MAX_FRESH_CROSS_DAYS
        and expansion <= 60
    ):
        return "รอแท่งยืนยันหรือ breakout พร้อม volume"

    if not by_key.get("breakout_ready", False):
        return "รอแท่งยืนยันหรือ breakout พร้อม volume"

    if not by_key.get("risk_passed", False):
        return "Risk ยังไม่ผ่าน"

    if priority == "BUY":
        return "ผ่านเงื่อนไข เตรียมประเมิน Entry / Stop / Target"

    if priority == "PREPARE":
        return "เตรียมซื้อเมื่อสัญญาณยืนยัน"

    return "เฝ้าดูต่อ"


def next_action_card(row, checklist=None):

    checklist = checklist or build_buy_checklist(row)
    priority = next_action_priority(row)
    return {
        "Priority": priority,
        "Message": next_action_message(row, checklist),
    }


def text_meter(label, value, maximum=100, inverse=False):

    value = safe_number(value)
    maximum = max(
        safe_number(maximum),
        1,
    )
    normalized = max(
        0,
        min(
            1,
            value / maximum,
        ),
    )
    fill_value = 1 - normalized if inverse else normalized
    filled = int(round(fill_value * 10))
    meter = "█" * filled + "░" * (10 - filled)

    return f"{label:<12} {meter} {value:.1f}"


def rr_meter(value):

    value = safe_number(value)
    filled = int(
        max(
            0,
            min(
                5,
                round(value),
            ),
        )
    )
    stars = "★" * filled + "☆" * (5 - filled)

    return f"RR           {stars} {value:.1f}"


def render_visual_meters(row):

    meters = [
        (
            "Confidence",
            meter_blocks(row.get("Confidence", 0)),
            f"{safe_number(row.get('Confidence', 0)):.0f}",
        ),
        (
            "Seed Quality",
            meter_blocks(row.get("SeedScore", 0)),
            f"{safe_number(row.get('SeedScore', 0)):.0f}",
        ),
        (
            "Freshness",
            meter_blocks(row.get("FreshnessScore", 0)),
            f"{safe_number(row.get('FreshnessScore', 0)):.0f}",
        ),
        (
            "Expansion",
            meter_blocks(
                row.get("ExpansionScore", 0),
                inverse=True,
            ),
            f"{safe_number(row.get('ExpansionScore', 0)):.0f}",
        ),
        (
            "RR",
            rr_meter(row.get("RR", 0)).split(" ", 1)[1].strip(),
            f"{safe_number(row.get('RR', 0)):.1f}",
        ),
    ]
    cards = "".join(
        f"""
        <div class="ra-meter-card">
            <div class="ra-meter-label">{html.escape(label)}</div>
            <div class="ra-meter-bar">{html.escape(bar)}</div>
            <div class="ra-meter-value">{html.escape(value)}</div>
        </div>
        """
        for label, bar, value in meters
    )
    st.markdown(
        f"""
        <style>
        .ra-meter-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 8px;
            margin: 0.35rem 0 0.85rem 0;
        }}
        .ra-meter-card {{
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 8px;
            padding: 8px 10px;
            background: rgba(15, 23, 42, 0.18);
        }}
        .ra-meter-label {{
            font-size: 0.72rem;
            opacity: 0.70;
        }}
        .ra-meter-bar {{
            font-family: Consolas, monospace;
            font-size: 0.88rem;
            margin-top: 3px;
        }}
        .ra-meter-value {{
            font-size: 0.78rem;
            opacity: 0.86;
            margin-top: 2px;
        }}
        </style>
        <div class="ra-meter-grid">{cards}</div>
        """,
        unsafe_allow_html=True,
    )


def render_buy_checklist(row):

    checklist = build_buy_checklist(row)
    passed = [
        item
        for item in checklist
        if item.get("passed")
    ]
    failed = [
        item
        for item in checklist
        if not item.get("passed")
    ]
    priority = next_action_priority(row)
    title = "🟡 ทำไมยังไม่ซื้อ?"

    if priority == "BUY":
        title = "🟢 เช็กลิสต์ก่อนซื้อ"
    elif priority == "EXIT":
        title = "🔴 เหตุผลที่ต้องระวัง"

    st.markdown(f"**{title}**")

    if failed:
        for item in failed:
            st.error(f"❌ {item['label']}")

    if passed:
        with st.expander("เงื่อนไขที่ผ่านแล้ว", expanded=False):
            for item in passed:
                st.success(f"✅ {item['label']}")

    st.caption(buy_checklist_summary(checklist))
    return checklist


def render_next_action(row, checklist=None):

    action = next_action_card(
        row,
        checklist,
    )
    priority = action["Priority"]
    message = action["Message"]
    body = f"**{priority}**\n\n{message}"

    st.markdown("**Next Action**")

    if priority == "BUY":
        st.success(body)
    elif priority == "PREPARE":
        st.warning(body)
    elif priority == "EXIT":
        st.error(body)
    else:
        st.info(body)


def render_opinion_and_next_step(row):

    st.markdown("**AI Opinion**")
    st.info(ai_opinion_from_metrics(row))
    checklist = render_buy_checklist(row)
    render_next_action(row, checklist)


def render_opportunity_details_legacy(row, market_quality_score):

    st.subheader(f"{row['Symbol']} Opportunity Details")

    cols = st.columns(4)
    cols[0].metric(
        "Decision Score",
        f"{safe_number(row.get('StrategyScore', row.get('Score', 0))):.0f}",
    )
    cols[1].metric(
        "Opportunity Score",
        f"{safe_number(row.get('OpportunityScore', 0)):.2f}",
    )
    cols[2].metric(
        "Priority Score",
        f"{safe_number(row.get('PriorityScore', 0)):.2f}",
    )
    cols[3].metric(
        "Priority Rank",
        int(safe_number(row.get("PriorityRank", 0))),
    )

    cols = st.columns(4)
    cols[0].metric(
        "Seed Score",
        f"{safe_number(row.get('SeedScore', 0)):.2f}",
    )
    cols[1].metric(
        "Seed Probability",
        f"{safe_number(row.get('SeedProbability', 0)):.2f}",
    )
    cols[2].metric(
        "Freshness",
        f"{safe_number(row.get('FreshnessScore', 0)):.2f}",
    )
    cols[3].metric(
        "Base Days",
        int(safe_number(row.get("BaseDays", 0))),
    )

    cols = st.columns(4)
    cols[0].metric(
        "Pattern",
        str(row.get("PatternName", "")),
    )
    cols[1].metric(
        "Pattern Score",
        f"{safe_number(row.get('PatternScore', 0)):.2f}",
    )
    cols[2].metric(
        "VCP Probability",
        f"{safe_number(row.get('VCPProbability', 0)):.2f}",
    )
    cols[3].metric(
        "Base Quality",
        f"{safe_number(row.get('BaseQuality', 0)):.2f}",
    )

    cols = st.columns(4)
    cols[0].metric(
        "Accumulation",
        f"{safe_number(row.get('AccumulationScore', 0)):.2f}",
    )
    cols[1].metric(
        "Dry Volume Days",
        int(safe_number(row.get("DryVolumeDays", 0))),
    )
    cols[2].metric(
        "EMA Compression %",
        f"{safe_number(row.get('EMACompressionPct', 0)):.2f}",
    )
    cols[3].metric(
        "ATR Percentile 60",
        f"{safe_number(row.get('ATRPercentile60', 0)):.2f}",
    )

    cols = st.columns(4)
    cols[0].metric(
        "Bottoming Seed",
        f"{safe_number(row.get('BottomingSeedScore', 0)):.2f}",
    )
    cols[1].metric(
        "Downtrend Decel",
        f"{safe_number(row.get('DowntrendDecelerationScore', 0)):.2f}",
    )
    cols[2].metric(
        "Selling Pressure",
        f"{safe_number(row.get('SellingPressureScore', 0)):.2f}",
    )
    cols[3].metric(
        "Small Candles",
        f"{safe_number(row.get('SmallCandleScore', 0)):.2f}",
    )

    cols = st.columns(4)
    cols[0].metric(
        "Expansion Score",
        f"{safe_number(row.get('ExpansionScore', 0)):.2f}",
    )
    cols[1].metric(
        "20-Bar Low Expansion",
        f"{safe_number(row.get('PriceAboveLowClose20Pct', 0)):.2f}%",
    )
    cols[2].metric(
        "5D Return",
        f"{safe_number(row.get('Return5DPct', 0)):.2f}%",
    )
    cols[3].metric(
        "10D Return",
        f"{safe_number(row.get('Return10DPct', 0)):.2f}%",
    )

    cols = st.columns(4)
    cols[0].metric(
        "Lifecycle",
        str(row.get("LifecycleState", "UNKNOWN")),
    )
    cols[1].metric(
        "Days in State",
        int(safe_number(row.get("DaysInState", 0))),
    )
    cols[2].metric(
        "Priority Mode",
        str(row.get("PriorityMode", "")),
    )
    cols[3].metric(
        "Priority Action",
        str(row.get("PriorityAction", "")),
    )

    cols = st.columns(4)
    cols[0].metric(
        "Market Quality",
        f"{market_quality_score:.2f}",
    )
    cols[1].metric(
        "Risk %",
        f"{safe_number(row.get('RiskPct', 0)):.2f}",
    )
    cols[2].metric(
        "Reward %",
        f"{safe_number(row.get('RewardPct', 0)):.2f}",
    )
    cols[3].metric(
        "RR",
        f"{safe_number(row.get('RR', 0)):.2f}",
    )

    cols = st.columns(4)
    cols[0].metric(
        "Confidence",
        f"{safe_number(row.get('Confidence', 0)):.1f}",
    )
    cols[1].metric(
        "Recommended Action",
        str(row.get("RecommendedAction", "")),
    )
    cols[2].metric(
        "Strategy Signal",
        str(row.get("StrategySignal", row.get("Signal", ""))),
    )
    cols[3].metric(
        "Strategy Setup",
        str(row.get("StrategySetup", row.get("Setup", ""))),
    )

    priority_reasons = [
        reason.strip()
        for reason in str(
            row.get(
                "PriorityReasons",
                "",
            )
        ).split(";")
        if reason.strip()
    ]

    if priority_reasons:
        st.markdown("**Priority Reasons**")
        st.markdown(
            "\n".join(
                f"- {reason}"
                for reason in priority_reasons
            )
        )

    ai_reason = str(
        row.get(
            "AIRecommendationReason",
            "",
        )
    ).strip()

    if ai_reason:
        st.info(ai_reason)

    seed_reasons = [
        reason.strip()
        for reason in str(
            row.get(
                "SeedReasons",
                "",
            )
        ).split(";")
        if reason.strip()
    ]

    if seed_reasons:
        st.markdown("**Seed Reasons**")
        st.markdown(
            "\n".join(
                f"- {reason}"
                for reason in seed_reasons
            )
        )

    chart_summary = str(
        row.get(
            "ChartReaderSummary",
            "",
        )
    ).strip()

    if chart_summary:
        st.markdown("**Chart Reader Summary**")
        st.info(chart_summary)

    bottoming_reasons = [
        reason.strip()
        for reason in str(
            row.get(
                "BottomingReasons",
                "",
            )
        ).split(";")
        if reason.strip()
        and reason.strip() != "Bottoming profile not confirmed"
    ]

    if bottoming_reasons:
        st.markdown("**Bottoming / Reversal Evidence**")
        st.markdown(
            "\n".join(
                f"- {reason}"
                for reason in bottoming_reasons
            )
        )

    expansion_reasons = [
        reason.strip()
        for reason in str(
            row.get(
                "ExpansionReasons",
                "",
            )
        ).split(";")
        if reason.strip()
        and reason.strip() != "Expansion still quiet"
    ]

    if expansion_reasons:
        st.markdown("**Expansion Penalties**")
        st.markdown(
            "\n".join(
                f"- {reason}"
                for reason in expansion_reasons
            )
        )

    reasons = [
        reason.strip()
        for reason in str(
            row.get(
                "OpportunityReasons",
                "",
            )
        ).split(";")
        if reason.strip()
    ]

    if reasons:
        st.markdown("**Opportunity Reasons**")
        st.markdown(
            "\n".join(
                f"- {reason}"
                for reason in reasons
            )
        )


def render_opportunity_details(row, market_quality_score):

    symbol = str(row.get("Symbol", ""))
    st.subheader(f"{symbol} Opportunity Details")

    overview, thesis, risk_tab, indicators, debug = st.tabs(
        [
            "Overview",
            "Seed Thesis",
            "Risk / Reward",
            "Indicators",
            "Debug",
        ]
    )

    with overview:
        cols = st.columns(4)
        cols[0].metric(
            "Symbol",
            symbol,
        )
        cols[1].metric(
            "Action",
            str(row.get("RecommendedAction", "")),
        )
        cols[2].metric(
            "SeedScore",
            f"{safe_number(row.get('SeedScore', 0)):.1f}",
        )
        cols[3].metric(
            "PriorityScore",
            f"{safe_number(row.get('PriorityScore', 0)):.1f}",
        )

        cols = st.columns(4)
        cols[0].metric(
            "Confidence",
            f"{safe_number(row.get('Confidence', 0)):.1f}",
        )
        cols[1].metric(
            "Pattern",
            str(row.get("PatternName", "")),
        )
        cols[2].metric(
            "Lifecycle",
            str(row.get("LifecycleState", "UNKNOWN")),
        )
        cols[3].metric(
            "RR",
            f"{safe_number(row.get('RR', 0)):.2f}",
        )

        cols = st.columns(2)
        cols[0].metric(
            "ExpansionScore",
            f"{safe_number(row.get('ExpansionScore', 0)):.1f}",
        )
        cols[1].metric(
            "Strategy Setup",
            str(row.get("StrategySetup", row.get("Setup", ""))),
        )
        render_visual_meters(row)
        render_opinion_and_next_step(row)
        render_seed_timeline(row)

    with thesis:
        chart_summary = str(
            row.get(
                "ChartReaderSummary",
                "",
            )
        ).strip()

        if chart_summary:
            st.info(chart_summary)

        render_reason_block(
            "Seed Reasons",
            split_reason_text(row.get("SeedReasons", "")),
        )
        render_reason_block(
            "Bottoming / Reversal Evidence",
            split_reason_text(
                row.get("BottomingReasons", ""),
                exclude={"Bottoming profile not confirmed"},
            ),
        )
        render_reason_block(
            "Opportunity Reasons",
            split_reason_text(row.get("OpportunityReasons", "")),
        )
        render_reason_block(
            "Priority Reasons",
            split_reason_text(row.get("PriorityReasons", "")),
        )

    with risk_tab:
        stop_loss = first_existing_number(
            row,
            [
                "StopLoss",
                "Stop Loss",
                "SL",
            ],
        )
        target = first_existing_number(
            row,
            [
                "Target",
                "TakeProfit",
                "Take Profit",
                "TP",
            ],
        )
        cols = st.columns(4)
        cols[0].metric(
            "RiskPct",
            f"{safe_number(row.get('RiskPct', 0)):.2f}%",
        )
        cols[1].metric(
            "RewardPct",
            f"{safe_number(row.get('RewardPct', 0)):.2f}%",
        )
        cols[2].metric(
            "RR",
            f"{safe_number(row.get('RR', 0)):.2f}",
        )
        cols[3].metric(
            "Market Quality",
            f"{market_quality_score:.1f}",
        )

        cols = st.columns(2)
        cols[0].metric(
            "Stop Loss",
            f"{stop_loss:.2f}" if stop_loss else "N/A",
        )
        cols[1].metric(
            "Target",
            f"{target:.2f}" if target else "N/A",
        )

        if market_quality_score < 40:
            st.warning("Market quality is weak. Use selective sizing.")
        elif market_quality_score < 60:
            st.info("Market quality is mixed. Confirm liquidity and risk.")

        render_reason_block(
            "Expansion Penalties",
            split_reason_text(
                row.get("ExpansionReasons", ""),
                exclude={"Expansion still quiet"},
            ),
        )

    with indicators:
        ema_debug = checklist_debug_fields(row)
        cols = st.columns(4)
        cols[0].metric(
            "RSI",
            f"{safe_number(row.get('RSI', 0)):.1f}",
        )
        cols[1].metric(
            "RVOL",
            f"{safe_number(row.get('RVOL', 0)):.2f}",
        )
        cols[2].metric(
            "EMA Compression",
            f"{safe_number(row.get('EMACompressionPct', 0)):.2f}%",
        )
        cols[3].metric(
            "ATR Percentile 60",
            f"{safe_number(row.get('ATRPercentile60', 0)):.1f}",
        )

        cols = st.columns(3)
        cols[0].metric(
            "Dry Volume Days",
            int(safe_number(row.get("DryVolumeDays", 0))),
        )
        cols[1].metric(
            "Base Days",
            int(safe_number(row.get("BaseDays", 0))),
        )
        cols[2].metric(
            "FreshnessScore",
            f"{safe_number(row.get('FreshnessScore', 0)):.1f}",
        )

        cols = st.columns(5)
        cols[0].metric(
            "Latest Price Date",
            ema_debug.get("LatestPriceDate") or "N/A",
        )
        cols[1].metric(
            "Cross Date",
            ema_debug.get("CrossDate") or "N/A",
        )
        cols[2].metric(
            "EMA9",
            f"{safe_number(ema_debug.get('EMA9')):.4f}",
        )
        cols[3].metric(
            "EMA20",
            f"{safe_number(ema_debug.get('EMA20')):.4f}",
        )
        cols[4].metric(
            "EMA9 > EMA20",
            "Yes" if ema_debug.get("EMA9AboveEMA20") else "No",
        )

        cols = st.columns(4)
        cols[0].metric(
            "Cross Today",
            "Yes" if ema_debug.get("EMABullishCrossToday") else "No",
        )
        cols[1].metric(
            f"Fresh <= {MAX_FRESH_CROSS_DAYS}D",
            "Yes" if ema_debug.get("IsFreshEMA9Cross") else "No",
        )
        days_since_cross = ema_debug.get("DaysSinceEMACross")
        cols[2].metric(
            "Days Since Cross",
            (
                f"{days_since_cross:.0f}"
                if days_since_cross is not None
                else "N/A"
            ),
        )
        cols[3].metric(
            "Cross Age Source",
            ema_debug.get("CrossAgeSource", "N/A"),
        )

    with debug:
        debug_row = dict(row)
        debug_row.update(checklist_debug_fields(row))
        debug_data = pd.DataFrame(
            [
                {
                    "Field": key,
                    "Value": str(value),
                }
                for key, value in debug_row.items()
            ]
        )
        st.dataframe(
            debug_data,
            use_container_width=True,
            hide_index=True,
        )


def opportunity_reason_summary(row):

    reasons = [
        reason.strip()
        for reason in str(
            row.get(
                "PriorityReasons",
                "",
            )
        ).split(";")
        if reason.strip()
    ]

    if not reasons:
        reasons = [
            reason.strip()
            for reason in str(
                row.get(
                    "OpportunityReasons",
                    "",
                )
            ).split(";")
            if reason.strip()
        ]

    if not reasons:
        return ""

    priority_terms = [
        "Seed",
        "Early",
        "Breakout",
        "Momentum",
        "Penalty",
        "EMA20",
        "RVOL",
        "RR",
        "RSI",
        "Previous lifecycle",
        "Setup",
        "Market Quality",
    ]
    ranked = []

    for reason in reasons:
        priority = next(
            (
                index
                for index, term in enumerate(priority_terms)
                if term.upper() in reason.upper()
            ),
            len(priority_terms),
        )
        ranked.append(
            (
                priority,
                reason,
            )
        )

    ranked = sorted(
        ranked,
        key=lambda item: item[0],
    )

    return "; ".join(
        reason
        for _, reason in ranked[:2]
    )


def seed_reason_line(row):

    base_days = int(safe_number(row.get("BaseDays", 0)))
    dry_days = int(safe_number(row.get("DryVolumeDays", 0)))
    ema_compression = safe_number(row.get("EMACompressionPct", 0))

    parts = []

    if base_days > 0:
        parts.append(f"Base {base_days}d")

    if dry_days > 0:
        parts.append(f"Dry {dry_days}d")

    if ema_compression > 0:
        parts.append(f"EMA {ema_compression:.1f}%")

    if not parts:
        summary = opportunity_reason_summary(row)
        return summary or "Seed profile is still forming"

    return " · ".join(parts)


def seed_action_label(row):

    action = str(row.get("RecommendedAction", "")).strip()

    return action or "WATCH"


def seed_accent(row):

    signal = str(row.get("StrategySignal", "")).upper()
    action = str(row.get("RecommendedAction", "")).upper()
    lifecycle = str(row.get("LifecycleState", "")).upper()

    if "SEED BUY" in signal or action in {
        "STRONG BUY",
        "BUY",
    }:
        return "#22c55e", "rgba(34, 197, 94, 0.10)"

    if "MOMENTUM" in signal or lifecycle == "MOMENTUM":
        return "#fb923c", "rgba(251, 146, 60, 0.10)"

    if "EXTENDED" in signal or lifecycle == "EXTENDED":
        return "#f87171", "rgba(248, 113, 113, 0.10)"

    if action == "IGNORE":
        return "#94a3b8", "rgba(148, 163, 184, 0.08)"

    return "#60a5fa", "rgba(96, 165, 250, 0.10)"


def valid_seed_opportunities(opportunities, market=None):

    if opportunities.empty:
        return opportunities.copy()

    data = canonical_fresh_cross_candidates(opportunities)

    for column in [
        "Market",
        "LifecycleState",
        "StrategySignal",
        "RecommendedAction",
    ]:
        if column not in data.columns:
            data[column] = ""

    rank_column = (
        "PriorityRank"
        if "PriorityRank" in data.columns
        else "OpportunityRank"
        if "OpportunityRank" in data.columns
        else None
    )
    score_column = (
        "PriorityScore"
        if "PriorityScore" in data.columns
        else "OpportunityScore"
        if "OpportunityScore" in data.columns
        else "SeedScore"
    )
    lifecycle = data["LifecycleState"].astype(str).str.upper()
    signal = data["StrategySignal"].astype(str).str.upper()
    action = data["RecommendedAction"].astype(str).str.upper()
    mask = (
        data["FreshCrossEligible"]
        & (lifecycle == "SEED")
        & ~signal.str.contains(
            "MOMENTUM|EXTENDED|SKIP",
            regex=True,
            na=False,
        )
        & (action != "IGNORE")
    )

    if market:
        mask = mask & (
            data["Market"].astype(str).str.upper()
            == str(market).upper()
        )

    valid = data[mask].copy()

    if valid.empty:
        return valid

    if rank_column:
        valid["_seed_rank_sort"] = pd.to_numeric(
            valid[rank_column],
            errors="coerce",
        ).fillna(999999)
    else:
        valid["_seed_rank_sort"] = 999999

    valid["_seed_score_sort"] = pd.to_numeric(
        valid[score_column],
        errors="coerce",
    ).fillna(0)

    return valid.sort_values(
        [
            "_seed_rank_sort",
            "_seed_score_sort",
        ],
        ascending=[
            True,
            False,
        ],
    )


def top_seed_opportunities(opportunities, market, limit=5):

    return valid_seed_opportunities(
        opportunities,
        market=market,
    ).head(limit)


def seed_badges(row):

    badges = []
    pattern = str(row.get("PatternName", "")).strip()
    setup = str(row.get("StrategySetup", "")).strip()
    lifecycle = str(row.get("LifecycleState", "")).strip()

    for value in [
        pattern,
        "Bottoming" if "BOTTOM" in setup.upper() else "",
        lifecycle.title() if lifecycle else "Seed",
    ]:
        if value and value not in badges:
            badges.append(value)

    return badges[:3]


def compact_symbol_title(row):

    rank = int(
        safe_number(
            row.get(
                "PriorityRank",
                row.get("OpportunityRank", 0),
            )
        )
    )

    if rank > 0:
        return f"#{rank} {row.get('Symbol', '')}"

    return str(row.get("Symbol", ""))


def render_seed_card(row):

    accent, background = seed_accent(row)
    symbol = html.escape(str(row.get("Symbol", "")))
    action = html.escape(seed_action_label(row))
    seed_score = safe_number(row.get("SeedScore", 0))
    fresh = safe_number(row.get("FreshnessScore", 0))
    expansion = safe_number(row.get("ExpansionScore", 0))
    risk = safe_number(row.get("RiskPct", 0))
    reason = html.escape(seed_reason_line(row))
    badges = "".join(
        f"<span>{html.escape(str(badge))}</span>"
        for badge in seed_badges(row)
    )

    st.markdown(
        f"""
        <div class="ra-seed-card" style="--seed-accent: {accent}; --seed-bg: {background};">
            <div class="ra-seed-top">
                <span class="ra-seed-symbol">{symbol}</span>
                <span class="ra-seed-action">{action}</span>
                <span class="ra-seed-score">Seed {seed_score:.0f}</span>
            </div>
            <div class="ra-seed-badges">{badges}</div>
            <div class="ra-seed-chips">
                <span>Fresh {fresh:.0f}</span>
                <span>Exp {expansion:.0f}</span>
                <span>Risk {risk:.1f}%</span>
            </div>
            <div class="ra-seed-reason">{reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_seed_market_section(seed_opportunities, market):

    st.markdown(f"**🌱 Top 5 {market} Seed**")

    rows = top_seed_opportunities(
        seed_opportunities,
        market,
        limit=5,
    )

    if rows.empty:
        st.info("No valid SEED opportunities for this market.")
        return rows

    for _, row in rows.iterrows():
        render_seed_card(row)

    return rows


def render_seed_detail_table(seed_rows):

    if seed_rows.empty:
        return

    detail = seed_rows.copy()
    rank_source = (
        "PriorityRank"
        if "PriorityRank" in detail.columns
        else "OpportunityRank"
        if "OpportunityRank" in detail.columns
        else None
    )

    if rank_source:
        detail["Rank"] = detail[rank_source]
    else:
        detail["Rank"] = range(
            1,
            len(detail) + 1,
        )

    columns = [
        column
        for column in SEED_DETAIL_COLUMNS
        if column in detail.columns
    ]

    if not columns:
        return

    with st.expander("Detailed Seed Table", expanded=False):
        st.dataframe(
            detail[columns],
            use_container_width=True,
            hide_index=True,
        )


def pattern_distribution(seed_rows):

    if seed_rows.empty or "PatternName" not in seed_rows.columns:
        return {
            "VCP": 0,
            "Flat Base": 0,
            "Ascending Base": 0,
            "Other": 0,
        }

    patterns = seed_rows["PatternName"].fillna("").astype(str).str.upper()
    vcp = int(patterns.str.contains("VCP", regex=False).sum())
    flat = int(patterns.str.contains("FLAT BASE", regex=False).sum())
    ascending = int(
        patterns.str.contains("ASCENDING BASE", regex=False).sum()
    )
    other = max(
        0,
        len(seed_rows) - vcp - flat - ascending,
    )

    return {
        "VCP": vcp,
        "Flat Base": flat,
        "Ascending Base": ascending,
        "Other": other,
    }


def ai_opinion_from_metrics(row):

    lifecycle = str(row.get("LifecycleState", "")).upper()
    expansion = safe_number(row.get("ExpansionScore", 0))
    seed = safe_number(row.get("SeedScore", 0))
    fresh = safe_number(row.get("FreshnessScore", 0))
    rvol = safe_number(row.get("RVOL", 0))

    if lifecycle in {
        "MOMENTUM",
        "EXTENDED",
    } or expansion >= 70:
        return "This stock is becoming extended. Wait for another base."

    if seed >= 75 and fresh >= 75 and expansion <= 25:
        return "This stock is still inside institutional accumulation. Momentum has not started yet."

    if seed >= 70 and rvol < 1:
        return "The base is forming, but volume has not confirmed accumulation yet."

    if seed >= 70 and expansion <= 40:
        return "This setup is early, but still needs confirmation before expansion."

    return "This setup needs more evidence before it becomes a priority."


def meter_blocks(value, maximum=100, inverse=False):

    value = safe_number(value)
    maximum = max(
        safe_number(maximum),
        1,
    )
    ratio = max(
        0,
        min(
            1,
            value / maximum,
        ),
    )
    fill_ratio = 1 - ratio if inverse else ratio
    filled = int(round(fill_ratio * 10))

    return "█" * filled + "░" * (10 - filled)


def timeline_level(row, stage):

    lifecycle = str(row.get("LifecycleState", "")).upper()
    expansion = safe_number(row.get("ExpansionScore", 0))
    seed = safe_number(row.get("SeedScore", 0))
    fresh = safe_number(row.get("FreshnessScore", 0))

    if stage == "Sleeping":
        return max(
            0,
            10 - int(min(seed, 100) / 12),
        )

    if stage == "Accumulating":
        return int(min(max(seed, 0), 100) / 10)

    if stage == "Ignition":
        return int(min(max(fresh, 0), 100) / 25)

    if stage == "Breakout":
        return 8 if lifecycle == "BREAKOUT" else int(min(expansion, 100) / 18)

    if stage == "Momentum":
        return 9 if lifecycle in {"MOMENTUM", "EXTENDED"} else int(min(expansion, 100) / 20)

    return 0


def render_seed_timeline(row):

    st.markdown("**Seed Timeline**")
    lines = []

    for stage in [
        "Sleeping",
        "Accumulating",
        "Ignition",
        "Breakout",
        "Momentum",
    ]:
        level = max(
            0,
            min(
                10,
                timeline_level(row, stage),
            ),
        )
        lines.append(
            f"{stage:<13} {'■' * level}{'□' * (10 - level)}"
        )

    st.code("\n".join(lines))


def render_ai_pick_today(seed_opportunities, quality):

    valid = valid_seed_opportunities(seed_opportunities)

    st.markdown(
        """
        <style>
        .ra-ai-pick {
            border: 1px solid rgba(96, 165, 250, 0.26);
            border-left: 5px solid #60a5fa;
            border-radius: 12px;
            padding: 16px 18px;
            background: linear-gradient(135deg, rgba(96, 165, 250, 0.14), rgba(15, 23, 42, 0.18));
            margin: 0.2rem 0 1rem 0;
        }
        .ra-ai-pick-label {
            font-size: 0.74rem;
            opacity: 0.72;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .ra-ai-pick-main {
            display: flex;
            align-items: baseline;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 6px;
        }
        .ra-ai-pick-symbol {
            font-size: 1.55rem;
            font-weight: 800;
        }
        .ra-ai-pick-action {
            color: #60a5fa;
            font-size: 0.85rem;
            font-weight: 800;
            text-transform: uppercase;
        }
        .ra-ai-pick-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 10px;
        }
        .ra-ai-pick-meta span {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 0.76rem;
            opacity: 0.9;
        }
        .ra-ai-pick-why {
            margin-top: 12px;
            font-size: 0.82rem;
            opacity: 0.78;
        }
        .ra-ai-pick-why ul {
            margin: 6px 0 0 1rem;
            padding: 0;
        }
        .ra-ai-opinion {
            margin-top: 10px;
            font-size: 0.82rem;
            opacity: 0.88;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if valid.empty:
        market_note = ""

        if quality is not None and not quality.empty:
            avg_quality = safe_number(quality["QualityScore"].mean())
            market_note = f" Market quality score: {avg_quality:.1f}."

        st.info(
            "No high-quality Seed candidate today. "
            f"Market quality is weak.{market_note}"
        )
        return None

    row = valid.iloc[0]
    symbol = html.escape(str(row.get("Symbol", "")))
    action = html.escape(seed_action_label(row))
    seed_score = safe_number(row.get("SeedScore", 0))
    pattern = html.escape(str(row.get("PatternName", "") or "Seed"))
    confidence = safe_number(row.get("Confidence", 0))
    fresh = safe_number(row.get("FreshnessScore", 0))
    expansion = safe_number(row.get("ExpansionScore", 0))
    rr = safe_number(row.get("RR", 0))
    setup = str(row.get("StrategySetup", "Seed")).strip() or "Seed"
    reason_parts = [
        setup,
        "Dry volume"
        if safe_number(row.get("DryVolumeDays", 0)) > 0
        else "",
        f"Base {int(safe_number(row.get('BaseDays', 0)))} days"
        if safe_number(row.get("BaseDays", 0)) > 0
        else "",
        "EMA compression"
        if safe_number(row.get("EMACompressionPct", 0)) > 0
        else "",
        "Expansion still very low"
        if expansion <= 25
        else "Expansion risk rising",
    ]
    reason_items = "".join(
        f"<li>{html.escape(reason)}</li>"
        for reason in reason_parts
        if reason
    )
    opinion = html.escape(ai_opinion_from_metrics(row))

    st.markdown(
        f"""
        <div class="ra-ai-pick">
            <div class="ra-ai-pick-label">AI Pick Today</div>
            <div class="ra-ai-pick-main">
                <span class="ra-ai-pick-symbol">{symbol}</span>
                <span class="ra-ai-pick-action">{action}</span>
            </div>
            <div class="ra-ai-pick-meta">
                <span>Seed {seed_score:.0f}</span>
                <span>Pattern {pattern}</span>
                <span>Confidence {confidence:.0f}%</span>
                <span>Freshness {fresh:.0f}%</span>
                <span>RR {rr:.1f}</span>
            </div>
            <div class="ra-ai-pick-why"><strong>Why this stock?</strong><ul>{reason_items}</ul></div>
            <div class="ra-ai-opinion">{opinion}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return row


def render_seed_summary_cards(seed_opportunities):

    valid = valid_seed_opportunities(seed_opportunities)
    best = valid.iloc[0] if not valid.empty else None
    pattern_counts = pattern_distribution(valid)
    seed_buy = int(
        (
            valid["StrategySignal"]
            .astype(str)
            .str.upper()
            == "SEED BUY"
        ).sum()
    ) if not valid.empty and "StrategySignal" in valid.columns else 0
    seed_watch = int(
        (
            valid["StrategySignal"]
            .astype(str)
            .str.upper()
            == "SEED WATCH"
        ).sum()
    ) if not valid.empty and "StrategySignal" in valid.columns else 0

    st.subheader("Seed Summary")
    cols = st.columns(4)
    cols[0].metric(
        "Best Seed Today",
        str(best.get("Symbol", "N/A")) if best is not None else "N/A",
    )
    cols[1].metric(
        "Best Pattern",
        str(best.get("PatternName", "N/A")) if best is not None else "N/A",
    )
    cols[2].metric("SEED BUY", seed_buy)
    cols[3].metric("SEED WATCH", seed_watch)

    cols = st.columns(4)
    cols[0].metric(
        "Avg SeedScore",
        f"{safe_number(valid['SeedScore'].mean()):.1f}"
        if not valid.empty and "SeedScore" in valid.columns
        else "0.0",
    )
    cols[1].metric(
        "Avg Freshness",
        f"{safe_number(valid['FreshnessScore'].mean()):.1f}"
        if not valid.empty and "FreshnessScore" in valid.columns
        else "0.0",
    )
    cols[2].metric(
        "Avg Expansion",
        f"{safe_number(valid['ExpansionScore'].mean()):.1f}"
        if not valid.empty and "ExpansionScore" in valid.columns
        else "0.0",
    )
    cols[3].metric(
        "Avg Base Days",
        f"{safe_number(valid['BaseDays'].mean()):.0f}"
        if not valid.empty and "BaseDays" in valid.columns
        else "0",
    )

    cols = st.columns(4)
    cols[0].metric("VCP", pattern_counts["VCP"])
    cols[1].metric("Flat Base", pattern_counts["Flat Base"])
    cols[2].metric("Ascending Base", pattern_counts["Ascending Base"])
    cols[3].metric("Other", pattern_counts["Other"])


def render_opportunity_or_seed_summary(opportunities, seed_opportunities):

    mode = current_strategy_mode(opportunities)

    if "PURE EARLY" in mode.upper():
        render_seed_summary_cards(seed_opportunities)
        return

    render_opportunity_summary_cards(opportunities)


def render_top_seed_sections(opportunities):

    st.markdown(
        """
        <style>
        .ra-seed-card {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-left: 3px solid var(--seed-accent);
            border-radius: 8px;
            background: var(--seed-bg);
            padding: 8px 10px;
            margin: 0 0 7px 0;
        }
        .ra-seed-top {
            display: flex;
            align-items: center;
            gap: 6px;
            justify-content: space-between;
            line-height: 1.05;
        }
        .ra-seed-symbol {
            font-weight: 750;
            font-size: 0.92rem;
        }
        .ra-seed-action {
            color: var(--seed-accent);
            font-size: 0.68rem;
            font-weight: 750;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .ra-seed-score {
            font-size: 0.76rem;
            font-weight: 700;
            opacity: 0.92;
            white-space: nowrap;
        }
        .ra-seed-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 5px;
        }
        .ra-seed-badges span {
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 999px;
            padding: 1px 6px;
            font-size: 0.66rem;
            opacity: 0.92;
        }
        .ra-seed-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 5px;
        }
        .ra-seed-chips span {
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 999px;
            padding: 1px 6px;
            font-size: 0.66rem;
            opacity: 0.94;
        }
        .ra-seed-secondary span {
            opacity: 0.72;
        }
        .ra-seed-reason {
            margin-top: 5px;
            font-size: 0.70rem;
            opacity: 0.70;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Top 5 Seed Opportunities")
    cols = st.columns(2)

    with cols[0]:
        set_rows = render_seed_market_section(
            opportunities,
            "SET",
        )

    with cols[1]:
        usa_rows = render_seed_market_section(
            opportunities,
            "USA",
        )

    seed_rows = pd.concat(
        [
            set_rows,
            usa_rows,
        ],
        ignore_index=True,
    )
    render_seed_detail_table(seed_rows)


def render_opportunity_summary_cards(opportunities):

    st.subheader("Opportunity Summary")
    diagnostics = opportunity_score_diagnostics(opportunities)

    top = (
        opportunities.sort_values(
            [
                "PriorityRank"
                if "PriorityRank" in opportunities.columns
                else "OpportunityRank",
                "PriorityScore"
                if "PriorityScore" in opportunities.columns
                else "OpportunityScore",
            ],
            ascending=[
                True,
                False,
            ],
        ).iloc[0]
        if not opportunities.empty
        else None
    )
    top_label = (
        f"{top['Symbol']} ({safe_number(top.get('PriorityScore', top.get('OpportunityScore', 0))):.2f})"
        if top is not None
        else "N/A"
    )
    top_action = str(top.get("RecommendedAction", "")).upper() if top is not None else ""
    top_lifecycle = str(top.get("LifecycleState", "")).upper() if top is not None else ""
    top_is_actionable = (
        top is not None
        and "IGNORE" not in top_action
        and "AVOID" not in top_action
        and top_lifecycle not in {"SKIP", "EXTENDED"}
    )
    top_metric_label = (
        "Top Opportunity"
        if top_is_actionable
        else "Top Broad-Ranked Candidate"
    )
    cols = st.columns(5)
    cols[0].metric(
        top_metric_label,
        top_label,
    )
    cols[1].metric(
        "Strong Buy Count",
        int(
            (
                opportunities["RecommendedAction"] == "Strong Buy"
            ).sum()
        ),
    )
    cols[2].metric(
        "Buy Count",
        int(
            (
                opportunities["RecommendedAction"] == "Buy"
            ).sum()
        ),
    )
    cols[3].metric(
        "Watch Closely Count",
        int(
            (
                opportunities["RecommendedAction"] == "Watch Closely"
            ).sum()
        ),
    )
    cols[4].metric(
        "Watch Count",
        int(
            (
                opportunities["RecommendedAction"] == "Watch"
            ).sum()
        ),
    )

    cols = st.columns(5)
    cols[0].metric(
        "Avg Opportunity Score",
        f"{diagnostics['mean']:.2f}",
    )
    cols[1].metric(
        "Median Opportunity Score",
        f"{diagnostics['median']:.2f}",
    )
    cols[2].metric(
        "Zero Scores",
        int(diagnostics["zero_count"]),
    )
    cols[3].metric(
        "SET Opportunities",
        int(
            (
                opportunities["Market"] == "SET"
            ).sum()
        ),
    )
    cols[4].metric(
        "USA Opportunities",
        int(
            (
                opportunities["Market"] == "USA"
            ).sum()
        ),
    )


def opportunity_filter_values(df, column):

    if column not in df.columns:
        return [
            "ALL",
        ]

    values = sorted(
        [
            str(value)
            for value in df[column].dropna().unique().tolist()
            if str(value)
        ]
    )

    return [
        "ALL",
    ] + values


def apply_opportunity_filters(
    opportunities,
    market_filter,
    action_filter,
    grade_filter,
    lifecycle_filter,
    min_score,
    state_changed_only,
    symbol_search,
    top_50_only=True,
):

    data = opportunities.copy()

    if market_filter != "ALL":
        data = data[data["Market"] == market_filter]

    if action_filter and "ALL" not in action_filter:
        data = data[
            data["RecommendedAction"].isin(action_filter)
        ]

    if grade_filter and "ALL" not in grade_filter:
        data = data[
            data["OpportunityGrade"].isin(grade_filter)
        ]

    if lifecycle_filter and "ALL" not in lifecycle_filter:
        data = data[
            data["LifecycleState"].isin(lifecycle_filter)
        ]

    data = data[
        data["OpportunityScore"] >= min_score
    ]

    if state_changed_only:
        data = data[data["StateChanged"]]

    symbol_search = symbol_search.strip().upper()

    if symbol_search:
        data = data[
            data["Symbol"]
            .astype(str)
            .str.upper()
            .str.contains(
                symbol_search,
                regex=False,
            )
        ]

    rank_column = (
        "PriorityRank"
        if "PriorityRank" in data.columns
        else "OpportunityRank"
    )
    score_column = (
        "PriorityScore"
        if "PriorityScore" in data.columns
        else "OpportunityScore"
    )
    data = data.sort_values(
        [
            rank_column,
            score_column,
        ],
        ascending=[
            True,
            False,
        ],
    )

    if top_50_only:
        return data.head(50)

    return data


def priority_badge(row, display_rank):

    action = str(
        row.get(
            "PriorityAction",
            row.get("RecommendedAction", ""),
        )
    ).upper()

    if display_rank == 1:
        return "TOP PICK"

    if "HIGH" in action or "REVIEW FIRST" in action:
        return "A+"

    if "WATCH" in action:
        return "HIGH"

    return "QUEUE"


def render_buy_queue(opportunities):

    st.subheader("Buy Queue")
    st.caption("If you can buy only 5 today, review these first.")

    fresh_opportunities = canonical_fresh_cross_candidates(opportunities)
    preferred = fresh_opportunities[
        fresh_opportunities.get(
            "PriorityAction",
            pd.Series("", index=fresh_opportunities.index),
        ).isin(
            [
                "Review First",
                "High Priority",
                "Watch Closely",
            ]
        )
    ].copy()
    queue = (
        preferred
        if not preferred.empty
        else fresh_opportunities.copy()
    )
    rank_column = (
        "PriorityRank"
        if "PriorityRank" in queue.columns
        else "OpportunityRank"
    )
    score_column = (
        "PriorityScore"
        if "PriorityScore" in queue.columns
        else "OpportunityScore"
    )
    queue = queue.sort_values(
        [
            rank_column,
            score_column,
        ],
        ascending=[
            True,
            False,
        ],
    ).head(5).copy()

    if queue.empty:
        st.info("No buy queue candidates")
        return

    queue["Reason Summary"] = queue.apply(
        opportunity_reason_summary,
        axis=1,
    )
    st.markdown(
        """
        <style>
        .ra-queue-card {
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 8px;
            padding: 9px 11px;
            margin-bottom: 8px;
            background: rgba(15, 23, 42, 0.22);
        }
        .ra-queue-title {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: center;
        }
        .ra-queue-symbol {
            font-weight: 780;
            font-size: 0.95rem;
        }
        .ra-queue-badge {
            border: 1px solid rgba(96, 165, 250, 0.30);
            border-radius: 999px;
            padding: 2px 8px;
            color: #93c5fd;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.03em;
        }
        .ra-queue-meta {
            font-size: 0.78rem;
            opacity: 0.82;
            margin-top: 4px;
        }
        .ra-queue-reason {
            font-size: 0.75rem;
            opacity: 0.70;
            margin-top: 5px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for display_rank, (_, row) in enumerate(
        queue.iterrows(),
        start=1,
    ):
        symbol = html.escape(str(row.get("Symbol", "")))
        badge = html.escape(priority_badge(row, display_rank))
        seed_score = safe_number(row.get("SeedScore", 0))
        priority_score = safe_number(row.get("PriorityScore", 0))
        rr = safe_number(row.get("RR", 0))
        fresh = safe_number(row.get("FreshnessScore", 0))
        expansion = safe_number(row.get("ExpansionScore", 0))
        pattern = str(row.get("PatternName", "")).strip()
        setup = str(row.get("StrategySetup", "")).strip()
        dry_days = int(safe_number(row.get("DryVolumeDays", 0)))
        reason_parts = [
            part
            for part in [
                setup,
                pattern,
                f"Dry volume {dry_days}d" if dry_days else "",
            ]
            if part
        ]
        reason = html.escape(
            " · ".join(reason_parts)
            or str(row.get("Reason Summary", ""))
        )

        st.markdown(
            f"""
            <div class="ra-queue-card">
                <div class="ra-queue-title">
                    <span class="ra-queue-symbol">#{display_rank} {symbol}</span>
                    <span class="ra-queue-badge">{badge}</span>
                </div>
                <div class="ra-queue-meta">Seed {seed_score:.0f} · Priority {priority_score:.1f}</div>
                <div class="ra-queue-meta">RR {rr:.1f} · Fresh {fresh:.0f} · Exp {expansion:.0f}</div>
                <div class="ra-queue-reason"><strong>Reason:</strong> {reason}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    columns = [
        "PriorityRank"
        if "PriorityRank" in queue.columns
        else "OpportunityRank",
        "Symbol",
        "Market",
        "PriorityScore"
        if "PriorityScore" in queue.columns
        else "OpportunityScore",
        "PriorityAction"
        if "PriorityAction" in queue.columns
        else "RecommendedAction",
        "RecommendedAction",
        "Reason Summary",
    ]
    columns = [
        column
        for column in columns
        if column in queue.columns
    ]

    with st.expander("Detailed Buy Queue", expanded=False):
        st.dataframe(
            queue[columns],
            use_container_width=True,
            hide_index=True,
        )


def sort_ranked_candidates(data):

    if data.empty:
        return data

    ranked = data.copy()
    rank_column = (
        "PriorityRank"
        if "PriorityRank" in ranked.columns
        else "OpportunityRank"
    )
    score_column = (
        "PriorityScore"
        if "PriorityScore" in ranked.columns
        else "OpportunityScore"
    )

    if rank_column not in ranked.columns:
        ranked[rank_column] = range(1, len(ranked) + 1)
    if score_column not in ranked.columns:
        ranked[score_column] = 0

    ranked[rank_column] = pd.to_numeric(
        ranked[rank_column],
        errors="coerce",
    ).fillna(999999)
    ranked[score_column] = pd.to_numeric(
        ranked[score_column],
        errors="coerce",
    ).fillna(0)
    return ranked.sort_values(
        [
            rank_column,
            score_column,
        ],
        ascending=[
            True,
            False,
        ],
    )


def render_top_ranked_candidates(candidates):

    st.subheader("Broad Ranking")
    st.caption(
        "Non-actionable diagnostic ranking. Use Buy Queue or Watch Queue for decisions."
    )

    ranked = sort_ranked_candidates(candidates).head(10).copy()

    if ranked.empty:
        st.info("No ranked candidates found.")
        return

    ranked["Reason Summary"] = ranked.apply(
        opportunity_reason_summary,
        axis=1,
    )
    columns = [
        "PriorityRank"
        if "PriorityRank" in ranked.columns
        else "OpportunityRank",
        "Symbol",
        "Market",
        "LifecycleState",
        "RecommendedAction",
        "QueueClass",
        "AIDecision",
        "AIConfidence",
        "RR",
        "PriorityScore"
        if "PriorityScore" in ranked.columns
        else "OpportunityScore",
        "BlockingReasons",
        "WarningReasons",
    ]
    columns = [
        column
        for column in columns
        if column in ranked.columns
    ]

    st.dataframe(
        ranked[columns],
        use_container_width=True,
        hide_index=True,
    )


def render_queue_card_styles():

    st.markdown(
        """
        <style>
        .ra-queue-card {
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 8px;
            padding: 9px 11px;
            margin-bottom: 8px;
            background: rgba(15, 23, 42, 0.22);
        }
        .ra-queue-title {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: center;
        }
        .ra-queue-symbol {
            font-weight: 780;
            font-size: 0.95rem;
        }
        .ra-queue-badge {
            border: 1px solid rgba(96, 165, 250, 0.30);
            border-radius: 999px;
            padding: 2px 8px;
            color: #93c5fd;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.03em;
        }
        .ra-queue-meta {
            font-size: 0.78rem;
            opacity: 0.82;
            margin-top: 4px;
        }
        .ra-queue-reason {
            font-size: 0.75rem;
            opacity: 0.70;
            margin-top: 5px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_queue_cards(queue, empty_message):

    if queue.empty:
        st.info(empty_message)
        return

    queue = sort_ranked_candidates(queue).head(5).copy()
    queue["Reason Summary"] = queue.apply(
        opportunity_reason_summary,
        axis=1,
    )
    render_queue_card_styles()

    for display_rank, (_, row) in enumerate(
        queue.iterrows(),
        start=1,
    ):
        symbol = html.escape(str(row.get("Symbol", "")))
        badge = html.escape(priority_badge(row, display_rank))
        seed_score = safe_number(row.get("SeedScore", 0))
        priority_score = safe_number(row.get("PriorityScore", 0))
        rr = safe_number(row.get("RR", 0))
        fresh = safe_number(row.get("FreshnessScore", 0))
        expansion = safe_number(row.get("ExpansionScore", 0))
        pattern = str(row.get("PatternName", "")).strip()
        setup = str(row.get("StrategySetup", "")).strip()
        dry_days = int(safe_number(row.get("DryVolumeDays", 0)))
        reason_parts = [
            part
            for part in [
                setup,
                pattern,
                f"Dry volume {dry_days}d" if dry_days else "",
            ]
            if part
        ]
        reason = html.escape(
            " · ".join(reason_parts)
            or str(row.get("Reason Summary", ""))
        )

        st.markdown(
            f"""
            <div class="ra-queue-card">
                <div class="ra-queue-title">
                    <span class="ra-queue-symbol">#{display_rank} {symbol}</span>
                    <span class="ra-queue-badge">{badge}</span>
                </div>
                <div class="ra-queue-meta">Seed {seed_score:.0f} &middot; Priority {priority_score:.1f}</div>
                <div class="ra-queue-meta">RR {rr:.1f} &middot; Fresh {fresh:.0f} &middot; Exp {expansion:.0f}</div>
                <div class="ra-queue-reason"><strong>Reason:</strong> {reason}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_candidate_queues(
    opportunities,
    ai_decisions=None,
    risk_proposals=None,
):

    ranked, buy_queue, watch_queue = split_candidate_queues(
        opportunities,
        ai_decisions=ai_decisions,
        risk_proposals=risk_proposals,
    )

    render_top_ranked_candidates(ranked)

    st.subheader("Buy Queue")
    st.caption("Only actionable candidates that pass AI, RR, price, and risk gates.")
    render_queue_cards(
        buy_queue,
        "No actionable Buy Queue candidates today.",
    )

    buy_columns = [
        "PriorityRank"
        if "PriorityRank" in buy_queue.columns
        else "OpportunityRank",
        "Symbol",
        "Market",
        "PriorityScore"
        if "PriorityScore" in buy_queue.columns
        else "OpportunityScore",
        "PriorityAction"
        if "PriorityAction" in buy_queue.columns
        else "RecommendedAction",
        "RecommendedAction",
        "AIDecision",
        "AIConfidence",
        "RR",
        "EntryPrice",
        "StopPrice",
        "TargetPrice",
        "EligibilityReasons",
    ]
    buy_columns = [
        column
        for column in buy_columns
        if column in buy_queue.columns
    ]

    with st.expander("Detailed Buy Queue", expanded=False):
        if buy_queue.empty:
            st.info("No actionable Buy Queue candidates.")
        else:
            st.dataframe(
                buy_queue[buy_columns],
                use_container_width=True,
                hide_index=True,
            )

    render_watch_queue(watch_queue)


def render_watch_queue(watch_queue):

    st.subheader("Watch Queue")
    st.caption("Candidates worth monitoring, but not eligible for Buy Queue yet.")

    if watch_queue.empty:
        st.info("No watch queue candidates today.")
        return

    watch = sort_ranked_candidates(watch_queue).head(10).copy()
    watch["Reason Summary"] = watch.apply(
        opportunity_reason_summary,
        axis=1,
    )
    columns = [
        "PriorityRank"
        if "PriorityRank" in watch.columns
        else "OpportunityRank",
        "Symbol",
        "Market",
        "LifecycleState",
        "RecommendedAction",
        "AIDecision",
        "AIConfidence",
        "RR",
        "EligibilityReasons",
        "Reason Summary",
    ]
    columns = [
        column
        for column in columns
        if column in watch.columns
    ]

    st.dataframe(
        watch[columns],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Detailed Watch Queue", expanded=False):
        st.dataframe(
            watch[columns],
            use_container_width=True,
            hide_index=True,
        )


def normalize_ai_decision_frame(df):

    data = df.copy()

    defaults = {
        "Symbol": "",
        "Market": "",
        "AIDecision": "NO_ACTION",
        "AIAction": "No Action",
        "AIConfidence": 0,
        "AIConviction": "NONE",
        "AIPositionIntent": "NONE",
        "AIEntryReadiness": "NOT_APPLICABLE",
        "AIRiskLevel": "UNKNOWN",
        "AIReason": "",
        "AIPositiveFactors": "",
        "AINegativeFactors": "",
        "AIBlockers": "",
        "AIReviewPriority": 5,
        "AIRequiresApproval": False,
        "StrategyScore": 0,
        "OpportunityScore": 0,
        "PriorityScore": 0,
        "MarketQualityScore": 0,
        "LifecycleState": "",
    }

    for column, default in defaults.items():
        if column not in data.columns:
            data[column] = default

    for column in [
        "AIConfidence",
        "AIReviewPriority",
        "StrategyScore",
        "OpportunityScore",
        "PriorityScore",
        "MarketQualityScore",
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        ).fillna(0)

    data["AIRequiresApproval"] = (
        data["AIRequiresApproval"]
        .astype(str)
        .str.upper()
        .isin(
            [
                "TRUE",
                "1",
                "YES",
            ]
        )
    )

    for column in [
        "Symbol",
        "Market",
        "AIDecision",
        "AIConviction",
        "AIRiskLevel",
        "LifecycleState",
    ]:
        data[column] = (
            data[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return data


def ai_filter_options(df, column):

    values = []

    if column in df.columns:
        values = sorted(
            value
            for value in df[column].dropna().astype(str).unique()
            if value.strip()
        )

    return [
        "ALL",
    ] + values


AI_MAIN_ACTIONS = [
    "BUY",
    "PREPARE",
    "WATCH",
    "EXIT",
]

AI_ACTION_ORDER = {
    "BUY": 1,
    "PREPARE": 2,
    "EXIT": 3,
    "HOLD": 4,
    "WATCH": 5,
}

AI_ACTION_LABELS = {
    "BUY": "🟢 ซื้อได้",
    "PREPARE": "🟡 ใกล้ซื้อ",
    "WATCH": "👀 เฝ้าดู",
    "HOLD": "🔵 ถือ",
    "EXIT": "🔴 ขาย",
    "NONE": "⚪ ยังไม่ทำอะไร",
    "NO_ACTION": "⚪ ยังไม่ทำอะไร",
    "SKIP": "⚪ ยังไม่ทำอะไร",
    "AVOID": "⚪ ยังไม่ทำอะไร",
}

AI_ADVANCED_COLUMNS = [
    "AIReviewPriority",
    "Symbol",
    "Market",
    "AIDecision",
    "AIConfidence",
    "AIConviction",
    "LifecycleState",
    "PriorityScore",
    "OpportunityScore",
    "AIRiskLevel",
    "AIReason",
]

AI_SIMPLE_COLUMNS = [
    "Symbol",
    "Action",
    "Cross Age",
    "AI Score",
    "Risk",
    "Reason",
]

SIMPLE_DASHBOARD_BUY_COLUMNS = [
    "Symbol",
    "Market",
    "Cross Age",
    "Price",
    "AI Score",
    "Reason",
]

SIMPLE_DASHBOARD_NEAR_BUY_COLUMNS = [
    "Symbol",
    "Market",
    "Cross Age",
    "Missing Condition",
    "AI Score",
    "Next Action",
]

SIMPLE_DASHBOARD_WATCH_COLUMNS = [
    "Symbol",
    "Market",
    "Cross Age",
    "Reason",
    "AI Score",
]

DEFAULT_SHOW_ADVANCED_DETAILS = False


def ai_action_key(value):

    action = str(value or "NO_ACTION").strip().upper()
    if action == "":
        return "NO_ACTION"
    return action


def ai_action_label(value):

    return AI_ACTION_LABELS.get(
        ai_action_key(value),
        AI_ACTION_LABELS["NO_ACTION"],
    )


def ai_summary_counts(df):

    data = normalize_ai_decision_frame(df)
    decisions = data["AIDecision"].astype(str).str.upper()

    return {
        action: int((decisions == action).sum())
        for action in AI_MAIN_ACTIONS
    }


def ai_empty_state_message(counts):

    if int(counts.get("BUY", 0) or 0) != 0:
        return ""

    message = "วันนี้ยังไม่มีหุ้นที่ AI แนะนำให้ซื้อ"
    prepare_count = int(counts.get("PREPARE", 0) or 0)
    if prepare_count > 0:
        message += f"\n\nมี {prepare_count} ตัวใกล้เข้าเงื่อนไขซื้อ"
    return message


def summarize_reason(row):

    if hasattr(row, "get"):
        text = " ".join(
            row_text(
                row,
                field,
            )
            for field in [
                "AIReason",
                "AIBlockers",
                "AINegativeFactors",
                "AIPositiveFactors",
                "OpportunityReasons",
                "PriorityReasons",
                "StrategySignal",
                "StrategySetup",
            ]
            if row_text(
                row,
                field,
            )
        )
        action_key = ai_action_key(
            row_value(
                row,
                "AIDecision",
                "RecommendedAction",
                default="",
            )
        )
    else:
        text = str(row or "").strip()
        action_key = "NO_ACTION"

    lowered = text.lower()

    if "breakout" in lowered or "pivot" in lowered:
        return "รอ Breakout"
    if "watch context" in lowered:
        return "ยังอยู่ช่วงสะสม"
    if "priority" in lowered:
        return "แนวโน้มดี"
    if "volume" in lowered or "rvol" in lowered:
        return "รอ Volume"
    if "skip" in lowered:
        return "สถานะ Scanner เป็น SKIP"
    if "exit" in lowered or "below stop" in lowered:
        return "แนวโน้มเสีย"
    if "rr" in lowered or "risk/reward" in lowered or "risk reward" in lowered:
        return "Risk/Reward ยังไม่เหมาะ"
    if "ema" in lowered:
        return "EMA ยังไม่ยืนยัน"
    if "risk" in lowered or "extended" in lowered or "chasing" in lowered:
        return "Risk ยังไม่ผ่าน"
    if "trend" in lowered or "confirm" in lowered or "confirmation" in lowered:
        return "แนวโน้มยังไม่ยืนยัน"
    if "ready" in lowered or "buy" in lowered or "approval" in lowered:
        return "พร้อมเข้าซื้อ"

    if not text:
        if action_key == "BUY":
            return "พร้อมเข้าซื้อ"
        if action_key == "PREPARE":
            return "รอ Breakout"
        if action_key == "WATCH":
            return "เฝ้าดูต่อ"
        if action_key == "EXIT":
            return "หลุดแนวโน้ม"
        return "ยังไม่เข้าเงื่อนไข"

    return text[:57] + "..." if len(text) > 60 else text


def shorten_ai_reason(reason, action=""):

    return summarize_reason(
        {
            "AIReason": reason,
            "AIDecision": action,
        }
    )


def ai_sort_frame(df):

    data = normalize_ai_decision_frame(df)
    data["_AIActionOrder"] = (
        data["AIDecision"]
        .astype(str)
        .str.upper()
        .map(AI_ACTION_ORDER)
        .fillna(99)
    )
    if "PriorityRank" not in data.columns:
        data["PriorityRank"] = data["PriorityScore"]
    data["PriorityRank"] = pd.to_numeric(
        data["PriorityRank"],
        errors="coerce",
    ).fillna(999999)

    return data.sort_values(
        [
            "_AIActionOrder",
            "AIReviewPriority",
            "AIConfidence",
            "PriorityRank",
        ],
        ascending=[
            True,
            True,
            False,
            True,
        ],
    ).drop(columns=["_AIActionOrder"])


def build_ai_simple_table(df, show_all_watch=False):

    data = ai_sort_frame(df)
    if data.empty:
        return pd.DataFrame(columns=AI_SIMPLE_COLUMNS)

    if not show_all_watch:
        watch_mask = data["AIDecision"].astype(str).str.upper() == "WATCH"
        watch_rows = data[watch_mask].head(20)
        non_watch_rows = data[~watch_mask]
        data = pd.concat(
            [
                non_watch_rows,
                watch_rows,
            ],
            ignore_index=True,
        )
        data = ai_sort_frame(data)

    simple = pd.DataFrame(
        {
            "Symbol": data["Symbol"],
            "Action": data["AIDecision"].apply(ai_action_label),
            "Cross Age": [
                format_cross_age(
                    ema_check_context(row).get("DaysSinceEMACross")
                )
                for row in data.to_dict(orient="records")
            ],
            "AI Score": data["AIConfidence"],
            "Risk": data["AIRiskLevel"],
            "Reason": [
                summarize_reason(row)
                for row in data.to_dict(
                    orient="records",
                )
            ],
        }
    )
    return simple[AI_SIMPLE_COLUMNS]


def build_ai_advanced_table(df):

    data = normalize_ai_decision_frame(df)
    for column in AI_ADVANCED_COLUMNS:
        if column not in data.columns:
            data[column] = ""
    return data[AI_ADVANCED_COLUMNS].copy()


def simple_action_label(action):

    action = ai_action_key(action)
    if action == "INELIGIBLE":
        return "ไม่เข้าเกณฑ์"
    if action == "BUY":
        return "ซื้อได้"
    if action in {"PREPARE", "NEAR BUY"}:
        return "ใกล้ซื้อ"
    if action == "WATCH":
        return "เฝ้าดู"
    if action == "EXIT":
        return "ขาย"
    return "ไม่สนใจ"


def simple_action_order(action):

    return {
        "BUY": 1,
        "PREPARE": 2,
        "WATCH": 3,
        "AVOID": 4,
    }.get(
        ai_action_key(action),
        4,
    )


def simple_market_status_label(score):

    score = safe_number(score)
    if score >= 60:
        return "แข็งแรง"
    if score >= 40:
        return "ปกติ"
    return "อ่อนแอ"


def simple_market_status_rows(quality):

    data = quality.copy() if quality is not None else pd.DataFrame()
    rows = []

    for market in ["SET", "USA"]:
        score = 0
        if not data.empty and "Market" in data.columns:
            hit = data[
                data["Market"].astype(str).str.upper() == market
            ]
            if not hit.empty:
                score = safe_number(hit.iloc[0].get("QualityScore", 0))
        rows.append({
            "Market": market,
            "Status": simple_market_status_label(score),
        })

    return pd.DataFrame(rows)


def scanner_market_status_from_quality(quality):

    status = simple_market_status_rows(quality)
    return {
        row["Market"]: row["Status"]
        for _, row in status.iterrows()
    }


def risk_passed_for_simple(row):

    if row_bool(row, "RiskApproved"):
        return True

    if row_text(row, "AIRiskLevel").upper() == "HIGH":
        return False

    rr = row_number_or_none(row, "RR", "RiskRewardRatio")
    risk_pct = row_number_or_none(row, "RiskPct", "StopDistancePct")

    if rr is None or risk_pct is None:
        return False

    return rr >= 1.5 and risk_pct <= 8


def risk_approved_for_buy_now(row):

    if row_value(row, "RiskApproved", default=None) is not None:
        return row_bool(row, "RiskApproved")

    return risk_passed_for_simple(row)


def simple_setup_valid(row):

    action = ai_action_key(row_text(row, "AIDecision"))
    signal = row_text(row, "StrategySignal", "Signal").upper()
    lifecycle = row_text(row, "LifecycleState").upper()

    if action in {"EXIT", "AVOID", "NO_ACTION", "NONE", "SKIP"}:
        return False

    blocked_terms = {
        "SKIP",
        "EXTENDED",
        "NO DATA",
    }

    return not any(
        term in signal or term in lifecycle
        for term in blocked_terms
    )


def build_simple_readiness_checklist(row):

    ema_context = ema_check_context(row)
    days_since_ema20_turn = row_number_or_none(
        row,
        "DaysSinceEMA20SlopeTurnPositive",
    )
    rsi = row_number_or_none(row, "RSI")
    rvol = row_number_or_none(row, "RVOL", "rvol")
    expansion = row_number_or_none(row, "ExpansionScore")

    ema20_ready = (
        row_bool(row, "EMA20Improving")
        or (
            days_since_ema20_turn is not None
            and days_since_ema20_turn >= 0
            and days_since_ema20_turn <= 20
        )
    )

    items = [
        {
            "key": "setup_valid",
            "label": "Setup ใช้งานได้",
            "missing": "Setup ยังไม่ยืนยัน",
            "passed": simple_setup_valid(row),
        },
        {
            "key": "ema9_above_ema20",
            "label": "EMA9 อยู่เหนือ EMA20",
            "missing": "รอ EMA9 ตัดขึ้นเหนือ EMA20",
            "passed": ema_context["EMA9AboveEMA20"],
        },
        {
            "key": "ema_cross_fresh",
            "label": (
                f"EMA9 Cross ไม่เกิน {MAX_FRESH_CROSS_DAYS} วันทำการ"
            ),
            "missing": (
                f"EMA9 Cross ไม่เกิน {MAX_FRESH_CROSS_DAYS} วันทำการ"
            ),
            "passed": ema_context["IsFreshEMA9Cross"],
        },
        {
            "key": "ema20_recovering",
            "label": "EMA20 เริ่มฟื้น",
            "missing": "รอ EMA20 ฟื้นตัว",
            "passed": ema20_ready,
        },
        {
            "key": "rsi_zone",
            "label": "RSI อยู่ในโซน",
            "missing": "รอ RSI กลับเข้าโซน",
            "passed": rsi is not None and 45 <= rsi <= 65,
        },
        {
            "key": "rvol_ready",
            "label": "RVOL ≥ 1.5x",
            "missing": "RVOL ≥ 1.5x",
            "passed": rvol is not None and rvol >= 1.5,
        },
        {
            "key": "risk_passed",
            "label": "Risk ผ่าน",
            "missing": "Risk ยังไม่ผ่าน",
            "passed": risk_passed_for_simple(row),
        },
        {
            "key": "expansion_quiet",
            "label": "ยังไม่ไล่ราคา",
            "missing": "ราคาเริ่มวิ่งแล้ว",
            "passed": expansion is not None and expansion <= 60,
        },
        {
            "key": "rr_ready",
            "label": "RR เหมาะสม",
            "missing": "Risk/Reward ยังไม่เหมาะ",
            "passed": safe_number(row_value(row, "RR", "RiskRewardRatio", default=0)) >= 1.5,
        },
    ]

    return [
        {
            **item,
            "passed": bool(item["passed"]),
        }
        for item in items
    ]


def simple_checklist_status(row):

    checklist = build_simple_readiness_checklist(row)
    passed = sum(
        1
        for item in checklist
        if item["passed"]
    )
    missing = [
        item["missing"]
        for item in checklist
        if not item["passed"]
    ]

    return {
        "passed": passed,
        "total": len(checklist),
        "missing": missing,
        "checklist": checklist,
    }


def simple_next_action(row, status=None):

    status = status or simple_checklist_status(row)
    action = ai_action_key(row_text(row, "AIDecision"))
    missing = status.get("missing", [])
    ema_context = ema_check_context(row)

    if action == "EXIT":
        return "ควรขาย"

    if not missing:
        return "ผ่านเงื่อนไข เตรียมประเมิน Entry / Stop / Target"

    if not ema_context["IsFreshEMA9Cross"]:
        if not ema_context["EMA9AboveEMA20"]:
            return "รอ EMA9 ตัดขึ้นเหนือ EMA20"
        if ema_context["DaysSinceEMACross"] is None:
            return "ยังไม่มีประวัติ EMA9 ตัด EMA20"
        return f"EMA9 Cross เกิน {MAX_FRESH_CROSS_DAYS} วันทำการแล้ว"

    if "RVOL ≥ 1.5x" in missing:
        return "รอ Volume ยืนยัน"

    if "รอ EMA9 ตัดขึ้นเหนือ EMA20" in missing:
        return "รอ EMA9 ตัดขึ้นเหนือ EMA20"

    if "Risk ยังไม่ผ่าน" in missing:
        return "รอ Risk ผ่าน"

    return missing[0]


def daily_action_for_row(row):

    action = ai_action_key(row_text(row, "AIDecision"))
    status = simple_checklist_status(row)
    is_fresh_cross = ema_check_context(row)["IsFreshEMA9Cross"]

    if not is_fresh_cross:
        if action in {"BUY", "PREPARE", "WATCH", "HOLD"}:
            return "WATCH"
        return "AVOID"

    if action == "BUY" and risk_approved_for_buy_now(row):
        return "BUY"

    if (
        action in {"BUY", "PREPARE", "WATCH"}
        and status["passed"] == status["total"] - 1
    ):
        return "PREPARE"

    if action in {"BUY", "PREPARE", "WATCH", "HOLD"}:
        return "WATCH"

    return "AVOID"


def merge_risk_approval(ai_decisions, risk_proposals=None):

    data = normalize_ai_decision_frame(ai_decisions)

    if risk_proposals is None or risk_proposals.empty:
        return data

    risk = normalize_order_proposals_frame(risk_proposals)
    merge_columns = [
        column
        for column in [
            "Symbol",
            "Market",
            "RiskApproved",
            "ProposalStatus",
            "RejectReason",
        ]
        if column in risk.columns
    ]

    if "Symbol" not in merge_columns or "Market" not in merge_columns:
        return data

    risk = risk[merge_columns].drop_duplicates(
        subset=[
            "Symbol",
            "Market",
        ],
        keep="last",
    )
    merged = data.merge(
        risk,
        on=[
            "Symbol",
            "Market",
        ],
        how="left",
        suffixes=(
            "",
            "_Risk",
        ),
    )

    if "RiskApproved_Risk" in merged.columns:
        merged["RiskApproved"] = merged["RiskApproved_Risk"].fillna(
            merged.get("RiskApproved", False)
        )
        merged = merged.drop(
            columns=["RiskApproved_Risk"],
            errors="ignore",
        )

    return merged


def build_simple_dashboard_sections(ai_decisions, risk_proposals=None):

    enriched = prepare_daily_candidates(
        ai_decisions,
        risk_proposals,
    )

    if enriched.empty:
        empty = enriched.copy()
        return {
            "all": empty,
            "buy_now": empty,
            "near_buy": empty,
            "watch": empty,
        }

    canonical = canonical_fresh_cross_candidates(enriched)
    if canonical.empty:
        return {
            "all": canonical,
            "buy_now": canonical,
            "near_buy": canonical,
            "watch": canonical,
        }

    decisions = canonical["AIDecision"].astype(str).str.upper()
    buy_now_risk_passed = canonical.apply(
        risk_approved_for_buy_now,
        axis=1,
    )

    buy_now = canonical[
        (decisions == "BUY")
        & buy_now_risk_passed
    ].copy()
    buy_keys = set(
        zip(
            buy_now["Symbol"],
            buy_now["Market"],
        )
    )

    near_buy = canonical[
        ~pd.Series(
            list(zip(canonical["Symbol"], canonical["Market"])),
            index=canonical.index,
        ).isin(buy_keys)
        & decisions.isin(
            [
                "BUY",
                "PREPARE",
                "WATCH",
            ]
        )
        & (
            canonical["_PassedCount"]
            == canonical["_TotalCount"] - 1
        )
    ].copy()
    near_buy_keys = set(
        zip(
            near_buy["Symbol"],
            near_buy["Market"],
        )
    )
    excluded_keys = buy_keys | near_buy_keys

    watch = canonical[
        ~pd.Series(
            list(zip(canonical["Symbol"], canonical["Market"])),
            index=canonical.index,
        ).isin(excluded_keys)
        & (decisions == "WATCH")
    ].head(10).copy()

    return {
        "all": canonical,
        "buy_now": buy_now,
        "near_buy": near_buy,
        "watch": watch,
    }


def prepare_daily_candidates(ai_decisions, risk_proposals=None):

    data = merge_risk_approval(
        ai_decisions,
        risk_proposals,
    )

    if data.empty:
        return data

    rows = []
    for _, row in data.iterrows():
        record = row.to_dict()
        ema_context = ema_check_context(record)
        cross_age = ema_context["DaysSinceEMACross"]
        is_fresh_cross = ema_context["IsFreshEMA9Cross"]
        record["_CrossAge"] = cross_age
        record["_CrossAgeLabel"] = format_cross_age(cross_age)
        record["_CrossAgeSort"] = (
            cross_age
            if cross_age is not None and cross_age >= 0
            else float("inf")
        )
        record["_IsFreshEMACross"] = is_fresh_cross
        record["_FreshCrossStatusLabel"] = ema_context[
            "FreshCrossStatusLabel"
        ]
        record["_FreshCrossOrder"] = 0 if is_fresh_cross else 1
        status = simple_checklist_status(record)
        action = daily_action_for_row(record)
        record["_DisplayAction"] = action
        record["_ActionLabel"] = simple_action_label(action)
        record["_ActionOrder"] = simple_action_order(action)
        record["_PassedCount"] = status["passed"]
        record["_TotalCount"] = status["total"]
        record["_MissingConditions"] = " · ".join(status["missing"])
        record["_PrimaryMissingCondition"] = (
            status["missing"][0]
            if status["missing"]
            else ""
        )
        record["_NextAction"] = simple_next_action(record, status)
        record["_SimpleReason"] = (
            fresh_cross_reason(cross_age)
            if is_fresh_cross
            else simple_next_action(record, status)
        )
        rows.append(record)

    candidates = pd.DataFrame(rows)
    candidates = candidates.sort_values(
        [
            "_FreshCrossOrder",
            "_CrossAgeSort",
            "AIConfidence",
            "_ActionOrder",
            "PriorityScore",
        ],
        ascending=[
            True,
            True,
            False,
            True,
            False,
        ],
    )

    return candidates.drop_duplicates(
        subset=[
            "Symbol",
            "Market",
        ],
        keep="first",
    ).reset_index(drop=True)


def prepare_scanner_daily_candidates(df):

    data = prepare_data(df)
    rows = []

    for _, row in data.iterrows():
        source = row.to_dict()
        ema_context = ema_check_context(source)
        cross_age = ema_context["DaysSinceEMACross"]
        is_fresh_cross = ema_context["IsFreshEMA9Cross"]
        signal_group = row_text(row, "_signal_group").upper()
        if signal_group == "BUY":
            action = "BUY"
        elif signal_group in {"WATCH", "EARLY"}:
            action = "WATCH"
        else:
            action = "AVOID"

        if not is_fresh_cross and action in {"BUY", "WATCH"}:
            action = "WATCH"

        rows.append({
            "Symbol": row.get("Symbol", ""),
            "Market": row.get("Market", ""),
            "Price": safe_number(row.get("Price", 0)),
            "RSI": safe_number(row.get("RSI", 0)),
            "RVOL": safe_number(row.get("RVOL", 0)),
            "StrategySetup": row.get("StrategySetup", row.get("Setup", "")),
            "Score": safe_number(row.get("StrategyScore", row.get("Score", 0))),
            "AIConfidence": safe_number(row.get("StrategyScore", row.get("Score", 0))),
            "AIDecision": action,
            "EMA9": row.get("EMA9", None),
            "EMA20": row.get("EMA20", None),
            "PreviousEMA9": row.get("PreviousEMA9", None),
            "PreviousEMA20": row.get("PreviousEMA20", None),
            "EMA9AboveEMA20": ema_context["EMA9AboveEMA20"],
            "DaysSinceEMA9CrossEMA20": cross_age,
            "LatestPriceDate": ema_context["LatestPriceDate"],
            "CrossDate": ema_context["CrossDate"],
            "CrossAgeSource": ema_context["CrossAgeSource"],
            "BullishCrossEvent": ema_context["BullishCrossEvent"],
            "_DisplayAction": action,
            "_ActionLabel": simple_action_label(action),
            "_ActionOrder": simple_action_order(action),
            "_SimpleReason": (
                fresh_cross_reason(cross_age)
                if is_fresh_cross
                else (
                    "รอ EMA9 ตัดขึ้นเหนือ EMA20"
                    if not ema_context["EMA9AboveEMA20"]
                    else (
                        "ยังไม่มีประวัติ EMA9 ตัด EMA20"
                        if cross_age is None
                        else (
                            f"EMA9 Cross เกิน {MAX_FRESH_CROSS_DAYS} "
                            "วันทำการแล้ว"
                        )
                    )
                )
            ),
            "_CrossAge": cross_age,
            "_CrossAgeLabel": format_cross_age(cross_age),
            "_CrossAgeSort": (
                cross_age
                if cross_age is not None and cross_age >= 0
                else float("inf")
            ),
            "_IsFreshEMACross": is_fresh_cross,
            "_FreshCrossStatusLabel": ema_context[
                "FreshCrossStatusLabel"
            ],
            "_FreshCrossOrder": 0 if is_fresh_cross else 1,
            "_PassedCount": 0,
            "_TotalCount": 0,
            "_MissingConditions": "",
            "_PrimaryMissingCondition": "",
            "_NextAction": "",
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(
        [
            "_FreshCrossOrder",
            "_CrossAgeSort",
            "AIConfidence",
            "_ActionOrder",
        ],
        ascending=[
            True,
            True,
            False,
            True,
        ],
    ).drop_duplicates(
        subset=[
            "Symbol",
            "Market",
        ],
        keep="first",
    ).reset_index(drop=True)


def column_or_default(data, column, default=0):

    if column in data.columns:
        return data[column]

    return pd.Series(
        default,
        index=data.index,
    )


def load_daily_candidates(df):

    ai_decisions, _, ai_missing = load_ai_decisions_from_disk()
    risk_proposals, _, risk_missing = load_order_proposals_from_disk()

    if ai_missing or ai_decisions.empty:
        prepared = prepare_scanner_daily_candidates(df)
    else:
        if risk_missing:
            risk_proposals = None

        prepared = prepare_daily_candidates(
            ai_decisions,
            risk_proposals,
        )

    fresh, audit, fresh_missing, audit_missing = (
        load_candidate_ranking_outputs_from_disk()
    )
    return merge_canonical_scanner_fields(
        prepared,
        fresh_candidates=None if fresh_missing else fresh,
        audit=None if audit_missing else audit,
    )


def _canonical_bool(value):

    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().upper() in {"TRUE", "YES", "Y", "1"}


def _canonical_keys(data):

    return list(
        zip(
            data["Symbol"].fillna("").astype(str).str.upper().str.strip(),
            data["Market"].fillna("").astype(str).str.upper().str.strip(),
        )
    )


def merge_canonical_scanner_fields(
    candidates,
    fresh_candidates=None,
    audit=None,
):

    if candidates is None:
        return pd.DataFrame()

    data = candidates.copy()
    if data.empty:
        data["FreshCrossEligible"] = pd.Series(dtype="bool")
        data["_CanonicalEligibilityMerged"] = pd.Series(dtype="bool")
        return data

    for column in ["Symbol", "Market"]:
        if column not in data.columns:
            data[column] = ""

    if audit is None or audit.empty:
        _, calculated_audit, calculated_fresh = rank_candidate_universe(data)
        audit = calculated_audit
        if fresh_candidates is None:
            fresh_candidates = calculated_fresh

    audit_data = audit.copy() if audit is not None else pd.DataFrame()
    if not audit_data.empty and {"Symbol", "Market"}.issubset(audit_data.columns):
        audit_data["_SymbolKey"] = (
            audit_data["Symbol"].fillna("").astype(str).str.upper().str.strip()
        )
        audit_data["_MarketKey"] = (
            audit_data["Market"].fillna("").astype(str).str.upper().str.strip()
        )
        audit_data = audit_data.drop_duplicates(
            subset=["_SymbolKey", "_MarketKey"],
            keep="first",
        ).set_index(["_SymbolKey", "_MarketKey"])
    else:
        audit_data = pd.DataFrame()

    candidate_keys = _canonical_keys(data)
    audit_keys = set(audit_data.index) if not audit_data.empty else set()
    has_audit_row = pd.Series(
        [key in audit_keys for key in candidate_keys],
        index=data.index,
    )
    canonical_fields = {
        "LatestPriceDate": "LatestPriceDate",
        "CrossDate": "CrossDate",
        "CrossAge": "DaysSinceEMA9CrossEMA20",
        "CrossAgeSource": "CrossAgeSource",
        "EMA9": "EMA9",
        "EMA20": "EMA20",
        "PreviousEMA9": "PreviousEMA9",
        "PreviousEMA20": "PreviousEMA20",
        "EMA9AboveEMA20": "EMA9AboveEMA20",
        "BullishCrossEvent": "BullishCrossEvent",
        "FreshCrossEligible": "FreshCrossEligible",
        "FreshCrossStatus": "FreshCrossStatus",
        "FreshCrossStatusLabel": "FreshCrossStatusLabel",
        "Rank": "CanonicalRank",
        "IncludedInTop5": "IncludedInTop5",
        "Top5EligibilityReason": "Top5EligibilityReason",
        "ExclusionReason": "ExclusionReason",
    }
    for source, target in canonical_fields.items():
        if not audit_data.empty and source in audit_data.columns:
            lookup = audit_data[source].to_dict()
            data[target] = [lookup.get(key, pd.NA) for key in candidate_keys]
        else:
            data[target] = pd.NA

    eligible = data["FreshCrossEligible"].apply(_canonical_bool)
    if fresh_candidates is not None:
        if (
            not fresh_candidates.empty
            and {"Symbol", "Market"}.issubset(fresh_candidates.columns)
        ):
            fresh_keys = set(_canonical_keys(fresh_candidates))
        else:
            fresh_keys = set()
        in_fresh_file = pd.Series(
            [key in fresh_keys for key in candidate_keys],
            index=data.index,
        )
        missing_from_fresh = eligible & ~in_fresh_file
        eligible = eligible & in_fresh_file
    else:
        missing_from_fresh = pd.Series(False, index=data.index)

    data["FreshCrossEligible"] = eligible
    data["IsFreshEMA9Cross"] = eligible
    data["_IsFreshEMACross"] = eligible
    data["_CanonicalEligibilityMerged"] = True
    data["_CrossAge"] = pd.to_numeric(
        data["DaysSinceEMA9CrossEMA20"],
        errors="coerce",
    )
    data["_CrossAgeLabel"] = data["_CrossAge"].apply(format_cross_age)
    data["_CrossAgeSort"] = data["_CrossAge"].fillna(float("inf"))
    data["_FreshCrossOrder"] = (~eligible).astype(int)

    reasons = data["ExclusionReason"].fillna("").astype(str).str.strip()
    reasons.loc[missing_from_fresh] = "NOT_IN_CANONICAL_SET"
    reasons.loc[~has_audit_row] = "NO_CANONICAL_AUDIT"
    reasons = reasons.mask(
        (~eligible) & reasons.eq(""),
        "INELIGIBLE",
    )
    data["ExclusionReason"] = reasons
    data["Top5EligibilityReason"] = data[
        "Top5EligibilityReason"
    ].fillna(reasons)

    status_labels = data["FreshCrossStatusLabel"].fillna("").astype(str)
    data["_FreshCrossStatusLabel"] = [
        (status or "Fresh Cross")
        if is_eligible
        else ("EXTENDED" if reason.upper() == "EXTENDED" else "INELIGIBLE")
        for status, is_eligible, reason in zip(
            status_labels,
            eligible,
            reasons,
        )
    ]
    data["FreshCrossStatus"] = data["_FreshCrossStatusLabel"]

    ineligible = ~eligible
    data.loc[ineligible, "AIDecision"] = "INELIGIBLE"
    data.loc[ineligible, "_DisplayAction"] = "INELIGIBLE"
    data.loc[ineligible, "_ActionLabel"] = "ไม่เข้าเกณฑ์"
    data.loc[ineligible, "_ActionOrder"] = simple_action_order("INELIGIBLE")
    data.loc[ineligible, "_SimpleReason"] = reasons.loc[ineligible]

    return data


def scanner_results_view(
    candidates,
    show_all=False,
    fresh_candidates=None,
    audit=None,
):

    if fresh_candidates is None and audit is None:
        fresh, loaded_audit, fresh_missing, audit_missing = (
            load_candidate_ranking_outputs_from_disk()
        )
        fresh_candidates = None if fresh_missing else fresh
        audit = None if audit_missing else loaded_audit

    data = merge_canonical_scanner_fields(
        candidates,
        fresh_candidates=fresh_candidates,
        audit=audit,
    )
    if show_all or data.empty:
        return data
    return data[data["FreshCrossEligible"].apply(_canonical_bool)].copy()


def simple_candidate_table(data):

    if data.empty:
        return pd.DataFrame(
            columns=[
                "Symbol",
                "Market",
                "Action",
                "Cross Age",
                "Cross Status",
                "Score",
                "Price",
                "RSI",
                "RVOL",
                "Reason",
            ]
        )

    table = pd.DataFrame(
        {
            "Symbol": data["Symbol"],
            "Market": data["Market"],
            "Action": data["_ActionLabel"],
            "Cross Age": column_or_default(data, "_CrossAgeLabel", "-"),
            "Cross Status": column_or_default(
                data,
                "_FreshCrossStatusLabel",
                "ยังไม่ Cross",
            ),
            "Score": data["AIConfidence"],
            "Price": column_or_default(data, "Price", 0),
            "RSI": column_or_default(data, "RSI", 0),
            "RVOL": column_or_default(data, "RVOL", 0),
            "Reason": data["_SimpleReason"],
        }
    )

    return table[
        [
            "Symbol",
            "Market",
            "Action",
            "Cross Age",
            "Cross Status",
            "Score",
            "Price",
            "RSI",
            "RVOL",
            "Reason",
        ]
    ]


def simple_pick_table(candidates, market, limit=5):

    if candidates.empty:
        return pd.DataFrame(
            columns=[
                "Symbol",
                "Action",
                "Cross Age",
                "Score",
                "Price",
                "Reason",
            ]
        )

    data = top_five_candidates(
        candidates,
        market,
        limit=limit,
    )

    if data.empty:
        return pd.DataFrame(
            columns=[
                "Symbol",
                "Action",
                "Cross Age",
                "Score",
                "Price",
                "Reason",
            ]
        )

    table = pd.DataFrame(
        {
            "Symbol": data["Symbol"],
            "Action": data["_ActionLabel"],
            "Cross Age": column_or_default(data, "_CrossAgeLabel", "-"),
            "Score": data["AIConfidence"],
            "Price": column_or_default(data, "Price", 0),
            "Reason": data["_SimpleReason"],
        }
    )

    return table[
        [
            "Symbol",
            "Action",
            "Cross Age",
            "Score",
            "Price",
            "Reason",
        ]
    ]


def all_fresh_cross_table(candidates, market):

    fresh = canonical_fresh_cross_candidates(candidates)
    if fresh.empty:
        return simple_candidate_table(fresh)

    market_rows = fresh[
        fresh["Market"].astype(str).str.upper() == str(market).upper()
    ].copy()
    return simple_candidate_table(market_rows)


def simple_buy_now_table(data):

    if data.empty:
        return pd.DataFrame(columns=SIMPLE_DASHBOARD_BUY_COLUMNS)

    table = pd.DataFrame(
        {
            "Symbol": data["Symbol"],
            "Market": data["Market"],
            "Cross Age": column_or_default(data, "_CrossAgeLabel", "-"),
            "Price": data.get("Price", 0),
            "AI Score": data["AIConfidence"],
            "Reason": data["_SimpleReason"],
        }
    )
    return table[SIMPLE_DASHBOARD_BUY_COLUMNS]


def simple_near_buy_table(data):

    if data.empty:
        return pd.DataFrame(columns=SIMPLE_DASHBOARD_NEAR_BUY_COLUMNS)

    table = pd.DataFrame(
        {
            "Symbol": data["Symbol"],
            "Market": data["Market"],
            "Cross Age": column_or_default(data, "_CrossAgeLabel", "-"),
            "Missing Condition": data["_PrimaryMissingCondition"],
            "AI Score": data["AIConfidence"],
            "Next Action": data["_NextAction"],
        }
    )
    return table[SIMPLE_DASHBOARD_NEAR_BUY_COLUMNS]


def simple_watch_table(data):

    if data.empty:
        return pd.DataFrame(columns=SIMPLE_DASHBOARD_WATCH_COLUMNS)

    table = pd.DataFrame(
        {
            "Symbol": data["Symbol"],
            "Market": data["Market"],
            "Cross Age": column_or_default(data, "_CrossAgeLabel", "-"),
            "Reason": data["_SimpleReason"],
            "AI Score": data["AIConfidence"],
        }
    )
    return table[SIMPLE_DASHBOARD_WATCH_COLUMNS]


def render_clean_scanner_header(last_scan, metadata, current_strategy):

    st.title("River Alpha Scanner")
    cols = st.columns([1.6, 1.1, 0.9, 0.7, 0.8])
    cols[0].metric(
        "Last Scan Time",
        str(last_scan or "N/A"),
    )

    current_mode = str(
        (metadata or {}).get(
            "ExecutedScanMode",
            (metadata or {}).get("RequestedMode", "ALL"),
        )
        or "ALL"
    )
    scan_index = (
        SCAN_MODE_OPTIONS.index(current_mode)
        if current_mode in SCAN_MODE_OPTIONS
        else SCAN_MODE_OPTIONS.index("ALL")
    )
    scan_mode = cols[1].selectbox(
        "Scan Mode",
        SCAN_MODE_OPTIONS,
        index=scan_index,
        key="scanner_header_scan_mode",
    )

    cols[2].metric(
        "Current Mode",
        current_mode,
    )
    run_clicked = cols[3].button(
        "Run Scanner",
        type="primary",
        key="scanner_header_run",
    )
    force_clicked = cols[4].button(
        "Force Refresh",
        key="scanner_header_force",
    )

    notice = st.session_state.pop(
        "scanner_run_notice",
        "",
    )
    if notice:
        st.success(notice)

    if not run_clicked and not force_clicked:
        return

    with st.spinner("Running scanner..."):
        result = run_scanner_from_dashboard(
            force_refresh=True,
            mode=scan_mode,
            workers=int(MAX_WORKERS),
            strategy_mode=current_strategy or "Standard",
        )

    if result.returncode == 0:
        st.session_state["scanner_run_notice"] = (
            "Fresh scan complete. Dashboard output reloaded."
        )
        st.rerun()
        return

    st.error("Scanner failed. Open Advanced Tools for details.")
    st.session_state["scanner_last_error"] = (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    ).strip()


def render_daily_market_summary(df, candidates, quality):

    st.subheader("Market Summary")
    statuses = scanner_market_status_from_quality(quality)
    cols = st.columns(5)

    for index, market in enumerate(["SET", "USA"]):
        stocks = 0
        if "Market" in df.columns:
            stocks = int(
                (
                    df["Market"]
                    .astype(str)
                    .str.upper()
                    == market
                ).sum()
            )
        buy_count = 0
        if not candidates.empty and "Market" in candidates.columns:
            buy_count = int(
                (
                    (
                        candidates["Market"]
                        .astype(str)
                        .str.upper()
                        == market
                    )
                    & (candidates["_DisplayAction"] == "BUY")
                ).sum()
            )

        cols[index * 2].metric(
            f"{market} Stocks",
            stocks,
        )
        cols[index * 2 + 1].metric(
            f"{market} BUY",
            buy_count,
        )

    cols[4].metric(
        "Market Status",
        f"SET {statuses.get('SET', 'N/A')} / USA {statuses.get('USA', 'N/A')}",
    )


def render_todays_picks_simple(candidates):

    st.subheader("Today's Picks")
    set_col, usa_col = st.columns(2)

    with set_col:
        st.markdown("**Top 5 SET**")
        table = simple_pick_table(candidates, "SET")
        if table.empty:
            st.info("ไม่มีรายการ")
        else:
            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True,
            )

    with usa_col:
        st.markdown("**Top 5 USA**")
        table = simple_pick_table(candidates, "USA")
        if table.empty:
            st.info("ไม่มีรายการ")
        else:
            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True,
            )


def render_all_fresh_cross_candidates(candidates):

    st.subheader("All Fresh Cross Candidates")
    set_col, usa_col = st.columns(2)

    with set_col:
        st.markdown("**SET — All Eligible**")
        table = all_fresh_cross_table(candidates, "SET")
        if table.empty:
            st.info("ไม่มีหุ้น SET ที่ผ่าน Fresh Cross hard gate")
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)

    with usa_col:
        st.markdown("**USA — All Eligible**")
        table = all_fresh_cross_table(candidates, "USA")
        if table.empty:
            st.info("ไม่มีหุ้น USA ที่ผ่าน Fresh Cross hard gate")
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)

def render_scanner_results_simple(candidates):

    st.subheader("Scanner Results")

    show_all = st.checkbox(
        "Show all",
        value=False,
        help=(
            "แสดงหุ้นที่ EMA Cross เกินช่วง Fresh Cross, "
            "EMA9 ต่ำกว่า EMA20 หรือไม่มีประวัติ Cross ด้วย"
        ),
        key="simple_scanner_show_all",
    )

    search = st.text_input(
        "Search",
        value="",
        placeholder="AAPL, PTT, KPNREIT",
        key="simple_scanner_search",
    )
    data = scanner_results_view(
        candidates,
        show_all=show_all,
    )

    if search.strip() and not data.empty:
        needles = [
            item.strip().upper()
            for item in search.split(",")
            if item.strip()
        ]
        data = data[
            data["Symbol"]
            .astype(str)
            .str.upper()
            .apply(
                lambda value: any(
                    needle in value
                    for needle in needles
                )
            )
        ]

    st.dataframe(
        simple_candidate_table(data),
        use_container_width=True,
        hide_index=True,
    )

    return data


def render_stock_detail_simple(candidates):

    st.subheader("Stock Detail")

    if candidates.empty:
        st.info("ไม่มีหุ้นสำหรับแสดงรายละเอียด")
        return

    detail_source = candidates[
        candidates["_DisplayAction"] != "AVOID"
    ].copy()
    if detail_source.empty:
        detail_source = candidates.head(50).copy()

    labels = [
        (
            f"{row['Symbol']} | {row['Market']} | "
            f"{row['_ActionLabel']}"
        )
        for _, row in detail_source.iterrows()
    ]
    selected = st.selectbox(
        "Select Stock",
        labels,
        key="daily_stock_detail_select",
    )
    row = detail_source.iloc[labels.index(selected)]
    missing = [
        item.strip()
        for item in str(row.get("_MissingConditions", "")).split("·")
        if item.strip()
    ]
    setup = str(row.get("StrategySetup", row.get("Setup", "")))
    entry = first_existing_number(
        row,
        [
            "EntryPrice",
            "Entry",
            "Price",
        ],
    )
    stop = first_existing_number(
        row,
        [
            "StopLoss",
            "StopPrice",
            "Stop Loss",
            "SL",
        ],
    )
    target = first_existing_number(
        row,
        [
            "Target",
            "TargetPrice",
            "TakeProfit",
            "TP",
        ],
    )

    cols = st.columns(5)
    cols[0].metric("Symbol", row.get("Symbol", ""))
    cols[1].metric("Action", row.get("_ActionLabel", ""))
    cols[2].metric("Score", f"{safe_number(row.get('AIConfidence', 0)):.1f}")
    cols[3].metric("Setup", setup)
    cols[4].metric("Current Price", f"{safe_number(row.get('Price', 0)):.2f}")

    cols = st.columns(3)
    cols[0].metric("Entry", f"{entry:.2f}" if entry else "N/A")
    cols[1].metric("Stop Loss", f"{stop:.2f}" if stop else "N/A")
    cols[2].metric("Target", f"{target:.2f}" if target else "N/A")

    st.markdown("**Why not buy yet**")
    st.write(" · ".join(missing) if missing else "ผ่านครบ")

    st.markdown("**Next Action**")
    st.info(str(row.get("_NextAction", "")) or "เฝ้าดูต่อ")


def render_daily_scanner_dashboard(df, quality):

    candidates = load_daily_candidates(df)
    fresh_candidates = candidates[
        candidates["FreshCrossEligible"].apply(_canonical_bool)
    ].copy() if not candidates.empty else candidates.copy()
    render_daily_market_summary(
        df,
        fresh_candidates,
        quality,
    )
    render_todays_picks_simple(fresh_candidates)
    render_all_fresh_cross_candidates(fresh_candidates)
    filtered = render_scanner_results_simple(candidates)
    render_stock_detail_simple(fresh_candidates)


def render_ai_decision_center():

    ai_decisions, ai_path, missing = load_ai_decisions_from_disk()

    st.subheader("AI Decision Center")
    st.warning(
        "AI Decision Engine Phase 1 provides decision support only. "
        "No order is sent automatically."
    )

    if missing:
        st.info("Run Scanner first to create output/ai_decisions.csv.")
        return

    if ai_decisions.empty:
        st.info("No AI decisions found.")
        return

    ai_decisions = normalize_ai_decision_frame(ai_decisions)
    counts = ai_summary_counts(ai_decisions)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 BUY", counts["BUY"])
    c2.metric("🟡 PREPARE", counts["PREPARE"])
    c3.metric("👀 WATCH", counts["WATCH"])
    c4.metric("🔴 EXIT", counts["EXIT"])

    message = ai_empty_state_message(counts)
    if message:
        st.info(message)

    with st.expander("AI Decision Filters", expanded=False):
        c1, c2, c3 = st.columns(3)
        market_filter = c1.selectbox(
            "Market",
            ai_filter_options(ai_decisions, "Market"),
            key="ai_decision_market_filter",
        )
        decision_filter = c2.multiselect(
            "AI Decision",
            ai_filter_options(ai_decisions, "AIDecision"),
            default=[
                "ALL",
            ],
            key="ai_decision_filter",
        )
        conviction_filter = c3.multiselect(
            "AI Conviction",
            ai_filter_options(ai_decisions, "AIConviction"),
            default=[
                "ALL",
            ],
            key="ai_conviction_filter",
        )

        c1, c2, c3 = st.columns(3)
        risk_filter = c1.multiselect(
            "AI Risk",
            ai_filter_options(ai_decisions, "AIRiskLevel"),
            default=[
                "ALL",
            ],
            key="ai_risk_filter",
        )
        approval_filter = c2.selectbox(
            "Requires Approval",
            [
                "ALL",
                "TRUE",
                "FALSE",
            ],
            key="ai_approval_filter",
        )
        min_confidence = c3.slider(
            "Minimum AI Confidence",
            min_value=0,
            max_value=100,
            value=0,
            step=1,
            key="ai_min_confidence",
        )
        symbol_search = st.text_input(
            "Search Symbol",
            value="",
            placeholder="AAPL, PTT, DUK",
            key="ai_symbol_search",
        )

    show_all_watch = st.checkbox(
        "Show all WATCH candidates",
        value=False,
        key="ai_show_all_watch",
    )

    filtered = ai_decisions.copy()

    if market_filter != "ALL":
        filtered = filtered[
            filtered["Market"] == market_filter
        ]

    if "ALL" not in decision_filter:
        filtered = filtered[
            filtered["AIDecision"].isin(decision_filter)
        ]

    if "ALL" not in conviction_filter:
        filtered = filtered[
            filtered["AIConviction"].isin(conviction_filter)
        ]

    if "ALL" not in risk_filter:
        filtered = filtered[
            filtered["AIRiskLevel"].isin(risk_filter)
        ]

    if approval_filter != "ALL":
        required = approval_filter == "TRUE"
        filtered = filtered[
            filtered["AIRequiresApproval"] == required
        ]

    filtered = filtered[
        filtered["AIConfidence"] >= min_confidence
    ]

    if symbol_search.strip():
        needles = [
            symbol.strip().upper()
            for symbol in symbol_search.split(",")
            if symbol.strip()
        ]

        if needles:
            filtered = filtered[
                filtered["Symbol"]
                .astype(str)
                .str.upper()
                .apply(
                    lambda value: any(
                        needle in value
                        for needle in needles
                    )
                )
            ]

    filtered = ai_sort_frame(filtered)

    st.markdown("**AI Action Queue**")

    if filtered.empty:
        st.info("No AI decisions found for current filters.")
        return

    simple_table = build_ai_simple_table(
        filtered,
        show_all_watch=show_all_watch,
    )
    st.dataframe(
        simple_table,
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Advanced Details", expanded=False):
        advanced_sorted = ai_sort_frame(ai_decisions)
        top_row = advanced_sorted.iloc[0]
        portfolio_actions = int(
            ai_decisions["AIDecision"].isin(
                [
                    "HOLD",
                    "ADD",
                    "REDUCE",
                    "EXIT",
                ]
            ).sum()
        )
        avg_confidence = safe_number(ai_decisions["AIConfidence"].mean())

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Top AI Decision",
            f"{top_row['Symbol']} {top_row['AIDecision']}",
        )
        c2.metric("Portfolio Actions", portfolio_actions)
        c3.metric("Avg Confidence", f"{avg_confidence:.1f}")

        st.dataframe(
            build_ai_advanced_table(filtered),
            use_container_width=True,
            hide_index=True,
        )

    detail_labels = [
        f"{row.Symbol} | {row.Market} | {row.AIDecision} | {row.AIConfidence:.1f}"
        for row in filtered.itertuples()
    ]

    with st.expander("AI Decision Detail", expanded=False):
        selected_label = st.selectbox(
            "Select Symbol",
            detail_labels,
            key="ai_detail_symbol",
        )
        selected_index = detail_labels.index(selected_label)
        row = filtered.iloc[selected_index]

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Decision", row["AIDecision"])
        c2.metric("Confidence", f"{safe_number(row['AIConfidence']):.1f}")
        c3.metric("Conviction", row["AIConviction"])
        c4.metric("Intent", row["AIPositionIntent"])
        c5.metric("Readiness", row["AIEntryReadiness"])
        c6.metric("Risk", row["AIRiskLevel"])

        st.markdown("**Main Reason**")
        st.write(str(row["AIReason"]))

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Positive Factors**")
            st.write(str(row["AIPositiveFactors"]) or "N/A")
        with c2:
            st.markdown("**Negative Factors**")
            st.write(str(row["AINegativeFactors"]) or "N/A")
        with c3:
            st.markdown("**Blockers**")
            st.write(str(row["AIBlockers"]) or "None")

        score_columns = [
            "StrategyScore",
            "OpportunityScore",
            "PriorityScore",
            "MarketQualityScore",
        ]
        score_data = {
            column: safe_number(row.get(column, 0))
            for column in score_columns
            if column in row.index
        }

        st.markdown("**Score Context**")
        st.json(score_data)

    st.caption(f"Loaded AI decisions from {ai_path}")


def normalize_order_proposals_frame(df):

    data = df.copy()

    defaults = {
        "ProposalPriority": 5,
        "ProposalId": "",
        "Symbol": "",
        "Market": "",
        "SourceDecision": "",
        "ProposalAction": "NONE",
        "ProposalStatus": "NO_PROPOSAL",
        "RiskApproved": False,
        "ApprovalRequired": False,
        "EntryPrice": 0,
        "StopPrice": 0,
        "TargetPrice": 0,
        "StopDistancePct": 0,
        "RewardDistancePct": 0,
        "RiskRewardRatio": 0,
        "RiskBudget": 0,
        "ProposedQty": 0,
        "ProposedOrderValue": 0,
        "EstimatedCommission": 0,
        "EstimatedSlippage": 0,
        "EstimatedTotalCost": 0,
        "CurrentPositionQty": 0,
        "FinalPositionQty": 0,
        "CurrentExposurePct": 0,
        "ProjectedExposurePct": 0,
        "PortfolioExposureAfterPct": 0,
        "CashAfterOrder": 0,
        "RiskLevel": "UNKNOWN",
        "RiskScore": 0,
        "RejectReason": "NONE",
        "RiskWarnings": "",
    }

    for column, default in defaults.items():
        if column not in data.columns:
            data[column] = default

    numeric_columns = [
        "ProposalPriority",
        "EntryPrice",
        "StopPrice",
        "TargetPrice",
        "StopDistancePct",
        "RewardDistancePct",
        "RiskRewardRatio",
        "RiskBudget",
        "ProposedQty",
        "ProposedOrderValue",
        "EstimatedCommission",
        "EstimatedSlippage",
        "EstimatedTotalCost",
        "CurrentPositionQty",
        "FinalPositionQty",
        "CurrentExposurePct",
        "ProjectedExposurePct",
        "PortfolioExposureAfterPct",
        "CashAfterOrder",
        "RiskScore",
    ]

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        ).fillna(0)

    for column in [
        "RiskApproved",
        "ApprovalRequired",
    ]:
        data[column] = (
            data[column]
            .astype(str)
            .str.upper()
            .isin(
                [
                    "TRUE",
                    "1",
                    "YES",
                ]
            )
        )

    for column in [
        "ProposalId",
        "Symbol",
        "Market",
        "SourceDecision",
        "ProposalAction",
        "ProposalStatus",
        "RiskLevel",
        "RejectReason",
        "RiskWarnings",
    ]:
        data[column] = (
            data[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return data


def risk_filter_options(df, column):

    values = []

    if column in df.columns:
        values = sorted(
            value
            for value in df[column].dropna().astype(str).unique()
            if value.strip()
        )

    return [
        "ALL",
    ] + values


def render_risk_manager_center():

    proposals, proposal_path, missing = load_order_proposals_from_disk()

    st.subheader("Risk Manager & Order Proposals")
    st.warning(
        "Risk Manager Phase 1 creates proposals only. "
        "No real or paper order is executed."
    )

    if missing:
        st.info("Run Scanner first to create output/order_proposals.csv.")
        return

    if proposals.empty:
        st.info("No order proposals found.")
        return

    proposals = normalize_order_proposals_frame(proposals)
    risk_summary, summary_path, summary_fallback = load_risk_summary_from_disk(proposals)

    if risk_summary.empty:
        summary_row = {}
    else:
        summary_row = risk_summary.iloc[0].to_dict()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric(
        "Pending Approval",
        int(safe_number(summary_row.get("PendingProposals", 0))),
    )
    c2.metric(
        "Rejected",
        int(safe_number(summary_row.get("RejectedProposals", 0))),
    )
    c3.metric(
        "Proposed Buy",
        f"{safe_number(summary_row.get('TotalProposedBuyValue', 0)):,.0f}",
    )
    c4.metric(
        "Proposed Sell",
        f"{safe_number(summary_row.get('TotalProposedSellValue', 0)):,.0f}",
    )
    c5.metric(
        "Proposed Add'l Exposure",
        f"{safe_number(summary_row.get('ProjectedExposurePct', 0)):.2f}%",
    )
    c6.metric(
        "Current Exposure",
        f"{safe_number(summary_row.get('CurrentExposurePct', 0)):.2f}%",
    )
    st.caption(
        "Cash after valid proposals: "
        f"{safe_number(summary_row.get('EstimatedCashAfter', 0)):,.0f}"
    )

    with st.expander("Risk Manager Filters", expanded=False):
        c1, c2, c3 = st.columns(3)
        market_filter = c1.selectbox(
            "Market",
            risk_filter_options(proposals, "Market"),
            key="risk_market_filter",
        )
        action_filter = c2.multiselect(
            "Proposal Action",
            risk_filter_options(proposals, "ProposalAction"),
            default=[
                "ALL",
            ],
            key="risk_action_filter",
        )
        status_filter = c3.multiselect(
            "Proposal Status",
            risk_filter_options(proposals, "ProposalStatus"),
            default=[
                "ALL",
            ],
            key="risk_status_filter",
        )

        c1, c2, c3 = st.columns(3)
        level_filter = c1.multiselect(
            "Risk Level",
            risk_filter_options(proposals, "RiskLevel"),
            default=[
                "ALL",
            ],
            key="risk_level_filter",
        )
        approved_filter = c2.selectbox(
            "Risk Approved",
            [
                "ALL",
                "TRUE",
                "FALSE",
            ],
            key="risk_approved_filter",
        )
        approval_required_filter = c3.selectbox(
            "Approval Required",
            [
                "ALL",
                "TRUE",
                "FALSE",
            ],
            key="risk_approval_required_filter",
        )

        c1, c2, c3 = st.columns(3)
        symbol_search = c1.text_input(
            "Search Symbol",
            value="",
            placeholder="AAPL, PTT, DUK",
            key="risk_symbol_search",
        )
        max_risk_score = c2.slider(
            "Maximum Risk Score",
            min_value=0,
            max_value=100,
            value=100,
            step=1,
            key="risk_max_score",
        )
        min_order_value = c3.number_input(
            "Minimum Proposed Order Value",
            min_value=0.0,
            value=0.0,
            step=100.0,
            key="risk_min_order_value",
        )

    filtered = proposals.copy()

    if market_filter != "ALL":
        filtered = filtered[
            filtered["Market"] == market_filter
        ]

    if "ALL" not in action_filter:
        filtered = filtered[
            filtered["ProposalAction"].isin(action_filter)
        ]

    if "ALL" not in status_filter:
        filtered = filtered[
            filtered["ProposalStatus"].isin(status_filter)
        ]

    if "ALL" not in level_filter:
        filtered = filtered[
            filtered["RiskLevel"].isin(level_filter)
        ]

    if approved_filter != "ALL":
        filtered = filtered[
            filtered["RiskApproved"] == (approved_filter == "TRUE")
        ]

    if approval_required_filter != "ALL":
        filtered = filtered[
            filtered["ApprovalRequired"] == (approval_required_filter == "TRUE")
        ]

    filtered = filtered[
        (filtered["RiskScore"] <= max_risk_score)
        & (filtered["ProposedOrderValue"] >= min_order_value)
    ]

    if symbol_search.strip():
        needles = [
            symbol.strip().upper()
            for symbol in symbol_search.split(",")
            if symbol.strip()
        ]

        if needles:
            filtered = filtered[
                filtered["Symbol"]
                .astype(str)
                .str.upper()
                .apply(
                    lambda value: any(
                        needle in value
                        for needle in needles
                    )
                )
            ]

    filtered = filtered.sort_values(
        [
            "ProposalPriority",
            "RiskApproved",
            "RiskScore",
        ],
        ascending=[
            True,
            False,
            False,
        ],
    )

    st.markdown("**Order Proposal Queue**")

    columns = [
        "ProposalPriority",
        "ProposalId",
        "Symbol",
        "Market",
        "SourceDecision",
        "ProposalAction",
        "ProposalStatus",
        "RiskApproved",
        "EntryPrice",
        "StopPrice",
        "TargetPrice",
        "RiskRewardRatio",
        "ProposedQty",
        "ProposedOrderValue",
        "RiskBudget",
        "ProjectedExposurePct",
        "RiskLevel",
        "RiskScore",
        "RejectReason",
        "RiskWarnings",
        "ApprovalRequired",
    ]
    columns = [
        column
        for column in columns
        if column in filtered.columns
    ]

    if filtered.empty:
        st.info("No order proposals found for current filters.")
        return

    st.dataframe(
        filtered[columns].head(100),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Proposal Detail", expanded=False):
        labels = [
            f"{row.ProposalId} | {row.Symbol} | {row.ProposalAction} | {row.ProposalStatus}"
            for row in filtered.itertuples()
        ]
        selected_label = st.selectbox(
            "Select Proposal",
            labels,
            key="risk_detail_proposal",
        )
        row = filtered.iloc[labels.index(selected_label)]

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Action", row["ProposalAction"])
        c2.metric("Status", row["ProposalStatus"])
        c3.metric("Entry", f"{safe_number(row['EntryPrice']):,.2f}")
        c4.metric("Stop", f"{safe_number(row['StopPrice']):,.2f}")
        c5.metric("Target", f"{safe_number(row['TargetPrice']):,.2f}")
        c6.metric("RR", f"{safe_number(row['RiskRewardRatio']):.2f}")

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Risk Budget", f"{safe_number(row['RiskBudget']):,.2f}")
        c2.metric("Qty", f"{safe_number(row['ProposedQty']):,.2f}")
        c3.metric("Order Value", f"{safe_number(row['ProposedOrderValue']):,.2f}")
        c4.metric("Commission", f"{safe_number(row['EstimatedCommission']):,.2f}")
        c5.metric("Slippage", f"{safe_number(row['EstimatedSlippage']):,.2f}")
        c6.metric("Total Cost", f"{safe_number(row['EstimatedTotalCost']):,.2f}")

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Current Qty", f"{safe_number(row['CurrentPositionQty']):,.2f}")
        c2.metric("Final Qty", f"{safe_number(row['FinalPositionQty']):,.2f}")
        c3.metric("Current Exp", f"{safe_number(row['CurrentExposurePct']):.2f}%")
        c4.metric("Projected Exp", f"{safe_number(row['ProjectedExposurePct']):.2f}%")
        c5.metric("Portfolio Exp", f"{safe_number(row['PortfolioExposureAfterPct']):.2f}%")
        c6.metric("Cash After", f"{safe_number(row['CashAfterOrder']):,.2f}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Risk Score", f"{safe_number(row['RiskScore']):.1f}")
        c2.metric("Risk Level", row["RiskLevel"])
        c3.metric("Approval Required", str(bool(row["ApprovalRequired"])))

        st.markdown("**Reject Reason**")
        st.write(str(row["RejectReason"]) or "NONE")
        st.markdown("**Warnings**")
        st.write(str(row["RiskWarnings"]) or "None")

    st.download_button(
        "Export Order Proposals",
        data=ORDER_PROPOSALS_FILE.read_bytes(),
        file_name="order_proposals.csv",
        mime="text/csv",
    )
    st.caption(f"Loaded order proposals from {proposal_path}")

    if summary_path is not None:
        st.caption(f"Loaded risk summary from {summary_path}")
    elif summary_fallback:
        st.caption("Risk summary calculated from order proposals.")


def render_opportunity_export():

    if not OPPORTUNITY_RESULT_FILE.exists():
        st.info("Run Scanner first to create output/opportunity_results.csv")
        return

    st.download_button(
        "Export Today's Opportunities",
        data=OPPORTUNITY_RESULT_FILE.read_bytes(),
        file_name="opportunity_results.csv",
        mime="text/csv",
    )
    st.caption(str(OPPORTUNITY_RESULT_FILE))

    if PRIORITY_RESULT_FILE.exists():
        st.download_button(
            "Export Priority Results",
            data=PRIORITY_RESULT_FILE.read_bytes(),
            file_name="priority_results.csv",
            mime="text/csv",
        )
        st.caption(str(PRIORITY_RESULT_FILE))


def render_opportunity_add_to_watchlist(row):

    with st.form("opportunity_add_watchlist_form"):
        note = st.text_input(
            "Watchlist Note",
            value=opportunity_reason_summary(row),
        )
        stop_loss = st.number_input(
            "Stop Loss",
            min_value=0.0,
            value=first_existing_number(
                row,
                [
                    "StopLoss",
                    "Stop Loss",
                    "SL",
                ],
            ),
            step=0.01,
            key="opportunity_stop_loss",
        )
        target = st.number_input(
            "Target",
            min_value=0.0,
            value=first_existing_number(
                row,
                [
                    "Target",
                    "TakeProfit",
                    "Take Profit",
                    "TP",
                ],
            ),
            step=0.01,
            key="opportunity_target",
        )
        submitted = st.form_submit_button(
            "Add Opportunity to Watchlist"
        )

    if not submitted:
        return

    add_to_watchlist(
        row["Symbol"],
        row["Market"],
        price=safe_number(row.get("Price", 0.0)),
        setup=row.get("Setup", ""),
        score=safe_number(row.get("Score", 0.0)),
        signal=row.get("Signal", ""),
        strategy_mode=row.get("StrategyMode", "Standard"),
        strategy_setup=row.get("StrategySetup", row.get("Setup", "")),
        strategy_score=safe_number(
            row.get(
                "StrategyScore",
                row.get("Score", 0.0),
            )
        ),
        strategy_signal=row.get("StrategySignal", row.get("Signal", "")),
        lifecycle_state=row.get("LifecycleState", "UNKNOWN"),
        previous_lifecycle_state=row.get(
            "PreviousLifecycleState",
            "UNKNOWN",
        ),
        days_in_state=safe_number(row.get("DaysInState", 0)),
        state_changed=row.get("StateChanged", False),
        opportunity_score=safe_number(row.get("OpportunityScore", 0)),
        opportunity_grade=row.get("OpportunityGrade", ""),
        confidence=safe_number(row.get("Confidence", 0)),
        recommended_action=row.get("RecommendedAction", ""),
        opportunity_reasons=row.get("OpportunityReasons", ""),
        stop_loss=stop_loss,
        target=target,
        note=note,
    )
    st.success(f"Added {row['Symbol']} opportunity to Watchlist")


def render_todays_opportunities(
    opportunities,
    quality,
    opportunity_path=None,
    is_fallback=False,
):

    st.subheader("Today's Opportunities")

    if is_fallback:
        st.warning(
            "No opportunity results found. Falling back to scanner results. "
            "Run Scanner first to create output/opportunity_results.csv."
        )

    if opportunities.empty:
        if opportunity_path is None:
            st.info("No opportunity results found. Run Scanner first.")
        else:
            st.info("No opportunities found for current filters.")
        return

    opportunities = prepare_data(opportunities)
    lifecycle = load_lifecycle()
    ai_recommendation = recommend_priority_mode(
        quality,
        lifecycle,
        opportunities,
    )

    st.markdown("**Priority Mode**")
    c1, c2 = st.columns([1, 2])
    selected_priority_mode = c1.selectbox(
        "Priority Mode",
        PRIORITY_UI_OPTIONS,
        index=0,
        label_visibility="collapsed",
        key="priority_mode_select",
    )
    effective_priority_mode = (
        ai_recommendation.get(
            "AIRecommendedPriority",
            "Seed First",
        )
        if selected_priority_mode == "AI Recommended"
        else selected_priority_mode
    )
    c2.metric(
        "AI Recommended Priority",
        ai_recommendation.get(
            "AIRecommendedPriority",
            "N/A",
        ),
    )
    st.caption(
        "AI Recommended Priority: "
        f"{ai_recommendation.get('AIRecommendedPriority', 'N/A')}"
    )
    reason = ai_recommendation.get(
        "AIRecommendationReason",
        "",
    )
    if selected_priority_mode == "AI Recommended" and reason:
        st.info(reason)

    opportunities = apply_priority_mode(
        opportunities,
        effective_priority_mode,
        market_quality_df=quality,
        lifecycle_df=lifecycle,
        ai_recommended_priority=ai_recommendation.get(
            "AIRecommendedPriority",
            effective_priority_mode,
        ),
        ai_recommendation_reason=reason,
    )
    opportunities = ensure_priority_columns(
        opportunities,
        effective_priority_mode,
        quality=quality,
        lifecycle=lifecycle,
        ai_recommendation=ai_recommendation,
    )
    priority_results, _, priority_missing = load_priority_results_from_disk()
    seed_opportunities = (
        priority_results.copy()
        if not priority_missing and not priority_results.empty
        else opportunities.copy()
    )
    ai_decisions, _, ai_missing = load_ai_decisions_from_disk()
    if ai_missing or ai_decisions.empty:
        ai_decisions = None
    else:
        ai_decisions = normalize_ai_decision_frame(ai_decisions)

    risk_proposals, _, risk_missing = load_order_proposals_from_disk()
    if risk_missing or risk_proposals.empty:
        risk_proposals = None
    else:
        risk_proposals = normalize_order_proposals_frame(risk_proposals)

    render_ai_pick_today(
        seed_opportunities,
        quality,
    )
    render_opportunity_or_seed_summary(
        opportunities,
        seed_opportunities,
    )
    render_top_seed_sections(seed_opportunities)
    render_candidate_queues(
        seed_opportunities,
        ai_decisions=ai_decisions,
        risk_proposals=risk_proposals,
    )
    render_ai_decision_center()
    render_risk_manager_center()
    render_opportunity_export()
    render_opportunity_debug(
        opportunities,
        opportunity_path,
        is_fallback=is_fallback,
    )
    render_priority_debug(
        opportunities,
        effective_priority_mode,
        ai_recommendation,
    )

    with st.expander("Opportunity Filters", expanded=False):
        c1, c2 = st.columns(2)
        market_filter = c1.selectbox(
            "Market",
            [
                "ALL",
                "SET",
                "USA",
            ],
            key="opportunity_market_filter",
        )
        action_filter = c2.multiselect(
            "Recommended Action",
            OPPORTUNITY_ACTIONS,
            default=[
                "ALL",
            ],
            key="opportunity_action_filter",
        )

        c1, c2 = st.columns(2)
        grade_filter = c1.multiselect(
            "Opportunity Grade",
            opportunity_filter_values(
                opportunities,
                "OpportunityGrade",
            ),
            default=[
                "ALL",
            ],
            key="opportunity_grade_filter",
        )
        lifecycle_filter = c2.multiselect(
            "Lifecycle State",
            LIFECYCLE_STATES,
            default=[
                "ALL",
            ],
            key="opportunity_lifecycle_filter",
        )

        c1, c2 = st.columns(2)
        min_score = c1.slider(
            "Min Opportunity Score",
            min_value=0,
            max_value=100,
            value=0,
            step=1,
            key="opportunity_min_score",
        )
        symbol_search = c2.text_input(
            "Search Symbol",
            value="",
            placeholder="AAPL, PTT, DUK",
            key="opportunity_symbol_search",
        )

        c1, c2 = st.columns(2)
        top_50_only = c1.checkbox(
            "Show top 50 opportunities only",
            value=True,
            key="opportunity_top_50_only",
        )
        state_changed_only = c2.checkbox(
            "State Changed Only",
            value=False,
            key="opportunity_state_changed_only",
        )

    filtered = apply_opportunity_filters(
        opportunities,
        market_filter,
        action_filter,
        grade_filter,
        lifecycle_filter,
        min_score,
        state_changed_only,
        symbol_search,
        top_50_only=top_50_only,
    )

    if filtered.empty:
        st.info("No opportunities found for current filters.")
        return

    st.caption(
        f"Showing {len(filtered):,} of {len(opportunities):,} opportunities"
    )

    display_columns = opportunity_display_columns(
        filtered
    )

    with st.expander("Sortable Opportunity Table", expanded=False):
        render_opportunity_overview_table(filtered)
        st.dataframe(
            filtered[display_columns],
            use_container_width=True,
            hide_index=True,
        )

    labels = [
        (
            f"#{int(row.get('PriorityRank', row.get('OpportunityRank', 0)))} | "
            f"{row['Symbol']} | {row['Market']} | "
            f"Priority {safe_number(row.get('PriorityScore', row.get('OpportunityScore', 0))):.2f}"
        )
        for _, row in filtered.iterrows()
    ]
    selected = st.selectbox(
        "Opportunity Detail",
        labels,
        key="opportunity_detail_select",
    )
    row = selected_opportunity_row(
        filtered,
        selected,
    )

    render_opportunity_details(
        row,
        market_quality_for_row(
            row,
            quality,
        ),
    )
    render_opportunity_add_to_watchlist(row)


def build_market_summary(df):

    rows = []

    for market in ("SET", "USA"):

        data = df[df["Market"] == market]

        rows.append({
            "Market": market,
            "Stocks": len(data),
            "BUY": int((data["_signal_group"] == "BUY").sum()),
            "WATCH": int((data["_signal_group"] == "WATCH").sum()),
            "Seed Buy Count": int(
                (
                    data["StrategySignal"]
                    .astype(str)
                    .str.upper()
                    == "SEED BUY"
                ).sum()
            ),
            "Seed Watch Count": int(
                (
                    data["StrategySignal"]
                    .astype(str)
                    .str.upper()
                    == "SEED WATCH"
                ).sum()
            ),
            "EARLY": int((data["_signal_group"] == "EARLY").sum()),
            "EXTENDED": int((data["_signal_group"] == "EXTENDED").sum()),
            "SKIP": int((data["_signal_group"] == "SKIP").sum()),
            "Avg Score": round(data["StrategyScore"].mean(), 1)
            if not data.empty
            else 0,
            "Max Score": data["StrategyScore"].max()
            if not data.empty
            else 0,
        })

    return pd.DataFrame(rows)


def render_summary(df):

    summary = build_market_summary(df)

    st.subheader("Market Summary")

    metric_cols = st.columns(2)

    for index, market in enumerate(("SET", "USA")):

        data = summary[summary["Market"] == market].iloc[0]

        with metric_cols[index]:
            seed_total = int(
                data.get(
                    "Seed Buy Count",
                    0,
                )
            ) + int(
                data.get(
                    "Seed Watch Count",
                    0,
                )
            )

            if seed_total:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"{market} Stocks", int(data["Stocks"]))
                c2.metric(
                    f"{market} Seed BUY",
                    int(data["Seed Buy Count"]),
                )
                c3.metric(
                    f"{market} Seed WATCH",
                    int(data["Seed Watch Count"]),
                )
                c4.metric(f"{market} Max", int(data["Max Score"]))
                continue

            c1, c2, c3 = st.columns(3)
            c1.metric(f"{market} Stocks", int(data["Stocks"]))
            c2.metric(f"{market} BUY", int(data["BUY"]))
            c3.metric(f"{market} Max", int(data["Max Score"]))

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
    )


def render_add_to_watchlist(df):

    candidates = df[
        df["_signal_group"] != "SKIP"
    ].copy()

    if candidates.empty:
        return

    st.subheader("Watchlist")

    labels = [
        watchlist_label(row)
        for _, row in candidates.iterrows()
    ]

    with st.form("scanner_add_watchlist_form"):
        selected = st.selectbox(
            "Candidate",
            labels,
        )
        row = selected_candidate_row(
            candidates,
            selected,
        )
        stop_loss_default = first_existing_number(
            row,
            [
                "StopLoss",
                "Stop Loss",
                "Stop_Loss",
                "SL",
            ],
        )
        target_default = first_existing_number(
            row,
            [
                "Target",
                "TakeProfit",
                "Take Profit",
                "TP",
            ],
        )
        note = st.text_input(
            "Note",
            value="",
        )
        stop_loss = st.number_input(
            "Stop Loss",
            min_value=0.0,
            value=stop_loss_default,
            step=0.01,
        )
        target = st.number_input(
            "Target",
            min_value=0.0,
            value=target_default,
            step=0.01,
        )
        submitted = st.form_submit_button(
            "Add to Watchlist"
        )

    if not submitted:
        return

    add_to_watchlist(
        row["Symbol"],
        row["Market"],
        price=safe_number(row.get("Price", 0.0)),
        setup=row.get("Setup", ""),
        score=safe_number(row.get("Score", 0.0)),
        signal=row.get("Signal", ""),
        strategy_mode=row.get("StrategyMode", "Standard"),
        strategy_setup=row.get("StrategySetup", row.get("Setup", "")),
        strategy_score=safe_number(
            row.get(
                "StrategyScore",
                row.get("Score", 0.0),
            )
        ),
        strategy_signal=row.get("StrategySignal", row.get("Signal", "")),
        lifecycle_state=row.get("LifecycleState", "UNKNOWN"),
        previous_lifecycle_state=row.get(
            "PreviousLifecycleState",
            "UNKNOWN",
        ),
        days_in_state=safe_number(row.get("DaysInState", 0)),
        state_changed=row.get("StateChanged", False),
        opportunity_score=safe_number(row.get("OpportunityScore", 0)),
        opportunity_grade=row.get("OpportunityGrade", ""),
        confidence=safe_number(row.get("Confidence", 0)),
        recommended_action=row.get("RecommendedAction", ""),
        opportunity_reasons=row.get("OpportunityReasons", ""),
        stop_loss=stop_loss,
        target=target,
        note=note,
    )

    st.success(f"Added {row['Symbol']} to Watchlist")


def strategy_mode_cli_arg(strategy_mode):

    key = str(strategy_mode or "Standard").strip().upper()
    return STRATEGY_MODE_CLI_ARGS.get(
        key,
        key.lower().replace(
            " ",
            "_",
        ),
    )


def run_scanner_from_dashboard(force_refresh, mode, workers, strategy_mode):

    command = [
        sys.executable,
        "scanner.py",
        "--mode",
        mode,
        "--workers",
        str(workers),
        "--strategy-mode",
        strategy_mode_cli_arg(strategy_mode),
    ]

    # Dashboard-triggered scans always bypass cached market data. Keep the
    # argument for call-site compatibility, but never allow a stale UI scan.
    command.append("--force-refresh")

    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def render_scanner_actions():

    st.sidebar.header("Scanner")
    st.sidebar.caption(f"Price cache: {PRICE_CACHE_DIR}")
    scan_mode = st.sidebar.selectbox(
        "Scan Mode",
        SCAN_MODE_OPTIONS,
        key="scanner_scan_mode",
    )
    workers = st.sidebar.number_input(
        "Workers",
        min_value=1,
        max_value=32,
        value=int(MAX_WORKERS),
        step=1,
        key="scanner_workers",
    )
    strategy_mode = st.sidebar.selectbox(
        "Strategy Mode",
        STRATEGY_MODE_OPTIONS,
        key="scanner_strategy_mode",
    )
    run_clicked = st.sidebar.button(
        "Run Scanner"
    )
    force_clicked = st.sidebar.button(
        "Force Refresh"
    )

    if not run_clicked and not force_clicked:
        return

    with st.spinner(
        "Running scanner..."
    ):
        result = run_scanner_from_dashboard(
            force_refresh=True,
            mode=scan_mode,
            workers=workers,
            strategy_mode=strategy_mode,
        )

    output = (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    ).strip()

    if result.returncode == 0:
        st.session_state["scanner_run_notice"] = (
            "Fresh scan complete. Dashboard output reloaded."
        )
        st.rerun()
        return
    else:
        st.error(
            f"Scanner failed with exit code {result.returncode}."
        )
        st.warning(
            "Existing dashboard data below may still be from the previous successful scan."
        )

    if output:
        with st.expander("Scanner Output"):
            st.code(
                output[-12000:],
                language="text",
            )


def scanner_page():

    df, result_path = load_scanner_results_from_disk()
    scan_metadata = load_scan_metadata()

    if result_path is None or df.empty:
        render_clean_scanner_header(
            "N/A",
            scan_metadata,
            "Standard",
        )
        st.warning("scanner_results.csv or scanner_results.xlsx not found")
        st.info("กด Run Scanner เพื่อเริ่มสแกน")
        return

    df = prepare_data(df)
    opportunity_df, opportunity_path, opportunity_fallback = (
        load_opportunity_results_from_disk(df)
    )
    last_scan = scan_metadata.get("ScanCompletedAt") or result_file_display_time(result_path)
    current_strategy = current_strategy_mode(df)

    render_clean_scanner_header(
        last_scan,
        scan_metadata,
        current_strategy,
    )
    quality = load_quality_for_dashboard(
        df,
        last_scan,
    )

    render_daily_scanner_dashboard(
        df,
        quality,
    )

    show_advanced = st.checkbox(
        "Show Advanced Details",
        value=DEFAULT_SHOW_ADVANCED_DETAILS,
        key="scanner_show_advanced_details",
    )

    if not show_advanced:
        return

    with st.expander("Advanced Tools", expanded=False):
        scanner_error = st.session_state.get("scanner_last_error", "")
        if scanner_error:
            with st.expander("Scanner Output", expanded=False):
                st.code(
                    scanner_error[-12000:],
                    language="text",
                )
        render_scanner_status(
            df,
            result_path,
            last_scan,
            scan_metadata,
        )
        render_debug_info(
            df,
            result_path,
            scan_metadata,
        )
        render_pipeline_health(
            df,
            opportunity_df,
            scan_metadata,
        )
        render_market_quality_cards(df, last_scan)
        render_lifecycle_section(df)
        render_summary(df)

        render_todays_opportunities(
            opportunity_df,
            quality,
            opportunity_path=opportunity_path,
            is_fallback=opportunity_fallback,
        )

        with st.expander("Scanner Results", expanded=False):
            render_add_to_watchlist(df)
            render_table(df)
