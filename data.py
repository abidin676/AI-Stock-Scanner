import yfinance as yf
import pandas as pd


def format_symbol(symbol: str, market: str) -> str:

    symbol = symbol.upper().strip()
    market = market.upper()

    if market == "SET":

        # ถ้ามี .BK อยู่แล้ว ไม่ต้องเติม
        if symbol.endswith(".BK"):
            return symbol

        return symbol + ".BK"

    return symbol


def get_history(
    symbol,
    market="USA",
    period="1y",
    interval="1d"
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

    # แก้ปัญหา MultiIndex ของ yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)

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