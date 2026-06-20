import os
import pandas as pd

WATCHLIST_DIR = "watchlists"

os.makedirs(WATCHLIST_DIR, exist_ok=True)


def save(name, symbols):

    symbols = sorted(set(symbols))

    with open(
        os.path.join(WATCHLIST_DIR, name),
        "w",
        encoding="utf-8"
    ) as f:

        for s in symbols:
            f.write(s + "\n")

    print(f"{name} : {len(symbols)} symbols")


# ==========================
# S&P500
# ==========================
try:

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    table = pd.read_html(url)[0]

    sp500 = table["Symbol"].tolist()

    save("sp500.txt", sp500)

except Exception as e:

    print("SP500 Error :", e)


# ==========================
# Nasdaq100
# ==========================
try:

    url = "https://en.wikipedia.org/wiki/Nasdaq-100"

    tables = pd.read_html(url)

    us100 = []

    for t in tables:

        if "Ticker" in t.columns:
            us100 = t["Ticker"].tolist()
            break

        if "Ticker symbol" in t.columns:
            us100 = t["Ticker symbol"].tolist()
            break

    save("us100.txt", us100)

except Exception as e:

    print("US100 Error :", e)