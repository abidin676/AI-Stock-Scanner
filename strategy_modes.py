import math

import pandas as pd


STRATEGY_MODE_CHOICES = [
    "standard",
    "early",
    "pure_early",
    "breakout",
    "momentum",
]
STRATEGY_MODE_LABELS = {
    "standard": "Standard",
    "early": "Early",
    "pure_early": "🌱 Pure Early",
    "breakout": "Breakout",
    "momentum": "Momentum",
}
STRATEGY_MODE_ALIASES = {
    "pure-early": "pure_early",
    "pureearly": "pure_early",
    "seed": "pure_early",
    "ต้นน้ำ": "pure_early",
}
STRATEGY_MODE_CLI_CHOICES = (
    STRATEGY_MODE_CHOICES
    + sorted(STRATEGY_MODE_ALIASES.keys())
)


def normalize_strategy_mode(mode):

    key = (
        str(mode or "standard")
        .strip()
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
    )
    key = STRATEGY_MODE_ALIASES.get(
        key,
        key,
    ).replace("-", "_")

    if key not in STRATEGY_MODE_CHOICES:
        raise ValueError(f"Unknown strategy mode: {mode}")

    return key


def strategy_mode_label(mode):

    return STRATEGY_MODE_LABELS[
        normalize_strategy_mode(mode)
    ]


def safe_float(value, default=0.0):

    try:
        if value is None or pd.isna(value):
            return float(default)

        value = float(value)

        if math.isfinite(value):
            return value
    except (TypeError, ValueError):
        pass

    return float(default)


def safe_bool(value):

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in (
        "true",
        "1",
        "yes",
        "y",
    )


def latest_row(row_or_context):

    if isinstance(row_or_context, pd.DataFrame):
        if row_or_context.empty:
            return {}

        return row_or_context.iloc[-1].to_dict()

    if isinstance(row_or_context, pd.Series):
        return row_or_context.to_dict()

    if isinstance(row_or_context, dict):
        if "row" in row_or_context:
            return latest_row(row_or_context["row"])

        if "df" in row_or_context:
            return latest_row(row_or_context["df"])

        return row_or_context

    return {}


def latest_frame(row_or_context, bars=10):

    if isinstance(row_or_context, pd.DataFrame):
        return row_or_context.tail(bars)

    if isinstance(row_or_context, dict) and "df" in row_or_context:
        df = row_or_context["df"]

        if isinstance(df, pd.DataFrame):
            return df.tail(bars)

    return pd.DataFrame()


def context_decision(row_or_context):

    if isinstance(row_or_context, dict):
        decision = row_or_context.get("decision")

        if isinstance(decision, dict):
            return decision

    return {}


def clamp_score(score):

    return int(
        round(
            max(
                0,
                min(
                    100,
                    safe_float(score),
                ),
            )
        )
    )


def distance_from_ema20(row):

    if "distance_ema20" in row:
        return safe_float(row.get("distance_ema20"))

    close = safe_float(row.get("close"))
    ema20 = safe_float(row.get("ema20"))

    if close <= 0 or ema20 <= 0:
        return 0

    return (
        close / ema20 - 1
    ) * 100


def has_price_data(row):

    return (
        safe_float(row.get("close")) > 0
        and safe_float(row.get("ema20")) > 0
        and safe_float(row.get("rsi")) > 0
    )


def skip_result(mode, setup="SKIP"):

    return {
        "StrategySignal": "SKIP",
        "StrategyScore": 0,
        "StrategySetup": setup,
        "StrategyReasons": [f"{strategy_mode_label(mode)} criteria not met"],
    }


def near(value, target, pct=2.0):

    value = safe_float(value)
    target = safe_float(target)

    if target <= 0:
        return False

    return abs(value - target) / target * 100 <= pct


def contains_any_text(text, terms):

    text = str(text or "").upper()

    return any(
        str(term).upper() in text
        for term in terms
    )


def normalize_strategy_signal(signal):

    signal = str(signal or "").upper()

    if "BUY" in signal:
        return "BUY"

    if "WATCH" in signal:
        return "WATCH"

    if "EARLY" in signal:
        return "EARLY"

    if "EXTENDED" in signal:
        return "EXTENDED"

    if "SKIP" in signal:
        return "SKIP"

    return "OTHER"


def standard_strategy_result(decision):

    decision = decision or {}

    return {
        "StrategySignal": decision.get("signal", "SKIP"),
        "StrategyScore": clamp_score(decision.get("score", 0)),
        "StrategySetup": decision.get("setup", ""),
        "StrategyReasons": decision.get("reasons", []),
    }


def zone_score(value, low, high, ideal=None):

    value = safe_float(value)
    ideal = safe_float(
        ideal,
        (low + high) / 2,
    )

    if low <= value <= high:
        span = max(
            abs(ideal - low),
            abs(high - ideal),
            1,
        )
        return max(
            75,
            100 - abs(value - ideal) / span * 25,
        )

    distance = min(
        abs(value - low),
        abs(value - high),
    )

    return max(
        0,
        70 - distance * 8,
    )


def lower_is_better_score(value, excellent, acceptable):

    value = safe_float(value)

    if value <= excellent:
        return 100

    if value >= acceptable:
        return 0

    return max(
        0,
        100
        - (value - excellent)
        / max(acceptable - excellent, 0.01)
        * 100,
    )


def days_score(days, fresh=5, stale=20, missing_score=55):

    if days is None or pd.isna(days):
        return missing_score

    days = safe_float(days)

    if days <= fresh:
        return 100

    if days >= stale:
        return 0

    return max(
        0,
        100
        - (days - fresh)
        / max(stale - fresh, 1)
        * 100,
    )


def score_higher_lows(row, frame):

    if safe_bool(row.get("higher_low")):
        base_score = 75
    else:
        base_score = 40

    if frame.empty or "low" not in frame.columns:
        return base_score

    lows = pd.to_numeric(
        frame["low"],
        errors="coerce",
    ).dropna()

    if len(lows) < 24:
        return base_score

    recent_low = lows.tail(10).min()
    prior_low = lows.iloc[-30:-10].min()

    if prior_low <= 0:
        return base_score

    if recent_low >= prior_low * 1.02:
        return 100

    if recent_low >= prior_low * 0.99:
        return max(
            base_score,
            75,
        )

    if recent_low >= prior_low * 0.96:
        return max(
            base_score,
            55,
        )

    return min(
        base_score,
        35,
    )


def bool_points(value, points=100):

    return points if safe_bool(value) else 0


def normalized_score(value):

    return max(
        0,
        min(
            100,
            safe_float(value),
        ),
    )


def expansion_component(value, start, full):

    value = safe_float(value)

    if value <= start:
        return 0

    if value >= full:
        return 100

    return max(
        0,
        min(
            100,
            (value - start)
            / max(full - start, 0.01)
            * 100,
        ),
    )


def calculate_expansion_profile(row):

    price_above_low20 = safe_float(
        row.get("price_above_low_close20_pct")
    )
    return_5d = safe_float(row.get("return_5d_pct"))
    return_10d = safe_float(row.get("return_10d_pct"))
    bullish_streak = safe_float(row.get("bullish_candle_streak"))
    wide_bullish_count = safe_float(
        row.get("wide_range_bullish_count_10")
    )
    days_since_breakout = row.get("days_since_breakout")
    momentum_established = safe_bool(
        row.get("momentum_established")
    )
    rsi = safe_float(row.get("rsi"))
    ema9 = safe_float(row.get("ema9"))
    ema20 = safe_float(row.get("ema20"))
    close = safe_float(row.get("close"))
    ema9_ema20_spread_pct = (
        abs(ema9 - ema20)
        / close
        * 100
        if close > 0
        else 0
    )
    ema20_slope = safe_float(row.get("ema20_slope"))
    reasons = []

    price_score = expansion_component(
        price_above_low20,
        5,
        12,
    )
    return_5d_score = expansion_component(
        return_5d,
        2,
        8,
    )
    return_10d_score = expansion_component(
        return_10d,
        4,
        15,
    )
    bullish_streak_score = expansion_component(
        bullish_streak,
        3,
        4,
    )
    wide_bullish_score = expansion_component(
        wide_bullish_count,
        2,
        3,
    )
    momentum_score = 100 if momentum_established else 0
    ema_spread_score = expansion_component(
        ema9_ema20_spread_pct,
        2.2,
        4.0,
    )

    if (
        not momentum_established
        and rsi > 58
        and ema9 > ema20 > 0
        and close > ema20 * 1.025
        and ema20_slope > 0
    ):
        momentum_score = 65

    breakout_score = 0

    if not pd.isna(days_since_breakout):
        breakout_days = safe_float(days_since_breakout)

        if 3 < breakout_days <= 20:
            breakout_score = 100
        elif breakout_days <= 3:
            breakout_score = 60

    expansion_score = max(
        price_score,
        return_5d_score,
        return_10d_score,
        bullish_streak_score,
        wide_bullish_score,
        momentum_score,
        ema_spread_score,
        breakout_score,
    )

    if price_above_low20 > 12:
        reasons.append(
            f"Price {price_above_low20:.1f}% above 20-bar low close"
        )

    if return_5d > 8:
        reasons.append(f"5-day return {return_5d:.1f}%")

    if return_10d > 15:
        reasons.append(f"10-day return {return_10d:.1f}%")

    if bullish_streak > 3:
        reasons.append(
            f"{int(bullish_streak)} consecutive bullish candles"
        )

    if wide_bullish_count > 2:
        reasons.append(
            f"{int(wide_bullish_count)} wide-range bullish candles"
        )

    if momentum_established:
        reasons.append("Momentum already established")

    if ema9_ema20_spread_pct > 3:
        reasons.append(
            f"EMA9/EMA20 spread {ema9_ema20_spread_pct:.1f}%"
        )

    if (
        not pd.isna(days_since_breakout)
        and 3 < safe_float(days_since_breakout) <= 20
    ):
        reasons.append(
            f"Breakout {int(safe_float(days_since_breakout))} bars ago"
        )

    if not reasons:
        reasons.append("Expansion still quiet")

    return {
        "ExpansionScore": round(
            normalized_score(expansion_score),
            2,
        ),
        "PriceAboveLowClose20Pct": round(
            price_above_low20,
            2,
        ),
        "Return5DPct": round(
            return_5d,
            2,
        ),
        "Return10DPct": round(
            return_10d,
            2,
        ),
        "BullishCandleStreak": int(bullish_streak)
        if bullish_streak > 0
        else 0,
        "WideRangeBullishCount": int(wide_bullish_count)
        if wide_bullish_count > 0
        else 0,
        "MomentumEstablished": bool(momentum_established),
        "EMA9EMA20SpreadPct": round(
            ema9_ema20_spread_pct,
            2,
        ),
        "ExpansionReasons": "; ".join(reasons),
    }


def calculate_bottoming_profile(row, frame, expansion_profile):

    if frame.empty:
        return {
            "BottomingSeedScore": 0,
            "DowntrendDecelerationScore": 0,
            "SellingPressureScore": 0,
            "SmallCandleScore": 0,
            "LowerLowsStopped": False,
            "FirstHigherLow": False,
            "EMA9CurlUp": False,
            "EMA20Improving": False,
            "FirstIgnition": False,
            "DistanceFromHigh60Pct": 0,
            "NearLow60Pct": 0,
            "BottomingReasons": "No bottoming frame",
        }

    close = safe_float(row.get("close"))
    ema9 = safe_float(row.get("ema9"))
    ema20 = safe_float(row.get("ema20"))
    ema9_slope = safe_float(row.get("ema9_slope"))
    ema20_slope = safe_float(row.get("ema20_slope"))
    rsi = safe_float(row.get("rsi"))
    rsi_slope = safe_float(row.get("rsi_slope"))
    rvol = safe_float(row.get("rvol"))
    expansion_score = safe_float(expansion_profile.get("ExpansionScore"))
    wide_count = safe_float(expansion_profile.get("WideRangeBullishCount"))
    bullish_streak = safe_float(expansion_profile.get("BullishCandleStreak"))

    highs = pd.to_numeric(
        frame.get("high", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    lows = pd.to_numeric(
        frame.get("low", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    closes = pd.to_numeric(
        frame.get("close", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    opens = pd.to_numeric(
        frame.get("open", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    volumes = pd.to_numeric(
        frame.get("volume", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()

    if highs.empty or lows.empty or closes.empty:
        return {
            "BottomingSeedScore": 0,
            "DowntrendDecelerationScore": 0,
            "SellingPressureScore": 0,
            "SmallCandleScore": 0,
            "LowerLowsStopped": False,
            "FirstHigherLow": False,
            "EMA9CurlUp": False,
            "EMA20Improving": False,
            "FirstIgnition": False,
            "DistanceFromHigh60Pct": 0,
            "NearLow60Pct": 0,
            "BottomingReasons": "Insufficient bottoming data",
        }

    high60 = highs.tail(60).max()
    low60 = lows.tail(60).min()
    distance_from_high60 = (
        (high60 - close)
        / high60
        * 100
        if high60 > 0 and close > 0
        else 0
    )
    near_low60 = (
        (close - low60)
        / low60
        * 100
        if low60 > 0 and close > 0
        else 0
    )
    correction_score = (
        zone_score(
            distance_from_high60,
            8,
            45,
            ideal=18,
        )
        * 0.55
        + lower_is_better_score(
            near_low60,
            8,
            22,
        )
        * 0.45
    )

    latest_low5 = lows.tail(5).min()
    prior_low20 = lows.iloc[-25:-5].min() if len(lows) >= 25 else lows.iloc[:-5].min()
    lower_lows_stopped = (
        prior_low20 > 0
        and latest_low5 >= prior_low20 * 0.98
    )
    first_higher_low = (
        prior_low20 > 0
        and latest_low5 >= prior_low20 * 1.01
    )
    higher_low_score = 100 if first_higher_low else 75 if lower_lows_stopped else 25

    ema9_slopes = pd.to_numeric(
        frame.get("ema9_slope", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    ema20_slopes = pd.to_numeric(
        frame.get("ema20_slope", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    prior_ema9_slope = (
        ema9_slopes.iloc[-6]
        if len(ema9_slopes) >= 6
        else ema9_slope
    )
    prior_ema20_slope = (
        ema20_slopes.iloc[-6]
        if len(ema20_slopes) >= 6
        else ema20_slope
    )
    ema9_curl_up = (
        ema9_slope > prior_ema9_slope
        and ema9_slope > -abs(ema9) * 0.0025
    ) or (
        len(closes) >= 3
        and ema9 > 0
        and close >= ema9 * 0.985
        and closes.iloc[-1] >= closes.iloc[-3] * 0.99
    )
    ema20_improving = (
        ema20_slope > prior_ema20_slope
        and ema20_slope <= abs(ema20) * 0.0025
    )
    ema9_curl_score = 100 if ema9_curl_up else 25
    ema20_improving_score = 100 if ema20_improving else 35

    candle_ranges = highs.align(lows, join="inner")[0] - highs.align(lows, join="inner")[1]
    avg_range5 = candle_ranges.tail(5).mean()
    avg_range20 = candle_ranges.tail(20).mean()
    avg_range_pct = (
        avg_range5
        / close
        * 100
        if close > 0
        else 0
    )
    range_ratio = (
        avg_range5
        / avg_range20
        if avg_range20 > 0
        else 1
    )
    small_candle_score = (
        lower_is_better_score(
            range_ratio,
            0.70,
            1.30,
        )
        * 0.55
        + lower_is_better_score(
            avg_range_pct,
            2.0,
            5.0,
        )
        * 0.45
    )

    red_recent = 0
    red_prior = 0

    if len(closes) >= 15 and len(opens) >= 15:
        red_recent = int((closes.tail(5).values < opens.tail(5).values).sum())
        red_prior = int((closes.iloc[-15:-5].values < opens.iloc[-15:-5].values).sum())

    volume5 = volumes.tail(5).mean() if not volumes.empty else 0
    volume20 = volumes.tail(20).mean() if len(volumes) >= 20 else volume5
    volume_quiet_score = (
        lower_is_better_score(
            volume5 / volume20 if volume20 > 0 else 1,
            0.70,
            1.15,
        )
    )
    red_pressure_score = 100 if red_recent <= 2 else 70 if red_recent <= 3 else 35
    selling_pressure_score = (
        volume_quiet_score * 0.35
        + small_candle_score * 0.25
        + red_pressure_score * 0.20
        + (100 if lower_lows_stopped else 35) * 0.20
    )

    rsi_recovery_score = (
        zone_score(
            rsi,
            42,
            55,
            ideal=49,
        )
        * 0.70
        + (100 if rsi_slope > 0 else 35) * 0.30
    )
    first_ignition = (
        close > safe_float(row.get("open"))
        and 1.05 <= rvol <= 2.5
        and wide_count <= 1
        and bullish_streak <= 2
        and expansion_score < 45
    )
    first_ignition_score = 100 if first_ignition else 65 if expansion_score < 20 else 25
    downtrend_deceleration_score = (
        correction_score * 0.35
        + ema20_improving_score * 0.25
        + selling_pressure_score * 0.20
        + rsi_recovery_score * 0.20
    )
    bottoming_seed_score = (
        correction_score * 0.17
        + higher_low_score * 0.18
        + ema9_curl_score * 0.16
        + ema20_improving_score * 0.12
        + rsi_recovery_score * 0.12
        + selling_pressure_score * 0.10
        + small_candle_score * 0.08
        + first_ignition_score * 0.07
    )

    if expansion_score >= 70:
        bottoming_seed_score = min(
            bottoming_seed_score,
            30,
        )
    elif expansion_score >= 45:
        bottoming_seed_score = min(
            bottoming_seed_score,
            55,
        )

    if wide_count > 1:
        bottoming_seed_score = min(
            bottoming_seed_score,
            72,
        )

    reasons = []

    if distance_from_high60 >= 8:
        reasons.append("Long decline/correction first")

    if lower_lows_stopped:
        reasons.append("Lower lows stopped")

    if first_higher_low:
        reasons.append("Fresh higher low")

    if ema9_curl_up:
        reasons.append("EMA9 curling upward")

    if ema20_improving:
        reasons.append("EMA20 flat/down but improving")

    if selling_pressure_score >= 65:
        reasons.append("Selling pressure slowing")

    if small_candle_score >= 65:
        reasons.append("Small candles near bottom")

    if first_ignition:
        reasons.append("First ignition candle")

    if not reasons:
        reasons.append("Bottoming profile not confirmed")

    return {
        "BottomingSeedScore": round(
            normalized_score(bottoming_seed_score),
            2,
        ),
        "DowntrendDecelerationScore": round(
            normalized_score(downtrend_deceleration_score),
            2,
        ),
        "SellingPressureScore": round(
            normalized_score(selling_pressure_score),
            2,
        ),
        "SmallCandleScore": round(
            normalized_score(small_candle_score),
            2,
        ),
        "LowerLowsStopped": bool(lower_lows_stopped),
        "FirstHigherLow": bool(first_higher_low),
        "EMA9CurlUp": bool(ema9_curl_up),
        "EMA20Improving": bool(ema20_improving),
        "FirstIgnition": bool(first_ignition),
        "DistanceFromHigh60Pct": round(distance_from_high60, 2),
        "NearLow60Pct": round(near_low60, 2),
        "BottomingReasons": "; ".join(reasons),
    }


def detect_chart_pattern(row, frame, metrics):

    base_days = safe_float(metrics.get("base_days"))
    base_tightness = safe_float(metrics.get("base_tightness_pct"))
    range10 = safe_float(metrics.get("high_low_range_10"))
    range20 = safe_float(metrics.get("high_low_range_20"))
    dry_days = safe_float(metrics.get("dry_volume_days"))
    ema_compression = safe_float(metrics.get("ema_spread_pct"))
    atr_compression = safe_float(metrics.get("atr_compression_score"))
    higher_lows = safe_float(metrics.get("higher_low_score"))
    vcp_probability = safe_float(metrics.get("vcp_probability"))
    base_quality = safe_float(metrics.get("base_quality"))
    accumulation = safe_float(metrics.get("accumulation_score"))
    close = safe_float(row.get("close"))
    ema9 = safe_float(row.get("ema9"))
    ema20 = safe_float(row.get("ema20"))
    rsi = safe_float(row.get("rsi"))
    move_from_low90 = safe_float(row.get("move_from_low90"))
    near_pivot = safe_bool(row.get("near_pivot"))
    pocket_pivot = safe_bool(row.get("pocket_pivot"))
    spring_score = 0
    shakeout_score = 0
    double_bottom_score = 0

    if not frame.empty and {"low", "close"}.issubset(frame.columns):
        lows = pd.to_numeric(frame["low"], errors="coerce").dropna()

        if len(lows) >= 25:
            prior_low20 = lows.iloc[:-1].tail(20).min()
            latest_low = lows.iloc[-1]

            if prior_low20 > 0 and latest_low < prior_low20 * 0.985 and close > prior_low20:
                spring_score = 82

            if prior_low20 > 0 and latest_low < prior_low20 * 0.97 and close > ema9:
                shakeout_score = 78

            left_low = lows.iloc[-60:-30].min() if len(lows) >= 60 else lows.iloc[:-20].min()
            right_low = lows.tail(20).min()

            if left_low > 0 and abs(right_low / left_low - 1) <= 0.06:
                double_bottom_score = 72

    flat_base_score = (
        zone_score(base_days, 20, 60, ideal=35) * 0.35
        + lower_is_better_score(base_tightness, 9, 18) * 0.35
        + lower_is_better_score(range10, 5, 12) * 0.15
        + higher_lows * 0.15
    )
    cup_handle_score = (
        zone_score(base_days, 30, 120, ideal=55) * 0.30
        + lower_is_better_score(range10, 8, 18) * 0.20
        + normalized_score(base_quality) * 0.25
        + (80 if near_pivot else 35) * 0.25
    )
    ascending_base_score = (
        normalized_score(higher_lows) * 0.40
        + zone_score(base_days, 15, 70, ideal=32) * 0.25
        + lower_is_better_score(ema_compression, 1.5, 4.5) * 0.20
        + (75 if close >= ema20 else 40) * 0.15
    )
    tight_flag_score = (
        zone_score(base_days, 5, 25, ideal=12) * 0.35
        + lower_is_better_score(range10, 4.5, 10) * 0.35
        + normalized_score(atr_compression) * 0.20
        + (70 if close >= ema9 else 35) * 0.10
    )
    high_tight_flag_score = (
        lower_is_better_score(range10, 5, 12) * 0.30
        + zone_score(base_days, 8, 25, ideal=15) * 0.20
        + (90 if move_from_low90 >= 45 else 20) * 0.30
        + normalized_score(higher_lows) * 0.20
    )
    wyckoff_score = (
        zone_score(base_days, 25, 90, ideal=45) * 0.25
        + zone_score(dry_days, 3, 12, ideal=7) * 0.25
        + normalized_score(accumulation) * 0.25
        + zone_score(rsi, 43, 56, ideal=50) * 0.15
        + normalized_score(atr_compression) * 0.10
    )
    pivot_point_score = (
        (90 if near_pivot else 35) * 0.35
        + (100 if pocket_pivot else 35) * 0.25
        + normalized_score(base_quality) * 0.20
        + lower_is_better_score(range10, 5, 14) * 0.20
    )

    pattern_scores = {
        "VCP": vcp_probability,
        "Flat Base": flat_base_score,
        "Cup with Handle": cup_handle_score,
        "Double Bottom": double_bottom_score,
        "Ascending Base": ascending_base_score,
        "Tight Flag": tight_flag_score,
        "High Tight Flag": high_tight_flag_score,
        "Wyckoff Accumulation": wyckoff_score,
        "Spring": spring_score,
        "Shakeout": shakeout_score,
        "Pivot Point": pivot_point_score,
    }
    pattern_name = max(
        pattern_scores,
        key=pattern_scores.get,
    )
    pattern_score = normalized_score(pattern_scores[pattern_name])

    if pattern_score < 45:
        pattern_name = "Unconfirmed Base"

    return pattern_name, round(pattern_score, 2)


def calculate_seed_profile(row_or_context):

    row = latest_row(row_or_context)
    frame = latest_frame(
        row_or_context,
        bars=120,
    )

    if not has_price_data(row):
        return {
            "SeedScore": 0,
            "SeedProbability": 0,
            "BaseDays": 0,
            "HighLowRange10": 0,
            "HighLowRange20": 0,
            "BaseTightnessPct": 0,
            "Vol5Vol20": 0,
            "Vol5ToVol20": 0,
            "DryVolumeDays": 0,
            "DryVolumeScore": 0,
            "EMACompressionPct": 0,
            "CompressionScore": 0,
            "ATRPercentile60": 0,
            "ATRCompressionScore": 0,
            "PocketPivot": False,
            "FreshnessScore": 0,
            "DaysSinceEMA20SlopeTurnPositive": None,
            "DaysSinceEMA9CrossEMA20": None,
            "DaysSinceBreakout": None,
            "PatternName": "No Data",
            "PatternScore": 0,
            "VCPProbability": 0,
            "BaseQuality": 0,
            "AccumulationScore": 0,
            "ChartReaderSummary": "No price data",
            "ExpansionScore": 0,
            "PriceAboveLowClose20Pct": 0,
            "Return5DPct": 0,
            "Return10DPct": 0,
            "BullishCandleStreak": 0,
            "WideRangeBullishCount": 0,
            "MomentumEstablished": False,
            "EMA9EMA20SpreadPct": 0,
            "ExpansionReasons": "No price data",
            "BottomingSeedScore": 0,
            "DowntrendDecelerationScore": 0,
            "SellingPressureScore": 0,
            "SmallCandleScore": 0,
            "LowerLowsStopped": False,
            "FirstHigherLow": False,
            "EMA9CurlUp": False,
            "EMA20Improving": False,
            "FirstIgnition": False,
            "DistanceFromHigh60Pct": 0,
            "NearLow60Pct": 0,
            "BottomingReasons": "No price data",
            "SeedReasons": "No price data",
        }

    close = safe_float(row.get("close"))
    open_ = safe_float(row.get("open"))
    ema9 = safe_float(row.get("ema9"))
    ema20 = safe_float(row.get("ema20"))
    ema20_slope = safe_float(row.get("ema20_slope"))
    rsi = safe_float(row.get("rsi"))
    rvol = safe_float(row.get("rvol"))
    distance = abs(distance_from_ema20(row))
    signed_distance = (
        (close / ema20 - 1) * 100
        if close > 0 and ema20 > 0
        else 0
    )
    move_from_low90 = safe_float(row.get("move_from_low90"))
    base_days = safe_float(row.get("base_days"))
    high_low_range_10 = safe_float(row.get("high_low_range_10"))
    high_low_range_20 = safe_float(row.get("high_low_range_20"))
    base_tightness_pct = safe_float(
        row.get(
            "base_tightness_pct",
            high_low_range_20,
        )
    )
    vol5_vol20 = safe_float(row.get("vol5_vol20"))
    dry_volume_days = safe_float(row.get("dry_volume_days"))
    dry_volume_score = safe_float(row.get("dry_volume_score"))
    ema_spread_pct = safe_float(
        row.get(
            "ema_spread_pct",
            row.get("ema_spread"),
        )
    )
    compression_score = safe_float(row.get("compression_score"))
    atr_compression_score = safe_float(
        row.get("atr_compression_score")
    )
    atr_percentile_60 = safe_float(
        row.get("atr_percentile_60")
    )
    pocket_pivot = safe_bool(row.get("pocket_pivot"))
    days_since_ema20_turn = row.get(
        "days_since_ema20_slope_turn_positive"
    )
    days_since_ema9_cross = row.get(
        "days_since_ema9_cross_ema20"
    )
    days_since_breakout = row.get("days_since_breakout")
    expansion_profile = calculate_expansion_profile(row)
    expansion_score = safe_float(
        expansion_profile.get("ExpansionScore")
    )
    bottoming_profile = calculate_bottoming_profile(
        row,
        frame,
        expansion_profile,
    )
    bottoming_seed_score = safe_float(
        bottoming_profile.get("BottomingSeedScore")
    )
    higher_low_score = score_higher_lows(
        row,
        frame,
    )

    base_day_score = zone_score(
        base_days,
        15,
        60,
        ideal=32,
    )
    tightness_score = lower_is_better_score(
        base_tightness_pct,
        8,
        22,
    )
    range10_score = lower_is_better_score(
        high_low_range_10,
        5,
        14,
    )
    rsi_seed_score = zone_score(
        rsi,
        45,
        55,
        ideal=50,
    )
    ema_distance_score = lower_is_better_score(
        distance,
        2.5,
        8,
    )
    low_move_score = lower_is_better_score(
        move_from_low90,
        12,
        32,
    )
    seed_formation = (
        base_day_score * 0.24
        + tightness_score * 0.22
        + range10_score * 0.10
        + rsi_seed_score * 0.16
        + ema_distance_score * 0.10
        + low_move_score * 0.05
        + higher_low_score * 0.13
    )

    vol_ratio_score = lower_is_better_score(
        vol5_vol20,
        0.65,
        1.15,
    )
    dry_days_score = zone_score(
        dry_volume_days,
        3,
        8,
        ideal=5,
    )
    volume_dry_up = (
        dry_volume_score * 0.45
        + vol_ratio_score * 0.30
        + dry_days_score * 0.25
    )

    ema_compression = (
        compression_score * 0.75
        + lower_is_better_score(
            ema_spread_pct,
            1.2,
            4.0,
        )
        * 0.25
    )

    if pocket_pivot:
        pocket_pivot_score = 100
    elif (
        close > open_ > 0
        and close >= ema20
        and ema20_slope > 0
        and 1.05 <= rvol <= 2.5
    ):
        pocket_pivot_score = 55
    else:
        pocket_pivot_score = 15

    ema20_turn_score = (
        100
        if ema20_slope > 0
        else 20
    )
    if not pd.isna(days_since_ema20_turn):
        ema20_turn_score = max(
            ema20_turn_score,
            days_score(
                days_since_ema20_turn,
                fresh=4,
                stale=16,
            ),
        )
    trend_confirmation = (
        ema20_turn_score * 0.70
        + (
            80
            if ema9 <= ema20 * 1.02
            else 40
        )
        * 0.30
    )

    momentum_control = (
        zone_score(
            rsi,
            45,
            58,
            ideal=51,
        )
        * 0.55
        + zone_score(
            rvol,
            0.75,
            2.2,
            ideal=1.15,
        )
        * 0.45
    )
    base_quality = (
        base_day_score * 0.24
        + tightness_score * 0.24
        + range10_score * 0.12
        + higher_low_score * 0.18
        + atr_compression_score * 0.12
        + ema_compression * 0.10
    )
    accumulation_score = (
        volume_dry_up * 0.38
        + dry_volume_score * 0.22
        + pocket_pivot_score * 0.15
        + rsi_seed_score * 0.15
        + higher_low_score * 0.10
    )
    vcp_probability = (
        lower_is_better_score(
            high_low_range_10,
            5,
            14,
        )
        * 0.24
        + lower_is_better_score(
            high_low_range_20,
            10,
            22,
        )
        * 0.18
        + zone_score(
            dry_volume_days,
            3,
            12,
            ideal=7,
        )
        * 0.20
        + lower_is_better_score(
            ema_spread_pct,
            1.2,
            4.0,
        )
        * 0.14
        + atr_compression_score * 0.14
        + higher_low_score * 0.10
    )

    seed_score = (
        seed_formation * 0.35
        + volume_dry_up * 0.20
        + ema_compression * 0.15
        + pocket_pivot_score * 0.15
        + trend_confirmation * 0.10
        + momentum_control * 0.05
    )
    seed_score = (
        seed_score * 0.68
        + bottoming_seed_score * 0.32
    )

    breakout_freshness = (
        100
        if pd.isna(days_since_breakout)
        else days_score(
            days_since_breakout,
            fresh=30,
            stale=5,
            missing_score=100,
        )
    )
    if not pd.isna(days_since_breakout):
        breakout_days = safe_float(days_since_breakout)
        breakout_freshness = (
            100
            if breakout_days > 30
            else max(
                0,
                breakout_days / 30 * 100,
            )
        )

    ema9_cross_freshness = (
        95
        if pd.isna(days_since_ema9_cross)
        else days_score(
            days_since_ema9_cross,
            fresh=3,
            stale=18,
            missing_score=95,
        )
    )
    ema20_turn_freshness = days_score(
        days_since_ema20_turn,
        fresh=4,
        stale=18,
        missing_score=55 if ema20_slope > 0 else 15,
    )
    freshness_score = (
        ema20_turn_freshness * 0.35
        + ema9_cross_freshness * 0.20
        + breakout_freshness * 0.25
        + ema_distance_score * 0.10
        + low_move_score * 0.10
    )

    hard_caps = []

    if rsi > 62:
        seed_score = min(seed_score, 59)
        hard_caps.append("RSI too hot for seed")

    if distance > 6:
        seed_score = min(seed_score, 55)
        hard_caps.append("Too far from EMA20")

    if move_from_low90 > 28:
        seed_score = min(seed_score, 55)
        hard_caps.append("Already moved far from base")

    if rvol > 3.0 and not pocket_pivot:
        seed_score = min(seed_score, 55)
        hard_caps.append("Volume spike without seed pocket pivot")

    if safe_bool(row.get("break20")) or safe_bool(row.get("break55")):
        seed_score = min(seed_score, 49)
        hard_caps.append("Breakout already triggered")

    if not pd.isna(days_since_breakout) and safe_float(days_since_breakout) <= 10:
        seed_score = min(seed_score, 55)
        hard_caps.append("Recent breakout already occurred")

    if ema20_slope <= 0 and pd.isna(days_since_ema20_turn):
        seed_score = min(seed_score, 62)
        hard_caps.append("EMA20 has not turned up")

    if bottoming_seed_score < 55:
        seed_score = min(seed_score, 58)
        hard_caps.append(
            f"Bottoming profile weak ({bottoming_seed_score:.0f})"
        )

    if expansion_score >= 70:
        seed_score = min(seed_score, 49)
        hard_caps.append(
            f"Move already started (ExpansionScore {expansion_score:.0f})"
        )
    elif expansion_score >= 45:
        seed_score = min(seed_score, 62)
        hard_caps.append(
            f"Expansion risk rising (ExpansionScore {expansion_score:.0f})"
        )

    reasons = []

    if base_days >= 10:
        reasons.append(f"Base {int(base_days)} days")

    if dry_volume_days >= 3:
        reasons.append(f"Volume dry-up {int(dry_volume_days)} sessions")

    if ema_spread_pct > 0:
        reasons.append(f"EMA compression {ema_spread_pct:.1f}%")

    if atr_compression_score >= 70:
        reasons.append("ATR lowest zone")

    if pocket_pivot:
        reasons.append("Pocket pivot detected")

    if higher_low_score >= 75:
        reasons.append("Higher lows inside base")

    bottoming_reasons = [
        reason.strip()
        for reason in str(
            bottoming_profile.get(
                "BottomingReasons",
                "",
            )
        ).split(";")
        if reason.strip()
        and reason.strip() != "Bottoming profile not confirmed"
    ]

    reasons.extend(
        f"Bottoming: {reason}"
        for reason in bottoming_reasons[:6]
    )

    if not pd.isna(days_since_ema20_turn) and safe_float(days_since_ema20_turn) <= 4:
        reasons.append("First EMA20 slope positive")
    elif ema20_slope > 0:
        reasons.append("EMA20 starting to turn up")

    if hard_caps:
        reasons.extend(
            f"Penalty: {reason}"
            for reason in hard_caps
        )

    expansion_reasons = [
        reason.strip()
        for reason in str(
            expansion_profile.get(
                "ExpansionReasons",
                "",
            )
        ).split(";")
        if reason.strip()
        and reason.strip() != "Expansion still quiet"
    ]

    if expansion_reasons:
        reasons.extend(
            f"Expansion: {reason}"
            for reason in expansion_reasons[:4]
        )

    if not reasons:
        reasons.append("Seed metrics not confirmed")

    seed_score = round(
        max(
            0,
            min(
                100,
                seed_score,
            ),
        ),
        2,
    )
    freshness_score = round(
        max(
            0,
            min(
                100,
                freshness_score,
            ),
        ),
        2,
    )
    seed_probability = round(
        seed_score * 0.72
        + freshness_score * 0.28,
        2,
    )
    pattern_metrics = {
        "base_days": base_days,
        "base_tightness_pct": base_tightness_pct,
        "high_low_range_10": high_low_range_10,
        "high_low_range_20": high_low_range_20,
        "dry_volume_days": dry_volume_days,
        "ema_spread_pct": ema_spread_pct,
        "atr_compression_score": atr_compression_score,
        "higher_low_score": higher_low_score,
        "vcp_probability": vcp_probability,
        "base_quality": base_quality,
        "accumulation_score": accumulation_score,
    }
    pattern_name, pattern_score = detect_chart_pattern(
        row,
        frame,
        pattern_metrics,
    )
    chart_reader_summary = (
        f"Pattern: {pattern_name}. "
        f"Base {int(base_days) if base_days > 0 else 0} days, "
        f"dry volume {int(dry_volume_days) if dry_volume_days > 0 else 0} sessions, "
        f"bottoming {bottoming_seed_score:.0f}, "
        f"EMA compression {ema_spread_pct:.1f}%, "
        f"ATR compression {atr_compression_score:.0f}, "
        f"expansion {expansion_score:.0f}, "
        f"freshness {freshness_score:.0f}. "
        f"{'Price still near base.' if distance <= 3 else 'Price is moving away from EMA20.'}"
    )

    return {
        "SeedScore": seed_score,
        "SeedProbability": seed_probability,
        "BaseDays": int(base_days) if base_days > 0 else 0,
        "HighLowRange10": round(high_low_range_10, 2),
        "HighLowRange20": round(high_low_range_20, 2),
        "BaseTightnessPct": round(base_tightness_pct, 2),
        "Vol5Vol20": round(vol5_vol20, 2),
        "Vol5ToVol20": round(vol5_vol20, 2),
        "DryVolumeDays": int(dry_volume_days) if dry_volume_days > 0 else 0,
        "DryVolumeScore": round(dry_volume_score, 2),
        "EMACompressionPct": round(ema_spread_pct, 2),
        "CompressionScore": round(compression_score, 2),
        "ATRPercentile60": round(atr_percentile_60, 2),
        "ATRCompressionScore": round(atr_compression_score, 2),
        "PocketPivot": bool(pocket_pivot),
        "FreshnessScore": freshness_score,
        "DaysSinceEMA20SlopeTurnPositive": (
            None
            if pd.isna(days_since_ema20_turn)
            else int(safe_float(days_since_ema20_turn))
        ),
        "DaysSinceEMA9CrossEMA20": (
            None
            if pd.isna(days_since_ema9_cross)
            else int(safe_float(days_since_ema9_cross))
        ),
        "DaysSinceBreakout": (
            None
            if pd.isna(days_since_breakout)
            else int(safe_float(days_since_breakout))
        ),
        "PatternName": pattern_name,
        "PatternScore": pattern_score,
        "VCPProbability": round(normalized_score(vcp_probability), 2),
        "BaseQuality": round(normalized_score(base_quality), 2),
        "AccumulationScore": round(normalized_score(accumulation_score), 2),
        "ChartReaderSummary": chart_reader_summary,
        **expansion_profile,
        **bottoming_profile,
        "SeedReasons": "; ".join(reasons),
    }


def score_early_mode(row_or_context):

    row = latest_row(row_or_context)

    if not has_price_data(row):
        return skip_result(
            "early",
            "🌱 Early Trend Start",
        )

    close = safe_float(row.get("close"))
    ema9 = safe_float(row.get("ema9"))
    ema20 = safe_float(row.get("ema20"))
    ema50 = safe_float(row.get("ema50"))
    rsi = safe_float(row.get("rsi"))
    rvol = safe_float(row.get("rvol"))
    macd_hist = safe_float(row.get("macd_hist"))
    macd_hist_slope = safe_float(row.get("macd_hist_slope"))
    ema20_slope = safe_float(row.get("ema20_slope"))
    ema9_slope = safe_float(row.get("ema9_slope"))
    distance = distance_from_ema20(row)
    score = 0
    reasons = []

    if close < ema20 * 0.98 or distance > 12 or rsi < 45 or rsi > 70:
        return skip_result(
            "early",
            "🌱 Pullback Start",
        )

    if ema20_slope > 0:
        score += 16
        reasons.append("EMA20 turning up")

    if ema9 >= ema20 or near(ema9, ema20, pct=1.5) or ema9_slope > 0:
        score += 14
        reasons.append("EMA9 near/above EMA20")

    if close >= ema20:
        score += 16
        reasons.append("Close reclaimed EMA20")

    if 50 <= rsi <= 65:
        score += 15
        reasons.append("RSI in early strength zone")
    elif 45 <= rsi < 50:
        score += 7
        reasons.append("RSI improving zone")

    if rvol >= 1.2:
        score += 12
        reasons.append("RVOL expansion")

    if macd_hist > 0 or macd_hist_slope > 0:
        score += 12
        reasons.append("MACD histogram improving")

    if -2 <= distance <= 8:
        score += 11
        reasons.append("Not extended from EMA20")
    elif 8 < distance <= 12:
        score += 4
        reasons.append("Slightly extended from EMA20")

    if ema50 > 0 and ema20 >= ema50 * 0.97:
        score += 3
        reasons.append("EMA20 near EMA50")

    seed_profile = calculate_seed_profile(row_or_context)
    seed_score = safe_float(seed_profile.get("SeedScore"))
    freshness_score = safe_float(seed_profile.get("FreshnessScore"))
    score = clamp_score(
        seed_score * 0.78
        + score * 0.22
    )
    reasons.append(
        f"SeedScore {seed_score:.1f}"
    )

    if seed_score >= 82 and freshness_score >= 68 and score >= 78:
        signal = "EARLY BUY"
    elif seed_score >= 72 and freshness_score >= 55 and score >= 64:
        signal = "EARLY WATCH"
    else:
        signal = "SKIP"

    if close >= ema20 and ema20_slope > 0 and rsi >= 50:
        setup = "🌱 Early Trend Start"
    elif ema9 >= ema20 or near(ema9, ema20, pct=1.5):
        setup = "🌱 EMA Turn"
    elif rvol >= 1.2 and macd_hist_slope > 0:
        setup = "🌱 Accumulation"
    else:
        setup = "🌱 Pullback Start"

    return {
        "StrategySignal": signal,
        "StrategyScore": score,
        "StrategySetup": setup,
        "StrategyReasons": reasons,
    }


def score_pure_early_mode(row_or_context):

    row = latest_row(row_or_context)
    tail = latest_frame(
        row_or_context,
        bars=12,
    )
    decision = context_decision(row_or_context)

    if not has_price_data(row):
        return skip_result(
            "pure_early",
            "🌱 Seed",
        )

    close = safe_float(row.get("close"))
    ema9 = safe_float(row.get("ema9"))
    ema20 = safe_float(row.get("ema20"))
    ema50 = safe_float(row.get("ema50"))
    rsi = safe_float(row.get("rsi"))
    rvol = safe_float(row.get("rvol"))
    ema9_slope = safe_float(row.get("ema9_slope"))
    ema20_slope = safe_float(row.get("ema20_slope"))
    distance = distance_from_ema20(row)
    signed_distance = (
        (close / ema20 - 1) * 100
        if close > 0 and ema20 > 0
        else 0
    )
    move_from_low90 = safe_float(row.get("move_from_low90"))
    high55 = safe_float(row.get("high55"))
    high20 = safe_float(row.get("high20"))
    decision_text = " ".join(
        [
            str(decision.get("signal", "")),
            str(decision.get("setup", "")),
            " ".join(
                str(reason)
                for reason in decision.get("reasons", [])
            ),
        ]
    ).upper()
    score = 0
    reasons = []

    hard_exclusions = []

    if rsi > 70:
        hard_exclusions.append("RSI above 70")

    if signed_distance > 8:
        hard_exclusions.append("Price above EMA20 by more than 8%")
    elif signed_distance < -12:
        hard_exclusions.append("Price too far below EMA20")

    if contains_any_text(
        decision_text,
        [
            "BREAKOUT",
            "52-WEEK",
            "BREAK 55 DAY HIGH",
            "CLOSE ABOVE PREVIOUS HIGH",
        ],
    ):
        hard_exclusions.append("Breakout setup already triggered")

    if contains_any_text(
        decision_text,
        [
            "EXTENDED",
        ],
    ):
        hard_exclusions.append("Already extended")

    if rvol > 4.0 and abs(signed_distance) > 3:
        hard_exclusions.append("High RVOL away from EMA20")

    if move_from_low90 > 40:
        hard_exclusions.append("Move from 90-day low above 40%")

    if high55 > 0 and close > high55 * 1.03:
        hard_exclusions.append("Price above recent high by more than 3%")

    if hard_exclusions:
        result = skip_result(
            "pure_early",
            "SKIP",
        )
        result["StrategyReasons"] = hard_exclusions
        return result

    seed_profile = calculate_seed_profile(row_or_context)
    seed_score = safe_float(seed_profile.get("SeedScore"))
    freshness_score = safe_float(seed_profile.get("FreshnessScore"))
    expansion_score = safe_float(seed_profile.get("ExpansionScore"))
    bottoming_score = safe_float(seed_profile.get("BottomingSeedScore"))
    first_higher_low = safe_bool(seed_profile.get("FirstHigherLow"))
    ema9_curl_up = safe_bool(seed_profile.get("EMA9CurlUp"))
    first_ignition = safe_bool(seed_profile.get("FirstIgnition"))
    distance_from_high60 = safe_float(seed_profile.get("DistanceFromHigh60Pct"))
    price_above_low20 = safe_float(seed_profile.get("PriceAboveLowClose20Pct"))
    return_5d = safe_float(seed_profile.get("Return5DPct"))
    return_10d = safe_float(seed_profile.get("Return10DPct"))
    score = clamp_score(
        seed_profile.get(
            "SeedProbability",
            seed_score,
        )
    )
    reasons = [
        reason.strip()
        for reason in str(
            seed_profile.get(
                "SeedReasons",
                "",
            )
        ).split(";")
        if reason.strip()
    ]

    if (
        seed_score >= 82
        and freshness_score >= 70
        and bottoming_score >= 82
        and distance_from_high60 >= 8
        and first_higher_low
        and ema9_curl_up
        and expansion_score < 35
    ):
        signal = "SEED BUY"
    elif (
        seed_score >= 74
        and freshness_score >= 60
        and bottoming_score >= 75
        and distance_from_high60 >= 8
        and first_higher_low
        and ema9_curl_up
        and expansion_score < 35
    ):
        signal = "SEED WATCH"
    else:
        signal = "SKIP"

    if expansion_score >= 70:
        if (
            signed_distance > 8
            or price_above_low20 > 12
            or return_5d > 8
            or return_10d > 15
        ):
            signal = "EXTENDED"
        else:
            signal = "MOMENTUM"
        score = min(
            score,
            68 if signal == "MOMENTUM" else 58,
        )

    if signal == "MOMENTUM":
        setup = "Move Already Started"
    elif signal == "EXTENDED":
        setup = "Already Expanded"
    elif first_ignition:
        setup = "First Ignition Seed"
    elif bottoming_score >= 70 and first_higher_low and ema9_curl_up:
        setup = "Bottoming Seed"
    elif bottoming_score >= 62:
        setup = "Reversal Accumulation"
    elif seed_profile.get("PocketPivot"):
        setup = "Seed Pocket Pivot"
    elif safe_float(seed_profile.get("BaseDays")) >= 15:
        setup = "Seed Base"
    elif safe_float(seed_profile.get("ATRCompressionScore")) >= 70:
        setup = "Tight Accumulation"
    elif safe_float(seed_profile.get("EMACompressionPct")) <= 2:
        setup = "EMA Compression Seed"
    else:
        setup = "Seed"

    return {
        "StrategySignal": signal,
        "StrategyScore": score,
        "StrategySetup": setup,
        "StrategyReasons": reasons,
    }

    recent_ema20_turn = False
    recent_ema9_cross = False
    recent_ema20_ema50_cross = False

    if not tail.empty:
        if "ema20_slope" in tail.columns:
            slopes = tail["ema20_slope"].dropna()
            recent_ema20_turn = (
                ema20_slope > 0
                and not slopes.empty
                and (slopes.iloc[:-1] <= 0).any()
            )

        if {
            "ema9",
            "ema20",
        }.issubset(tail.columns):
            spread = tail["ema9"] - tail["ema20"]
            recent_ema9_cross = (
                not spread.dropna().empty
                and spread.iloc[-1] >= 0
                and (spread.iloc[:-1] <= 0).any()
            )

        if {
            "ema20",
            "ema50",
        }.issubset(tail.columns):
            spread = tail["ema20"] - tail["ema50"]
            recent_ema20_ema50_cross = (
                not spread.dropna().empty
                and spread.iloc[-1] >= 0
                and (spread.iloc[:-1] <= 0).any()
            )

    if ema20_slope > 0:
        score += 25
        reasons.append(
            "EMA20 slope turned positive"
            if recent_ema20_turn
            else "EMA20 rising"
        )

    if -2 <= signed_distance <= 3:
        score += 15
        reasons.append("Close near EMA20")
    elif 3 < signed_distance <= 5:
        score += 10
        reasons.append("Close slightly above EMA20")

    ema9_ready = (
        ema9 >= ema20
        or near(ema9, ema20, pct=1.0)
        or ema9_slope > 0
        or recent_ema9_cross
    )

    if ema9_ready:
        reasons.append(
            "EMA9 near or just above EMA20"
        )

    if 50 <= rsi <= 60:
        score += 15
        reasons.append("RSI accumulation zone")
    elif 48 <= rsi < 50 or 60 < rsi <= 62:
        score += 10
        reasons.append("RSI near accumulation zone")

    if 1.1 <= rvol <= 2.5:
        score += 15
        reasons.append("Volume pickup without breakout")
    elif 0.8 <= rvol < 1.1:
        score += 7
        reasons.append("Quiet volume near setup")
    elif 2.5 < rvol <= 4.0:
        score += 6
        reasons.append("Volume pickup, monitor breakout risk")

    compression = (
        safe_bool(row.get("ema_compression"))
        or safe_bool(row.get("atr_compression"))
        or safe_bool(row.get("dry_volume"))
    )

    if compression:
        score += 10
        reasons.append("Compression/base forming")

    if safe_bool(row.get("higher_low")):
        score += 10
        reasons.append("Higher low forming")

    if distance <= 5 and rsi <= 70 and move_from_low90 <= 25:
        score += 10
        reasons.append("Not extended")

    if ema20 < ema50 and ema20_slope > 0:
        reasons.append("EMA20 below EMA50 but turning up")
    elif recent_ema20_ema50_cross:
        reasons.append("EMA20 recently crossed EMA50")

    score = clamp_score(score)

    if rvol < 0.8:
        score = min(
            score,
            59,
        )
        reasons.append("RVOL too quiet for Seed BUY")
    elif rvol < 1.1:
        score = min(
            score,
            74,
        )
        reasons.append("RVOL not yet in seed pickup zone")

    if score >= 75:
        signal = "SEED BUY"
    elif score >= 60:
        signal = "SEED WATCH"
    else:
        signal = "SKIP"

    if compression:
        setup = "🌱 Early Base"
    elif recent_ema20_turn or ema20_slope > 0:
        setup = "🌱 EMA20 Turn"
    elif safe_bool(row.get("higher_low")) and rvol >= 1.1:
        setup = "🌱 Accumulation Start"
    elif high20 > 0 and high20 * 0.94 <= close <= high20:
        setup = "🌱 Pre-Breakout"
    else:
        setup = "🌱 Seed"

    return {
        "StrategySignal": signal,
        "StrategyScore": score,
        "StrategySetup": setup,
        "StrategyReasons": reasons,
    }


def score_breakout_mode(row_or_context):

    row = latest_row(row_or_context)

    if not has_price_data(row):
        return skip_result(
            "breakout",
            "🚀 Breakout",
        )

    close = safe_float(row.get("close"))
    high55 = safe_float(row.get("high55"))
    high20 = safe_float(row.get("high20"))
    rvol = safe_float(row.get("rvol"))
    rsi = safe_float(row.get("rsi"))
    distance = distance_from_ema20(row)
    score = 0
    reasons = []

    if safe_bool(row.get("break55")):
        score += 24
        reasons.append("55-day breakout")
    elif safe_bool(row.get("break20")):
        score += 18
        reasons.append("20-day breakout")
    elif safe_bool(row.get("near_pivot")):
        score += 10
        reasons.append("Near pivot")

    if safe_bool(row.get("pocket_pivot")):
        score += 18
        reasons.append("Pocket pivot")

    if safe_bool(row.get("volume_breakout")) or rvol >= 2.0:
        score += 16
        reasons.append("Volume expansion")
    elif rvol >= 1.5:
        score += 10
        reasons.append("RVOL above 1.5")

    if safe_bool(row.get("strong_close")):
        score += 10
        reasons.append("Strong close")

    if safe_bool(row.get("close_above_prev_high")):
        score += 8
        reasons.append("Close above previous high")

    if high55 > 0 and close >= high55 * 0.92:
        score += 10
        reasons.append("Near 52-week high zone")
    elif high20 > 0 and close >= high20 * 0.95:
        score += 6
        reasons.append("Near 20-day high")

    if safe_bool(row.get("nr7")) or safe_bool(row.get("inside_bar")):
        score += 7
        reasons.append("Tight range")

    if 50 <= rsi <= 80:
        score += 7
        reasons.append("RSI supports breakout")

    extended = distance > 18 or rsi > 84
    score = clamp_score(score)

    if extended and score >= 55:
        signal = "EXTENDED"
    elif score >= 72:
        signal = "BREAKOUT BUY"
    elif score >= 55:
        signal = "BREAKOUT WATCH"
    else:
        signal = "SKIP"

    if safe_bool(row.get("pocket_pivot")):
        setup = "🚀 Pocket Pivot"
    elif safe_bool(row.get("nr7")) or safe_bool(row.get("inside_bar")):
        setup = "🚀 VCP Breakout"
    else:
        setup = "🚀 Breakout"

    return {
        "StrategySignal": signal,
        "StrategyScore": score,
        "StrategySetup": setup,
        "StrategyReasons": reasons,
    }


def score_momentum_mode(row_or_context):

    row = latest_row(row_or_context)

    if not has_price_data(row):
        return skip_result(
            "momentum",
            "⚡ Momentum",
        )

    close = safe_float(row.get("close"))
    ema20 = safe_float(row.get("ema20"))
    ema50 = safe_float(row.get("ema50"))
    ema200 = safe_float(row.get("ema200"))
    ema20_slope = safe_float(row.get("ema20_slope"))
    ema50_slope = safe_float(row.get("ema50_slope"))
    rsi = safe_float(row.get("rsi"))
    rvol = safe_float(row.get("rvol"))
    distance = distance_from_ema20(row)
    score = 0
    reasons = []

    if ema20 > ema50 > 0:
        score += 20
        reasons.append("EMA20 above EMA50")

    if ema50 > ema200 > 0:
        score += 20
        reasons.append("EMA50 above EMA200")

    if close > ema20 > 0:
        score += 12
        reasons.append("Price above EMA20")

    if ema20_slope > 0 and ema50_slope >= 0:
        score += 12
        reasons.append("Trend slopes positive")

    if 60 <= rsi <= 75:
        score += 16
        reasons.append("RSI momentum zone")
    elif 55 <= rsi < 60:
        score += 8
        reasons.append("RSI building")

    if rvol >= 1.5:
        score += 12
        reasons.append("RVOL above 1.5")
    elif rvol >= 1.2:
        score += 7
        reasons.append("RVOL above 1.2")

    if 0 <= distance <= 12:
        score += 8
        reasons.append("Controlled extension")

    extended = distance > 18 or rsi > 82
    score = clamp_score(score)
    if rsi < 55:
        score = min(score, 54)
    if rvol < 1.2:
        score = min(score, 54)
    elif rvol < 1.5:
        score = min(score, 71)

    confirmed_momentum = (
        ema20 > ema50 > 0
        and ema50 > ema200 > 0
        and close > ema20 > 0
        and 60 <= rsi <= 75
        and rvol >= 1.5
    )

    if extended and score >= 55:
        signal = "EXTENDED"
    elif score >= 72 and confirmed_momentum:
        signal = "MOMENTUM BUY"
    elif score >= 60:
        signal = "MOMENTUM WATCH"
    else:
        signal = "SKIP"

    if ema20 > ema50 > ema200 > 0 and rsi >= 60:
        setup = "⚡ Strong Trend"
    elif score >= 72:
        setup = "⚡ Momentum"
    else:
        setup = "⚡ Trend Continuation"

    return {
        "StrategySignal": signal,
        "StrategyScore": score,
        "StrategySetup": setup,
        "StrategyReasons": reasons,
    }


def apply_strategy_mode(row_or_context, mode="standard", decision=None):

    mode = normalize_strategy_mode(mode)

    if mode == "standard":
        result = standard_strategy_result(decision)
    elif decision and safe_float(decision.get("price")) <= 0:
        result = skip_result(mode)
    elif mode == "early":
        result = score_early_mode(row_or_context)
    elif mode == "pure_early":
        result = score_pure_early_mode({
            "df": row_or_context,
            "decision": decision or {},
        })
    elif mode == "breakout":
        result = score_breakout_mode(row_or_context)
    elif mode == "momentum":
        result = score_momentum_mode(row_or_context)
    else:
        result = standard_strategy_result(decision)

    result.update(
        calculate_seed_profile(row_or_context)
    )
    result["StrategyMode"] = strategy_mode_label(mode)

    return result
