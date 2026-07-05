from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path
import io

import pandas as pd
import yfinance as yf

from data import format_symbol
from fee_engine import calculate_fee
from indicators import add_indicators
from strategy import trend_start


OUTPUT_DIR = Path("output")
TRADES_FILE = OUTPUT_DIR / "backtest_trades.csv"
SUMMARY_FILE = OUTPUT_DIR / "backtest_summary.csv"
EQUITY_FILE = OUTPUT_DIR / "backtest_equity_curve.csv"
TRADE_COLUMNS = [
    "Symbol",
    "Market",
    "EntryDate",
    "ExitDate",
    "EntryPrice",
    "ExitPrice",
    "HoldingDays",
    "Signal",
    "Setup",
    "Score",
    "StopLoss",
    "Target",
    "ExitReason",
    "GrossReturnPct",
    "NetReturnPct",
    "WinLoss",
]
SUMMARY_COLUMNS = [
    "Total Trades",
    "Win Rate",
    "Avg Gain",
    "Avg Loss",
    "Avg Return",
    "Best Trade",
    "Worst Trade",
    "Profit Factor",
    "Expectancy",
    "Max Drawdown",
]


def signal_matches(signal, signal_filter):

    signal = str(signal).upper()
    filters = signal_filter

    if isinstance(filters, str):
        filters = [filters]

    filters = [
        str(item).upper()
        for item in filters
        if str(item).strip()
    ]

    if not filters or "ALL" in filters:
        return True

    return any(
        item in signal
        for item in filters
    )


def download_history(symbol, market, start_date, end_date):

    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    download_start = start - timedelta(days=420)
    download_end = end + timedelta(days=1)
    ticker = format_symbol(
        symbol,
        market,
    )

    df = yf.download(
        ticker,
        start=download_start.strftime("%Y-%m-%d"),
        end=download_end.strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)
    df.columns = [
        str(column).lower()
        for column in df.columns
    ]
    df["symbol"] = str(symbol).upper().strip()
    df["market"] = str(market).upper().strip()

    return df[
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


def evaluate_day(history, market):

    with redirect_stdout(io.StringIO()):
        return trend_start(
            history,
            market=market,
        )


def calculate_stop_target(row, entry_price):

    atr = float(row.get("atr", 0) or 0)

    if atr <= 0:
        return 0.0, 0.0

    stop_loss = max(
        0.0,
        entry_price - atr,
    )
    target = entry_price + (atr * 2)

    return round(stop_loss, 4), round(target, 4)


def find_exit(df, entry_index, holding_days, stop_loss, target):

    max_index = min(
        entry_index + int(holding_days),
        len(df) - 1,
    )

    for index in range(entry_index + 1, max_index + 1):
        row = df.iloc[index]

        if stop_loss > 0 and float(row["low"]) <= stop_loss:
            return index, stop_loss, "STOP_LOSS"

        if target > 0 and float(row["high"]) >= target:
            return index, target, "TARGET"

    exit_index = max_index
    exit_reason = (
        "HOLDING_DAYS"
        if exit_index > entry_index
        else "END_OF_DATA"
    )

    return (
        exit_index,
        float(df.iloc[exit_index]["close"]),
        exit_reason,
    )


def calculate_trade_returns(entry_price, exit_price, market):

    shares = 1.0
    buy_amount = entry_price * shares
    sell_amount = exit_price * shares
    buy_fee = calculate_fee(
        buy_amount,
        market,
        "BUY",
    )
    sell_fee = calculate_fee(
        sell_amount,
        market,
        "SELL",
    )
    net_cost = buy_amount + buy_fee["total_fee"]
    net_proceeds = sell_amount - sell_fee["total_fee"]
    gross_return_pct = (
        (sell_amount - buy_amount)
        / buy_amount
        * 100
        if buy_amount
        else 0
    )
    net_return_pct = (
        (net_proceeds - net_cost)
        / net_cost
        * 100
        if net_cost
        else 0
    )

    return round(gross_return_pct, 4), round(net_return_pct, 4)


def build_equity_curve(trades):

    if trades.empty:
        return pd.DataFrame(
            columns=[
                "Trade",
                "ExitDate",
                "Equity",
                "DrawdownPct",
            ]
        )

    equity = 1.0
    rows = []
    peak = equity

    for index, trade in trades.reset_index(drop=True).iterrows():
        equity *= 1 + (
            float(trade["NetReturnPct"])
            / 100
        )
        peak = max(
            peak,
            equity,
        )
        drawdown = (
            equity / peak - 1
        ) * 100

        rows.append({
            "Trade": index + 1,
            "ExitDate": trade["ExitDate"],
            "Equity": round(equity, 6),
            "DrawdownPct": round(drawdown, 4),
        })

    return pd.DataFrame(rows)


def calculate_summary(trades, equity_curve=None):

    if trades.empty:
        return pd.DataFrame([
            {
                column: 0
                for column in SUMMARY_COLUMNS
            }
        ])

    returns = pd.to_numeric(
        trades["NetReturnPct"],
        errors="coerce",
    ).fillna(0)
    gains = returns[returns > 0]
    losses = returns[returns < 0]
    total_gain = gains.sum()
    total_loss = losses.sum()
    profit_factor = (
        total_gain / abs(total_loss)
        if total_loss < 0
        else 0
    )

    if equity_curve is None:
        equity_curve = build_equity_curve(trades)

    max_drawdown = (
        equity_curve["DrawdownPct"].min()
        if not equity_curve.empty
        else 0
    )

    return pd.DataFrame([
        {
            "Total Trades": int(len(trades)),
            "Win Rate": round((returns > 0).mean() * 100, 2),
            "Avg Gain": round(gains.mean(), 4) if not gains.empty else 0,
            "Avg Loss": round(losses.mean(), 4) if not losses.empty else 0,
            "Avg Return": round(returns.mean(), 4),
            "Best Trade": round(returns.max(), 4),
            "Worst Trade": round(returns.min(), 4),
            "Profit Factor": round(profit_factor, 4),
            "Expectancy": round(returns.mean(), 4),
            "Max Drawdown": round(float(max_drawdown), 4),
        }
    ])


def save_results(trades, summary, equity_curve):

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )
    trades.to_csv(
        TRADES_FILE,
        index=False,
    )
    summary.to_csv(
        SUMMARY_FILE,
        index=False,
    )
    equity_curve.to_csv(
        EQUITY_FILE,
        index=False,
    )


def run_backtest(
    symbol,
    market,
    start_date,
    end_date,
    holding_days,
    min_score,
    signal_filter,
):

    market = str(market).upper().strip()
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    holding_days = int(holding_days)
    min_score = float(min_score)
    df = download_history(
        symbol,
        market,
        start,
        end,
    )

    if df.empty:
        trades = pd.DataFrame(columns=TRADE_COLUMNS)
        summary = calculate_summary(trades)
        equity_curve = build_equity_curve(trades)
        save_results(
            trades,
            summary,
            equity_curve,
        )
        return trades, summary, equity_curve

    df = add_indicators(df)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    trades = []

    for index in range(len(df)):
        row = df.iloc[index]

        if row["date"] < start or row["date"] > end:
            continue

        history = df.iloc[:index + 1].copy()
        result = evaluate_day(
            history,
            market,
        )
        score = float(result.get("score", 0) or 0)
        signal = result.get("signal", "")

        if score < min_score:
            continue

        if not signal_matches(
            signal,
            signal_filter,
        ):
            continue

        entry_price = float(row["close"])
        stop_loss, target = calculate_stop_target(
            row,
            entry_price,
        )
        exit_index, exit_price, exit_reason = find_exit(
            df,
            index,
            holding_days,
            stop_loss,
            target,
        )
        exit_row = df.iloc[exit_index]
        gross_return_pct, net_return_pct = calculate_trade_returns(
            entry_price,
            exit_price,
            market,
        )

        trades.append({
            "Symbol": str(symbol).upper().strip(),
            "Market": market,
            "EntryDate": row["date"].date().isoformat(),
            "ExitDate": exit_row["date"].date().isoformat(),
            "EntryPrice": round(entry_price, 4),
            "ExitPrice": round(float(exit_price), 4),
            "HoldingDays": int(exit_index - index),
            "Signal": signal,
            "Setup": result.get("setup", ""),
            "Score": round(score, 2),
            "StopLoss": stop_loss,
            "Target": target,
            "ExitReason": exit_reason,
            "GrossReturnPct": gross_return_pct,
            "NetReturnPct": net_return_pct,
            "WinLoss": "WIN" if net_return_pct > 0 else "LOSS",
        })

    trades_df = pd.DataFrame(
        trades,
        columns=TRADE_COLUMNS,
    )
    equity_curve = build_equity_curve(trades_df)
    summary = calculate_summary(
        trades_df,
        equity_curve,
    )
    save_results(
        trades_df,
        summary,
        equity_curve,
    )

    return trades_df, summary, equity_curve
