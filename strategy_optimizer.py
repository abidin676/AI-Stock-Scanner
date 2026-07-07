from itertools import product
from pathlib import Path

import pandas as pd

from backtest_engine import (
    prepare_history,
    run_strategy_lab_from_history,
)


OUTPUT_DIR = Path("output")
OPTIMIZER_FILE = OUTPUT_DIR / "optimizer_results.csv"
OPTIMIZER_COLUMNS = [
    "MinScore",
    "StopLossPct",
    "TargetPct",
    "MaxHoldingDays",
    "TrailingStopPct",
    "TotalTrades",
    "WinRate",
    "ProfitFactor",
    "TotalReturnPct",
    "MaxDrawdown",
    "FinalEquity",
    "AvgRR",
]


def build_parameter_range(start, end, step, as_int=False):

    start = float(start)
    end = float(end)
    step = float(step)

    if step <= 0:
        raise ValueError("Step must be greater than 0")

    if end < start:
        raise ValueError("Range end must be greater than or equal to start")

    values = []
    current = start

    while current <= end + (step / 1000):
        values.append(
            int(round(current))
            if as_int
            else round(current, 4)
        )
        current += step

    return values


def count_optimizer_combinations(
    min_scores,
    stop_loss_pcts,
    target_pcts,
    max_holding_days,
    trailing_stop_pcts,
):

    return (
        len(min_scores)
        * len(stop_loss_pcts)
        * len(target_pcts)
        * len(max_holding_days)
        * len(trailing_stop_pcts)
    )


def summary_value(summary, column, default=0):

    if summary is None or summary.empty or column not in summary.columns:
        return default

    return summary.iloc[0].get(
        column,
        default,
    )


def numeric(value, default=0):

    try:
        if pd.isna(value):
            return default

        return float(value)
    except (TypeError, ValueError):
        return default


def optimizer_row(
    min_score,
    stop_loss_pct,
    target_pct,
    max_holding_days,
    trailing_stop_pct,
    summary,
):

    return {
        "MinScore": numeric(min_score),
        "StopLossPct": numeric(stop_loss_pct),
        "TargetPct": numeric(target_pct),
        "MaxHoldingDays": int(max_holding_days),
        "TrailingStopPct": numeric(trailing_stop_pct),
        "TotalTrades": int(
            numeric(
                summary_value(
                    summary,
                    "Total Trades",
                    0,
                )
            )
        ),
        "WinRate": numeric(
            summary_value(
                summary,
                "Win Rate",
                0,
            )
        ),
        "ProfitFactor": numeric(
            summary_value(
                summary,
                "Profit Factor",
                0,
            )
        ),
        "TotalReturnPct": numeric(
            summary_value(
                summary,
                "Total Return %",
                0,
            )
        ),
        "MaxDrawdown": numeric(
            summary_value(
                summary,
                "Max Drawdown %",
                0,
            )
        ),
        "FinalEquity": numeric(
            summary_value(
                summary,
                "Final Equity",
                0,
            )
        ),
        "AvgRR": numeric(
            summary_value(
                summary,
                "Average RR",
                0,
            )
        ),
    }


def save_optimizer_results(results):

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )
    results.to_csv(
        OPTIMIZER_FILE,
        index=False,
    )

    return OPTIMIZER_FILE


def run_strategy_optimizer(
    symbol,
    market,
    start_date,
    end_date,
    min_scores,
    stop_loss_pcts,
    target_pcts,
    max_holding_days,
    trailing_stop_pcts,
    progress_callback=None,
):

    history = prepare_history(
        symbol,
        market,
        start_date,
        end_date,
    )
    combinations = list(
        product(
            min_scores,
            stop_loss_pcts,
            target_pcts,
            max_holding_days,
            trailing_stop_pcts,
        )
    )
    rows = []
    total = len(combinations)

    for index, (
        min_score,
        stop_loss_pct,
        target_pct,
        max_holding_day,
        trailing_stop_pct,
    ) in enumerate(combinations, start=1):
        _, summary, _, _ = run_strategy_lab_from_history(
            symbol=symbol,
            market=market,
            history=history,
            start_date=start_date,
            end_date=end_date,
            min_score=min_score,
            enable_stop_loss=stop_loss_pct > 0,
            stop_loss_pct=stop_loss_pct,
            enable_target=target_pct > 0,
            target_pct=target_pct,
            enable_max_holding_days=max_holding_day > 0,
            max_holding_days=max_holding_day,
            enable_trailing_stop=trailing_stop_pct > 0,
            trailing_stop_pct=trailing_stop_pct,
            save_output=False,
        )
        rows.append(
            optimizer_row(
                min_score,
                stop_loss_pct,
                target_pct,
                max_holding_day,
                trailing_stop_pct,
                summary,
            )
        )

        if progress_callback:
            progress_callback(
                index,
                total,
                rows[-1],
            )

    results = pd.DataFrame(
        rows,
        columns=OPTIMIZER_COLUMNS,
    )

    if not results.empty:
        results = results.sort_values(
            [
                "ProfitFactor",
                "TotalReturnPct",
            ],
            ascending=[
                False,
                False,
            ],
        ).reset_index(drop=True)

    save_optimizer_results(results)

    return results
