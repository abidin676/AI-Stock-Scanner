import yfinance as yf


FX_TICKERS = {
    ("USD", "THB"): "USDTHB=X",
}


def get_fx_rate(from_currency, to_currency="THB"):

    from_currency = str(from_currency).upper().strip()
    to_currency = str(to_currency).upper().strip()

    if from_currency == to_currency:
        return 1.0

    ticker = FX_TICKERS.get(
        (
            from_currency,
            to_currency,
        )
    )

    if ticker is None:
        reverse_ticker = FX_TICKERS.get(
            (
                to_currency,
                from_currency,
            )
        )

        if reverse_ticker is None:
            raise ValueError(
                f"Unsupported FX pair: {from_currency}/{to_currency}"
            )

        reverse_rate = _download_fx_rate(reverse_ticker)

        if reverse_rate <= 0:
            raise ValueError(
                f"Invalid FX rate for {to_currency}/{from_currency}"
            )

        return round(
            1 / reverse_rate,
            6,
        )

    return _download_fx_rate(ticker)


def _download_fx_rate(ticker):

    df = yf.download(
        ticker,
        period="5d",
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No FX data for {ticker}")

    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    close = df["Close"].dropna()

    if close.empty:
        raise ValueError(f"No FX close data for {ticker}")

    return round(
        float(close.iloc[-1]),
        6,
    )
