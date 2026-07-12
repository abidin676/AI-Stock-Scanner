from datetime import datetime
from pathlib import Path

import pandas as pd

from runtime_io import atomic_write_csv


MARKET_QUALITY_FILE = Path("output") / "market_quality.csv"
MARKET_QUALITY_COLUMNS = [
    "Market",
    "StrategyMode",
    "LastScanTime",
    "ScanTimeSeconds",
    "TotalStocks",
    "BuyCount",
    "WatchCount",
    "EarlyCount",
    "SkipCount",
    "ExtendedCount",
    "AvgScore",
    "MaxScore",
    "AvgBuyScore",
    "BuyRatioPct",
    "WatchRatioPct",
    "BreakoutCount",
    "EarlyReversalCount",
    "PullbackCount",
    "QualityScore",
    "QualityLabel",
    "ScanRunId",
]


def is_buy_signal(signal):

    signal = str(signal).upper()

    return (
        "BUY" in signal
        or "ELITE" in signal
    )


def signal_contains(series, text):

    return series.astype(str).str.upper().str.contains(
        text.upper(),
        regex=False,
        na=False,
    )


def setup_contains(series, text):

    return series.astype(str).str.upper().str.contains(
        text.upper(),
        regex=False,
        na=False,
    )


def clamp(value, minimum=0, maximum=100):

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def quality_label(score):

    score = float(score)

    if score >= 80:
        return "🔥 Strong Market"

    if score >= 60:
        return "🟢 Healthy"

    if score >= 40:
        return "🟡 Mixed"

    if score >= 20:
        return "🟠 Weak"

    return "🔴 Avoid"


def safe_numeric(series):

    return pd.to_numeric(
        series,
        errors="coerce",
    ).fillna(0)


def first_existing_column(df, columns, default_name):

    for column in columns:
        if column in df.columns:
            return column

    df[default_name] = ""

    return default_name


def normalize_strategy_columns(df):

    data = df.copy()

    if "Signal" not in data.columns:
        data["Signal"] = ""

    if "Setup" not in data.columns:
        data["Setup"] = ""

    if "Score" not in data.columns:
        data["Score"] = 0

    if "StrategyMode" not in data.columns:
        data["StrategyMode"] = "Standard"

    if "StrategySignal" not in data.columns:
        data["StrategySignal"] = data["Signal"]

    if "StrategySetup" not in data.columns:
        data["StrategySetup"] = data["Setup"]

    if "StrategyScore" not in data.columns:
        data["StrategyScore"] = data["Score"]

    return data


def dominant_strategy_mode(df):

    if df.empty or "StrategyMode" not in df.columns:
        return "Standard"

    modes = (
        df["StrategyMode"]
        .fillna("Standard")
        .astype(str)
        .replace("", "Standard")
    )

    if modes.empty:
        return "Standard"

    return modes.mode().iloc[0]


def count_true(series):

    if series.empty:
        return 0

    return int(
        series.fillna(False).astype(bool).sum()
    )


def normalize_scan_seconds(scan_time_seconds):

    if not scan_time_seconds:
        return {}

    return {
        str(market).upper(): float(seconds)
        for market, seconds in scan_time_seconds.items()
    }


def calculate_quality_score(
    buy_ratio_pct,
    avg_buy_score,
    breakout_ratio_pct,
    max_score,
):

    score = (
        (buy_ratio_pct / 100 * 30)
        + (avg_buy_score / 100 * 30)
        + (breakout_ratio_pct / 100 * 20)
        + (max_score / 100 * 20)
    )

    return round(
        clamp(score),
        2,
    )


def calculate_market_quality(
    results,
    scan_time_seconds=None,
    last_scan_time=None,
    markets=("SET", "USA"),
    scan_run_id=None,
):

    scan_time_seconds = normalize_scan_seconds(
        scan_time_seconds
    )
    last_scan_time = (
        last_scan_time
        or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    rows = []

    if results is None:
        results = pd.DataFrame()

    df = normalize_strategy_columns(results)
    if scan_run_id is None and "ScanRunId" in df.columns:
        scan_run_ids = (
            df["ScanRunId"]
            .dropna()
            .astype(str)
            .replace("", pd.NA)
            .dropna()
            .unique()
            .tolist()
        )
        scan_run_id = scan_run_ids[0] if scan_run_ids else ""

    if "Market" not in df.columns:
        df["Market"] = ""

    for market in markets:
        market = str(market).upper()
        data = df[
            df["Market"].astype(str).str.upper() == market
        ].copy()
        strategy_mode = dominant_strategy_mode(data)
        total_stocks = int(len(data))
        scores = safe_numeric(
            data["StrategyScore"]
        )
        buy_mask = data["StrategySignal"].apply(
            is_buy_signal
        )
        buy_count = count_true(
            buy_mask
        )
        watch_count = count_true(
            signal_contains(
                data["StrategySignal"],
                "WATCH",
            )
        )
        early_count = count_true(
            signal_contains(
                data["StrategySignal"],
                "EARLY",
            )
        )
        skip_count = count_true(
            signal_contains(
                data["StrategySignal"],
                "SKIP",
            )
        )
        extended_count = count_true(
            signal_contains(
                data["StrategySignal"],
                "EXTENDED",
            )
        )
        breakout_mask = setup_contains(
            data["StrategySetup"],
            "Breakout",
        ) & ~setup_contains(
            data["StrategySetup"],
            "Pre-Breakout",
        )
        breakout_count = count_true(
            breakout_mask
        )
        early_reversal_count = count_true(
            setup_contains(
                data["StrategySetup"],
                "Early Reversal",
            )
        )
        pullback_count = count_true(
            setup_contains(
                data["StrategySetup"],
                "Pullback",
            )
        )
        avg_score = (
            scores.mean()
            if total_stocks
            else 0
        )
        max_score = (
            scores.max()
            if total_stocks
            else 0
        )
        buy_scores = scores[buy_mask]
        avg_buy_score = (
            buy_scores.mean()
            if buy_count
            else 0
        )
        buy_ratio_pct = (
            buy_count / total_stocks * 100
            if total_stocks
            else 0
        )
        watch_ratio_pct = (
            watch_count / total_stocks * 100
            if total_stocks
            else 0
        )
        breakout_ratio_pct = (
            breakout_count / total_stocks * 100
            if total_stocks
            else 0
        )
        quality_score = calculate_quality_score(
            buy_ratio_pct,
            avg_buy_score,
            breakout_ratio_pct,
            max_score,
        )

        rows.append({
            "Market": market,
            "StrategyMode": strategy_mode,
            "LastScanTime": last_scan_time,
            "ScanTimeSeconds": round(
                scan_time_seconds.get(
                    market,
                    0,
                ),
                2,
            ),
            "TotalStocks": total_stocks,
            "BuyCount": buy_count,
            "WatchCount": watch_count,
            "EarlyCount": early_count,
            "SkipCount": skip_count,
            "ExtendedCount": extended_count,
            "AvgScore": round(avg_score, 2),
            "MaxScore": round(max_score, 2),
            "AvgBuyScore": round(avg_buy_score, 2),
            "BuyRatioPct": round(buy_ratio_pct, 2),
            "WatchRatioPct": round(watch_ratio_pct, 2),
            "BreakoutCount": breakout_count,
            "EarlyReversalCount": early_reversal_count,
            "PullbackCount": pullback_count,
            "QualityScore": quality_score,
            "QualityLabel": quality_label(quality_score),
            "ScanRunId": scan_run_id or "",
        })

    return pd.DataFrame(
        rows,
        columns=MARKET_QUALITY_COLUMNS,
    )


def ensure_market_quality_columns(df):

    data = df.copy()

    for column in MARKET_QUALITY_COLUMNS:
        if column not in data.columns:
            data[column] = None

    return data[MARKET_QUALITY_COLUMNS]


def load_market_quality(path=MARKET_QUALITY_FILE):

    path = Path(path)

    if not path.exists():
        return pd.DataFrame(
            columns=MARKET_QUALITY_COLUMNS
        )

    try:
        data = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        data = pd.DataFrame(
            columns=MARKET_QUALITY_COLUMNS
        )

    return ensure_market_quality_columns(data)


def save_market_quality(quality, path=MARKET_QUALITY_FILE):

    path = Path(path)
    path.parent.mkdir(
        exist_ok=True
    )
    current = load_market_quality(path)
    quality = ensure_market_quality_columns(quality)
    combined = pd.concat(
        [
            current,
            quality,
        ],
        ignore_index=True,
    )
    atomic_write_csv(
        combined,
        path,
        index=False,
    )

    return path


def quality_trend(latest_score, previous_score):

    if previous_score is None or pd.isna(previous_score):
        return "N/A"

    latest_score = float(latest_score)
    previous_score = float(previous_score)

    if latest_score > previous_score:
        return "▲"

    if latest_score < previous_score:
        return "▼"

    return "—"


def latest_market_quality_with_trend(history):

    if history is None or history.empty:
        return pd.DataFrame(
            columns=MARKET_QUALITY_COLUMNS + ["Trend"]
        )

    data = ensure_market_quality_columns(history)
    data = data.copy()
    data["_scan_time"] = pd.to_datetime(
        data["LastScanTime"],
        errors="coerce",
    )
    data["_row_order"] = range(len(data))
    rows = []

    group_columns = [
        "Market",
        "StrategyMode",
    ]

    for _, group in data.groupby(group_columns, dropna=False):
        group = group.sort_values(
            [
                "_scan_time",
                "_row_order",
            ],
            na_position="first",
        )
        latest = group.iloc[-1].copy()
        previous_score = None

        if len(group) >= 2:
            previous_score = pd.to_numeric(
                group.iloc[-2].get(
                    "QualityScore",
                    None,
                ),
                errors="coerce",
            )

        latest["Trend"] = quality_trend(
            pd.to_numeric(
                latest.get(
                    "QualityScore",
                    0,
                ),
                errors="coerce",
            ),
            previous_score,
        )
        rows.append(
            latest.drop(
                labels=[
                    "_scan_time",
                    "_row_order",
                ]
            )
        )

    return pd.DataFrame(rows)
