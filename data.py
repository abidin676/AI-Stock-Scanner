import yfinance as yf
import pandas as pd


def format_symbol(symbol: str, market: str) -> str:

    symbol = symbol.upper().strip()
    market = market.upper()

    if market == "SET":

        if not symbol.endswith(".BK"):
            symbol += ".BK"

    return symbol


def get_history(
    symbol,
    market="USA",
    period="1y",
    interval="1d",
):

    ticker = format_symbol(symbol, market)

    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        return pd.DataFrame()

    # แก้ MultiIndex ของ yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # ย้าย Date มาเป็นคอลัมน์
    df.reset_index(inplace=True)

    # ชื่อคอลัมน์เป็นตัวเล็กทั้งหมด
    df.columns = [str(col).lower() for col in df.columns]

    df["symbol"] = symbol.upper()
    df["market"] = market.upper()

    df = df[
        [
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "symbol",
            "market",
        ]
    ]

    return df

