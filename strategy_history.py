from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import io
from pathlib import Path

import pandas as pd
import yfinance as yf

from data import format_symbol


DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
HISTORY_FILE = DATA_DIR / "strategy_history.csv"
BENCHMARK_FILE = OUTPUT_DIR / "strategy_lab_benchmark.csv"
DEFAULT_VERSION = "River Alpha Strategy v1"

HISTORY_COLUMNS = [
    "RunID",
    "RunTimestamp",
    "Market",
    "Symbol",
    "StartDate",
    "EndDate",
    "MinScore",
    "StopLossEnabled",
    "StopLossPct",
    "TargetEnabled",
    "TargetPct",
    "TrailingEnabled",
    "TrailingPct",
    "MaxHoldingEnabled",
    "MaxHoldingDays",
    "InitialCapital",
    "TotalTrades",
    "WinRate",
    "ProfitFactor",
    "AverageReturn",
    "AverageHoldingDays",
    "MaxDrawdown",
    "FinalEquity",
    "TotalReturnPct",
    "BestTrade",
    "WorstTrade",
    "WinningTrades",
    "LosingTrades",
    "Version",
]

BENCHMARK_COLUMNS = [
    "Benchmark",
    "Ticker",
    "Date",
    "Close",
    "BenchmarkReturnPct",
    "BenchmarkEquity",
    "BenchmarkDrawdownPct",
]

BENCHMARK_COMPARISON_COLUMNS = [
    "Metric",
    "River Alpha",
    "Benchmark",
    "Difference",
]


def _empty_history():

    return pd.DataFrame(
        columns=HISTORY_COLUMNS
    )


def _empty_benchmark():

    return pd.DataFrame(
        columns=BENCHMARK_COLUMNS
    )


def _write_history(df):

    DATA_DIR.mkdir(
        exist_ok=True
    )
    df.to_csv(
        HISTORY_FILE,
        index=False,
    )


def _ensure_history_file():

    DATA_DIR.mkdir(
        exist_ok=True
    )

    if not HISTORY_FILE.exists():
        _write_history(
            _empty_history()
        )


def _to_bool(value):

    if isinstance(value, str):
        return value.strip().lower() in (
            "true",
            "1",
            "yes",
            "y",
        )

    return bool(value)


def _to_float(value, default=0):

    try:
        if pd.isna(value):
            return float(default)

        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _to_int(value, default=0):

    try:
        if pd.isna(value):
            return int(default)

        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _summary_value(summary, column, default=0):

    if summary is None or summary.empty or column not in summary.columns:
        return default

    return summary.iloc[0].get(
        column,
        default,
    )


def _average_return(trades):

    if trades is None or trades.empty or "NetReturnPct" not in trades.columns:
        return 0

    return pd.to_numeric(
        trades["NetReturnPct"],
        errors="coerce",
    ).fillna(0).mean()


def _win_loss_count(trades, value):

    if trades is None or trades.empty or "WinLoss" not in trades.columns:
        return 0

    return int(
        (
            trades["WinLoss"].astype(str).str.upper()
            == value
        ).sum()
    )


def _next_run_id(history):

    if history.empty or "RunID" not in history.columns:
        return 1

    run_ids = pd.to_numeric(
        history["RunID"],
        errors="coerce",
    ).dropna()

    if run_ids.empty:
        return 1

    return int(run_ids.max()) + 1


def load_strategy_history():

    _ensure_history_file()

    try:
        history = pd.read_csv(HISTORY_FILE)
    except pd.errors.EmptyDataError:
        history = _empty_history()

    changed = False

    for column in HISTORY_COLUMNS:
        if column not in history.columns:
            history[column] = None
            changed = True

    history = history[HISTORY_COLUMNS]

    if changed:
        _write_history(history)

    return history


def save_strategy_run(
    market,
    symbol,
    start_date,
    end_date,
    min_score,
    summary,
    trades,
    stop_loss_enabled=False,
    stop_loss_pct=0,
    target_enabled=False,
    target_pct=0,
    trailing_enabled=False,
    trailing_pct=0,
    max_holding_enabled=False,
    max_holding_days=0,
    initial_capital=100000,
    version=DEFAULT_VERSION,
):

    history = load_strategy_history()
    run_id = _next_run_id(history)
    total_trades = _to_int(
        _summary_value(
            summary,
            "Total Trades",
            0,
        )
    )

    row = {
        "RunID": run_id,
        "RunTimestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Market": str(market).upper().strip(),
        "Symbol": str(symbol).upper().strip(),
        "StartDate": pd.to_datetime(start_date).date().isoformat(),
        "EndDate": pd.to_datetime(end_date).date().isoformat(),
        "MinScore": _to_float(min_score),
        "StopLossEnabled": _to_bool(stop_loss_enabled),
        "StopLossPct": _to_float(stop_loss_pct),
        "TargetEnabled": _to_bool(target_enabled),
        "TargetPct": _to_float(target_pct),
        "TrailingEnabled": _to_bool(trailing_enabled),
        "TrailingPct": _to_float(trailing_pct),
        "MaxHoldingEnabled": _to_bool(max_holding_enabled),
        "MaxHoldingDays": _to_int(max_holding_days),
        "InitialCapital": _to_float(initial_capital),
        "TotalTrades": total_trades,
        "WinRate": _to_float(
            _summary_value(
                summary,
                "Win Rate",
                0,
            )
        ),
        "ProfitFactor": _to_float(
            _summary_value(
                summary,
                "Profit Factor",
                0,
            )
        ),
        "AverageReturn": round(
            _to_float(
                _average_return(trades)
            ),
            4,
        ),
        "AverageHoldingDays": _to_float(
            _summary_value(
                summary,
                "Avg Holding Days",
                0,
            )
        ),
        "MaxDrawdown": _to_float(
            _summary_value(
                summary,
                "Max Drawdown %",
                0,
            )
        ),
        "FinalEquity": _to_float(
            _summary_value(
                summary,
                "Final Equity",
                initial_capital,
            )
        ),
        "TotalReturnPct": _to_float(
            _summary_value(
                summary,
                "Total Return %",
                0,
            )
        ),
        "BestTrade": _to_float(
            _summary_value(
                summary,
                "Best Trade",
                0,
            )
        ),
        "WorstTrade": _to_float(
            _summary_value(
                summary,
                "Worst Trade",
                0,
            )
        ),
        "WinningTrades": _win_loss_count(
            trades,
            "WIN",
        ),
        "LosingTrades": _win_loss_count(
            trades,
            "LOSS",
        ),
        "Version": version or DEFAULT_VERSION,
    }

    updated = pd.concat(
        [
            history,
            pd.DataFrame(
                [
                    row,
                ],
                columns=HISTORY_COLUMNS,
            ),
        ],
        ignore_index=True,
    )
    _write_history(updated)

    return row


def _history_row(run_id):

    history = load_strategy_history()
    matches = history[
        pd.to_numeric(
            history["RunID"],
            errors="coerce",
        )
        == int(run_id)
    ]

    if matches.empty:
        return None

    return matches.iloc[0]


def _better_metric(metric, value_a, value_b):

    if pd.isna(value_a) or pd.isna(value_b):
        return ""

    lower_is_better = {
        "Max Drawdown",
        "Average Holding Days",
    }

    if metric in lower_is_better:
        if abs(value_a) == abs(value_b):
            return ""

        return "A" if abs(value_a) < abs(value_b) else "B"

    if value_a == value_b:
        return ""

    return "A" if value_a > value_b else "B"


def compare_runs(run_id_a, run_id_b):

    row_a = _history_row(run_id_a)
    row_b = _history_row(run_id_b)

    if row_a is None or row_b is None:
        return pd.DataFrame(
            columns=[
                "Metric",
                "RunA",
                "RunB",
                "Better",
            ]
        )

    metric_map = [
        (
            "Total Return",
            "TotalReturnPct",
        ),
        (
            "Profit Factor",
            "ProfitFactor",
        ),
        (
            "Win Rate",
            "WinRate",
        ),
        (
            "Max Drawdown",
            "MaxDrawdown",
        ),
        (
            "Average Return",
            "AverageReturn",
        ),
        (
            "Average Holding Days",
            "AverageHoldingDays",
        ),
        (
            "Trades",
            "TotalTrades",
        ),
        (
            "Final Equity",
            "FinalEquity",
        ),
    ]

    rows = []

    for metric, column in metric_map:
        value_a = _to_float(
            row_a.get(
                column,
                0,
            )
        )
        value_b = _to_float(
            row_b.get(
                column,
                0,
            )
        )
        rows.append({
            "Metric": metric,
            "RunA": value_a,
            "RunB": value_b,
            "Better": _better_metric(
                metric,
                value_a,
                value_b,
            ),
        })

    return pd.DataFrame(rows)


def _benchmark_candidates(benchmark, symbol, market):

    benchmark = str(benchmark).strip()

    if benchmark == "Buy & Hold":
        return [
            format_symbol(
                symbol,
                market,
            ),
        ]

    mapping = {
        "SET Index": [
            "^SET.BK",
            "SET.BK",
        ],
        "SET50": [
            "^SET50.BK",
            "SET50.BK",
            "TDEX.BK",
        ],
        "SET100": [
            "^SET100.BK",
            "SET100.BK",
            "BSET100.BK",
        ],
        "NASDAQ100": [
            "^NDX",
            "QQQ",
        ],
        "S&P500": [
            "^GSPC",
            "SPY",
        ],
    }

    return mapping.get(
        benchmark,
        [],
    )


def _download_prices(ticker, start_date, end_date):

    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date) + pd.Timedelta(days=1)

    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False,
        )

    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    df.columns = [
        str(column)
        for column in df.columns
    ]

    close_column = "Close" if "Close" in df.columns else "close"
    date_column = "Date" if "Date" in df.columns else "date"

    if close_column not in df.columns or date_column not in df.columns:
        return pd.DataFrame()

    prices = df[
        [
            date_column,
            close_column,
        ]
    ].rename(
        columns={
            date_column: "Date",
            close_column: "Close",
        }
    )
    prices["Date"] = pd.to_datetime(
        prices["Date"],
        errors="coerce",
    ).dt.tz_localize(None)
    prices["Close"] = pd.to_numeric(
        prices["Close"],
        errors="coerce",
    )
    prices = prices.dropna(
        subset=[
            "Date",
            "Close",
        ]
    )

    return prices


def _save_benchmark(df):

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )
    df.to_csv(
        BENCHMARK_FILE,
        index=False,
    )


def load_benchmark(
    benchmark,
    symbol,
    market,
    start_date,
    end_date,
    initial_capital=100000,
):

    if not benchmark or benchmark == "None":
        empty = _empty_benchmark()
        _save_benchmark(empty)
        return empty

    candidates = _benchmark_candidates(
        benchmark,
        symbol,
        market,
    )

    for ticker in candidates:
        prices = _download_prices(
            ticker,
            start_date,
            end_date,
        )

        if prices.empty:
            continue

        initial_close = float(prices.iloc[0]["Close"])

        if initial_close <= 0:
            continue

        result = prices.copy()
        result["Benchmark"] = benchmark
        result["Ticker"] = ticker
        result["BenchmarkReturnPct"] = (
            result["Close"] / initial_close - 1
        ) * 100
        result["BenchmarkEquity"] = (
            float(initial_capital)
            * result["Close"]
            / initial_close
        )
        peak = result["BenchmarkEquity"].cummax()
        result["BenchmarkDrawdownPct"] = (
            result["BenchmarkEquity"] / peak - 1
        ) * 100
        result = result[
            BENCHMARK_COLUMNS
        ].round(
            {
                "Close": 4,
                "BenchmarkReturnPct": 4,
                "BenchmarkEquity": 2,
                "BenchmarkDrawdownPct": 4,
            }
        )
        _save_benchmark(result)

        return result

    empty = _empty_benchmark()
    _save_benchmark(empty)

    return empty


def _annual_return(total_return_pct, start_date, end_date):

    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    days = max(
        int((end - start).days),
        1,
    )
    multiplier = 1 + _to_float(total_return_pct) / 100

    if multiplier <= 0:
        return -100

    return (
        multiplier ** (365 / days) - 1
    ) * 100


def compare_benchmark(
    summary,
    benchmark_curve,
    start_date,
    end_date,
    initial_capital=100000,
):

    if benchmark_curve is None or benchmark_curve.empty:
        return pd.DataFrame(
            columns=BENCHMARK_COMPARISON_COLUMNS
        )

    river_total_return = _to_float(
        _summary_value(
            summary,
            "Total Return %",
            0,
        )
    )
    river_final_equity = _to_float(
        _summary_value(
            summary,
            "Final Equity",
            initial_capital,
        )
    )
    river_max_drawdown = _to_float(
        _summary_value(
            summary,
            "Max Drawdown %",
            0,
        )
    )
    river_annual_return = _annual_return(
        river_total_return,
        start_date,
        end_date,
    )

    benchmark_final_equity = _to_float(
        benchmark_curve.iloc[-1].get(
            "BenchmarkEquity",
            initial_capital,
        )
    )
    benchmark_total_return = (
        (benchmark_final_equity - float(initial_capital))
        / float(initial_capital)
        * 100
        if initial_capital
        else 0
    )
    benchmark_max_drawdown = _to_float(
        benchmark_curve["BenchmarkDrawdownPct"].min()
    )
    benchmark_annual_return = _annual_return(
        benchmark_total_return,
        start_date,
        end_date,
    )

    rows = [
        (
            "Total Return",
            river_total_return,
            benchmark_total_return,
        ),
        (
            "Annual Return",
            river_annual_return,
            benchmark_annual_return,
        ),
        (
            "Max Drawdown",
            river_max_drawdown,
            benchmark_max_drawdown,
        ),
        (
            "Final Equity",
            river_final_equity,
            benchmark_final_equity,
        ),
    ]

    return pd.DataFrame(
        [
            {
                "Metric": metric,
                "River Alpha": round(
                    _to_float(river_value),
                    4,
                ),
                "Benchmark": round(
                    _to_float(benchmark_value),
                    4,
                ),
                "Difference": round(
                    _to_float(river_value)
                    - _to_float(benchmark_value),
                    4,
                ),
            }
            for metric, river_value, benchmark_value in rows
        ],
        columns=BENCHMARK_COMPARISON_COLUMNS,
    )
