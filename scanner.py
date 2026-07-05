import os
import pandas as pd

from providers.thai import get_symbols
from data import get_history
from indicators import add_indicators
from strategy import trend_start
from providers.usa import get_symbols as get_us_symbols
from config import (
    SCAN_MARKETS,
    OUTPUT_FOLDER,
    CSV_FILE,
    EXCEL_FILE,
    SAVE_CSV,
    SAVE_EXCEL,
)

OUTPUT_DIR = OUTPUT_FOLDER
os.makedirs(OUTPUT_DIR, exist_ok=True)

BREAKDOWN_ENGINES = (
    "Trend",
    "Momentum",
    "Volume",
    "Base",
    "Breakout",
    "Price",
    "Stage",
)


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


def scan_market(index="SET", market="SET"):

    market = (market or "SET").upper()

    if market.upper() == "SET":
        symbols = get_symbols(index)

    elif market.upper() == "USA":
        symbols = get_us_symbols(index)

    else:
        raise ValueError(f"Unknown market: {market}")

    results = []

    print(f"\n========== SCANNING {index} ==========\n")
    print(f"Total Symbols : {len(symbols)}\n")

    for i, symbol in enumerate(symbols, start=1):

        print(f"[{i}/{len(symbols)}] {symbol}")

        try:
            df = get_history(symbol, market)

            if df.empty:
                print("   No Data")
                continue

            df = add_indicators(df)
            result = trend_start(
                df,
                market=market,
            )

            results.append({
                "Symbol": symbol,
                "Market": market,
                "Signal": result["signal"],
                "Setup": result["setup"],
                "Score": result["score"],
                "Price": result["price"],
                "RSI": result["rsi"],
                "RVOL": result["rvol"],
                "Reasons": ", ".join(result["reasons"])
            })

            print(
                f"   {result['signal']} | "
                f"Score {result['score']}"
            )

            if is_buy_candidate(result["signal"]):
                print_score_breakdown(
                    symbol,
                    result,
                )

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


def main():

    all_results = []

    for index, market in SCAN_MARKETS:

        df = scan_market(
            index=index,
            market=market
        )

        all_results.append(df)

    df = pd.concat(
        all_results,
        ignore_index=True
    )

    if df.empty:

        print("No Stocks")

        return

    df = df.sort_values(
        by="Score",
        ascending=False
    )

    save_results(df)

    show_summary(df)


if __name__ == "__main__":
    main()
