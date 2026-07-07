from datetime import datetime
from pathlib import Path

import pandas as pd


MARKET_QUALITY_FILE = Path("output") / "market_quality.csv"
MARKET_QUALITY_COLUMNS = [
    "Market",
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

    df = results.copy()

    if "Market" not in df.columns:
        df["Market"] = ""

    if "Signal" not in df.columns:
        df["Signal"] = ""

    if "Setup" not in df.columns:
        df["Setup"] = ""

    if "Score" not in df.columns:
        df["Score"] = 0

    for market in markets:
        market = str(market).upper()
        data = df[
            df["Market"].astype(str).str.upper() == market
        ].copy()
        total_stocks = int(len(data))
        scores = safe_numeric(
            data["Score"]
        )
        buy_mask = data["Signal"].apply(
            is_buy_signal
        )
        buy_count = int(
            buy_mask.sum()
        )
        watch_count = int(
            signal_contains(
                data["Signal"],
                "WATCH",
            ).sum()
        )
        early_count = int(
            signal_contains(
                data["Signal"],
                "EARLY",
            ).sum()
        )
        skip_count = int(
            signal_contains(
                data["Signal"],
                "SKIP",
            ).sum()
        )
        extended_count = int(
            signal_contains(
                data["Signal"],
                "EXTENDED",
            ).sum()
        )
        breakout_count = int(
            setup_contains(
                data["Setup"],
                "Breakout",
            ).sum()
        )
        early_reversal_count = int(
            setup_contains(
                data["Setup"],
                "Early Reversal",
            ).sum()
        )
        pullback_count = int(
            setup_contains(
                data["Setup"],
                "Pullback",
            ).sum()
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
    combined.to_csv(
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

    for market, group in data.groupby("Market", dropna=False):
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
