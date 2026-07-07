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
from indicators import add_indicators
from strategy import trend_start
from providers.usa import get_symbols as get_us_symbols
from alert_engine import run_watchlist_alert_check
from market_quality import (
    calculate_market_quality,
    save_market_quality,
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


def process_symbol(symbol, market, df):

    if df.empty:
        return {
            "symbol": symbol,
            "row": None,
            "decision": None,
            "error": None,
            "message": "No Data",
        }

    df = add_indicators(df)
    result = trend_start(
        df,
        market=market,
    )

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
            "Reasons": ", ".join(result["reasons"])
        },
        "decision": result,
        "error": None,
        "message": (
            f"{result['signal']} | "
            f"Score {result['score']}"
        ),
    }


def scan_market(
    index="SET",
    market="SET",
    force_refresh=False,
    workers=MAX_WORKERS,
):

    market = (market or "SET").upper()
    symbols = dedupe_symbols(
        load_symbols(
            index,
            market,
        )
    )

    results = []
    total_start = time.perf_counter()

    print(f"\n========== SCANNING {index} ==========\n")
    print(f"Total Symbols : {len(symbols)}\n")
    print(f"Workers       : {workers}\n")

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
    timing = {
        "Index": index,
        "Market": market,
        "Symbols": len(symbols),
        "Download Time": round(download_time, 2),
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
            )

            if payload["row"] is None:
                continue

            results.append(payload["row"])

        except Exception as e:
            print(f"   ERROR : {e}")

    return pd.DataFrame(results)


def save_results(df):

    if df.empty:
        print("\nNo Result")
        return

    csv_path = os.path.join(
        OUTPUT_DIR,
        "scanner_results.csv"
    )

    excel_path = os.path.join(
        OUTPUT_DIR,
        "scanner_results.xlsx"
    )

    df.to_csv(csv_path, index=False)

    df.to_excel(excel_path, index=False)

    print("\nSaved")

    print(csv_path)

    print(excel_path)


def run_watchlist_alerts(df):

    try:
        alerts = run_watchlist_alert_check(df)

        if alerts.empty:
            print("\nWatchlist Alerts : none")
            return

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


def show_summary(df):

    if df.empty:
        return

    print("\n========== MARKET SUMMARY ==========\n")

    summary_rows = []

    for market, data in df.groupby("Market"):

        summary_rows.append({
            "Market": market,
            "Stocks": len(data),
            "Buy Candidates": data["Signal"].apply(
                is_buy_candidate
            ).sum(),
            "WATCH": data["Signal"].astype(str).str.contains(
                "WATCH",
                regex=False,
            ).sum(),
            "EARLY": data["Signal"].astype(str).str.contains(
                "EARLY",
                regex=False,
            ).sum(),
            "SKIP": (
                data["Signal"] == "SKIP"
            ).sum(),
            "EXTENDED": (
                data["Signal"] == "EXTENDED"
            ).sum(),
            "Avg Score": round(
                data["Score"].mean(),
                1,
            ),
            "Max Score": data["Score"].max(),
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
                by="Score",
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
                    "Signal",
                    "Setup",
                    "Score",
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


def show_scan_duration(scan_timings, total_time):

    if not scan_timings:
        return

    summary = pd.DataFrame(scan_timings)
    total_download = summary["Download Time"].sum()
    total_processing = summary["Processing Time"].sum()
    total_row = {
        "Index": "TOTAL",
        "Market": "ALL",
        "Symbols": int(summary["Symbols"].sum()),
        "Download Time": round(total_download, 2),
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
        summary.to_string(
            index=False
        )
    )


def main(force_refresh=False, mode="ALL", workers=MAX_WORKERS):

    all_results = []
    market_scan_seconds = defaultdict(float)
    scan_timings = []
    total_start = time.perf_counter()
    scan_plan = resolve_scan_plan(mode)

    if force_refresh:
        print("\nPRICE CACHE : Force refresh enabled\n")

    print(f"\nSCAN MODE   : {mode}")
    print(f"MAX WORKERS : {workers}\n")

    for index, market in scan_plan:

        df, timing = scan_market(
            index=index,
            market=market,
            force_refresh=force_refresh,
            workers=workers,
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

    df = df.sort_values(
        by="Score",
        ascending=False
    )

    save_results(df)

    save_market_quality_summary(
        df,
        market_scan_seconds,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    run_watchlist_alerts(df)

    show_summary(df)

    show_scan_duration(
        scan_timings,
        time.perf_counter() - total_start,
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
    args = parser.parse_args()

    main(
        force_refresh=args.force_refresh,
        mode=args.mode,
        workers=args.workers,
    )
