from pathlib import Path

import pandas as pd


PORTFOLIO_FILE = Path("data") / "portfolio.csv"
PRIORITY_RESULTS_FILE = Path("output") / "priority_results.csv"
PORTFOLIO_ANALYSIS_FILE = Path("output") / "portfolio_analysis.csv"
PORTFOLIO_SUMMARY_FILE = Path("output") / "portfolio_summary.csv"
PORTFOLIO_ACTIONS_FILE = Path("output") / "portfolio_actions.csv"

OUTPUT_COLUMNS = [
    "Symbol",
    "Shares",
    "AverageCost",
    "CurrentPrice",
    "PnL",
    "SeedScore",
    "PriorityScore",
    "HoldingScore",
    "Recommendation",
    "RecommendedWeight",
    "RiskLevel",
    "AIReason",
]

SUMMARY_COLUMNS = [
    "PortfolioHealth",
    "TotalPositions",
    "AddCount",
    "HoldCount",
    "ReduceCount",
    "ExitCount",
    "HighRiskCount",
    "AvgHoldingScore",
    "RecommendedCashPct",
    "TopAction",
    "DailyBrief",
]

ACTION_COLUMNS = [
    "Symbol",
    "CurrentWeight",
    "RecommendedWeight",
    "WeightDiff",
    "Action",
    "ActionSizePct",
    "Priority",
    "Reason",
    "CashAction",
    "CashTargetPct",
    "PortfolioMode",
]


def empty_analysis():

    return pd.DataFrame(
        columns=OUTPUT_COLUMNS
    )


def empty_summary():

    return pd.DataFrame(
        [
            {
                "PortfolioHealth": "EMPTY",
                "TotalPositions": 0,
                "AddCount": 0,
                "HoldCount": 0,
                "ReduceCount": 0,
                "ExitCount": 0,
                "HighRiskCount": 0,
                "AvgHoldingScore": 0,
                "RecommendedCashPct": 100,
                "TopAction": "WATCH",
                "DailyBrief": "No open portfolio positions found. Keep cash ready and wait for valid setups.",
            }
        ],
        columns=SUMMARY_COLUMNS,
    )


def empty_actions():

    return pd.DataFrame(
        columns=ACTION_COLUMNS
    )


def safe_float(value, default=0.0):

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_text(value, default=""):

    if pd.isna(value):
        return default

    return str(value).strip()


def clamp(value, low=0, high=100):

    return max(
        low,
        min(
            high,
            safe_float(value),
        ),
    )


def lookup_symbol(symbol, market):

    symbol = safe_text(symbol).upper()
    market = safe_text(market).upper()

    if market == "SET" and symbol and not symbol.endswith(".BK"):
        return f"{symbol}.BK"

    return symbol


def load_portfolio_source(path=PORTFOLIO_FILE):

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_priority_source(path=PRIORITY_RESULTS_FILE):

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_portfolio_analysis(path=PORTFOLIO_ANALYSIS_FILE):

    if not path.exists():
        return empty_analysis()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return empty_analysis()


def load_portfolio_summary(path=PORTFOLIO_SUMMARY_FILE):

    if not path.exists():
        return empty_summary()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return empty_summary()


def normalize_portfolio(df):

    data = df.copy()

    for column in [
        "Symbol",
        "Market",
        "EntryPrice",
        "Shares",
        "Status",
        "NetCost",
    ]:
        if column not in data.columns:
            data[column] = 0 if column in {"EntryPrice", "Shares", "NetCost"} else ""

    data["Symbol"] = data["Symbol"].fillna("").astype(str).str.upper().str.strip()
    data["Market"] = data["Market"].fillna("").astype(str).str.upper().str.strip()
    data["LookupSymbol"] = data.apply(
        lambda row: lookup_symbol(
            row["Symbol"],
            row["Market"],
        ),
        axis=1,
    )
    data["Status"] = (
        data["Status"]
        .fillna("OPEN")
        .astype(str)
        .str.upper()
        .str.strip()
        .replace("", "OPEN")
    )

    for column in [
        "EntryPrice",
        "Shares",
        "NetCost",
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        ).fillna(0)

    return data


def normalize_priority_results(df):

    data = df.copy()

    defaults = {
        "Symbol": "",
        "Market": "",
        "Price": 0,
        "SeedScore": 0,
        "PriorityScore": 0,
        "ExpansionScore": 0,
        "RiskPct": 0,
        "RecommendedAction": "",
        "PriorityAction": "",
        "LifecycleState": "",
        "StrategySignal": "",
        "PatternName": "",
        "PriorityReasons": "",
        "OpportunityReasons": "",
    }

    for column, default in defaults.items():
        if column not in data.columns:
            data[column] = default

    data["Symbol"] = data["Symbol"].fillna("").astype(str).str.upper().str.strip()
    data["Market"] = data["Market"].fillna("").astype(str).str.upper().str.strip()
    data["LookupSymbol"] = data.apply(
        lambda row: lookup_symbol(
            row["Symbol"],
            row["Market"],
        ),
        axis=1,
    )

    for column in [
        "Price",
        "SeedScore",
        "PriorityScore",
        "ExpansionScore",
        "RiskPct",
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        ).fillna(0)

    return data


def position_average_cost(row):

    shares = safe_float(row.get("Shares"))
    net_cost = safe_float(row.get("NetCost"))
    entry_price = safe_float(row.get("EntryPrice"))

    if shares > 0 and net_cost > 0:
        return net_cost / shares

    return entry_price


def pnl_score(pnl_pct):

    if pnl_pct >= 10:
        return 95

    if pnl_pct >= 3:
        return 80

    if pnl_pct >= -3:
        return 65

    if pnl_pct >= -8:
        return 40

    return 15


def risk_score(risk_pct, expansion_score, pnl_pct):

    score = 100
    score -= min(
        45,
        safe_float(risk_pct) * 4,
    )
    score -= min(
        35,
        safe_float(expansion_score) * 0.35,
    )

    if pnl_pct < -5:
        score -= min(
            25,
            abs(pnl_pct) * 2,
        )

    return clamp(score)


def holding_score(row):

    average_cost = safe_float(row.get("AverageCost"))
    current_price = safe_float(row.get("CurrentPrice"))
    pnl_pct = (
        (current_price / average_cost - 1) * 100
        if average_cost > 0 and current_price > 0
        else 0
    )
    priority_score = safe_float(row.get("PriorityScore"))
    seed_score = safe_float(row.get("SeedScore"))
    risk_pct = safe_float(row.get("RiskPct"))
    expansion_score = safe_float(row.get("ExpansionScore"))

    return round(
        clamp(
            priority_score * 0.35
            + seed_score * 0.25
            + pnl_score(pnl_pct) * 0.20
            + risk_score(risk_pct, expansion_score, pnl_pct) * 0.20
        ),
        2,
    )


def risk_level(row):

    if not row.get("MatchedPriority", True):
        return "UNKNOWN"

    average_cost = safe_float(row.get("AverageCost"))
    current_price = safe_float(row.get("CurrentPrice"))
    pnl_pct = (
        (current_price / average_cost - 1) * 100
        if average_cost > 0 and current_price > 0
        else 0
    )
    risk_pct = safe_float(row.get("RiskPct"))
    expansion_score = safe_float(row.get("ExpansionScore"))

    if current_price <= 0:
        return "UNKNOWN"

    if risk_pct >= 8 or expansion_score >= 70 or pnl_pct <= -8:
        return "HIGH"

    if risk_pct >= 4 or expansion_score >= 35 or pnl_pct <= -4:
        return "MEDIUM"

    return "LOW"


def recommendation(row):

    if not row.get("MatchedPriority", True):
        return "WATCH"

    score = safe_float(row.get("HoldingScore"))
    seed_score = safe_float(row.get("SeedScore"))
    priority_score = safe_float(row.get("PriorityScore"))
    expansion_score = safe_float(row.get("ExpansionScore"))
    risk = safe_text(row.get("RiskLevel")).upper()
    average_cost = safe_float(row.get("AverageCost"))
    current_price = safe_float(row.get("CurrentPrice"))
    pnl_pct = (
        (current_price / average_cost - 1) * 100
        if average_cost > 0 and current_price > 0
        else 0
    )

    if current_price <= 0:
        return "WATCH"

    if risk == "HIGH" and (pnl_pct < -5 or priority_score < 35):
        return "EXIT"

    if expansion_score >= 70 and pnl_pct > 5:
        return "REDUCE"

    if score >= 75 and seed_score >= 70 and priority_score >= 80 and risk == "LOW":
        return "ADD"

    if score >= 55:
        return "HOLD"

    if risk == "MEDIUM" or priority_score >= 40:
        return "WATCH"

    return "REDUCE"


def recommended_weight(row):

    action = safe_text(row.get("Recommendation")).upper()
    score = safe_float(row.get("HoldingScore"))
    risk = safe_text(row.get("RiskLevel")).upper()

    if action == "EXIT":
        return 0.0

    if action == "REDUCE":
        return 3.0

    if action == "WATCH":
        return 0.0

    if action == "ADD":
        return round(
            min(
                15,
                max(
                    8,
                    score / 7,
                ),
            ),
            2,
        )

    if risk == "LOW":
        return round(
            min(
                10,
                max(
                    5,
                    score / 10,
                ),
            ),
            2,
        )

    return 5.0


def ai_reason(row):

    if not row.get("MatchedPriority", True):
        return "Watch only. No current scanner match was found for this holding."

    action = safe_text(row.get("Recommendation"))
    risk = safe_text(row.get("RiskLevel"))
    seed_score = safe_float(row.get("SeedScore"))
    priority_score = safe_float(row.get("PriorityScore"))
    expansion_score = safe_float(row.get("ExpansionScore"))
    pnl = safe_float(row.get("PnL"))
    pattern = safe_text(row.get("PatternName"), "N/A")

    if action == "ADD":
        return (
            f"Strong active holding: Seed {seed_score:.0f}, "
            f"Priority {priority_score:.0f}, {pattern}, risk {risk}."
        )

    if action == "HOLD":
        return (
            f"Hold while setup remains constructive. "
            f"Priority {priority_score:.0f}, Seed {seed_score:.0f}, PnL {pnl:.2f}."
        )

    if action == "REDUCE":
        return (
            f"Reduce exposure because risk or expansion is rising. "
            f"Expansion {expansion_score:.0f}, risk {risk}, PnL {pnl:.2f}."
        )

    if action == "EXIT":
        return (
            f"Exit candidate: weak priority or high risk. "
            f"Priority {priority_score:.0f}, risk {risk}, PnL {pnl:.2f}."
        )

    return (
        f"Watch only. Scanner confirmation is not strong enough. "
        f"Priority {priority_score:.0f}, Seed {seed_score:.0f}, risk {risk}."
    )


def analyze_portfolio(portfolio_df, priority_df):

    portfolio = normalize_portfolio(portfolio_df)
    priority = normalize_priority_results(priority_df)
    open_positions = portfolio[
        portfolio["Status"] == "OPEN"
    ].copy()

    if open_positions.empty:
        return empty_analysis()

    latest_priority = priority.drop_duplicates(
        subset=[
            "LookupSymbol",
            "Market",
        ],
        keep="first",
    )
    priority_columns = [
        column
        for column in latest_priority.columns
        if column != "Symbol"
    ]
    merged = open_positions.merge(
        latest_priority[priority_columns],
        on=[
            "LookupSymbol",
            "Market",
        ],
        how="left",
        suffixes=(
            "",
            "_Priority",
        ),
    )
    rows = []

    for _, row in merged.iterrows():
        shares = safe_float(row.get("Shares"))
        average_cost = position_average_cost(row)
        matched_priority = not pd.isna(row.get("Price"))
        current_price = (
            safe_float(row.get("Price"))
            if matched_priority
            else 0
        )
        pnl = (
            (current_price - average_cost) * shares
            if shares > 0 and current_price > 0
            else 0
        )
        base = {
            "Symbol": safe_text(row.get("Symbol")).upper(),
            "Shares": round(shares, 6),
            "AverageCost": round(average_cost, 6),
            "CurrentPrice": round(current_price, 6),
            "PnL": round(pnl, 6),
            "SeedScore": round(safe_float(row.get("SeedScore")), 2),
            "PriorityScore": round(safe_float(row.get("PriorityScore")), 2),
            "ExpansionScore": round(safe_float(row.get("ExpansionScore")), 2),
            "RiskPct": round(safe_float(row.get("RiskPct")), 2),
            "PatternName": safe_text(row.get("PatternName")),
            "MatchedPriority": matched_priority,
        }
        base["HoldingScore"] = holding_score(base)
        base["RiskLevel"] = risk_level(base)
        base["Recommendation"] = recommendation(base)
        base["RecommendedWeight"] = recommended_weight(base)
        base["AIReason"] = ai_reason(base)
        rows.append(base)

    analysis = pd.DataFrame(rows)

    if analysis.empty:
        return empty_analysis()

    return analysis[OUTPUT_COLUMNS]


def save_portfolio_analysis(df, path=PORTFOLIO_ANALYSIS_FILE):

    path.parent.mkdir(
        exist_ok=True
    )
    df = df.copy()

    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df[OUTPUT_COLUMNS].to_csv(
        path,
        index=False,
    )


def portfolio_health(
    total_positions,
    add_count,
    hold_count,
    reduce_count,
    exit_count,
    high_risk_count,
    avg_score,
):

    if total_positions <= 0:
        return "EMPTY"

    high_risk_ratio = high_risk_count / total_positions
    exit_ratio = exit_count / total_positions
    defensive_ratio = (reduce_count + exit_count) / total_positions
    constructive_ratio = (add_count + hold_count) / total_positions

    if exit_ratio >= 0.5 or high_risk_ratio >= 0.5 or avg_score < 40:
        return "WEAK"

    if defensive_ratio >= 0.5 or avg_score < 55:
        return "CAUTIOUS"

    if constructive_ratio >= 0.7 and high_risk_count == 0 and avg_score >= 70:
        return "STRONG"

    return "STABLE"


def recommended_cash_pct(
    total_positions,
    add_count,
    reduce_count,
    exit_count,
    high_risk_count,
):

    if total_positions <= 0:
        return 100

    cash_pct = 10
    cash_pct += (exit_count / total_positions) * 50
    cash_pct += (reduce_count / total_positions) * 25
    cash_pct += (high_risk_count / total_positions) * 20
    cash_pct -= (add_count / total_positions) * 15

    return round(
        clamp(
            cash_pct,
            0,
            100,
        ),
        2,
    )


def top_action(counts):

    priority_order = [
        "EXIT",
        "REDUCE",
        "ADD",
        "HOLD",
        "WATCH",
    ]

    for action in priority_order:
        if counts.get(action, 0) > 0:
            return action

    return "WATCH"


def daily_brief(
    health,
    total_positions,
    add_count,
    hold_count,
    reduce_count,
    exit_count,
    high_risk_count,
    recommended_cash,
):

    if total_positions <= 0:
        return "No open portfolio positions found. Keep cash ready and wait for valid setups."

    if health == "WEAK":
        add_text = (
            "No valid ADD candidate."
            if add_count == 0
            else f"{add_count} ADD candidate found."
        )
        return (
            f"Portfolio is weak. {high_risk_count} positions are high risk. "
            f"{add_text} Consider raising cash to {recommended_cash:.0f}%."
        )

    if health == "CAUTIOUS":
        return (
            f"Portfolio is cautious. {reduce_count} REDUCE and {exit_count} EXIT signals need review. "
            f"Suggested cash level is {recommended_cash:.0f}%."
        )

    if health == "STRONG":
        return (
            f"Portfolio is strong. {add_count} ADD and {hold_count} HOLD signals are constructive. "
            "Keep risk controlled and add only to the best setups."
        )

    return (
        f"Portfolio is stable. Review {high_risk_count} high-risk positions and keep "
        f"cash near {recommended_cash:.0f}% until stronger ADD signals appear."
    )


def summarize_portfolio_analysis(analysis_df):

    analysis = analysis_df.copy()

    for column in OUTPUT_COLUMNS:
        if column not in analysis.columns:
            analysis[column] = 0 if column in {"Shares", "AverageCost", "CurrentPrice", "PnL", "SeedScore", "PriorityScore", "HoldingScore", "RecommendedWeight"} else ""

    if analysis.empty:
        return empty_summary()

    analysis["Recommendation"] = (
        analysis["Recommendation"]
        .fillna("WATCH")
        .astype(str)
        .str.upper()
        .str.strip()
        .replace("", "WATCH")
    )
    analysis["RiskLevel"] = (
        analysis["RiskLevel"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    analysis["HoldingScore"] = pd.to_numeric(
        analysis["HoldingScore"],
        errors="coerce",
    ).fillna(0)

    counts = analysis["Recommendation"].value_counts().to_dict()
    total_positions = int(len(analysis))
    add_count = int(counts.get("ADD", 0))
    hold_count = int(counts.get("HOLD", 0))
    reduce_count = int(counts.get("REDUCE", 0))
    exit_count = int(counts.get("EXIT", 0))
    high_risk_count = int((analysis["RiskLevel"] == "HIGH").sum())
    avg_holding_score = round(
        safe_float(analysis["HoldingScore"].mean()),
        2,
    )
    health = portfolio_health(
        total_positions,
        add_count,
        hold_count,
        reduce_count,
        exit_count,
        high_risk_count,
        avg_holding_score,
    )
    cash_pct = recommended_cash_pct(
        total_positions,
        add_count,
        reduce_count,
        exit_count,
        high_risk_count,
    )
    action = top_action(counts)

    summary = {
        "PortfolioHealth": health,
        "TotalPositions": total_positions,
        "AddCount": add_count,
        "HoldCount": hold_count,
        "ReduceCount": reduce_count,
        "ExitCount": exit_count,
        "HighRiskCount": high_risk_count,
        "AvgHoldingScore": avg_holding_score,
        "RecommendedCashPct": cash_pct,
        "TopAction": action,
        "DailyBrief": daily_brief(
            health,
            total_positions,
            add_count,
            hold_count,
            reduce_count,
            exit_count,
            high_risk_count,
            cash_pct,
        ),
    }

    return pd.DataFrame(
        [
            summary,
        ],
        columns=SUMMARY_COLUMNS,
    )


def save_portfolio_summary(df, path=PORTFOLIO_SUMMARY_FILE):

    path.parent.mkdir(
        exist_ok=True
    )
    summary = df.copy()

    for column in SUMMARY_COLUMNS:
        if column not in summary.columns:
            summary[column] = ""

    summary[SUMMARY_COLUMNS].to_csv(
        path,
        index=False,
    )


def generate_portfolio_summary(
    analysis_path=PORTFOLIO_ANALYSIS_FILE,
    output_path=PORTFOLIO_SUMMARY_FILE,
):

    summary = summarize_portfolio_analysis(
        load_portfolio_analysis(analysis_path)
    )
    save_portfolio_summary(
        summary,
        output_path,
    )

    return summary


def portfolio_mode(summary_row):

    health = safe_text(summary_row.get("PortfolioHealth")).upper()
    cash_target = safe_float(summary_row.get("RecommendedCashPct"))
    add_count = safe_float(summary_row.get("AddCount"))

    if health in {"WEAK", "CAUTIOUS"} or cash_target >= 50:
        return "DEFENSIVE"

    if health == "STRONG" and cash_target <= 20 and add_count > 0:
        return "AGGRESSIVE"

    return "BALANCED"


def cash_action(summary_row):

    cash_target = safe_float(summary_row.get("RecommendedCashPct"))
    add_count = safe_float(summary_row.get("AddCount"))
    exit_count = safe_float(summary_row.get("ExitCount"))
    reduce_count = safe_float(summary_row.get("ReduceCount"))

    if cash_target >= 50 or exit_count > 0 or reduce_count > 0:
        return "RAISE_CASH"

    if cash_target <= 15 and add_count > 0:
        return "DEPLOY_CASH"

    return "HOLD_CASH"


def normalize_action(action):

    action = safe_text(action).upper()

    if action in {
        "ADD",
        "HOLD",
        "REDUCE",
        "EXIT",
        "WATCH",
    }:
        return action

    return "WATCH"


def action_priority(action, action_size, risk_level, holding_score):

    action = normalize_action(action)
    risk_level = safe_text(risk_level).upper()
    holding_score = safe_float(holding_score)
    action_size = safe_float(action_size)

    base_priority = {
        "EXIT": 82,
        "REDUCE": 72,
        "ADD": 65,
        "HOLD": 40,
        "WATCH": 30,
    }.get(action, 35)

    if risk_level == "HIGH":
        base_priority += 6
    elif risk_level == "LOW" and action == "ADD":
        base_priority += 5

    if action in {"EXIT", "REDUCE"}:
        base_priority += min(12, action_size)
    elif action == "ADD":
        base_priority += min(10, max(0, holding_score - 70) / 3)

    return round(
        clamp(
            base_priority,
            0,
            100,
        ),
        2,
    )


def action_reason(row, action, current_weight, recommended_weight, action_size):

    risk = safe_text(row.get("RiskLevel"), "UNKNOWN")
    score = safe_float(row.get("HoldingScore"))
    pnl = safe_float(row.get("PnL"))

    if action == "EXIT":
        return (
            f"Exit to move weight from {current_weight:.2f}% to 0.00%. "
            f"Holding score {score:.2f}, risk {risk}, PnL {pnl:.2f}."
        )

    if action == "REDUCE":
        return (
            f"Reduce by about {action_size:.2f}% to target {recommended_weight:.2f}%. "
            f"Holding score {score:.2f}, risk {risk}."
        )

    if action == "ADD":
        return (
            f"Add by about {action_size:.2f}% toward target {recommended_weight:.2f}%. "
            f"Holding score {score:.2f}, risk {risk}."
        )

    if action == "HOLD":
        return (
            f"Keep near current weight. Current {current_weight:.2f}%, "
            f"target {recommended_weight:.2f}%, risk {risk}."
        )

    return (
        f"Watch only. No position change yet. Current {current_weight:.2f}%, "
        f"target {recommended_weight:.2f}%."
    )


def summarize_action_row(
    row,
    total_value,
    cash_target,
    cash_plan,
    mode,
):

    symbol = safe_text(row.get("Symbol")).upper()
    shares = safe_float(row.get("Shares"))
    current_price = safe_float(row.get("CurrentPrice"))
    position_value = shares * current_price
    current_weight = (
        position_value / total_value * 100
        if total_value > 0 and position_value > 0
        else 0
    )
    action = normalize_action(row.get("Recommendation"))
    recommended_weight = safe_float(row.get("RecommendedWeight"))

    if action == "EXIT":
        recommended_weight = 0
    elif action == "WATCH":
        recommended_weight = current_weight
    elif action == "HOLD":
        recommended_weight = current_weight
    elif action == "REDUCE":
        recommended_weight = min(
            current_weight,
            recommended_weight,
        )
    elif action == "ADD":
        recommended_weight = max(
            current_weight,
            recommended_weight,
        )

    weight_diff = recommended_weight - current_weight
    action_size = 0 if action in {"HOLD", "WATCH"} else abs(weight_diff)

    return {
        "Symbol": symbol,
        "CurrentWeight": round(current_weight, 2),
        "RecommendedWeight": round(recommended_weight, 2),
        "WeightDiff": round(weight_diff, 2),
        "Action": action,
        "ActionSizePct": round(action_size, 2),
        "Priority": action_priority(
            action,
            action_size,
            row.get("RiskLevel"),
            row.get("HoldingScore"),
        ),
        "Reason": action_reason(
            row,
            action,
            current_weight,
            recommended_weight,
            action_size,
        ),
        "CashAction": cash_plan,
        "CashTargetPct": round(cash_target, 2),
        "PortfolioMode": mode,
    }


def generate_portfolio_actions_df(analysis_df, summary_df):

    analysis = analysis_df.copy()

    for column in OUTPUT_COLUMNS:
        if column not in analysis.columns:
            analysis[column] = 0 if column in {"Shares", "CurrentPrice", "RecommendedWeight", "HoldingScore", "PnL"} else ""

    if summary_df.empty:
        summary_df = empty_summary()

    summary_row = summary_df.iloc[0]
    cash_target = safe_float(summary_row.get("RecommendedCashPct"), 100)
    cash_plan = cash_action(summary_row)
    mode = portfolio_mode(summary_row)

    if analysis.empty:
        return empty_actions()

    analysis["Shares"] = pd.to_numeric(
        analysis["Shares"],
        errors="coerce",
    ).fillna(0)
    analysis["CurrentPrice"] = pd.to_numeric(
        analysis["CurrentPrice"],
        errors="coerce",
    ).fillna(0)
    total_value = safe_float(
        (
            analysis["Shares"]
            * analysis["CurrentPrice"]
        ).sum()
    )

    rows = [
        summarize_action_row(
            row,
            total_value,
            cash_target,
            cash_plan,
            mode,
        )
        for _, row in analysis.iterrows()
    ]

    actions = pd.DataFrame(
        rows,
        columns=ACTION_COLUMNS,
    )

    if actions.empty:
        return empty_actions()

    return actions.sort_values(
        by=[
            "Priority",
            "ActionSizePct",
        ],
        ascending=[
            False,
            False,
        ],
    ).reset_index(drop=True)


def save_portfolio_actions(df, path=PORTFOLIO_ACTIONS_FILE):

    path.parent.mkdir(
        exist_ok=True
    )
    actions = df.copy()

    for column in ACTION_COLUMNS:
        if column not in actions.columns:
            actions[column] = ""

    actions[ACTION_COLUMNS].to_csv(
        path,
        index=False,
    )


def generate_portfolio_actions(
    analysis_path=PORTFOLIO_ANALYSIS_FILE,
    summary_path=PORTFOLIO_SUMMARY_FILE,
    output_path=PORTFOLIO_ACTIONS_FILE,
):

    actions = generate_portfolio_actions_df(
        load_portfolio_analysis(analysis_path),
        load_portfolio_summary(summary_path),
    )
    save_portfolio_actions(
        actions,
        output_path,
    )

    return actions


def run_portfolio_ai(
    portfolio_path=PORTFOLIO_FILE,
    priority_path=PRIORITY_RESULTS_FILE,
    output_path=PORTFOLIO_ANALYSIS_FILE,
    summary_path=PORTFOLIO_SUMMARY_FILE,
    actions_path=PORTFOLIO_ACTIONS_FILE,
):

    analysis = analyze_portfolio(
        load_portfolio_source(portfolio_path),
        load_priority_source(priority_path),
    )
    save_portfolio_analysis(
        analysis,
        output_path,
    )
    summary = generate_portfolio_summary(
        output_path,
        summary_path,
    )
    actions = generate_portfolio_actions(
        output_path,
        summary_path,
        actions_path,
    )

    return analysis, summary, actions


def main():

    analysis, summary, actions = run_portfolio_ai()
    print(f"Portfolio analysis rows: {len(analysis)}")
    print(f"Output: {PORTFOLIO_ANALYSIS_FILE}")
    print(f"Summary: {PORTFOLIO_SUMMARY_FILE}")
    print(f"Actions: {PORTFOLIO_ACTIONS_FILE}")

    if not analysis.empty:
        print(
            analysis[
                [
                    "Symbol",
                    "Recommendation",
                    "HoldingScore",
                    "RiskLevel",
                    "RecommendedWeight",
                ]
            ].to_string(index=False)
        )

    if not summary.empty:
        print(
            summary[
                [
                    "PortfolioHealth",
                    "TotalPositions",
                    "TopAction",
                    "RecommendedCashPct",
                ]
            ].to_string(index=False)
        )

    if not actions.empty:
        print(
            actions[
                [
                    "Symbol",
                    "Action",
                    "CurrentWeight",
                    "RecommendedWeight",
                    "ActionSizePct",
                    "Priority",
                    "PortfolioMode",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
