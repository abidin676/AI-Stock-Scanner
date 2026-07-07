from datetime import datetime
from pathlib import Path
import re

import pandas as pd
import yfinance as yf


PRICE_CACHE_DIR = Path("data") / "price_cache"
BATCH_SIZE = 100
HISTORY_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "symbol",
    "market",
]


def format_symbol(symbol: str, market: str) -> str:

    symbol = symbol.upper().strip()
    market = market.upper()

    if market == "SET":

        if not symbol.endswith(".BK"):
            symbol += ".BK"

    return symbol


def price_cache_path(
    symbol,
    market="USA",
    period="1y",
    interval="1d",
):

    ticker = format_symbol(
        symbol,
        market,
    )
    key = "_".join(
        [
            str(market).upper().strip(),
            ticker.upper().strip(),
            str(period).strip(),
            str(interval).strip(),
        ]
    )
    filename = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        key,
    )

    return PRICE_CACHE_DIR / f"{filename}.csv"


def is_price_cache_fresh(path):

    if not path.exists():
        return False

    modified_date = datetime.fromtimestamp(
        path.stat().st_mtime
    ).date()

    return modified_date == datetime.now().date()


def normalize_history(df, symbol, market):

    if df.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.copy()
    df.reset_index(inplace=True)
    df.columns = [
        str(col).lower()
        for col in df.columns
    ]

    if "date" not in df.columns and "datetime" in df.columns:
        df = df.rename(
            columns={
                "datetime": "date",
            }
        )

    if "date" not in df.columns and "index" in df.columns:
        df = df.rename(
            columns={
                "index": "date",
            }
        )

    required = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in required:
        if column not in df.columns:
            return pd.DataFrame(columns=HISTORY_COLUMNS)

    df = df.dropna(
        subset=[
            "close",
        ],
        how="all",
    )

    if df.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    df["symbol"] = symbol.upper()
    df["market"] = market.upper()

    return df[HISTORY_COLUMNS]


def load_price_cache(path):

    try:
        df = pd.read_csv(
            path,
            dtype={
                "symbol": "string",
                "market": "string",
            },
            keep_default_na=False,
        )
    except Exception:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    for column in HISTORY_COLUMNS:
        if column not in df.columns:
            return pd.DataFrame(columns=HISTORY_COLUMNS)

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
    ):
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["market"] = df["market"].astype(str).str.upper()

    return df[HISTORY_COLUMNS]


def save_price_cache(path, df):

    PRICE_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    df.to_csv(
        path,
        index=False,
    )


def empty_history():

    return pd.DataFrame(columns=HISTORY_COLUMNS)


def chunks(values, size=BATCH_SIZE):

    for index in range(0, len(values), size):
        yield values[index:index + size]


def extract_ticker_frame(raw, ticker):

    if raw is None or raw.empty:
        return pd.DataFrame()

    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy()

    level_zero = raw.columns.get_level_values(0)
    level_one = raw.columns.get_level_values(1)

    if ticker in level_zero:
        return raw[ticker].copy()

    if ticker in level_one:
        return raw.xs(
            ticker,
            axis=1,
            level=1,
        ).copy()

    return pd.DataFrame()


def download_batch(symbols, market, period="1y", interval="1d"):

    ticker_map = {
        format_symbol(
            symbol,
            market,
        ): symbol
        for symbol in symbols
    }
    tickers = list(ticker_map.keys())
    results = {
        symbol: empty_history()
        for symbol in symbols
    }

    if not tickers:
        return results

    try:
        raw = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception:
        return results

    for ticker, symbol in ticker_map.items():
        frame = extract_ticker_frame(
            raw,
            ticker,
        )
        results[symbol] = normalize_history(
            frame,
            symbol,
            market,
        )

    return results


def get_histories(
    symbols,
    market="USA",
    period="1y",
    interval="1d",
    force_refresh=False,
):

    symbols = [
        str(symbol).upper().strip()
        for symbol in symbols
        if str(symbol).strip()
    ]
    histories = {}
    missing = []

    for symbol in symbols:
        cache_path = price_cache_path(
            symbol,
            market,
            period,
            interval,
        )

        if not force_refresh and is_price_cache_fresh(cache_path):
            histories[symbol] = load_price_cache(cache_path)
            continue

        missing.append(symbol)

    for batch_symbols in chunks(missing):
        downloaded = download_batch(
            batch_symbols,
            market,
            period,
            interval,
        )

        for symbol in batch_symbols:
            df = downloaded.get(
                symbol,
                empty_history(),
            )
            cache_path = price_cache_path(
                symbol,
                market,
                period,
                interval,
            )
            save_price_cache(
                cache_path,
                df,
            )
            histories[symbol] = df

    return histories


def get_history(
    symbol,
    market="USA",
    period="1y",
    interval="1d",
    force_refresh=False,
):

    histories = get_histories(
        [
            symbol,
        ],
        market=market,
        period=period,
        interval=interval,
        force_refresh=force_refresh,
    )

    return histories.get(
        str(symbol).upper().strip(),
        empty_history(),
    )
