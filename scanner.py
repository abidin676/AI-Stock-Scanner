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

    print("\n========== SUMMARY ==========\n")

    print(df["Signal"].value_counts())

    print("\nTop 10\n")

    print(
        df.sort_values(
            by="Score",
            ascending=False
        ).head(10)
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
