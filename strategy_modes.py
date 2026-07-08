import math

import pandas as pd


STRATEGY_MODE_CHOICES = [
    "standard",
    "early",
    "breakout",
    "momentum",
]
STRATEGY_MODE_LABELS = {
    "standard": "Standard",
    "early": "Early",
    "breakout": "Breakout",
    "momentum": "Momentum",
}


def normalize_strategy_mode(mode):

    key = str(mode or "standard").strip().lower().replace("_", "-")

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

    score = clamp_score(score)

    if score >= 78 and rvol >= 1.2:
        signal = "EARLY BUY"
    elif score >= 62:
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
    elif mode == "breakout":
        result = score_breakout_mode(row_or_context)
    elif mode == "momentum":
        result = score_momentum_mode(row_or_context)
    else:
        result = standard_strategy_result(decision)

    result["StrategyMode"] = strategy_mode_label(mode)

    return result
