import pandas as pd

URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"

print("Downloading S&P500 list...")

df = pd.read_csv(URL)

symbols = (
    df["Symbol"]
    .dropna()
    .astype(str)
    .str.strip()
    .str.replace(".", "-", regex=False)
    .sort_values()
    .unique()
)

with open("watchlists/sp500.txt", "w", encoding="utf-8") as f:
    for symbol in symbols:
        f.write(symbol + "\n")

print(f"Saved {len(symbols)} symbols")