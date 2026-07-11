import os
import time
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict
import pandas as pd

from providers.thai import get_symbols
from data import get_histories
from indicators import add_indicators_cached
from strategy import trend_start
from strategy_modes import (
    STRATEGY_MODE_CLI_CHOICES,
    apply_strategy_mode,
    normalize_strategy_mode,
    strategy_mode_label,
)
from strategy_lifecycle import update_lifecycle_from_scan
from providers.usa import get_symbols as get_us_symbols
from alert_engine import run_watchlist_alert_check
from market_quality import (
    calculate_market_quality,
    save_market_quality,
)
from opportunity_engine import (
    calculate_opportunities,
    save_opportunities,
)
from priority_engine import (
    apply_priority_mode,
    save_priority_results,
)
from ai_decision_engine import (
    build_ai_decisions,
    save_ai_decisions,
)
from approval_queue import (
    build_approval_summary,
    ready_for_paper_broker,
    sync_approval_queue,
)
from paper_broker import load_daily_state, load_paper_broker_config
from paper_portfolio import (
    calculate_portfolio_summary,
    load_paper_account,
    load_paper_portfolio,
)
from risk_manager import (
    build_order_proposals,
    build_risk_summary,
    load_risk_config,
    save_order_proposals,
    save_risk_summary,
)
from config import (
    PERIOD,
    INTERVAL,
    MAX_WORKERS,
    OUTPUT_FOLDER,
    CSV_FILE,
    EXCEL_FILE,
    SAVE_CSV,
    SAVE_EXCEL,
)

OUTPUT_DIR = OUTPUT_FOLDER
os.makedirs(OUTPUT_DIR, exist_ok=True)
PROFILE_FILE = os.path.join(
    OUTPUT_DIR,
    "scanner_profile.csv",
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BREAKDOWN_ENGINES = (
    "Trend",
    "Momentum",
    "Volume",
    "Base",
    "Breakout",
    "Price",
    "Stage",
)
SCAN_MODE_PLANS = {
    "ALL": [
        ("SET", "SET"),
        ("USA ALL", "USA"),
    ],
    "SET50": [
        ("SET50", "SET"),
    ],
    "SET100": [
        ("SET100", "SET"),
    ],
    "SET ALL": [
        ("SET", "SET"),
    ],
    "USA WATCHLIST": [
        ("USA WATCHLIST", "USA"),
    ],
    "USA ALL": [
        ("USA ALL", "USA"),
    ],
}
SCAN_MODE_CHOICES = [
    "ALL",
    "SET50",
    "SET100",
    "SET All",
    "USA Watchlist",
    "USA All",
]


def is_buy_candidate(signal):

    signal = str(signal)

    return (
        "BUY" in signal
        or "ELITE" in signal
    )


def print_score_breakdown(symbol, result):

    print("\n   BUY CANDIDATE BREAKDOWN")
    print(f"   Symbol : {symbol}")
    print(f"   Signal : {result['signal']}")
    print(f"   Score  : {result['score']}")

    for engine in BREAKDOWN_ENGINES:

        detail = result["score_breakdown"].get(
            engine,
            {}
        )

        score = detail.get("score", 0)
        max_score = detail.get("max_score", 0)
        weight = detail.get("weight", 0)
        weighted = detail.get("weighted_score", 0)
        quality = detail.get("quality", "")

        print(
            f"   {engine:<9} "
            f"{score:>5}/{max_score:<5} "
            f"weight={weight:>5} "
            f"weighted={weighted:>6} "
            f"{quality}"
        )

    print()


def strategy_signal_group(signal):

    signal = str(signal).upper()

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


def normalize_scan_mode(mode):

    return str(mode or "ALL").upper().replace("_", " ").strip()


def resolve_scan_plan(mode="ALL"):

    key = normalize_scan_mode(mode)

    if key not in SCAN_MODE_PLANS:
        raise ValueError(f"Unknown scan mode: {mode}")

    return SCAN_MODE_PLANS[key]


def dedupe_symbols(symbols):

    seen = set()
    result = []

    for symbol in symbols:
        symbol = str(symbol).upper().strip()

        if not symbol or symbol in seen:
            continue

        seen.add(symbol)
        result.append(symbol)

    return result


def load_symbols(index, market):

    market = (market or "SET").upper()

    if market.upper() == "SET":
        return get_symbols(index)

    if market.upper() == "USA":
        return get_us_symbols(index)

    raise ValueError(f"Unknown market: {market}")


def process_symbol(
    symbol,
    market,
    df,
    force_refresh=False,
    strategy_mode="standard",
):

    profile = {
        "indicator_time": 0.0,
        "decision_time": 0.0,
        "indicator_cache_hit": False,
    }

    if df.empty:
        return {
            "symbol": symbol,
            "row": None,
            "decision": None,
            "error": None,
            "message": "No Data",
            "profile": profile,
        }

    indicator_start = time.perf_counter()
    df, cache_hit = add_indicators_cached(
        df,
        symbol,
        market=market,
        period=PERIOD,
        interval=INTERVAL,
        force_refresh=force_refresh,
    )
    profile["indicator_time"] = (
        time.perf_counter() - indicator_start
    )
    profile["indicator_cache_hit"] = cache_hit

    decision_start = time.perf_counter()
    result = trend_start(
        df,
        market=market,
    )
    profile["decision_time"] = (
        time.perf_counter() - decision_start
    )
    strategy_result = apply_strategy_mode(
        df,
        mode=strategy_mode,
        decision=result,
    )
    strategy_reasons = strategy_result.get(
        "StrategyReasons",
        [],
    )
    latest = df.iloc[-1]

    return {
        "symbol": symbol,
        "row": {
            "Symbol": symbol,
            "Market": market,
            "Signal": result["signal"],
            "Setup": result["setup"],
            "Score": result["score"],
            "Price": result["price"],
            "RSI": result["rsi"],
            "RVOL": result["rvol"],
            "Reasons": ", ".join(result["reasons"]),
            "StrategyMode": strategy_result["StrategyMode"],
            "StrategySignal": strategy_result["StrategySignal"],
            "StrategyScore": strategy_result["StrategyScore"],
            "StrategySetup": strategy_result["StrategySetup"],
            "StrategyReasons": ", ".join(strategy_reasons),
            "SeedScore": strategy_result.get("SeedScore", 0),
            "SeedProbability": strategy_result.get("SeedProbability", 0),
            "BaseDays": strategy_result.get("BaseDays", 0),
            "HighLowRange10": strategy_result.get("HighLowRange10", 0),
            "HighLowRange20": strategy_result.get("HighLowRange20", 0),
            "BaseTightnessPct": strategy_result.get("BaseTightnessPct", 0),
            "Vol5Vol20": strategy_result.get("Vol5Vol20", 0),
            "Vol5ToVol20": strategy_result.get("Vol5ToVol20", 0),
            "DryVolumeDays": strategy_result.get("DryVolumeDays", 0),
            "DryVolumeScore": strategy_result.get("DryVolumeScore", 0),
            "EMACompressionPct": strategy_result.get("EMACompressionPct", 0),
            "CompressionScore": strategy_result.get("CompressionScore", 0),
            "ATRPercentile60": strategy_result.get("ATRPercentile60", 0),
            "ATRCompressionScore": strategy_result.get("ATRCompressionScore", 0),
            "PocketPivot": strategy_result.get("PocketPivot", False),
            "FreshnessScore": strategy_result.get("FreshnessScore", 0),
            "DaysSinceEMA20SlopeTurnPositive": strategy_result.get(
                "DaysSinceEMA20SlopeTurnPositive",
                None,
            ),
            "DaysSinceEMA9CrossEMA20": strategy_result.get(
                "DaysSinceEMA9CrossEMA20",
                None,
            ),
            "DaysSinceBreakout": strategy_result.get(
                "DaysSinceBreakout",
                None,
            ),
            "PatternName": strategy_result.get("PatternName", ""),
            "PatternScore": strategy_result.get("PatternScore", 0),
            "VCPProbability": strategy_result.get("VCPProbability", 0),
            "BaseQuality": strategy_result.get("BaseQuality", 0),
            "AccumulationScore": strategy_result.get("AccumulationScore", 0),
            "ChartReaderSummary": strategy_result.get(
                "ChartReaderSummary",
                "",
            ),
            "ExpansionScore": strategy_result.get("ExpansionScore", 0),
            "BottomingSeedScore": strategy_result.get(
                "BottomingSeedScore",
                0,
            ),
            "DowntrendDecelerationScore": strategy_result.get(
                "DowntrendDecelerationScore",
                0,
            ),
            "SellingPressureScore": strategy_result.get(
                "SellingPressureScore",
                0,
            ),
            "SmallCandleScore": strategy_result.get(
                "SmallCandleScore",
                0,
            ),
            "LowerLowsStopped": strategy_result.get(
                "LowerLowsStopped",
                False,
            ),
            "FirstHigherLow": strategy_result.get(
                "FirstHigherLow",
                False,
            ),
            "EMA9CurlUp": strategy_result.get(
                "EMA9CurlUp",
                False,
            ),
            "EMA20Improving": strategy_result.get(
                "EMA20Improving",
                False,
            ),
            "FirstIgnition": strategy_result.get(
                "FirstIgnition",
                False,
            ),
            "DistanceFromHigh60Pct": strategy_result.get(
                "DistanceFromHigh60Pct",
                0,
            ),
            "NearLow60Pct": strategy_result.get("NearLow60Pct", 0),
            "BottomingReasons": strategy_result.get(
                "BottomingReasons",
                "",
            ),
            "PriceAboveLowClose20Pct": strategy_result.get(
                "PriceAboveLowClose20Pct",
                0,
            ),
            "Return5DPct": strategy_result.get("Return5DPct", 0),
            "Return10DPct": strategy_result.get("Return10DPct", 0),
            "BullishCandleStreak": strategy_result.get(
                "BullishCandleStreak",
                0,
            ),
            "WideRangeBullishCount": strategy_result.get(
                "WideRangeBullishCount",
                0,
            ),
            "MomentumEstablished": strategy_result.get(
                "MomentumEstablished",
                False,
            ),
            "EMA9EMA20SpreadPct": strategy_result.get(
                "EMA9EMA20SpreadPct",
                0,
            ),
            "ExpansionReasons": strategy_result.get(
                "ExpansionReasons",
                "",
            ),
            "SeedReasons": strategy_result.get("SeedReasons", ""),
            "ATR": latest.get("atr", 0),
            "DistanceEMA20Pct": latest.get("distance_ema20", 0),
            "EMA20": latest.get("ema20", 0),
            "EMA50": latest.get("ema50", 0),
            "EMA200": latest.get("ema200", 0),
            "Low90": latest.get("low90", 0),
            "High20": latest.get("high20", 0),
            "High55": latest.get("high55", 0),
            "MoveFromLow90": latest.get("move_from_low90", 0),
        },
        "decision": result,
        "strategy": strategy_result,
        "error": None,
        "message": (
            f"{strategy_result['StrategySignal']} | "
            f"Strategy Score {strategy_result['StrategyScore']} | "
            f"Standard {result['signal']} {result['score']}"
        ),
        "profile": profile,
    }


def scan_market(
    index="SET",
    market="SET",
    force_refresh=False,
    workers=MAX_WORKERS,
    strategy_mode="standard",
):

    market = (market or "SET").upper()
    strategy_mode = normalize_strategy_mode(strategy_mode)
    symbols = dedupe_symbols(
        load_symbols(
            index,
            market,
        )
    )

    results = []
    payloads = []
    total_start = time.perf_counter()

    print(f"\n========== SCANNING {index} ==========\n")
    print(f"Total Symbols : {len(symbols)}\n")
    print(f"Workers       : {workers}\n")
    print(f"Strategy Mode : {strategy_mode_label(strategy_mode)}\n")

    download_start = time.perf_counter()
    histories = get_histories(
        symbols,
        market=market,
        period=PERIOD,
        interval=INTERVAL,
        force_refresh=force_refresh,
    )
    download_time = time.perf_counter() - download_start

    processing_start = time.perf_counter()
    max_workers = max(
        1,
        int(workers or MAX_WORKERS),
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                process_symbol,
                symbol,
                market,
                histories.get(symbol, pd.DataFrame()),
                force_refresh,
                strategy_mode,
            ): symbol
            for symbol in symbols
        }

        for i, future in enumerate(
            as_completed(future_map),
            start=1,
        ):
            symbol = future_map[future]
            print(f"[{i}/{len(symbols)}] {symbol}")

            try:
                payload = future.result()
            except Exception as e:
                print(f"   ERROR : {e}")
                continue

            payloads.append(payload)

            if payload["message"]:
                print(f"   {payload['message']}")

            if payload["row"] is not None:
                results.append(payload["row"])

            decision = payload.get("decision")

            if decision and is_buy_candidate(decision["signal"]):
                print_score_breakdown(
                    symbol,
                    decision,
                )

    processing_time = time.perf_counter() - processing_start
    total_time = time.perf_counter() - total_start
    indicator_total = sum(
        payload.get("profile", {}).get("indicator_time", 0.0)
        for payload in payloads
    )
    decision_total = sum(
        payload.get("profile", {}).get("decision_time", 0.0)
        for payload in payloads
    )
    cache_hits = sum(
        1
        for payload in payloads
        if payload.get("profile", {}).get("indicator_cache_hit")
    )
    timing = {
        "Index": index,
        "Market": market,
        "Symbols": len(symbols),
        "Download Time": round(download_time, 2),
        "Indicator Time": round(indicator_total, 2),
        "Decision Time": round(decision_total, 2),
        "Indicator Cache Hits": cache_hits,
        "Processing Time": round(processing_time, 2),
        "Total Time": round(total_time, 2),
    }

    print("\nSCAN DURATION")
    print(
        pd.DataFrame([timing]).to_string(
            index=False
        )
    )

    return pd.DataFrame(results), timing


def scan_market_legacy(index="SET", market="SET", force_refresh=False):

    symbols = dedupe_symbols(
        load_symbols(
            index,
            market,
        )
    )
    results = []

    for symbol in symbols:
        try:
            histories = get_histories(
                [
                    symbol,
                ],
                market=market,
                period=PERIOD,
                interval=INTERVAL,
                force_refresh=force_refresh,
            )
            payload = process_symbol(
                symbol,
                market,
                histories.get(symbol, pd.DataFrame()),
                force_refresh,
                "standard",
            )

            if payload["row"] is None:
                continue

            results.append(payload["row"])

        except Exception as e:
            print(f"   ERROR : {e}")

    return pd.DataFrame(results)


def save_results(df):

    export_start = time.perf_counter()

    if df.empty:
        print("\nNo Result")
        return 0.0

    csv_path = os.path.join(
        OUTPUT_DIR,
        CSV_FILE,
    )

    excel_path = os.path.join(
        OUTPUT_DIR,
        EXCEL_FILE,
    )

    if SAVE_CSV:
        df.to_csv(csv_path, index=False)

    if SAVE_EXCEL:
        df.to_excel(excel_path, index=False)

    print("\nSaved")

    if SAVE_CSV:
        print(csv_path)

    if SAVE_EXCEL:
        print(excel_path)

    return time.perf_counter() - export_start


def run_watchlist_alerts(df):

    alert_start = time.perf_counter()

    try:
        alerts = run_watchlist_alert_check(df)

        if alerts.empty:
            print("\nWatchlist Alerts : none")
            return time.perf_counter() - alert_start

        print(f"\nWatchlist Alerts : {len(alerts)}")
        print(
            alerts[
                [
                    "Symbol",
                    "Market",
                    "AlertType",
                    "Message",
                ]
            ].to_string(
                index=False
            )
        )

    except Exception as e:
        print(f"\nWatchlist Alerts ERROR : {e}")

    return time.perf_counter() - alert_start


def show_summary(df):

    if df.empty:
        return

    print("\n========== MARKET SUMMARY ==========\n")

    summary_rows = []
    signal_col = (
        "StrategySignal"
        if "StrategySignal" in df.columns
        else "Signal"
    )
    setup_col = (
        "StrategySetup"
        if "StrategySetup" in df.columns
        else "Setup"
    )
    score_col = (
        "StrategyScore"
        if "StrategyScore" in df.columns
        else "Score"
    )

    for market, data in df.groupby("Market"):

        summary_rows.append({
            "Market": market,
            "Stocks": len(data),
            "Buy Candidates": data[signal_col].apply(
                is_buy_candidate
            ).sum(),
            "Seed Buy": (
                data[signal_col].astype(str).str.upper() == "SEED BUY"
            ).sum(),
            "Seed Watch": (
                data[signal_col].astype(str).str.upper() == "SEED WATCH"
            ).sum(),
            "WATCH": data[signal_col].astype(str).str.contains(
                "WATCH",
                regex=False,
            ).sum(),
            "EARLY": data[signal_col].astype(str).str.contains(
                "EARLY",
                regex=False,
            ).sum(),
            "SKIP": (
                data[signal_col] == "SKIP"
            ).sum(),
            "EXTENDED": (
                data[signal_col] == "EXTENDED"
            ).sum(),
            "Avg Score": round(
                data[score_col].mean(),
                1,
            ),
            "Max Score": data[score_col].max(),
        })

    print(
        pd.DataFrame(summary_rows).to_string(
            index=False
        )
    )

    for market in ("SET", "USA"):

        top = (
            df[df["Market"] == market]
            .sort_values(
                by=score_col,
                ascending=False
            )
            .head(10)
        )

        print(f"\n========== TOP {market} ==========\n")

        if top.empty:
            print("No Result")
            continue

        print(
            top[
                [
                    "Symbol",
                    signal_col,
                    setup_col,
                    score_col,
                    "Price",
                    "RSI",
                    "RVOL",
                ]
            ].to_string(
                index=False
            )
        )


def save_market_quality_summary(
    df,
    market_scan_seconds,
    last_scan_time,
):

    quality_start = time.perf_counter()
    quality = calculate_market_quality(
        df,
        scan_time_seconds=market_scan_seconds,
        last_scan_time=last_scan_time,
    )
    output_path = save_market_quality(quality)

    print("\n========== MARKET QUALITY ==========\n")
    print(
        quality.to_string(
            index=False
        )
    )
    print(f"\nSaved Market Quality: {output_path}")

    return time.perf_counter() - quality_start, quality


def save_opportunity_summary(df, market_quality):

    opportunity_start = time.perf_counter()
    opportunities = calculate_opportunities(
        df,
        market_quality=market_quality,
    )
    output_path = save_opportunities(opportunities)

    print("\n========== TODAY'S OPPORTUNITIES ==========\n")

    if opportunities.empty:
        print("No opportunities")
    else:
        display_columns = [
            "OpportunityRank",
            "Symbol",
            "Market",
            "OpportunityScore",
            "OpportunityGrade",
            "RecommendedAction",
            "StrategySignal",
            "LifecycleState",
        ]
        display_columns = [
            column
            for column in display_columns
            if column in opportunities.columns
        ]
        print(
            opportunities[display_columns]
            .head(20)
            .to_string(index=False)
        )

    print(f"\nSaved Opportunities: {output_path}")

    return opportunities, time.perf_counter() - opportunity_start


def save_priority_summary(opportunities, market_quality):

    priority_start = time.perf_counter()
    prioritized = apply_priority_mode(
        opportunities,
        "Seed First",
        market_quality_df=market_quality,
        ai_recommended_priority="Seed First",
        ai_recommendation_reason=(
            "Default scanner priority after each run."
        ),
    )
    output_path = save_priority_results(prioritized)

    print("\n========== PRIORITY RESULTS ==========\n")

    if prioritized.empty:
        print("No priority results")
    else:
        display_columns = [
            "PriorityRank",
            "Symbol",
            "Market",
            "PriorityScore",
            "PriorityAction",
            "PriorityMode",
            "OpportunityScore",
            "StrategySignal",
            "LifecycleState",
        ]
        display_columns = [
            column
            for column in display_columns
            if column in prioritized.columns
        ]
        print(
            prioritized[display_columns]
            .head(20)
            .to_string(index=False)
        )

    print(f"\nSaved Priority Results: {output_path}")

    return prioritized, time.perf_counter() - priority_start


def load_portfolio_for_ai(path=os.path.join("data", "portfolio.csv")):

    if not os.path.exists(path):
        return None

    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(
            f"WARNING: Could not load portfolio for AI decisions: {exc}"
        )
        return None


def save_ai_decision_summary(priority_results):

    ai_start = time.perf_counter()
    decisions = pd.DataFrame()

    try:
        decisions = build_ai_decisions(
            priority_results,
            portfolio_dataframe=load_portfolio_for_ai(),
        )
        output_path = save_ai_decisions(decisions)

        print("\n========== AI DECISION SUMMARY ==========\n")

        if decisions.empty or "AIDecision" not in decisions.columns:
            print("No AI decisions")
        else:
            counts = decisions["AIDecision"].value_counts().to_dict()

            for decision in [
                "BUY",
                "PREPARE",
                "WATCH",
                "HOLD",
                "ADD",
                "REDUCE",
                "EXIT",
                "AVOID",
                "NO_ACTION",
            ]:
                print(f"{decision}: {int(counts.get(decision, 0))}")

        print(f"\nSaved AI Decisions: {output_path}")

    except Exception as exc:
        print(
            f"WARNING: AI Decision Engine failed, scanner output preserved: {exc}"
        )

    return decisions, time.perf_counter() - ai_start


def account_context_from_portfolio(portfolio, config):

    account = {
        "AccountEquity": config.account_equity,
        "AvailableCash": config.available_cash,
    }

    if portfolio is None or portfolio.empty:
        return account

    data = portfolio.copy()

    if "Status" in data.columns:
        open_positions = data[
            data["Status"].fillna("").astype(str).str.upper() == "OPEN"
        ].copy()
    else:
        open_positions = data.copy()

    if open_positions.empty:
        account["TotalExposure"] = 0
        account["OpenPositions"] = 0
        return account

    for column in [
        "CurrentValue",
        "NetCost",
        "BuyAmount",
    ]:
        if column in open_positions.columns:
            values = pd.to_numeric(
                open_positions[column],
                errors="coerce",
            ).fillna(0)
            total = float(values.sum())

            if total > 0:
                account["TotalExposure"] = total
                break
    else:
        account["TotalExposure"] = 0

    account["OpenPositions"] = int(len(open_positions))

    return account


def save_risk_manager_summary(ai_decisions):

    risk_start = time.perf_counter()

    try:
        config = load_risk_config()
        portfolio = load_portfolio_for_ai()
        account = account_context_from_portfolio(
            portfolio,
            config,
        )
        proposals = build_order_proposals(
            ai_decisions,
            portfolio_dataframe=portfolio,
            account=account,
            config=config,
        )
        proposal_path = save_order_proposals(proposals)
        summary = build_risk_summary(
            proposals,
            account=account,
            config=config,
        )
        summary_path = save_risk_summary(summary)

        print("\n========== RISK MANAGER SUMMARY ==========\n")

        if proposals.empty:
            print("No order proposals")
        else:
            pending = int((proposals["ProposalStatus"] == "PENDING_APPROVAL").sum())
            rejected = int((proposals["ProposalStatus"] == "REJECTED").sum())
            no_proposal = int((proposals["ProposalStatus"] == "NO_PROPOSAL").sum())
            buy_value = float(
                pd.to_numeric(
                    proposals[
                        proposals["ProposalAction"].isin(["BUY", "ADD"])
                    ]["ProposedOrderValue"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )
            sell_value = float(
                pd.to_numeric(
                    proposals[
                        proposals["ProposalAction"].isin(["REDUCE", "EXIT"])
                    ]["ProposedOrderValue"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )
            projected_exposure = 0
            available_cash_after = account.get("AvailableCash", config.available_cash)

            if not summary.empty:
                projected_exposure = float(
                    summary.iloc[0].get(
                        "ProjectedExposurePct",
                        0,
                    )
                )
                available_cash_after = float(
                    summary.iloc[0].get(
                        "EstimatedCashAfter",
                        available_cash_after,
                    )
                )

            print(f"Pending Approval: {pending}")
            print(f"Rejected: {rejected}")
            print(f"No Proposal: {no_proposal}")
            print(f"BUY Value: {buy_value:,.2f}")
            print(f"SELL Value: {sell_value:,.2f}")
            print(f"Projected Exposure: {projected_exposure:,.2f}%")
            print(f"Available Cash After: {available_cash_after:,.2f}")

        print(f"\nSaved Order Proposals: {proposal_path}")
        print(f"Saved Risk Summary: {summary_path}")

        try:
            approval_queue, _ = sync_approval_queue(proposals)
            approval_summary = build_approval_summary(approval_queue)

            if not approval_summary.empty:
                approval_row = approval_summary.iloc[0]
                print("\n========== APPROVAL QUEUE SUMMARY ==========\n")
                print(f"Pending: {int(approval_row.get('Pending', 0))}")
                print(f"Approved: {int(approval_row.get('Approved', 0))}")
                print(f"Rejected: {int(approval_row.get('Rejected', 0))}")
                print(f"Expired: {int(approval_row.get('Expired', 0))}")
                print(f"Cancelled: {int(approval_row.get('Cancelled', 0))}")
                print(
                    "Ready For Paper Broker: "
                    f"{int(approval_row.get('ReadyForPaperBroker', 0))}"
                )

                paper_config = load_paper_broker_config()
                paper_account = load_paper_account(config=paper_config)
                paper_portfolio = load_paper_portfolio()
                paper_summary = calculate_portfolio_summary(
                    paper_portfolio,
                    paper_account,
                )
                daily_state = load_daily_state(
                    paper_account,
                    paper_config,
                    persist=False,
                )
                ready = ready_for_paper_broker(approval_queue)
                executed_today = int(
                    (
                        approval_queue["Status"].astype(str).str.upper()
                        == "EXECUTED"
                    ).sum()
                )

                print("\n========== PAPER BROKER STATUS ==========\n")
                print(f"Execution Mode: {paper_config.execution_mode}")
                print(f"Approved Ready: {len(ready)}")
                print(f"Executed Today: {executed_today}")
                print(f"Open Positions: {paper_summary.get('OpenPositions', 0)}")
                print(f"Cash: {paper_summary.get('Cash', 0):,.2f}")
                print(f"Total Equity: {paper_summary.get('TotalEquity', 0):,.2f}")
                print(
                    "Daily Loss Lock: "
                    f"{'ON' if daily_state.get('LossLimitTriggered') else 'OFF'}"
                )

        except Exception as exc:
            print(
                f"WARNING: Approval Queue failed, scanner output preserved: {exc}"
            )

    except Exception as exc:
        print(
            f"WARNING: Risk Manager failed, scanner output preserved: {exc}"
        )

    return time.perf_counter() - risk_start


def show_scan_duration(scan_timings, total_time):

    if not scan_timings:
        return

    summary = pd.DataFrame(scan_timings)
    total_download = summary["Download Time"].sum()
    total_indicators = summary["Indicator Time"].sum()
    total_decision = summary["Decision Time"].sum()
    total_processing = summary["Processing Time"].sum()
    total_cache_hits = summary["Indicator Cache Hits"].sum()
    total_row = {
        "Index": "TOTAL",
        "Market": "ALL",
        "Symbols": int(summary["Symbols"].sum()),
        "Download Time": round(total_download, 2),
        "Indicator Time": round(total_indicators, 2),
        "Decision Time": round(total_decision, 2),
        "Indicator Cache Hits": int(total_cache_hits),
        "Processing Time": round(total_processing, 2),
        "Total Time": round(total_time, 2),
    }
    summary = pd.concat(
        [
            summary,
            pd.DataFrame([total_row]),
        ],
        ignore_index=True,
    )

    print("\n========== SCAN DURATION SUMMARY ==========\n")
    print(
        summary[
            [
                "Index",
                "Market",
                "Symbols",
                "Download Time",
                "Processing Time",
                "Total Time",
            ]
        ].to_string(
            index=False
        )
    )


def build_profile_rows(
    scan_timings,
    mode,
    workers,
    export_time,
    quality_time,
    alert_time,
    total_time,
):

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []

    for timing in scan_timings:
        rows.append({
            "RunTimestamp": timestamp,
            "Mode": mode,
            "Index": timing["Index"],
            "Market": timing["Market"],
            "Workers": workers,
            "Symbols": timing["Symbols"],
            "Download": timing["Download Time"],
            "Indicators": timing["Indicator Time"],
            "Decision": timing["Decision Time"],
            "Processing": timing["Processing Time"],
            "IndicatorCacheHits": timing["Indicator Cache Hits"],
            "Export": 0.0,
            "Quality": 0.0,
            "Alerts": 0.0,
            "Total": timing["Total Time"],
        })

    if scan_timings:
        scan_df = pd.DataFrame(scan_timings)
        rows.append({
            "RunTimestamp": timestamp,
            "Mode": mode,
            "Index": "TOTAL",
            "Market": "ALL",
            "Workers": workers,
            "Symbols": int(scan_df["Symbols"].sum()),
            "Download": round(scan_df["Download Time"].sum(), 2),
            "Indicators": round(scan_df["Indicator Time"].sum(), 2),
            "Decision": round(scan_df["Decision Time"].sum(), 2),
            "Processing": round(scan_df["Processing Time"].sum(), 2),
            "IndicatorCacheHits": int(scan_df["Indicator Cache Hits"].sum()),
            "Export": round(export_time, 2),
            "Quality": round(quality_time, 2),
            "Alerts": round(alert_time, 2),
            "Total": round(total_time, 2),
        })

    return pd.DataFrame(rows)


def save_profile_report(profile):

    if profile.empty:
        return

    profile.to_csv(
        PROFILE_FILE,
        index=False,
    )


def show_performance_report(profile):

    if profile.empty:
        return

    display = profile[
        [
            "Mode",
            "Index",
            "Market",
            "Download",
            "Indicators",
            "Decision",
            "Export",
            "Quality",
            "Alerts",
            "Total",
        ]
    ]

    print("\n========== PERFORMANCE REPORT ==========\n")
    print(
        display.to_string(
            index=False,
        )
    )
    print(f"\nSaved Scanner Profile: {PROFILE_FILE}")


def main(
    force_refresh=False,
    mode="ALL",
    workers=MAX_WORKERS,
    strategy_mode="standard",
):

    all_results = []
    market_scan_seconds = defaultdict(float)
    scan_timings = []
    total_start = time.perf_counter()
    scan_plan = resolve_scan_plan(mode)
    strategy_mode = normalize_strategy_mode(strategy_mode)

    if force_refresh:
        print("\nPRICE CACHE : Force refresh enabled\n")

    print(f"\nSCAN MODE   : {mode}")
    print(f"MAX WORKERS : {workers}\n")
    print(f"STRATEGY    : {strategy_mode_label(strategy_mode)}\n")

    for index, market in scan_plan:

        df, timing = scan_market(
            index=index,
            market=market,
            force_refresh=force_refresh,
            workers=workers,
            strategy_mode=strategy_mode,
        )

        market_scan_seconds[market.upper()] += timing["Total Time"]
        scan_timings.append(timing)

        all_results.append(df)

    df = pd.concat(
        all_results,
        ignore_index=True
    )

    before_dedupe = len(df)

    if not df.empty:
        df = df.drop_duplicates(
            subset=[
                "Symbol",
                "Market",
            ],
            keep="first",
        )

    removed = before_dedupe - len(df)

    if removed:
        print(
            f"Removed duplicate symbols: {removed}"
        )

    if df.empty:

        print("No Stocks")

        return

    df = update_lifecycle_from_scan(
        df,
        strategy_mode=strategy_mode,
    )
    df["ScanMode"] = mode

    df = df.sort_values(
        by="StrategyScore"
        if "StrategyScore" in df.columns
        else "Score",
        ascending=False
    )

    quality_time, market_quality = save_market_quality_summary(
        df,
        market_scan_seconds,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    df, opportunity_time = save_opportunity_summary(
        df,
        market_quality,
    )

    df, priority_time = save_priority_summary(
        df,
        market_quality,
    )
    ai_decisions, _ = save_ai_decision_summary(df)
    save_risk_manager_summary(ai_decisions)

    df = df.sort_values(
        by="PriorityScore"
        if "PriorityScore" in df.columns
        else "OpportunityScore"
        if "OpportunityScore" in df.columns
        else "StrategyScore"
        if "StrategyScore" in df.columns
        else "Score",
        ascending=False,
    )

    export_time = save_results(df)

    alert_time = run_watchlist_alerts(df)

    show_summary(df)

    total_time = time.perf_counter() - total_start
    profile = build_profile_rows(
        scan_timings=scan_timings,
        mode=mode,
        workers=workers,
        export_time=export_time,
        quality_time=quality_time,
        alert_time=alert_time,
        total_time=total_time,
    )
    save_profile_report(profile)
    show_performance_report(profile)

    show_scan_duration(
        scan_timings,
        total_time,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run River Alpha Scanner"
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore today's price cache and download fresh prices.",
    )
    parser.add_argument(
        "--mode",
        default="ALL",
        help=(
            "Scan mode: ALL, SET50, SET100, SET All, "
            "USA Watchlist, USA All."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help="Parallel worker count for indicator and decision processing.",
    )
    parser.add_argument(
        "--strategy-mode",
        default="standard",
        choices=STRATEGY_MODE_CLI_CHOICES,
        help=(
            "Scanner strategy mode: standard, early, pure_early, "
            "breakout, momentum."
        ),
    )
    args = parser.parse_args()

    main(
        force_refresh=args.force_refresh,
        mode=args.mode,
        workers=args.workers,
        strategy_mode=args.strategy_mode,
    )
