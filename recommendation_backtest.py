import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


PRIORITY_RESULTS_FILE = Path("output") / "priority_results.csv"
PORTFOLIO_ANALYSIS_FILE = Path("output") / "portfolio_analysis.csv"
PORTFOLIO_ACTIONS_FILE = Path("output") / "portfolio_actions.csv"
RECOMMENDATION_HISTORY_FILE = Path("data") / "recommendation_history.csv"
RECOMMENDATION_OUTCOMES_FILE = Path("output") / "recommendation_outcomes.csv"
AI_SCORECARD_FILE = Path("output") / "ai_scorecard.csv"

HISTORY_COLUMNS = [
    "Date",
    "Symbol",
    "Source",
    "Recommendation",
    "Action",
    "SeedScore",
    "PriorityScore",
    "HoldingScore",
    "Market",
    "MarketQuality",
    "PatternName",
    "LifecycleState",
    "ExpansionScore",
    "FreshnessScore",
    "RiskPct",
    "RR",
    "CurrentPrice",
    "PriceAtRecommendation",
    "Notes",
]

OUTCOME_COLUMNS = HISTORY_COLUMNS + [
    "Outcome_5D",
    "Outcome_10D",
    "Outcome_20D",
    "MaxGain_20D",
    "MaxDrawdown_20D",
    "BreakoutWithin10D",
    "DaysToBreakout",
    "Correct",
]

SCORECARD_COLUMNS = [
    "Metric",
    "Value",
    "Notes",
]

VALID_SEED_RECOMMENDATIONS = {
    "SEED BUY",
    "SEED WATCH",
    "EARLY WATCH",
    "WATCH",
    "WATCH CLOSELY",
}

PORTFOLIO_ACTIONS = {
    "ADD",
    "HOLD",
    "REDUCE",
    "EXIT",
    "WATCH",
}


def safe_text(value, default=""):

    if pd.isna(value):
        return default

    return str(value).strip()


def safe_float(value, default=0.0):

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv(path, columns=None):

    if not path.exists():
        return pd.DataFrame(columns=columns)

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)


def ensure_columns(df, columns):

    data = df.copy()

    for column in columns:
        if column not in data.columns:
            data[column] = pd.NA

    return data


def today_string():

    return datetime.now().date().isoformat()


def normalize_symbol(symbol, market=""):

    symbol = safe_text(symbol).upper()
    market = safe_text(market).upper()

    if market == "SET" and symbol and not symbol.endswith(".BK"):
        return f"{symbol}.BK"

    return symbol


def seed_action_from_row(row):

    for column in [
        "StrategySignal",
        "RecommendedAction",
        "PriorityAction",
        "Signal",
    ]:
        value = safe_text(row.get(column)).upper()

        if value in VALID_SEED_RECOMMENDATIONS:
            return value

    recommended = safe_text(row.get("RecommendedAction")).upper()
    strategy_signal = safe_text(row.get("StrategySignal")).upper()

    if "SEED BUY" in strategy_signal:
        return "SEED BUY"

    if "SEED WATCH" in strategy_signal:
        return "SEED WATCH"

    if "WATCH" in recommended:
        return recommended

    return recommended


def valid_seed_candidates(priority_df):

    priority = ensure_columns(
        priority_df,
        [
            "Symbol",
            "Market",
            "LifecycleState",
            "RecommendedAction",
            "StrategySignal",
            "PriorityAction",
            "Signal",
            "SeedScore",
            "PriorityScore",
            "MarketQualityScore",
            "PatternName",
            "ExpansionScore",
            "FreshnessScore",
            "RiskPct",
            "RR",
            "Price",
            "PriorityReasons",
            "OpportunityReasons",
            "SeedReasons",
        ],
    )

    priority["LifecycleState"] = (
        priority["LifecycleState"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    priority["RecommendedAction"] = (
        priority["RecommendedAction"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    priority["StrategySignal"] = (
        priority["StrategySignal"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    excluded_text = "MOMENTUM|EXTENDED|SKIP"
    valid = priority[
        (priority["LifecycleState"] == "SEED")
        & (priority["RecommendedAction"] != "IGNORE")
        & ~priority["LifecycleState"].str.contains(excluded_text, na=False)
        & ~priority["RecommendedAction"].str.contains(excluded_text, na=False)
        & ~priority["StrategySignal"].str.contains(excluded_text, na=False)
    ].copy()

    valid["SnapshotAction"] = valid.apply(
        seed_action_from_row,
        axis=1,
    )
    valid = valid[
        valid["SnapshotAction"].isin(VALID_SEED_RECOMMENDATIONS)
    ].copy()

    return valid


def priority_notes(row):

    for column in [
        "PriorityReasons",
        "OpportunityReasons",
        "SeedReasons",
    ]:
        value = safe_text(row.get(column))

        if value:
            return value

    return "Seed recommendation snapshot."


def snapshot_seed_recommendations(priority_df, snapshot_date):

    rows = []

    for _, row in valid_seed_candidates(priority_df).iterrows():
        action = safe_text(row.get("SnapshotAction")).upper()
        recommendation = safe_text(row.get("RecommendedAction")) or action
        current_price = safe_float(row.get("Price"))

        rows.append(
            {
                "Date": snapshot_date,
                "Symbol": safe_text(row.get("Symbol")).upper(),
                "Source": "PRIORITY",
                "Recommendation": recommendation,
                "Action": action,
                "SeedScore": safe_float(row.get("SeedScore")),
                "PriorityScore": safe_float(row.get("PriorityScore")),
                "HoldingScore": pd.NA,
                "Market": safe_text(row.get("Market")).upper(),
                "MarketQuality": safe_float(row.get("MarketQualityScore")),
                "PatternName": safe_text(row.get("PatternName")),
                "LifecycleState": safe_text(row.get("LifecycleState")).upper(),
                "ExpansionScore": safe_float(row.get("ExpansionScore")),
                "FreshnessScore": safe_float(row.get("FreshnessScore")),
                "RiskPct": safe_float(row.get("RiskPct")),
                "RR": safe_float(row.get("RR")),
                "CurrentPrice": current_price,
                "PriceAtRecommendation": current_price,
                "Notes": priority_notes(row),
            }
        )

    return pd.DataFrame(rows, columns=HISTORY_COLUMNS)


def priority_lookup(priority_df):

    priority = ensure_columns(
        priority_df,
        [
            "Symbol",
            "Market",
            "SeedScore",
            "PriorityScore",
            "MarketQualityScore",
            "PatternName",
            "LifecycleState",
            "ExpansionScore",
            "FreshnessScore",
            "RiskPct",
            "RR",
            "Price",
        ],
    ).copy()

    priority["Market"] = (
        priority["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    priority["LookupSymbol"] = priority.apply(
        lambda row: normalize_symbol(
            row.get("Symbol"),
            row.get("Market"),
        ),
        axis=1,
    )

    return priority.drop_duplicates(
        subset=["LookupSymbol"],
        keep="first",
    ).set_index("LookupSymbol")


def build_portfolio_source(portfolio_analysis_df, portfolio_actions_df, priority_df):

    analysis = ensure_columns(
        portfolio_analysis_df,
        [
            "Symbol",
            "Recommendation",
            "SeedScore",
            "PriorityScore",
            "HoldingScore",
            "CurrentPrice",
            "RiskLevel",
            "AIReason",
        ],
    ).copy()
    actions = ensure_columns(
        portfolio_actions_df,
        [
            "Symbol",
            "Action",
            "Reason",
        ],
    ).copy()

    if analysis.empty and actions.empty:
        return pd.DataFrame()

    analysis["Symbol"] = analysis["Symbol"].fillna("").astype(str).str.upper().str.strip()
    actions["Symbol"] = actions["Symbol"].fillna("").astype(str).str.upper().str.strip()

    merged = analysis.merge(
        actions[["Symbol", "Action", "Reason"]],
        on="Symbol",
        how="outer",
        suffixes=("", "_Action"),
    )

    priority = priority_lookup(priority_df)
    lookup_rows = []

    for _, row in merged.iterrows():
        symbol = safe_text(row.get("Symbol")).upper()
        priority_row = None

        if symbol in priority.index:
            priority_row = priority.loc[symbol]
        elif f"{symbol}.BK" in priority.index:
            priority_row = priority.loc[f"{symbol}.BK"]

        lookup_rows.append(
            {
                "Symbol": symbol,
                "Recommendation": safe_text(row.get("Recommendation")).upper(),
                "Action": safe_text(row.get("Action")).upper()
                or safe_text(row.get("Recommendation")).upper(),
                "SeedScore": safe_float(row.get("SeedScore")),
                "PriorityScore": safe_float(row.get("PriorityScore")),
                "HoldingScore": safe_float(row.get("HoldingScore")),
                "Market": safe_text(priority_row.get("Market")).upper()
                if priority_row is not None
                else "",
                "MarketQuality": safe_float(priority_row.get("MarketQualityScore"))
                if priority_row is not None
                else pd.NA,
                "PatternName": safe_text(priority_row.get("PatternName"))
                if priority_row is not None
                else "",
                "LifecycleState": safe_text(priority_row.get("LifecycleState")).upper()
                if priority_row is not None
                else "",
                "ExpansionScore": safe_float(priority_row.get("ExpansionScore"))
                if priority_row is not None
                else pd.NA,
                "FreshnessScore": safe_float(priority_row.get("FreshnessScore"))
                if priority_row is not None
                else pd.NA,
                "RiskPct": safe_float(priority_row.get("RiskPct"))
                if priority_row is not None
                else pd.NA,
                "RR": safe_float(priority_row.get("RR"))
                if priority_row is not None
                else pd.NA,
                "CurrentPrice": safe_float(row.get("CurrentPrice")),
                "Notes": safe_text(row.get("Reason"))
                or safe_text(row.get("AIReason"))
                or "Portfolio recommendation snapshot.",
            }
        )

    return pd.DataFrame(lookup_rows)


def snapshot_portfolio_recommendations(
    portfolio_analysis_df,
    portfolio_actions_df,
    priority_df,
    snapshot_date,
):

    source = build_portfolio_source(
        portfolio_analysis_df,
        portfolio_actions_df,
        priority_df,
    )

    if source.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    rows = []

    for _, row in source.iterrows():
        recommendation = safe_text(row.get("Recommendation")).upper()
        action = safe_text(row.get("Action")).upper() or recommendation

        if recommendation not in PORTFOLIO_ACTIONS and action not in PORTFOLIO_ACTIONS:
            continue

        if recommendation not in PORTFOLIO_ACTIONS:
            recommendation = action

        current_price = safe_float(row.get("CurrentPrice"))

        rows.append(
            {
                "Date": snapshot_date,
                "Symbol": safe_text(row.get("Symbol")).upper(),
                "Source": "PORTFOLIO",
                "Recommendation": recommendation,
                "Action": action,
                "SeedScore": safe_float(row.get("SeedScore")),
                "PriorityScore": safe_float(row.get("PriorityScore")),
                "HoldingScore": safe_float(row.get("HoldingScore")),
                "Market": safe_text(row.get("Market")).upper(),
                "MarketQuality": safe_float(row.get("MarketQuality"), pd.NA),
                "PatternName": safe_text(row.get("PatternName")),
                "LifecycleState": safe_text(row.get("LifecycleState")).upper(),
                "ExpansionScore": safe_float(row.get("ExpansionScore"), pd.NA),
                "FreshnessScore": safe_float(row.get("FreshnessScore"), pd.NA),
                "RiskPct": safe_float(row.get("RiskPct"), pd.NA),
                "RR": safe_float(row.get("RR"), pd.NA),
                "CurrentPrice": current_price,
                "PriceAtRecommendation": current_price,
                "Notes": safe_text(row.get("Notes")),
            }
        )

    return pd.DataFrame(rows, columns=HISTORY_COLUMNS)


def load_recommendation_history():

    history = read_csv(
        RECOMMENDATION_HISTORY_FILE,
        HISTORY_COLUMNS,
    )

    return ensure_columns(
        history,
        HISTORY_COLUMNS,
    )[HISTORY_COLUMNS]


def save_recommendation_history(history):

    RECOMMENDATION_HISTORY_FILE.parent.mkdir(
        exist_ok=True
    )
    history = ensure_columns(
        history,
        HISTORY_COLUMNS,
    )
    history[HISTORY_COLUMNS].to_csv(
        RECOMMENDATION_HISTORY_FILE,
        index=False,
    )


def snapshot_current_recommendations(snapshot_date=None):

    snapshot_date = snapshot_date or today_string()
    priority_df = read_csv(PRIORITY_RESULTS_FILE)
    portfolio_analysis_df = read_csv(PORTFOLIO_ANALYSIS_FILE)
    portfolio_actions_df = read_csv(PORTFOLIO_ACTIONS_FILE)

    seed_snapshot = snapshot_seed_recommendations(
        priority_df,
        snapshot_date,
    )
    portfolio_snapshot = snapshot_portfolio_recommendations(
        portfolio_analysis_df,
        portfolio_actions_df,
        priority_df,
        snapshot_date,
    )
    snapshot = pd.concat(
        [
            seed_snapshot,
            portfolio_snapshot,
        ],
        ignore_index=True,
    )

    history = load_recommendation_history()
    combined = pd.concat(
        [
            history,
            snapshot,
        ],
        ignore_index=True,
    )
    combined = ensure_columns(
        combined,
        HISTORY_COLUMNS,
    )
    combined = combined.drop_duplicates(
        subset=[
            "Date",
            "Symbol",
            "Source",
            "Recommendation",
            "Action",
        ],
        keep="last",
    ).reset_index(drop=True)

    save_recommendation_history(combined)

    return snapshot, combined


def generate_outcomes(history=None):

    if history is None:
        history = load_recommendation_history()

    outcomes = ensure_columns(
        history,
        OUTCOME_COLUMNS,
    )

    for column in OUTCOME_COLUMNS:
        if column not in outcomes.columns:
            outcomes[column] = pd.NA

    for column in OUTCOME_COLUMNS[len(HISTORY_COLUMNS):]:
        outcomes[column] = pd.NA

    RECOMMENDATION_OUTCOMES_FILE.parent.mkdir(
        exist_ok=True
    )
    outcomes[OUTCOME_COLUMNS].to_csv(
        RECOMMENDATION_OUTCOMES_FILE,
        index=False,
    )

    return outcomes[OUTCOME_COLUMNS]


def count_recommendations(history, target):

    target = target.upper()
    recommendation = (
        history["Recommendation"]
        .fillna("")
        .astype(str)
        .str.upper()
    )
    action = (
        history["Action"]
        .fillna("")
        .astype(str)
        .str.upper()
    )

    if target == "WATCH":
        return int(
            recommendation.str.contains("WATCH").sum()
            + ((action == "WATCH") & ~recommendation.str.contains("WATCH")).sum()
        )

    return int(((recommendation == target) | (action == target)).sum())


def average_metric(history, column):

    if column not in history.columns:
        return 0

    values = pd.to_numeric(
        history[column],
        errors="coerce",
    )

    if values.dropna().empty:
        return 0

    return round(
        safe_float(values.mean()),
        2,
    )


def scorecard_row(metric, value, notes=""):

    return {
        "Metric": metric,
        "Value": value,
        "Notes": notes,
    }


def generate_scorecard(history=None):

    if history is None:
        history = load_recommendation_history()

    history = ensure_columns(
        history,
        HISTORY_COLUMNS,
    )

    rows = [
        scorecard_row(
            "TotalRecommendations",
            int(len(history)),
            "All saved recommendation snapshots.",
        ),
        scorecard_row(
            "SeedRecommendations",
            int((history["LifecycleState"].fillna("").astype(str).str.upper() == "SEED").sum()),
            "Snapshots with LifecycleState = SEED.",
        ),
        scorecard_row(
            "PortfolioRecommendations",
            int((history["Source"].fillna("").astype(str).str.upper() == "PORTFOLIO").sum()),
            "Portfolio AI recommendations.",
        ),
        scorecard_row("AddCount", count_recommendations(history, "ADD")),
        scorecard_row("HoldCount", count_recommendations(history, "HOLD")),
        scorecard_row("ReduceCount", count_recommendations(history, "REDUCE")),
        scorecard_row("ExitCount", count_recommendations(history, "EXIT")),
        scorecard_row("WatchCount", count_recommendations(history, "WATCH")),
        scorecard_row("AvgSeedScore", average_metric(history, "SeedScore")),
        scorecard_row("AvgPriorityScore", average_metric(history, "PriorityScore")),
        scorecard_row("AvgHoldingScore", average_metric(history, "HoldingScore")),
        scorecard_row("AvgFreshness", average_metric(history, "FreshnessScore")),
        scorecard_row("AvgExpansion", average_metric(history, "ExpansionScore")),
        scorecard_row("AvgRiskPct", average_metric(history, "RiskPct")),
        scorecard_row("AvgRR", average_metric(history, "RR")),
        scorecard_row(
            "OutcomeTrackingStatus",
            "Pending price history integration",
            "Outcome fields are placeholders until future price tracking is added.",
        ),
    ]

    scorecard = pd.DataFrame(
        rows,
        columns=SCORECARD_COLUMNS,
    )
    AI_SCORECARD_FILE.parent.mkdir(
        exist_ok=True
    )
    scorecard.to_csv(
        AI_SCORECARD_FILE,
        index=False,
    )

    return scorecard


def reset_history():

    save_recommendation_history(
        pd.DataFrame(columns=HISTORY_COLUMNS)
    )


def run_default(reset=False):

    if reset:
        reset_history()

    snapshot, history = snapshot_current_recommendations()
    outcomes = generate_outcomes(history)
    scorecard = generate_scorecard(history)

    return snapshot, history, outcomes, scorecard


def run_snapshot_only(reset=False):

    if reset:
        reset_history()

    snapshot, history = snapshot_current_recommendations()

    return snapshot, history


def run_scorecard_only(reset=False):

    if reset:
        reset_history()

    history = load_recommendation_history()
    scorecard = generate_scorecard(history)

    return history, scorecard


def parse_args():

    parser = argparse.ArgumentParser(
        description="River Alpha Recommendation Backtest / AI Scorecard foundation."
    )
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Only snapshot current recommendations into data/recommendation_history.csv.",
    )
    parser.add_argument(
        "--scorecard-only",
        action="store_true",
        help="Only regenerate output/ai_scorecard.csv from recommendation history.",
    )
    parser.add_argument(
        "--reset-history",
        action="store_true",
        help="Clear data/recommendation_history.csv before running the selected action.",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    if args.snapshot_only and args.scorecard_only:
        raise SystemExit("Use either --snapshot-only or --scorecard-only, not both.")

    if args.snapshot_only:
        snapshot, history = run_snapshot_only(
            reset=args.reset_history
        )
        print(f"Snapshot rows: {len(snapshot)}")
        print(f"History rows: {len(history)}")
        print(f"History: {RECOMMENDATION_HISTORY_FILE}")
        return

    if args.scorecard_only:
        history, scorecard = run_scorecard_only(
            reset=args.reset_history
        )
        print(f"History rows: {len(history)}")
        print(f"Scorecard rows: {len(scorecard)}")
        print(f"Scorecard: {AI_SCORECARD_FILE}")
        return

    snapshot, history, outcomes, scorecard = run_default(
        reset=args.reset_history
    )
    print(f"Snapshot rows: {len(snapshot)}")
    print(f"History rows: {len(history)}")
    print(f"Outcome rows: {len(outcomes)}")
    print(f"Scorecard rows: {len(scorecard)}")
    print(f"History: {RECOMMENDATION_HISTORY_FILE}")
    print(f"Outcomes: {RECOMMENDATION_OUTCOMES_FILE}")
    print(f"Scorecard: {AI_SCORECARD_FILE}")


if __name__ == "__main__":
    main()
