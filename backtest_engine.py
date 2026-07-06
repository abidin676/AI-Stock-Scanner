from contextlib import redirect_stdout
from dataclasses import dataclass
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
    "EntrySignal",
    "ExitSignal",
    "Setup",
    "EntryScore",
    "ExitScore",
    "ExitReason",
    "GrossReturnPct",
    "NetReturnPct",
    "WinLoss",
]
SUMMARY_COLUMNS = [
    "Total Trades",
    "Win Rate",
    "Avg Return",
    "Avg Holding Days",
    "Profit Factor",
    "Max Drawdown",
]


@dataclass
class Position:

    entry_index: int
    entry_date: pd.Timestamp
    entry_price: float
    entry_signal: str
    setup: str
    entry_score: float
    highest_price: float


@dataclass
class ExitDecision:

    should_exit: bool
    reason: str = ""
    exit_price: float | None = None


class SignalChangeExitRule:

    def __init__(self, exit_groups=None):

        self.exit_groups = exit_groups or (
            "WATCH",
            "SKIP",
        )

    def evaluate(self, position, row, decision, index):

        group = signal_group(
            decision.get("signal", "")
        )

        if group in self.exit_groups:
            return ExitDecision(
                True,
                f"Signal Changed: BUY -> {group}",
            )

        return ExitDecision(False)


class StopLossExitRule:

    def __init__(self, stop_loss_pct):

        self.stop_loss_pct = float(stop_loss_pct)

    def evaluate(self, position, row, decision, index):

        stop_price = position.entry_price * (
            1 - self.stop_loss_pct / 100
        )

        if float(row["low"]) <= stop_price:
            return ExitDecision(
                True,
                f"Stop Loss {self.stop_loss_pct:.2f}%",
                round(stop_price, 4),
            )

        return ExitDecision(False)


class TargetExitRule:

    def __init__(self, target_pct):

        self.target_pct = float(target_pct)

    def evaluate(self, position, row, decision, index):

        target_price = position.entry_price * (
            1 + self.target_pct / 100
        )

        if float(row["high"]) >= target_price:
            return ExitDecision(
                True,
                f"Target {self.target_pct:.2f}%",
                round(target_price, 4),
            )

        return ExitDecision(False)


class MaxHoldingDaysExitRule:

    def __init__(self, max_holding_days):

        self.max_holding_days = int(max_holding_days)

    def evaluate(self, position, row, decision, index):

        holding_days = int(index - position.entry_index)

        if holding_days >= self.max_holding_days:
            return ExitDecision(
                True,
                f"Max Holding Days {self.max_holding_days}",
            )

        return ExitDecision(False)


class TrailingStopExitRule:

    def __init__(self, trailing_stop_pct):

        self.trailing_stop_pct = float(trailing_stop_pct)

    def evaluate(self, position, row, decision, index):

        position.highest_price = max(
            position.highest_price,
            float(row["high"]),
        )
        stop_price = position.highest_price * (
            1 - self.trailing_stop_pct / 100
        )

        if float(row["low"]) <= stop_price:
            return ExitDecision(
                True,
                f"Trailing Stop {self.trailing_stop_pct:.2f}%",
                round(stop_price, 4),
            )

        return ExitDecision(False)


def build_exit_rules(
    enable_stop_loss=False,
    stop_loss_pct=0,
    enable_target=False,
    target_pct=0,
    enable_max_holding_days=False,
    max_holding_days=0,
    enable_trailing_stop=False,
    trailing_stop_pct=0,
):

    rules = []

    if enable_stop_loss and float(stop_loss_pct) > 0:
        rules.append(
            StopLossExitRule(stop_loss_pct)
        )

    if enable_target and float(target_pct) > 0:
        rules.append(
            TargetExitRule(target_pct)
        )

    if enable_trailing_stop and float(trailing_stop_pct) > 0:
        rules.append(
            TrailingStopExitRule(trailing_stop_pct)
        )

    if enable_max_holding_days and int(max_holding_days) > 0:
        rules.append(
            MaxHoldingDaysExitRule(max_holding_days)
        )

    rules.append(
        SignalChangeExitRule()
    )

    return rules


def default_exit_rules():

    return [
        SignalChangeExitRule(),
    ]


def signal_group(signal):

    signal = str(signal).upper()

    if "BUY" in signal:
        return "BUY"

    if "WATCH" in signal:
        return "WATCH"

    if "SKIP" in signal:
        return "SKIP"

    if "EARLY" in signal:
        return "EARLY"

    if "EXTENDED" in signal:
        return "EXTENDED"

    return "OTHER"


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


def is_entry_signal(decision, min_score):

    score = float(
        decision.get("score", 0)
        or 0
    )

    return (
        signal_group(decision.get("signal", "")) == "BUY"
        and score >= float(min_score)
    )


def evaluate_exit(position, row, decision, exit_rules, index):

    for rule in exit_rules:
        result = rule.evaluate(
            position,
            row,
            decision,
            index,
        )

        if result.should_exit:
            return result

    return ExitDecision(False)


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


def close_position(
    symbol,
    market,
    position,
    row,
    decision,
    reason,
    index,
    exit_price=None,
):

    exit_price = (
        float(row["close"])
        if exit_price is None
        else float(exit_price)
    )
    gross_return_pct, net_return_pct = calculate_trade_returns(
        position.entry_price,
        exit_price,
        market,
    )

    return {
        "Symbol": str(symbol).upper().strip(),
        "Market": market,
        "EntryDate": position.entry_date.date().isoformat(),
        "ExitDate": row["date"].date().isoformat(),
        "EntryPrice": round(position.entry_price, 4),
        "ExitPrice": round(exit_price, 4),
        "HoldingDays": int(index - position.entry_index),
        "EntrySignal": position.entry_signal,
        "ExitSignal": decision.get("signal", ""),
        "Setup": position.setup,
        "EntryScore": round(position.entry_score, 2),
        "ExitScore": round(float(decision.get("score", 0) or 0), 2),
        "ExitReason": reason,
        "GrossReturnPct": gross_return_pct,
        "NetReturnPct": net_return_pct,
        "WinLoss": "WIN" if net_return_pct > 0 else "LOSS",
    }


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
            "Avg Return": round(returns.mean(), 4),
            "Avg Holding Days": round(
                pd.to_numeric(
                    trades["HoldingDays"],
                    errors="coerce",
                ).fillna(0).mean(),
                2,
            ),
            "Profit Factor": round(profit_factor, 4),
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


def prepare_history(symbol, market, start_date, end_date):

    df = download_history(
        symbol,
        market,
        start_date,
        end_date,
    )

    if df.empty:
        return df

    df = add_indicators(df)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

    return df


def run_strategy_lab(
    symbol,
    market,
    start_date,
    end_date,
    min_score,
    exit_rules=None,
    enable_stop_loss=False,
    stop_loss_pct=0,
    enable_target=False,
    target_pct=0,
    enable_max_holding_days=False,
    max_holding_days=0,
    enable_trailing_stop=False,
    trailing_stop_pct=0,
):

    market = str(market).upper().strip()
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    min_score = float(min_score)
    exit_rules = exit_rules or build_exit_rules(
        enable_stop_loss=enable_stop_loss,
        stop_loss_pct=stop_loss_pct,
        enable_target=enable_target,
        target_pct=target_pct,
        enable_max_holding_days=enable_max_holding_days,
        max_holding_days=max_holding_days,
        enable_trailing_stop=enable_trailing_stop,
        trailing_stop_pct=trailing_stop_pct,
    )
    df = prepare_history(
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

    trades = []
    position = None

    for index in range(len(df)):
        row = df.iloc[index]

        if row["date"] < start or row["date"] > end:
            continue

        history = df.iloc[:index + 1].copy()
        decision = evaluate_day(
            history,
            market,
        )

        if position is None:
            if is_entry_signal(
                decision,
                min_score,
            ):
                position = Position(
                    entry_index=index,
                    entry_date=row["date"],
                    entry_price=float(row["close"]),
                    entry_signal=decision.get("signal", ""),
                    setup=decision.get("setup", ""),
                    entry_score=float(decision.get("score", 0) or 0),
                    highest_price=float(row["close"]),
                )
            continue

        exit_decision = evaluate_exit(
            position,
            row,
            decision,
            exit_rules,
            index,
        )

        if exit_decision.should_exit:
            trades.append(
                close_position(
                    symbol,
                    market,
                    position,
                    row,
                    decision,
                    exit_decision.reason,
                    index,
                    exit_decision.exit_price,
                )
            )
            position = None

    if position is not None:
        row = df[
            (df["date"] >= start)
            &
            (df["date"] <= end)
        ].iloc[-1]
        history = df.loc[:row.name].copy()
        decision = evaluate_day(
            history,
            market,
        )
        trades.append(
            close_position(
                symbol,
                market,
                position,
                row,
                decision,
                "End of Data",
                int(row.name),
            )
        )

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


def run_backtest(
    symbol,
    market,
    start_date,
    end_date,
    holding_days=None,
    min_score=70,
    signal_filter=None,
):

    return run_strategy_lab(
        symbol=symbol,
        market=market,
        start_date=start_date,
        end_date=end_date,
        min_score=min_score,
    )
