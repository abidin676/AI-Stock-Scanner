from pathlib import Path

import pandas as pd

from runtime_io import atomic_write_csv


PRIORITY_FILE = Path("output") / "priority_results.csv"

PRIORITY_MODES = [
    "Seed First",
    "Balanced",
    "Breakout Hunter",
    "Momentum Trader",
    "Trend Follower",
]

PRIORITY_UI_OPTIONS = [
    "AI Recommended",
] + PRIORITY_MODES

PRIORITY_COLUMNS = [
    "PriorityMode",
    "PriorityScore",
    "PriorityRank",
    "PriorityAction",
    "PriorityReasons",
    "PriorityBaseScore",
    "PriorityBonuses",
    "PriorityPenalties",
    "PriorityReason",
    "AIRecommendedPriority",
    "AIRecommendationReason",
]


def clamp(value, lower=0, upper=100):

    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0

    return max(lower, min(upper, value))


def safe_float(value, default=0):

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value):

    if isinstance(value, bool):
        return value

    return str(value).strip().upper() in {
        "TRUE",
        "1",
        "YES",
        "Y",
    }


def text_value(row, column, default=""):

    value = row.get(column, default)

    if pd.isna(value):
        return default

    return str(value)


def upper_value(row, column, default=""):

    return text_value(row, column, default).upper()


def contains_any(text, terms):

    text = str(text).upper()

    return any(term.upper() in text for term in terms)


def base_opportunity_score(row):

    for column in [
        "OpportunityScore",
        "StrategyScore",
        "Score",
    ]:
        if column in row:
            value = safe_float(row.get(column), None)

            if value is not None:
                return clamp(value)

    return 0


def strategy_signal(row):

    return upper_value(
        row,
        "StrategySignal",
        text_value(row, "Signal", ""),
    )


def strategy_setup(row):

    return upper_value(
        row,
        "StrategySetup",
        text_value(row, "Setup", ""),
    )


def lifecycle_state(row):

    return upper_value(row, "LifecycleState", "UNKNOWN") or "UNKNOWN"


def opportunity_reasons(row):

    return text_value(row, "OpportunityReasons", "")


def distance_ema20_pct(row):

    for column in [
        "DistanceEMA20Pct",
        "DistanceFromEMA20Pct",
        "DistanceEMA20",
    ]:
        if column in row:
            return abs(safe_float(row.get(column), 0))

    price = safe_float(row.get("Price", row.get("close", 0)))
    ema20 = safe_float(row.get("EMA20", row.get("ema20", 0)))

    if price > 0 and ema20 > 0:
        return abs((price - ema20) / ema20 * 100)

    text = (
        f"{text_value(row, 'StrategyReasons', '')} "
        f"{text_value(row, 'Reasons', '')} "
        f"{opportunity_reasons(row)}"
    ).upper()

    if "NEAR EMA20" in text or "NOT EXTENDED FROM EMA20" in text:
        return 2

    if "SLIGHTLY EXTENDED FROM EMA20" in text:
        return 5

    if "FAR FROM EMA20" in text or "EXTENDED FROM EMA20" in text:
        return 8

    return 0


def near_ema20(row, max_distance=5):

    distance = distance_ema20_pct(row)

    if distance > 0:
        return distance <= max_distance

    text = (
        f"{text_value(row, 'StrategyReasons', '')} "
        f"{text_value(row, 'Reasons', '')} "
        f"{opportunity_reasons(row)}"
    ).upper()

    return contains_any(
        text,
        [
            "NEAR EMA20",
            "ABOVE EMA20",
            "CLOSE RECLAIMED EMA20",
            "NOT EXTENDED FROM EMA20",
        ],
    )


def ema_value(row, column):

    return safe_float(
        row.get(column, row.get(column.lower(), 0)),
        0,
    )


def ema20_above_ema50(row):

    ema20 = ema_value(row, "EMA20")
    ema50 = ema_value(row, "EMA50")

    if ema20 > 0 and ema50 > 0:
        return ema20 > ema50

    text = (
        f"{text_value(row, 'Reasons', '')} "
        f"{text_value(row, 'StrategyReasons', '')} "
        f"{opportunity_reasons(row)}"
    ).upper()

    return "EMA20 > EMA50" in text


def ema50_above_ema200(row):

    ema50 = ema_value(row, "EMA50")
    ema200 = ema_value(row, "EMA200")

    if ema50 > 0 and ema200 > 0:
        return ema50 > ema200

    text = (
        f"{text_value(row, 'Reasons', '')} "
        f"{text_value(row, 'StrategyReasons', '')} "
        f"{opportunity_reasons(row)}"
    ).upper()

    return "EMA50 > EMA200" in text


def close_above_ema20(row):

    price = safe_float(row.get("Price", row.get("close", 0)))
    ema20 = ema_value(row, "EMA20")

    if price > 0 and ema20 > 0:
        return price >= ema20

    text = (
        f"{text_value(row, 'Reasons', '')} "
        f"{text_value(row, 'StrategyReasons', '')} "
        f"{opportunity_reasons(row)}"
    ).upper()

    return contains_any(
        text,
        [
            "ABOVE EMA20",
            "CLOSE RECLAIMED EMA20",
            "PRICE ABOVE EMA20",
        ],
    )


def near_recent_high(row):

    price = safe_float(row.get("Price", row.get("close", 0)))

    for column in [
        "high55",
        "High55",
        "high20",
        "High20",
    ]:
        high = safe_float(row.get(column), 0)

        if price > 0 and high > 0:
            return price >= high * 0.95

    text = (
        f"{text_value(row, 'Reasons', '')} "
        f"{text_value(row, 'StrategyReasons', '')} "
        f"{opportunity_reasons(row)}"
    ).upper()

    return contains_any(
        text,
        [
            "NEAR 52-WEEK HIGH",
            "NEAR 20-DAY HIGH",
            "CLOSE ABOVE PREVIOUS HIGH",
            "BREAKOUT",
        ],
    )


def stable_trend(row):

    text = (
        f"{text_value(row, 'Reasons', '')} "
        f"{text_value(row, 'StrategyReasons', '')} "
        f"{opportunity_reasons(row)}"
    ).upper()

    return contains_any(
        text,
        [
            "ATR COMPRESSION",
            "EMA COMPRESSION",
            "STABLE",
            "LOW VOLATILITY",
            "NEAR BASE",
        ],
    )


def market_quality_score(row):

    return safe_float(
        row.get(
            "MarketQualityScore",
            row.get("QualityScore", 0),
        ),
        0,
    )


def rsi_fit_score(rsi, low, high, ideal):

    rsi = safe_float(rsi, 0)

    if rsi <= 0:
        return 0

    if low <= rsi <= high:
        spread = max(abs(ideal - low), abs(high - ideal), 1)
        return clamp(
            100 - abs(rsi - ideal) / spread * 20,
            70,
            100,
        )

    distance = min(
        abs(rsi - low),
        abs(rsi - high),
    )
    return clamp(
        70 - distance * 6,
        0,
        70,
    )


def rvol_fit_score(rvol, low, high, ideal):

    rvol = safe_float(rvol, 0)

    if rvol <= 0:
        return 0

    if low <= rvol <= high:
        spread = max(abs(ideal - low), abs(high - ideal), 0.1)
        return clamp(
            100 - abs(rvol - ideal) / spread * 20,
            70,
            100,
        )

    distance = min(
        abs(rvol - low),
        abs(rvol - high),
    )
    return clamp(
        70 - distance * 25,
        0,
        70,
    )


def seed_risk_score(row):

    risk = abs(
        safe_float(
            row.get(
                "RiskPct",
                row.get(
                    "DistanceEMA20Pct",
                    0,
                ),
            ),
            0,
        )
    )

    if risk <= 0:
        return 50

    if risk <= 3:
        return 100

    if risk <= 6:
        return 80

    if risk <= 10:
        return 45

    return 15


def priority_tie_breaker(row, priority_mode):

    mode = normalize_priority_mode(priority_mode)
    symbol = text_value(row, "Symbol", "")
    symbol_hash = (sum(ord(char) for char in symbol) % 113) / 10000
    opportunity = base_opportunity_score(row) / 100
    strategy = safe_float(row.get("StrategyScore", row.get("Score", 0))) / 100
    rr = clamp(safe_float(row.get("RR", 0)), 0, 4) / 4
    quality = market_quality_score(row) / 100
    days = safe_float(row.get("DaysInState"), 0)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)

    if mode == "Seed First":
        seed_score = clamp(safe_float(row.get("SeedScore", 0))) / 100
        freshness_score = clamp(safe_float(row.get("FreshnessScore", 0))) / 100
        bottoming_score = clamp(safe_float(row.get("BottomingSeedScore", 0))) / 100
        base_quality = clamp(safe_float(row.get("BaseQuality", 0))) / 100
        dry_score = clamp(safe_float(row.get("DryVolumeScore", 0))) / 100
        pocket = 1 if safe_bool(row.get("PocketPivot")) else 0
        higher_low = 1 if safe_bool(row.get("FirstHigherLow")) else 0
        ema9_curl = 1 if safe_bool(row.get("EMA9CurlUp")) else 0
        first_ignition = 1 if safe_bool(row.get("FirstIgnition")) else 0
        risk_fit = seed_risk_score(row) / 100
        freshness = clamp((5 - min(days, 5)) / 5 * 100, 0, 100) / 100
        return round(
            bottoming_score * 0.24
            + seed_score * 0.18
            + freshness_score * 0.12
            + higher_low * 0.10
            + ema9_curl * 0.09
            + dry_score * 0.09
            + first_ignition * 0.07
            + base_quality * 0.05
            + pocket * 0.03
            + risk_fit * 0.02
            + quality * 0.03
            + freshness * 0.01
            + symbol_hash,
            4,
        )
    elif mode == "Breakout Hunter":
        rsi_fit = rsi_fit_score(rsi, 55, 76, 66) / 100
        rvol_fit = clamp(min(rvol, 4) / 4 * 100, 0, 100) / 100
        freshness = clamp((8 - min(days, 8)) / 8 * 100, 0, 100) / 100
    elif mode == "Momentum Trader":
        rsi_fit = rsi_fit_score(rsi, 60, 75, 68) / 100
        rvol_fit = clamp(min(rvol, 4) / 4 * 100, 0, 100) / 100
        freshness = 0.5
    else:
        rsi_fit = rsi_fit_score(rsi, 55, 70, 62) / 100
        rvol_fit = rvol_fit_score(rvol, 0.8, 2.5, 1.2) / 100
        freshness = clamp(min(days, 20) / 20 * 100, 0, 100) / 100

    return round(
        opportunity * 0.20
        + strategy * 0.16
        + rr * 0.16
        + rsi_fit * 0.16
        + rvol_fit * 0.14
        + quality * 0.10
        + freshness * 0.07
        + symbol_hash,
        4,
    )


def finalize_priority_score(raw_score, row, priority_mode):

    mode = normalize_priority_mode(priority_mode)

    if mode == "Balanced":
        return round(
            clamp(base_opportunity_score(row)),
            2,
        )

    score = max(0, safe_float(raw_score, 0))

    if score > 88:
        score = 88 + (score - 88) * 0.28

    if score > 97:
        score = 97 + (score - 97) * 0.18

    score += priority_tie_breaker(
        row,
        mode,
    )

    return round(
        clamp(score, 0, 99.49),
        2,
    )


def seed_first_score(row):

    expansion_score = clamp(safe_float(row.get("ExpansionScore", 0)))
    bottoming_score = clamp(safe_float(row.get("BottomingSeedScore", 0)))
    first_higher_low = 100 if safe_bool(row.get("FirstHigherLow")) else 0
    ema9_curl = 100 if safe_bool(row.get("EMA9CurlUp")) else 0
    first_ignition = 100 if safe_bool(row.get("FirstIgnition")) else 0
    score = (
        bottoming_score * 0.30
        + clamp(safe_float(row.get("SeedScore", 0))) * 0.16
        + clamp(safe_float(row.get("FreshnessScore", 0))) * 0.10
        + first_higher_low * 0.12
        + ema9_curl * 0.11
        + clamp(safe_float(row.get("DryVolumeScore", 0))) * 0.10
        + first_ignition * 0.08
        + seed_risk_score(row) * 0.05
        + base_opportunity_score(row) * 0.03
        - expansion_score
    )
    signal = strategy_signal(row)
    setup = strategy_setup(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)
    days = safe_float(row.get("DaysInState"), 999)
    distance = distance_ema20_pct(row)

    if state == "SEED":
        score += 2
    elif state == "EARLY":
        score += 1

    if "SEED BUY" in signal:
        score += 2
    elif "SEED WATCH" in signal:
        score += 1
    elif "EARLY BUY" in signal or "EARLY" in signal:
        score += 1
    elif "SKIP" in signal:
        score -= 22

    if 48 <= rsi <= 62:
        score += 1
    elif 45 <= rsi < 48 or 62 < rsi <= 66:
        score += 0.5

    if 1.1 <= rvol <= 2.5:
        score += 1
    elif 0.8 <= rvol < 1.1:
        score += 0.5

    if near_ema20(row):
        score += 1

    if days <= 3:
        score += 1

    if safe_bool(row.get("StateChanged")):
        score += 1

    if contains_any(
        setup,
        [
            "EARLY",
            "PULLBACK",
            "ACCUMULATION",
            "EMA20 TURN",
            "EMA TURN",
            "SEED",
        ],
    ):
        score += 1

    if safe_float(row.get("BaseDays", 0)) >= 15:
        score += 0.5

    if safe_float(row.get("DryVolumeDays", 0)) >= 3:
        score += 0.5

    if safe_float(row.get("EMACompressionPct", 99)) <= 2:
        score += 0.5

    if safe_float(row.get("ATRCompressionScore", 0)) >= 70:
        score += 0.5

    if safe_bool(row.get("PocketPivot")):
        score += 2

    if "PRE-BREAKOUT" in setup:
        score -= 6
    elif "BREAKOUT" in setup:
        score -= 18

    if state in {
        "BREAKOUT",
        "MOMENTUM",
        "EXTENDED",
    }:
        score -= 20

    if rsi > 70:
        score -= 15

    if rvol > 4 and not near_ema20(row, max_distance=3):
        score -= 10

    if distance > 5:
        score -= 15

    if "EXTENDED" in signal:
        score -= 30

    return max(0, score)


def breakout_hunter_score(row):

    score = base_opportunity_score(row) * 0.45
    signal = strategy_signal(row)
    setup = strategy_setup(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)
    quality = market_quality_score(row)

    if "BREAKOUT" in setup:
        score += 22

    if "POCKET PIVOT" in setup or "POCKET PIVOT" in signal:
        score += 12

    if "BUY" in signal or "BREAKOUT BUY" in signal:
        score += 10

    if rvol >= 1.5:
        score += 12
    elif rvol < 1:
        score -= 10

    if near_recent_high(row):
        score += 10

    if quality >= 50:
        score += 8

    if state == "BREAKOUT":
        score += 15

    if state == "SKIP":
        score -= 15

    if state == "EXTENDED" or "EXTENDED" in signal:
        score -= 20

    if rsi > 78:
        score -= 12

    return max(0, score)


def momentum_trader_score(row):

    score = base_opportunity_score(row) * 0.45
    signal = strategy_signal(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)
    distance = distance_ema20_pct(row)

    if state == "MOMENTUM":
        score += 20

    if ema20_above_ema50(row):
        score += 12

    if ema50_above_ema200(row):
        score += 12

    if 60 <= rsi <= 75:
        score += 12
    elif 55 <= rsi < 60:
        score += 5

    if rvol >= 1.5:
        score += 12
    elif rvol < 1:
        score -= 12

    if "MOMENTUM BUY" in signal:
        score += 14
    elif "BUY" in signal:
        score += 8

    if rsi > 80:
        score -= 15

    if distance > 8:
        score -= 15
    elif distance > 5:
        score -= 8

    if "EXTENDED" in signal or state == "EXTENDED":
        score -= 22

    return max(0, score)


def trend_follower_score(row):

    score = base_opportunity_score(row) * 0.45
    signal = strategy_signal(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)
    days = safe_float(row.get("DaysInState"), 0)
    distance = distance_ema20_pct(row)

    if ema20_above_ema50(row):
        score += 16

    if ema50_above_ema200(row):
        score += 16

    if close_above_ema20(row):
        score += 10

    if 55 <= rsi <= 70:
        score += 12

    if stable_trend(row):
        score += 8

    if days > 3 and state not in {
        "EXTENDED",
        "SKIP",
    }:
        score += 8

    if "BUY" in signal:
        score += 6

    if "EXTENDED" in signal or state == "EXTENDED":
        score -= 20

    if rsi > 78:
        score -= 12

    if rvol > 4:
        score -= 8

    if distance > 8:
        score -= 16
    elif distance > 5:
        score -= 8

    return max(0, score)


def calculate_priority_score(row, priority_mode):

    mode = normalize_priority_mode(priority_mode)

    if mode == "Balanced":
        return finalize_priority_score(
            base_opportunity_score(row),
            row,
            mode,
        )

    if mode == "Breakout Hunter":
        return finalize_priority_score(
            breakout_hunter_score(row),
            row,
            mode,
        )

    if mode == "Momentum Trader":
        return finalize_priority_score(
            momentum_trader_score(row),
            row,
            mode,
        )

    if mode == "Trend Follower":
        return finalize_priority_score(
            trend_follower_score(row),
            row,
            mode,
        )

    return finalize_priority_score(
        seed_first_score(row),
        row,
        mode,
    )


def seed_first_reasons(row):

    reasons = []
    seed_reasons = [
        reason.strip()
        for reason in text_value(
            row,
            "SeedReasons",
            "",
        ).split(";")
        if reason.strip()
    ]
    reasons.extend(seed_reasons[:5])
    signal = strategy_signal(row)
    setup = strategy_setup(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)
    days = safe_float(row.get("DaysInState"), 999)
    distance = distance_ema20_pct(row)

    if state == "SEED":
        reasons.append("Seed lifecycle")
    elif state == "EARLY":
        reasons.append("Early lifecycle")

    if "SEED BUY" in signal or "SEED WATCH" in signal:
        reasons.append("Seed signal")
    elif "EARLY" in signal:
        reasons.append("Early signal")

    if 48 <= rsi <= 62:
        reasons.append("RSI in accumulation zone")

    if 1.1 <= rvol <= 2.5:
        reasons.append("Volume pickup without chase")

    if near_ema20(row):
        reasons.append("Price near EMA20")

    if days <= 3:
        reasons.append("Fresh lifecycle state")

    if safe_bool(row.get("StateChanged")):
        reasons.append("State changed recently")

    if contains_any(setup, ["EARLY", "PULLBACK", "ACCUMULATION", "EMA20 TURN", "SEED"]):
        reasons.append("Early/base setup")

    base_days = safe_float(row.get("BaseDays", 0))
    dry_days = safe_float(row.get("DryVolumeDays", 0))
    ema_compression = safe_float(row.get("EMACompressionPct", 0))
    atr_score = safe_float(row.get("ATRCompressionScore", 0))
    pattern_name = text_value(row, "PatternName", "").strip()
    pattern_score = safe_float(row.get("PatternScore", 0))
    base_quality = safe_float(row.get("BaseQuality", 0))
    accumulation = safe_float(row.get("AccumulationScore", 0))
    vcp_probability = safe_float(row.get("VCPProbability", 0))
    bottoming_score = safe_float(row.get("BottomingSeedScore", 0))
    risk_score = seed_risk_score(row)
    expansion_score = safe_float(row.get("ExpansionScore", 0))
    expansion_reasons = [
        reason.strip()
        for reason in text_value(
            row,
            "ExpansionReasons",
            "",
        ).split(";")
        if reason.strip()
        and reason.strip() != "Expansion still quiet"
    ]

    if pattern_name:
        reasons.append(f"Pattern {pattern_name} {pattern_score:.0f}")

    if bottoming_score > 0:
        reasons.append(f"Bottoming seed {bottoming_score:.0f}")

    if safe_bool(row.get("FirstHigherLow")):
        reasons.append("Fresh higher low")

    if safe_bool(row.get("EMA9CurlUp")):
        reasons.append("EMA9 curling up")

    if safe_bool(row.get("EMA20Improving")):
        reasons.append("EMA20 improving")

    if safe_bool(row.get("FirstIgnition")):
        reasons.append("First ignition candle")

    if base_quality > 0:
        reasons.append(f"Base quality {base_quality:.0f}")

    if accumulation > 0:
        reasons.append(f"Accumulation {accumulation:.0f}")

    if vcp_probability >= 60:
        reasons.append(f"VCP probability {vcp_probability:.0f}")

    if base_days > 0:
        reasons.append(f"Base {int(base_days)} days")

    if dry_days > 0:
        reasons.append(f"Volume dry-up {int(dry_days)} sessions")

    if ema_compression > 0:
        reasons.append(f"EMA compression {ema_compression:.1f}%")

    if atr_score >= 70:
        reasons.append("ATR lowest zone")

    if safe_bool(row.get("PocketPivot")):
        reasons.append("Pocket pivot detected")

    if risk_score >= 80:
        reasons.append("Risk still controlled")

    if expansion_score <= 20:
        reasons.append("Expansion still quiet")
    elif expansion_score >= 70:
        reasons.append(f"Penalty: move already started {expansion_score:.0f}")
    elif expansion_score > 0:
        reasons.append(f"Expansion risk {expansion_score:.0f}")

    reasons.extend(
        f"Expansion: {reason}"
        for reason in expansion_reasons[:3]
    )

    if "BREAKOUT" in setup:
        reasons.append("Penalty: breakout-like setup")

    if state in {"BREAKOUT", "MOMENTUM", "EXTENDED"}:
        reasons.append(f"Penalty: lifecycle {state}")

    if rsi > 70:
        reasons.append("Penalty: RSI above early zone")

    if distance > 5:
        reasons.append("Penalty: price far from EMA20")

    if rvol > 4 and not near_ema20(row, max_distance=3):
        reasons.append("Penalty: volume spike away from EMA20")

    if "EXTENDED" in signal:
        reasons.append("Penalty: extended signal")

    return reasons


def balanced_reasons(row):

    reasons = [
        reason.strip()
        for reason in opportunity_reasons(row).split(";")
        if reason.strip()
    ]

    if reasons:
        return reasons

    return ["Uses OpportunityScore ranking"]


def breakout_hunter_reasons(row):

    reasons = []
    signal = strategy_signal(row)
    setup = strategy_setup(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)
    quality = market_quality_score(row)

    if "BREAKOUT" in setup:
        reasons.append("Breakout setup")

    if "POCKET PIVOT" in setup or "POCKET PIVOT" in signal:
        reasons.append("Pocket Pivot")

    if "BUY" in signal:
        reasons.append("Buy signal")

    if rvol >= 1.5:
        reasons.append("Volume expansion")

    if near_recent_high(row):
        reasons.append("Price near recent high")

    if quality >= 50:
        reasons.append("Market quality supports breakouts")

    if state == "BREAKOUT":
        reasons.append("Breakout lifecycle")

    if state == "EXTENDED" or "EXTENDED" in signal:
        reasons.append("Penalty: extended")

    if rsi > 78:
        reasons.append("Penalty: RSI overheated")

    if rvol < 1:
        reasons.append("Penalty: low RVOL")

    if state == "SKIP":
        reasons.append("Penalty: lifecycle SKIP")

    return reasons


def momentum_trader_reasons(row):

    reasons = []
    signal = strategy_signal(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)
    distance = distance_ema20_pct(row)

    if state == "MOMENTUM":
        reasons.append("Momentum lifecycle")

    if ema20_above_ema50(row):
        reasons.append("EMA20 above EMA50")

    if ema50_above_ema200(row):
        reasons.append("EMA50 above EMA200")

    if 60 <= rsi <= 75:
        reasons.append("RSI momentum zone")

    if rvol >= 1.5:
        reasons.append("High RVOL")

    if "MOMENTUM BUY" in signal or "BUY" in signal:
        reasons.append("Momentum/Buy signal")

    if rsi > 80:
        reasons.append("Penalty: RSI overheated")

    if distance > 5:
        reasons.append("Penalty: distance from EMA20")

    if "EXTENDED" in signal or state == "EXTENDED":
        reasons.append("Penalty: extended")

    if rvol < 1:
        reasons.append("Penalty: low RVOL")

    return reasons


def trend_follower_reasons(row):

    reasons = []
    signal = strategy_signal(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI"), 0)
    rvol = safe_float(row.get("RVOL"), 0)
    days = safe_float(row.get("DaysInState"), 0)
    distance = distance_ema20_pct(row)

    if ema20_above_ema50(row):
        reasons.append("EMA20 above EMA50")

    if ema50_above_ema200(row):
        reasons.append("EMA50 above EMA200")

    if close_above_ema20(row):
        reasons.append("Close above EMA20")

    if 55 <= rsi <= 70:
        reasons.append("RSI trend zone")

    if stable_trend(row):
        reasons.append("Stable trend or compression")

    if days > 3 and state not in {"EXTENDED", "SKIP"}:
        reasons.append("Trend has persisted")

    if "BUY" in signal:
        reasons.append("Buy signal")

    if "EXTENDED" in signal or state == "EXTENDED":
        reasons.append("Penalty: extended")

    if rsi > 78:
        reasons.append("Penalty: RSI overheated")

    if rvol > 4:
        reasons.append("Penalty: volume spike")

    if distance > 5:
        reasons.append("Penalty: price far from EMA20")

    return reasons


def get_priority_reasons(row, priority_mode):

    mode = normalize_priority_mode(priority_mode)

    if mode == "Balanced":
        reasons = balanced_reasons(row)
    elif mode == "Breakout Hunter":
        reasons = breakout_hunter_reasons(row)
    elif mode == "Momentum Trader":
        reasons = momentum_trader_reasons(row)
    elif mode == "Trend Follower":
        reasons = trend_follower_reasons(row)
    else:
        reasons = seed_first_reasons(row)

    if not reasons:
        reasons = [f"{mode} ranking applied"]

    return "; ".join(reasons)


def priority_action(score):

    score = safe_float(score, 0)

    if score >= 96:
        return "Review First"

    if score >= 90:
        return "High Priority"

    if score >= 80:
        return "Watch Closely"

    if score >= 65:
        return "Monitor"

    return "Low Priority"


def normalize_priority_mode(priority_mode):

    value = str(priority_mode or "").strip()

    aliases = {
        "seed": "Seed First",
        "seed first": "Seed First",
        "balanced": "Balanced",
        "breakout": "Breakout Hunter",
        "breakout hunter": "Breakout Hunter",
        "momentum": "Momentum Trader",
        "momentum trader": "Momentum Trader",
        "trend": "Trend Follower",
        "trend follower": "Trend Follower",
    }

    normalized = aliases.get(value.lower(), value)

    if normalized not in PRIORITY_MODES:
        return "Seed First"

    return normalized


def ensure_priority_inputs(df):

    data = df.copy()

    if "OpportunityScore" not in data.columns:
        if "StrategyScore" in data.columns:
            data["OpportunityScore"] = data["StrategyScore"]
        elif "Score" in data.columns:
            data["OpportunityScore"] = data["Score"]
        else:
            data["OpportunityScore"] = 0

    if "LifecycleState" not in data.columns:
        data["LifecycleState"] = "UNKNOWN"

    if "DaysInState" not in data.columns:
        data["DaysInState"] = 0

    if "StateChanged" not in data.columns:
        data["StateChanged"] = False

    if "StrategySignal" not in data.columns:
        data["StrategySignal"] = data.get("Signal", "")

    if "StrategySetup" not in data.columns:
        data["StrategySetup"] = data.get("Setup", "")

    if "RecommendedAction" not in data.columns:
        data["RecommendedAction"] = ""

    if "OpportunityReasons" not in data.columns:
        data["OpportunityReasons"] = ""

    numeric_columns = [
        "OpportunityScore",
        "StrategyScore",
        "Score",
        "RSI",
        "RVOL",
        "DaysInState",
        "DistanceEMA20Pct",
        "MarketQualityScore",
        "SeedScore",
        "SeedProbability",
        "FreshnessScore",
        "BaseDays",
        "DryVolumeDays",
        "DryVolumeScore",
        "EMACompressionPct",
        "CompressionScore",
        "ATRCompressionScore",
        "ATRPercentile60",
        "Vol5Vol20",
        "Vol5ToVol20",
        "BaseTightnessPct",
        "HighLowRange10",
        "HighLowRange20",
        "DaysSinceEMA20SlopeTurnPositive",
        "DaysSinceEMA9CrossEMA20",
        "DaysSinceBreakout",
        "PatternScore",
        "VCPProbability",
        "BaseQuality",
        "AccumulationScore",
        "ExpansionScore",
        "BottomingSeedScore",
        "DowntrendDecelerationScore",
        "SellingPressureScore",
        "SmallCandleScore",
        "DistanceFromHigh60Pct",
        "NearLow60Pct",
        "PriceAboveLowClose20Pct",
        "Return5DPct",
        "Return10DPct",
        "BullishCandleStreak",
        "WideRangeBullishCount",
        "EMA9EMA20SpreadPct",
    ]

    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            ).fillna(0)

    data["LifecycleState"] = (
        data["LifecycleState"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .replace("", "UNKNOWN")
    )
    data["StateChanged"] = data["StateChanged"].apply(safe_bool)

    return data


def latest_market_quality(market_quality_df):

    if market_quality_df is None or market_quality_df.empty:
        return pd.DataFrame()

    quality = market_quality_df.copy()

    if "Market" not in quality.columns or "QualityScore" not in quality.columns:
        return pd.DataFrame()

    quality["Market"] = (
        quality["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    quality["QualityScore"] = pd.to_numeric(
        quality["QualityScore"],
        errors="coerce",
    ).fillna(0)

    if "LastScanTime" in quality.columns:
        quality["_scan_time"] = pd.to_datetime(
            quality["LastScanTime"],
            errors="coerce",
        )
    else:
        quality["_scan_time"] = pd.NaT

    quality["_row_order"] = range(len(quality))
    quality = quality.sort_values(
        [
            "_scan_time",
            "_row_order",
        ]
    )

    return quality.drop_duplicates(
        subset=["Market"],
        keep="last",
    )[
        [
            "Market",
            "QualityScore",
        ]
    ].rename(
        columns={"QualityScore": "MarketQualityScore"}
    )


def merge_market_quality(data, market_quality_df):

    quality = latest_market_quality(market_quality_df)

    if quality.empty or "Market" not in data.columns:
        return data

    output = data.copy()
    output["Market"] = (
        output["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    output = output.drop(
        columns=["MarketQualityScore"],
        errors="ignore",
    )

    return output.merge(
        quality,
        on="Market",
        how="left",
    )


def merge_lifecycle(data, lifecycle_df):

    if lifecycle_df is None or lifecycle_df.empty:
        return data

    if not {"Symbol", "Market"}.issubset(data.columns):
        return data

    life = lifecycle_df.copy()

    if not {"Symbol", "Market"}.issubset(life.columns):
        return data

    life = life.rename(
        columns={
            "CurrentState": "LifecycleState",
            "PreviousState": "PreviousLifecycleState",
        }
    )
    merge_columns = [
        column
        for column in [
            "Symbol",
            "Market",
            "LifecycleState",
            "PreviousLifecycleState",
            "DaysInState",
            "StateChanged",
        ]
        if column in life.columns
    ]

    if len(merge_columns) <= 2:
        return data

    output = data.copy()
    output["Symbol"] = (
        output["Symbol"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    output["Market"] = (
        output["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    life["Symbol"] = (
        life["Symbol"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    life["Market"] = (
        life["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    output = output.merge(
        life[merge_columns].drop_duplicates(
            subset=[
                "Symbol",
                "Market",
            ],
            keep="last",
        ),
        on=[
            "Symbol",
            "Market",
        ],
        how="left",
        suffixes=(
            "",
            "_PriorityLife",
        ),
    )

    for column in [
        "LifecycleState",
        "PreviousLifecycleState",
        "DaysInState",
        "StateChanged",
    ]:
        fallback = f"{column}_PriorityLife"

        if fallback not in output.columns:
            continue

        if column not in output.columns:
            output[column] = output[fallback]
        else:
            output[column] = output[column].fillna(output[fallback])

    return output.drop(
        columns=[
            column
            for column in output.columns
            if column.endswith("_PriorityLife")
        ],
        errors="ignore",
    )


def apply_priority_mode(
    opportunity_df,
    priority_mode,
    market_quality_df=None,
    lifecycle_df=None,
    ai_recommended_priority=None,
    ai_recommendation_reason="",
):

    if opportunity_df is None:
        return pd.DataFrame()

    mode = normalize_priority_mode(priority_mode)
    data = opportunity_df.copy()

    if data.empty:
        return ensure_priority_inputs(data)

    data = merge_lifecycle(
        data,
        lifecycle_df,
    )
    data = merge_market_quality(
        data,
        market_quality_df,
    )
    data = data.drop(
        columns=PRIORITY_COLUMNS,
        errors="ignore",
    )
    data = ensure_priority_inputs(data)

    rows = []

    for _, row in data.iterrows():
        score = calculate_priority_score(
            row,
            mode,
        )
        tie_breaker = (
            0
            if mode == "Balanced"
            else priority_tie_breaker(
                row,
                mode,
            )
        )
        rows.append({
            "PriorityMode": mode,
            "PriorityScore": score,
            "_PriorityTieBreaker": tie_breaker,
            "PriorityAction": priority_action(score),
            "PriorityReasons": get_priority_reasons(
                row,
                mode,
            ),
            "PriorityBaseScore": score,
            "PriorityBonuses": "",
            "PriorityPenalties": "",
            "PriorityReason": get_priority_reasons(
                row,
                mode,
            ),
            "AIRecommendedPriority": (
                ai_recommended_priority or mode
            ),
            "AIRecommendationReason": ai_recommendation_reason,
        })

    prioritized = pd.concat(
        [
            data.reset_index(drop=True),
            pd.DataFrame(rows),
        ],
        axis=1,
    )
    secondary_score = (
        "OpportunityScore"
        if "OpportunityScore" in prioritized.columns
        else "StrategyScore"
        if "StrategyScore" in prioritized.columns
        else "Score"
    )
    sort_columns = [
        "PriorityScore",
        "_PriorityTieBreaker",
        secondary_score,
    ]
    ascending = [
        False,
        False,
        False,
    ]

    if mode == "Balanced" and "OpportunityRank" in prioritized.columns:
        sort_columns = [
            "PriorityScore",
            "OpportunityRank",
        ]
        ascending = [
            False,
            True,
        ]

    prioritized = prioritized.sort_values(
        sort_columns,
        ascending=ascending,
    ).reset_index(drop=True)
    prioritized["PriorityRank"] = range(
        1,
        len(prioritized) + 1,
    )

    return prioritized.drop(
        columns=[
            "_PriorityTieBreaker",
        ],
        errors="ignore",
    )


def summarize_opportunities(opportunity_df):

    if opportunity_df is None or opportunity_df.empty:
        return {
            "seed": 0,
            "early": 0,
            "breakout": 0,
            "momentum": 0,
            "extended": 0,
            "total": 0,
            "avg_score": 0,
        }

    data = ensure_priority_inputs(opportunity_df)
    state = data["LifecycleState"].astype(str).str.upper()
    signal = data["StrategySignal"].astype(str).str.upper()
    setup = data["StrategySetup"].astype(str).str.upper()

    return {
        "seed": int(
            (
                (state == "SEED")
                | signal.str.contains("SEED", regex=True, na=False)
                | (pd.to_numeric(
                    data.get(
                        "SeedScore",
                        pd.Series(0, index=data.index),
                    ),
                    errors="coerce",
                ).fillna(0) >= 82)
            ).sum()
        ),
        "early": int(
            (
                (state == "EARLY")
                | signal.str.contains("SEED|EARLY", regex=True, na=False)
                | setup.str.contains("EARLY|ACCUMULATION|EMA20 TURN|SEED", regex=True, na=False)
            ).sum()
        ),
        "breakout": int(
            (
                (state == "BREAKOUT")
                | setup.str.contains("BREAKOUT|POCKET PIVOT", regex=True, na=False)
                | signal.str.contains("BREAKOUT", regex=True, na=False)
            ).sum()
        ),
        "momentum": int(
            (
                (state == "MOMENTUM")
                | signal.str.contains("MOMENTUM", regex=True, na=False)
            ).sum()
        ),
        "extended": int(
            (
                (state == "EXTENDED")
                | signal.str.contains("EXTENDED", regex=True, na=False)
            ).sum()
        ),
        "total": len(data),
        "avg_score": safe_float(data["OpportunityScore"].mean(), 0),
    }


def latest_quality_average(market_quality_df):

    quality = latest_market_quality(market_quality_df)

    if quality.empty:
        return 0

    return safe_float(
        quality["MarketQualityScore"].mean(),
        0,
    )


def recommend_priority_mode(
    market_quality_df,
    lifecycle_df,
    opportunity_df,
):

    quality = latest_quality_average(market_quality_df)
    summary = summarize_opportunities(opportunity_df)
    total = max(summary["total"], 1)
    early_ratio = summary["early"] / total
    seed_ratio = summary.get("seed", 0) / total
    breakout_ratio = summary["breakout"] / total
    momentum_ratio = summary["momentum"] / total

    if quality < 40:
        return {
            "AIRecommendedPriority": "Seed First",
            "AIRecommendationReason": (
                "Market quality is weak, so early-stage setups are safer "
                "to review than chasing breakouts."
            ),
        }

    if quality <= 60 and max(seed_ratio, early_ratio) >= max(
        breakout_ratio,
        momentum_ratio,
    ):
        return {
            "AIRecommendedPriority": "Seed First",
            "AIRecommendationReason": (
                "Market is mixed and early-stage opportunities dominate "
                "the current scan."
            ),
        }

    if quality > 60 and breakout_ratio >= 0.08:
        return {
            "AIRecommendedPriority": "Breakout Hunter",
            "AIRecommendationReason": (
                "Market quality is healthy and breakout candidates are "
                "well represented."
            ),
        }

    if quality > 60 and momentum_ratio >= 0.08:
        return {
            "AIRecommendedPriority": "Momentum Trader",
            "AIRecommendationReason": (
                "Market quality is healthy and momentum candidates are "
                "standing out."
            ),
        }

    if quality >= 50 and summary["avg_score"] >= 60 and breakout_ratio < 0.05:
        return {
            "AIRecommendedPriority": "Trend Follower",
            "AIRecommendationReason": (
                "Average opportunity quality is solid, but breakouts are "
                "not broad enough, so confirmed trends deserve priority."
            ),
        }

    return {
        "AIRecommendedPriority": "Balanced",
        "AIRecommendationReason": (
            "No single setup type dominates, so the original OpportunityScore "
            "ranking is the cleanest view."
        ),
    }


def save_priority_results(priority_results, path=PRIORITY_FILE):

    path = Path(path)
    path.parent.mkdir(
        exist_ok=True
    )
    atomic_write_csv(
        priority_results,
        path,
        index=False,
    )

    return path


def load_priority_results(path=PRIORITY_FILE):

    path = Path(path)

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
