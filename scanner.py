import os
import time
import argparse
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict
import pandas as pd

from providers.thai import get_symbols
from candidate_eligibility import apply_eligibility_policy
from data import get_histories, is_price_cache_fresh, price_cache_path
from fresh_cross_policy import evaluate_fresh_cross_policy
from fresh_cross_policy import AUTHORITATIVE_CROSS_AGE_SOURCE
from fresh_cross_candidates import save_candidate_ranking_outputs
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
from runtime_io import atomic_write_csv, atomic_write_excel
from scan_metadata import build_scan_metadata, save_scan_manifest, save_scan_metadata
from config import (
    PERIOD,
    INTERVAL,
    MAX_FRESH_CROSS_DAYS,
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
SCAN_FAILURES_FILE = os.path.join(
    OUTPUT_DIR,
    "scan_failures.csv",
)
SCAN_OUTPUT_FILES = [
    os.path.join(OUTPUT_DIR, CSV_FILE),
    os.path.join(OUTPUT_DIR, EXCEL_FILE),
    os.path.join(OUTPUT_DIR, "market_quality.csv"),
    os.path.join(OUTPUT_DIR, "opportunity_results.csv"),
    os.path.join(OUTPUT_DIR, "priority_results.csv"),
    os.path.join(OUTPUT_DIR, "ai_decisions.csv"),
    os.path.join(OUTPUT_DIR, "order_proposals.csv"),
    os.path.join(OUTPUT_DIR, "risk_summary.csv"),
    os.path.join(OUTPUT_DIR, "scan_metadata.json"),
    os.path.join(OUTPUT_DIR, "scan_failures.csv"),
    os.path.join(OUTPUT_DIR, "scan_run_manifest.json"),
    os.path.join(OUTPUT_DIR, "fresh_cross_candidates.csv"),
    os.path.join(OUTPUT_DIR, "candidate_ranking_audit.csv"),
]

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


def output_file_timestamps(paths):

    timestamps = {}

    for path in paths:
        if not os.path.exists(path):
            timestamps[path] = "MISSING"
            continue

        timestamps[path] = datetime.fromtimestamp(
            os.path.getmtime(path)
        ).strftime("%Y-%m-%d %H:%M:%S")

    return timestamps


def market_diagnostic_totals(scan_metadata):

    diagnostics = scan_metadata.get(
        "MarketDiagnostics",
        {},
    )
    values = list(diagnostics.values())

    return {
        "RequestedSymbolCount": sum(int(item.get("RequestedSymbols", 0) or 0) for item in values),
        "DownloadedCount": sum(int(item.get("DownloadedSymbols", 0) or 0) for item in values),
        "ProcessedCount": sum(int(item.get("ProcessedRows", 0) or 0) for item in values),
        "FailedCount": sum(int(item.get("FailedSymbols", 0) or 0) for item in values),
        "CompletedMarkets": [
            item.get("Market")
            for item in values
            if item.get("Status") in {"OK", "PARTIAL"}
            and int(item.get("ProcessedRows", 0) or 0) > 0
        ],
    }


def build_scan_manifest(
    scan_metadata,
    started_at,
    completed_at,
    mode,
    strategy_mode,
    force_refresh,
    workers,
    scanner_rows,
    opportunity_rows,
    priority_rows,
    ai_rows,
    proposal_rows,
):

    totals = market_diagnostic_totals(scan_metadata)

    return {
        "ScanRunId": scan_metadata.get("ScanRunId", ""),
        "StartedAt": started_at,
        "CompletedAt": completed_at,
        "RequestedMode": scan_metadata.get("RequestedScanMode", mode),
        "RequestedMarkets": scan_metadata.get("ExpectedMarkets", []),
        "CompletedMarkets": totals["CompletedMarkets"],
        "StrategyMode": strategy_mode_label(strategy_mode),
        "ForceRefresh": bool(force_refresh),
        "Workers": int(workers or MAX_WORKERS),
        "RequestedSymbolCount": totals["RequestedSymbolCount"],
        "DownloadedCount": totals["DownloadedCount"],
        "ProcessedCount": totals["ProcessedCount"],
        "FailedCount": totals["FailedCount"],
        "ScannerRowCount": int(scanner_rows),
        "OpportunityRowCount": int(opportunity_rows),
        "PriorityRowCount": int(priority_rows),
        "AIDecisionRowCount": int(ai_rows),
        "OrderProposalRowCount": int(proposal_rows),
        "Status": scan_metadata.get("ScanStatus", "UNKNOWN"),
        "ErrorSummary": " | ".join(scan_metadata.get("Warnings", [])),
        "OutputFileTimestamps": output_file_timestamps(SCAN_OUTPUT_FILES),
    }


def save_scan_failures(failures):

    columns = [
        "ScanRunId",
        "Index",
        "Market",
        "Symbol",
        "Reason",
        "Detail",
    ]
    data = pd.DataFrame(failures, columns=columns)
    atomic_write_csv(
        data,
        SCAN_FAILURES_FILE,
        index=False,
    )
    return SCAN_FAILURES_FILE


def normalize_scan_mode(mode):

    return str(mode or "ALL").upper().replace("_", " ").strip()


def resolve_scan_plan(mode="ALL"):

    key = normalize_scan_mode(mode)

    if key not in SCAN_MODE_PLANS:
        raise ValueError(f"Unknown scan mode: {mode}")

    return SCAN_MODE_PLANS[key]


def incomplete_requested_markets(scan_metadata):

    diagnostics = scan_metadata.get("MarketDiagnostics", {})
    incomplete = []

    for market in scan_metadata.get("ExpectedMarkets", []):
        market = str(market).upper()
        diagnostic = diagnostics.get(market, {})
        processed_rows = int(
            scan_metadata.get(
                f"{market}SymbolsProcessed",
                0,
            )
            or 0
        )

        if (
            str(diagnostic.get("Status", "")).upper() == "FAILED"
            or processed_rows <= 0
        ):
            incomplete.append(market)

    return incomplete


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


def _float_or_none(value):

    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_price_date(value):

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return str(value)


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
    previous = df.iloc[-2] if len(df) >= 2 else pd.Series(dtype="object")
    latest_ema9 = _float_or_none(latest.get("ema9", None))
    latest_ema20 = _float_or_none(latest.get("ema20", None))
    previous_ema9 = _float_or_none(previous.get("ema9", None))
    previous_ema20 = _float_or_none(previous.get("ema20", None))
    ema9_above_ema20 = (
        latest_ema9 is not None
        and latest_ema20 is not None
        and latest_ema9 > latest_ema20
    )
    days_since_ema_cross = _float_or_none(
        latest.get("days_since_ema9_cross_ema20", None)
    )
    bullish_cross_event = (
        latest_ema9 is not None
        and latest_ema20 is not None
        and previous_ema9 is not None
        and previous_ema20 is not None
        and latest_ema9 > latest_ema20
        and previous_ema9 <= previous_ema20
    )
    ema_bullish_cross_today = (
        days_since_ema_cross == 0
        and bullish_cross_event
    )
    latest_price_date = _format_price_date(latest.get("date", ""))
    cross_date = _format_price_date(latest.get("ema9_cross_date", ""))
    fresh_cross = evaluate_fresh_cross_policy(
        {
            "EMA9": latest_ema9,
            "EMA20": latest_ema20,
            "DaysSinceEMA9CrossEMA20": days_since_ema_cross,
            "LatestPriceDate": latest_price_date,
            "CrossDate": cross_date,
            "CrossAgeSource": AUTHORITATIVE_CROSS_AGE_SOURCE,
            "PreviousEMA9": previous_ema9,
            "PreviousEMA20": previous_ema20,
            "BullishCrossEvent": bullish_cross_event,
        }
    )
    ema_cross_within_fresh_days = (
        fresh_cross.age is not None
        and fresh_cross.age <= MAX_FRESH_CROSS_DAYS
    )
    is_fresh_ema9_cross = fresh_cross.eligible

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
            "DaysSinceEMA9CrossEMA20": days_since_ema_cross,
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
            "LatestPriceDate": latest_price_date,
            "CrossDate": cross_date,
            "EMA9": latest.get("ema9", 0),
            "EMA20": latest.get("ema20", 0),
            "PreviousEMA9": previous_ema9,
            "PreviousEMA20": previous_ema20,
            "EMA50": latest.get("ema50", 0),
            "EMA200": latest.get("ema200", 0),
            "EMA9AboveEMA20": ema9_above_ema20,
            "EMABullishCrossToday": ema_bullish_cross_today,
            "BullishCrossEvent": bullish_cross_event,
            "EMACrossWithinFreshDays": ema_cross_within_fresh_days,
            "IsFreshEMA9Cross": is_fresh_ema9_cross,
            "FreshCrossEligible": is_fresh_ema9_cross,
            "FreshCrossStatus": fresh_cross.status,
            "FreshCrossStatusLabel": fresh_cross.status_label,
            "FreshCrossReason": fresh_cross.reason,
            "CrossAgeSource": AUTHORITATIVE_CROSS_AGE_SOURCE,
            "Top5EligibilityReason": "PENDING_CANONICAL_RANK",
            "DaysSinceEMACross": days_since_ema_cross,
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
    provider_name = (
        "providers.thai.get_symbols"
        if market == "SET"
        else "providers.usa.get_symbols"
    )
    cached_count = 0
    download_count = 0

    for symbol in symbols:
        cache_path = price_cache_path(
            symbol,
            market,
            PERIOD,
            INTERVAL,
        )
        if not force_refresh and is_price_cache_fresh(cache_path):
            cached_count += 1
        else:
            download_count += 1

    results = []
    payloads = []
    failures = []
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
    loaded_count = sum(
        1
        for symbol in symbols
        if not histories.get(symbol, pd.DataFrame()).empty
    )
    no_data_count = max(len(symbols) - loaded_count, 0)

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
                failures.append({
                    "Index": index,
                    "Market": market,
                    "Symbol": symbol,
                    "Reason": "PROCESS_ERROR",
                    "Detail": str(e),
                })
                continue

            payloads.append(payload)

            if payload["message"]:
                print(f"   {payload['message']}")

            if payload["row"] is not None:
                results.append(payload["row"])
            elif payload.get("message"):
                failures.append({
                    "Index": index,
                    "Market": market,
                    "Symbol": symbol,
                    "Reason": payload.get("message", "NO_ROW"),
                    "Detail": payload.get("error") or "",
                })

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
        "SymbolsRequested": len(symbols),
        "LoadedCount": loaded_count,
        "RowsProcessed": len(results),
        "NoDataCount": no_data_count,
        "FailedCount": len(failures),
        "CachedCount": cached_count,
        "DownloadedCount": download_count,
        "ErrorCount": 0,
        "ProviderName": provider_name,
        "Status": "FAILED"
        if len(symbols) == 0 or loaded_count == 0
        else "PARTIAL"
        if failures
        else "OK",
        "Error": "",
        "_FailureRows": failures,
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
        atomic_write_csv(df, csv_path, index=False)

    if SAVE_EXCEL:
        atomic_write_excel(df, excel_path, index=False)

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
    scan_run_id=None,
):

    quality_start = time.perf_counter()
    quality = calculate_market_quality(
        df,
        scan_time_seconds=market_scan_seconds,
        last_scan_time=last_scan_time,
        scan_run_id=scan_run_id,
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
    prioritized = apply_eligibility_policy(prioritized)
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
    proposals = pd.DataFrame()
    summary = pd.DataFrame()

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
        if "ScanRunId" in proposals.columns and not summary.empty:
            scan_run_ids = (
                proposals["ScanRunId"]
                .dropna()
                .astype(str)
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )
            summary["ScanRunId"] = scan_run_ids[0] if scan_run_ids else ""
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

    return time.perf_counter() - risk_start, proposals, summary


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

    atomic_write_csv(
        profile,
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
    symbol_counts = defaultdict(int)
    market_errors = defaultdict(str)
    scan_failures = []
    total_start = time.perf_counter()
    scan_plan = resolve_scan_plan(mode)
    strategy_mode = normalize_strategy_mode(strategy_mode)
    scan_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scan_completed_at = scan_started_at
    scan_run_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    if force_refresh:
        print("\nPRICE CACHE : Force refresh enabled\n")

    print(f"\nSCAN MODE   : {mode}")
    print(f"SCAN RUN ID : {scan_run_id}")
    print(f"MAX WORKERS : {workers}\n")
    print(f"STRATEGY    : {strategy_mode_label(strategy_mode)}\n")

    for index, market in scan_plan:

        market_key = str(market).upper()

        try:
            df, timing = scan_market(
                index=index,
                market=market,
                force_refresh=force_refresh,
                workers=workers,
                strategy_mode=strategy_mode,
            )
        except Exception as exc:
            error_message = str(exc)
            print(
                f"\nWARNING: {market_key} scan failed for {index}: "
                f"{error_message}\n"
            )
            df = pd.DataFrame()
            timing = {
                "Index": index,
                "Market": market_key,
                "Symbols": 0,
                "SymbolsRequested": 0,
                "LoadedCount": 0,
                "RowsProcessed": 0,
                "NoDataCount": 0,
                "FailedCount": 0,
                "CachedCount": 0,
                "DownloadedCount": 0,
                "ErrorCount": 1,
                "ProviderName": "providers.thai.get_symbols"
                if market_key == "SET"
                else "providers.usa.get_symbols",
                "Status": "FAILED",
                "Error": error_message,
                "_FailureRows": [
                    {
                        "Index": index,
                        "Market": market_key,
                        "Symbol": "",
                        "Reason": "MARKET_SCAN_FAILED",
                        "Detail": error_message,
                    }
                ],
                "Download Time": 0.0,
                "Indicator Time": 0.0,
                "Decision Time": 0.0,
                "Indicator Cache Hits": 0,
                "Processing Time": 0.0,
                "Total Time": 0.0,
            }

        market_scan_seconds[market_key] += timing["Total Time"]
        scan_timings.append(timing)
        symbol_counts[market_key] += int(
            timing.get("SymbolsRequested", timing.get("Symbols", 0)) or 0
        )
        if timing.get("Error"):
            market_errors[market_key] = str(timing.get("Error"))
        for failure in timing.get("_FailureRows", []):
            failure = dict(failure)
            failure["ScanRunId"] = scan_run_id
            scan_failures.append(failure)

        all_results.append(df)

    df = (
        pd.concat(
            all_results,
            ignore_index=True
        )
        if all_results
        else pd.DataFrame()
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

    result_rows = (
        df.groupby("Market").size().to_dict()
        if "Market" in df.columns and not df.empty
        else {}
    )
    scan_completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scan_metadata = build_scan_metadata(
        requested_mode=mode,
        scan_timings=scan_timings,
        result_rows=result_rows,
        symbol_counts=symbol_counts,
        errors=market_errors,
        completed_at=scan_completed_at,
        scan_run_id=scan_run_id,
    )
    failures_path = save_scan_failures(scan_failures)
    print(f"Saved Scan Failures: {failures_path}")

    for warning in scan_metadata.get("Warnings", []):
        print(f"WARNING: {warning}")

    incomplete_markets = incomplete_requested_markets(scan_metadata)

    if incomplete_markets:
        print(
            "ERROR: Scan did not produce usable results for requested "
            f"market(s): {', '.join(incomplete_markets)}"
        )
        return 1

    if df.empty:

        print("No Stocks")

        return 1

    df = update_lifecycle_from_scan(
        df,
        strategy_mode=strategy_mode,
    )
    df["ScanMode"] = mode
    df["RequestedScanMode"] = scan_metadata["RequestedScanMode"]
    df["ExecutedScanMode"] = scan_metadata["ExecutedScanMode"]
    df["ScanCompletedAt"] = scan_metadata["ScanCompletedAt"]
    df["ScanStatus"] = scan_metadata["ScanStatus"]
    df["ScanRunId"] = scan_metadata["ScanRunId"]

    df = df.sort_values(
        by="StrategyScore"
        if "StrategyScore" in df.columns
        else "Score",
        ascending=False
    )

    quality_time, market_quality = save_market_quality_summary(
        df,
        market_scan_seconds,
        scan_completed_at,
        scan_run_id=scan_metadata["ScanRunId"],
    )

    opportunity_results, opportunity_time = save_opportunity_summary(
        df,
        market_quality,
    )

    priority_results, priority_time = save_priority_summary(
        opportunity_results,
        market_quality,
    )
    ai_decisions, ai_time = save_ai_decision_summary(priority_results)
    ranking_source = (
        ai_decisions
        if ai_decisions is not None and not ai_decisions.empty
        else priority_results
    )
    (
        fresh_cross_candidates,
        candidate_ranking_audit,
        fresh_candidates_path,
        ranking_audit_path,
    ) = save_candidate_ranking_outputs(ranking_source)
    print(
        "\nSaved Fresh Cross Candidates: "
        f"{fresh_candidates_path} ({len(fresh_cross_candidates)} rows)"
    )
    print(
        "Saved Candidate Ranking Audit: "
        f"{ranking_audit_path} ({len(candidate_ranking_audit)} rows)"
    )
    risk_time, risk_proposals, risk_summary = save_risk_manager_summary(ai_decisions)

    df = priority_results
    audit_columns = [
        "Symbol",
        "Market",
        "FreshCrossEligible",
        "Rank",
        "IncludedInTop5",
        "Top5EligibilityReason",
        "ExclusionReason",
    ]
    audit_debug = candidate_ranking_audit[audit_columns].rename(
        columns={"Rank": "CanonicalRank"}
    )
    df = df.drop(
        columns=[
            "FreshCrossEligible",
            "CanonicalRank",
            "IncludedInTop5",
            "Top5EligibilityReason",
            "ExclusionReason",
        ],
        errors="ignore",
    ).merge(
        audit_debug,
        on=["Symbol", "Market"],
        how="left",
    )

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

    # Publish completion metadata only after every scan output has succeeded.
    # The dashboard treats this final atomic write as the successful-run marker.
    scan_completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scan_metadata["ScanCompletedAt"] = scan_completed_at
    manifest = build_scan_manifest(
        scan_metadata=scan_metadata,
        started_at=scan_started_at,
        completed_at=scan_completed_at,
        mode=mode,
        strategy_mode=strategy_mode,
        force_refresh=force_refresh,
        workers=workers,
        scanner_rows=len(df),
        opportunity_rows=len(opportunity_results),
        priority_rows=len(priority_results),
        ai_rows=len(ai_decisions),
        proposal_rows=len(risk_proposals),
    )
    manifest_path = save_scan_manifest(manifest)
    manifest["OutputFileTimestamps"] = output_file_timestamps(SCAN_OUTPUT_FILES)
    save_scan_manifest(manifest)
    metadata_path = save_scan_metadata(scan_metadata)
    print(f"\nSaved Scan Manifest: {manifest_path}")
    print(f"Saved Scan Metadata: {metadata_path}")

    return 0


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

    raise SystemExit(
        main(
            force_refresh=args.force_refresh,
            mode=args.mode,
            workers=args.workers,
            strategy_mode=args.strategy_mode,
        )
    )
