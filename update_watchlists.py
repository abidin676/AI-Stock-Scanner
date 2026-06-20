"""
Update Watchlists
----------------------------------
Downloads latest stock lists and
saves them into watchlists/

Author : AI Stock Scanner
"""

from pathlib import Path
import pandas as pd

WATCHLIST_DIR = Path("watchlists")
WATCHLIST_DIR.mkdir(exist_ok=True)


# =====================================
# Save helper
# =====================================

def save_list(filename, symbols):

    symbols = sorted(set(symbols))

    path = WATCHLIST_DIR / filename

    with open(path, "w", encoding="utf-8") as f:

        for s in symbols:
            f.write(s + "\n")

    print(f"✓ {filename} ({len(symbols)} symbols)")


# =====================================
# SET50
# =====================================

SET50 = [
    "ADVANC","AOT","AWC","BBL","BDMS","BEM","BGRIM","BH",
    "CBG","CPALL","CPF","CPN","CRC","DELTA","EA","EGCO",
    "GLOBAL","GPSC","GULF","HMPRO","KBANK","KTB","KTC",
    "MINT","MTC","OR","OSP","PTT","PTTEP","PTTGC",
    "RATCH","SCB","SCC","TOP","TRUE","TTB","TU","WHA"
]

save_list(
    "set50.txt",
    SET50
)


# =====================================
# SET100
# =====================================

try:

    tables = pd.read_html(
        "https://en.wikipedia.org/wiki/SET100_Index"
    )

    df = tables[0]

    symbols = []

    for col in df.columns:

        if "Symbol" in str(col):

            symbols = df[col].tolist()

            break

    symbols = [
        s.replace(".BK", "").strip().upper()
        for s in symbols
    ]

    if symbols:
        save_list(
            "set100.txt",
            symbols
        )

except Exception as e:

    print("SET100 :", e)


# =====================================
# NASDAQ-100
# =====================================

try:

    df = pd.read_html(
        "https://en.wikipedia.org/wiki/Nasdaq-100"
    )[4]

    symbols = (
        df["Ticker"]
        .str.replace(".", "-", regex=False)
        .tolist()
    )

    save_list(
        "us100.txt",
        symbols
    )

except Exception as e:

    print("US100 :", e)


# =====================================
# S&P500
# =====================================

try:

    df = pd.read_html(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    )[0]

    symbols = (
        df["Symbol"]
        .str.replace(".", "-", regex=False)
        .tolist()
    )

    save_list(
        "sp500.txt",
        symbols
    )

except Exception as e:

    print("SP500 :", e)


print("\nDone.")