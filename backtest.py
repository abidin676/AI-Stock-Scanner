import os
import pandas as pd

from config import SCAN_MARKETS
from providers.thai import get_symbols
from providers.usa import get_symbols as get_us_symbols
from backtest_engine import run_backtest
from backtest_report import create_report

# ==========================================
# OUTPUT
# ==========================================

OUTPUT_DIR = "backtest"

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

# ==========================================
# MAIN
# ==========================================


def main():

    all_trades = []

    for index, market in SCAN_MARKETS:

        print("\n" + "=" * 60)
        print(f"BACKTEST : {market} ({index})")
        print("=" * 60)

        if market == "SET":
            symbols = get_symbols(index)

        else:
            symbols = get_us_symbols(index)

        print(f"Symbols : {len(symbols)}")

        for i, symbol in enumerate(symbols, start=1):

            print(
                f"[{i}/{len(symbols)}] {symbol}"
            )

            try:

                trades = run_backtest(
                    symbol=symbol,
                    market=market,
                )

                if not trades.empty:
                    all_trades.append(trades)

            except Exception as e:

                print(
                    f"ERROR : {symbol} : {e}"
                )

    if len(all_trades) == 0:

        print("\nNo Trades Found")

        return

    trades = pd.concat(
        all_trades,
        ignore_index=True
    )

    trades.to_csv(
        os.path.join(
            OUTPUT_DIR,
            "trades.csv"
        ),
        index=False
    )

    create_report(trades)

    print("\nFinished")

    print(
        os.path.join(
            OUTPUT_DIR,
            "trades.csv"
        )
    )


# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    main()