from pathlib import Path

import pandas as pd


OPPORTUNITY_FILE = Path("output") / "opportunity_results.csv"

OPPORTUNITY_COLUMNS = [
    "OpportunityScore",
    "OpportunityGrade",
    "OpportunityRank",
    "Confidence",
    "RecommendedAction",
    "OpportunityReasons",
    "RiskPct",
    "RewardPct",
    "RR",
]

DEFAULT_WEIGHTS = {
    "DecisionScore": 0.25,
    "SignalQuality": 0.15,
    "Lifecycle": 0.15,
    "RVOL": 0.10,
    "RSIZone": 0.08,
    "EMAStrength": 0.10,
    "SetupQuality": 0.07,
    "MarketQuality": 0.05,
    "RiskReward": 0.05,
}

LIFECYCLE_SCORES = {
    "SEED": 91,
    "BREAKOUT": 92,
    "MOMENTUM": 90,
    "EARLY": 88,
    "WATCH": 72,
    "EXTENDED": 45,
    "SKIP": 20,
    "UNKNOWN": 45,
}


def clamp(value, minimum=0, maximum=100):

    return max(
        minimum,
        min(
            maximum,
            float(value),
        ),
    )


def safe_float(value, default=0.0):

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_text(value, default=""):

    if value is None or pd.isna(value):
        return default

    return str(value)


def normalize_weights(weights=None):

    active = DEFAULT_WEIGHTS.copy()

    if weights:
        active.update(weights)

    total = sum(
        max(
            0,
            safe_float(value),
        )
        for value in active.values()
    )

    if total <= 0:
        return DEFAULT_WEIGHTS.copy()

    return {
        key: max(
            0,
            safe_float(value),
        )
        / total
        for key, value in active.items()
    }


def first_existing(row, columns, default=None):

    for column in columns:
        if column in row and not pd.isna(row.get(column)):
            return row.get(column)

    return default


def combined_reasons(row):

    return " ".join(
        safe_text(
            row.get(column, "")
        )
        for column in (
            "Reasons",
            "StrategyReasons",
            "Setup",
            "StrategySetup",
        )
    ).upper()


def contains_any(text, terms):

    return any(
        term.upper() in text
        for term in terms
    )


def signal_text(row):

    return safe_text(
        first_existing(
            row,
            [
                "StrategySignal",
                "Signal",
            ],
            "",
        )
    ).upper()


def setup_text(row):

    return safe_text(
        first_existing(
            row,
            [
                "StrategySetup",
                "Setup",
            ],
            "",
        )
    ).upper()


def lifecycle_state(row):

    return safe_text(
        first_existing(
            row,
            [
                "LifecycleState",
                "CurrentState",
            ],
            "UNKNOWN",
        ),
        "UNKNOWN",
    ).upper()


def bool_value(value):

    if isinstance(value, bool):
        return value

    return str(value).strip().upper() in {
        "TRUE",
        "1",
        "YES",
        "Y",
    }


def rsi_zone_label(rsi):

    if rsi <= 0:
        return "unknown"

    if 55 <= rsi <= 68:
        return "healthy accumulation"

    if 50 <= rsi < 55:
        return "early strength"

    if 68 < rsi <= 75:
        return "strong but warm"

    if rsi > 75:
        return "short-term overbought"

    if 45 <= rsi < 50:
        return "recovering"

    return "weak"


def normalize_market_quality(market_quality):

    if market_quality is None or market_quality.empty:
        return pd.DataFrame()

    quality = market_quality.copy()

    if "Market" not in quality.columns:
        quality["Market"] = ""

    if "StrategyMode" not in quality.columns:
        quality["StrategyMode"] = "Standard"

    if "QualityScore" not in quality.columns:
        quality["QualityScore"] = 0

    quality["Market"] = (
        quality["Market"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )
    quality["StrategyMode"] = (
        quality["StrategyMode"]
        .fillna("Standard")
        .astype(str)
        .replace("", "Standard")
    )
    quality["QualityScore"] = pd.to_numeric(
        quality["QualityScore"],
        errors="coerce",
    ).fillna(0)
    quality["_scan_time"] = pd.to_datetime(
        quality.get(
            "LastScanTime",
            pd.Series([None] * len(quality)),
        ),
        errors="coerce",
    )
    quality["_row_order"] = range(len(quality))

    return quality


def market_quality_lookup(market_quality):

    quality = normalize_market_quality(market_quality)
    lookup = {}

    if quality.empty:
        return lookup

    quality = quality.sort_values(
        [
            "_scan_time",
            "_row_order",
        ],
        na_position="first",
    )

    for _, row in quality.iterrows():
        market = row["Market"]
        mode = row["StrategyMode"]
        score = safe_float(
            row["QualityScore"]
        )
        lookup[
            (
                market,
                mode,
            )
        ] = score
        lookup[
            (
                market,
                "",
            )
        ] = score

    return lookup


def decision_score(row):

    return clamp(
        first_existing(
            row,
            [
                "StrategyScore",
                "Score",
            ],
            0,
        )
    )


def signal_quality_score(row):

    signal = signal_text(row)
    strategy_score = decision_score(row)

    if signal == "SKIP" or "SKIP" in signal:
        return 12

    if "EXTENDED" in signal:
        return 45

    if "SEED BUY" in signal:
        return clamp(92 + strategy_score * 0.06)

    if "SEED WATCH" in signal:
        return 80

    if "EARLY BUY" in signal:
        return clamp(88 + strategy_score * 0.08)

    if "BUY" in signal:
        return clamp(90 + strategy_score * 0.07)

    if "EARLY WATCH" in signal:
        return 76

    if "WATCH" in signal:
        return 70

    if "EARLY" in signal:
        return 68

    return 45


def lifecycle_score(row):

    state = lifecycle_state(row)
    score = LIFECYCLE_SCORES.get(
        state,
        LIFECYCLE_SCORES["UNKNOWN"],
    )

    if bool_value(row.get("StateChanged", False)) and state in {
        "EARLY",
        "BREAKOUT",
        "MOMENTUM",
    }:
        score += 5

    return clamp(score)


def rvol_score(row):

    rvol = safe_float(
        row.get(
            "RVOL",
            0,
        )
    )

    if rvol >= 5:
        return 100

    if rvol >= 3:
        return 92 + min(8, (rvol - 3) * 2)

    if rvol >= 2:
        return 82 + (rvol - 2) * 10

    if rvol >= 1.5:
        return 70 + (rvol - 1.5) * 24

    if rvol >= 1.2:
        return 58 + (rvol - 1.2) * 40

    if rvol >= 1:
        return 48 + (rvol - 1) * 50

    return clamp(25 + rvol * 23)


def rsi_zone_score(row):

    rsi = safe_float(
        row.get(
            "RSI",
            0,
        )
    )

    if rsi <= 0:
        return 40

    if 55 <= rsi <= 68:
        return clamp(96 - abs(rsi - 62) * 1.0)

    if 50 <= rsi < 55:
        return 78 + (rsi - 50) * 2.4

    if 68 < rsi <= 75:
        return 90 - (rsi - 68) * 2.5

    if 45 <= rsi < 50:
        return 60 + (rsi - 45) * 3

    if 75 < rsi <= 85:
        return 68 - (rsi - 75) * 3

    if rsi > 85:
        return 30

    return 42


def ema_strength_score(row):

    text = combined_reasons(row)
    score = 38

    if "EMA20 > EMA50" in text:
        score += 18

    if "EMA50 > EMA200" in text:
        score += 18

    if contains_any(
        text,
        [
            "EMA20 TURNING UP",
            "EMA20 RISING",
            "EMA20 SLOPE",
        ],
    ):
        score += 16

    if contains_any(
        text,
        [
            "ABOVE EMA20",
            "CLOSE RECLAIMED EMA20",
            "PRICE ABOVE EMA20",
        ],
    ):
        score += 16

    if contains_any(
        text,
        [
            "EMA9 NEAR/ABOVE EMA20",
            "EMA20 NEAR EMA50",
            "NEAR EMA20",
        ],
    ):
        score += 8

    if contains_any(
        text,
        [
            "MAJOR DOWNTREND",
            "TREND TOO WEAK",
            "PRICE BELOW EMA20",
        ],
    ):
        score -= 20

    return clamp(score)


def setup_quality_score(row):

    text = combined_reasons(row)
    setup = setup_text(row)
    score = 50

    if "EARLY TREND START" in setup:
        score = 92
    elif "SEED" in setup:
        score = 92
    elif "EARLY BASE" in setup:
        score = 90
    elif "EMA20 TURN" in setup:
        score = 88
    elif "ACCUMULATION START" in setup:
        score = 86
    elif "PRE-BREAKOUT" in setup:
        score = 84
    elif "BREAKOUT" in setup:
        score = 90
    elif "PULLBACK START" in setup:
        score = 84
    elif "EMA TURN" in setup:
        score = 80
    elif "ACCUMULATION" in setup:
        score = 78
    elif "EARLY REVERSAL" in setup:
        score = 78
    elif "SKIP" in setup:
        score = 18

    if contains_any(
        text,
        [
            "MACD BULLISH",
            "MACD HISTOGRAM POSITIVE",
            "MACD HISTOGRAM IMPROVING",
        ],
    ):
        score += 4

    if contains_any(
        text,
        [
            "VOLUME BREAKOUT",
            "POCKET PIVOT",
            "CLOSE ABOVE PREVIOUS HIGH",
        ],
    ):
        score += 4

    if "STAGE 2" in text:
        score += 3

    if contains_any(
        text,
        [
            "PRICE TOO FAR FROM EMA20",
            "EXTENDED",
        ],
    ):
        score -= 8

    return clamp(score)


def ema_distance_penalty(row):

    text = combined_reasons(row)

    if contains_any(
        text,
        [
            "PRICE TOO FAR FROM EMA20",
            "FAR FROM EMA20",
        ],
    ):
        return 10

    if "SLIGHTLY EXTENDED FROM EMA20" in text:
        return 4

    return 0


def risk_reward_details(row):

    price = safe_float(
        first_existing(
            row,
            [
                "Price",
                "Close",
                "close",
            ],
            0,
        )
    )
    stop_loss = safe_float(
        first_existing(
            row,
            [
                "StopLoss",
                "Stop Loss",
                "SL",
            ],
            0,
        )
    )
    target = safe_float(
        first_existing(
            row,
            [
                "Target",
                "TakeProfit",
                "Take Profit",
                "TP",
            ],
            0,
        )
    )
    atr = safe_float(
        first_existing(
            row,
            [
                "ATR",
                "atr",
            ],
            0,
        )
    )
    distance_ema20 = safe_float(
        first_existing(
            row,
            [
                "DistanceEMA20Pct",
                "distance_ema20",
                "DistanceEMA20",
            ],
            0,
        )
    )
    low90 = safe_float(
        first_existing(
            row,
            [
                "Low90",
                "low90",
            ],
            0,
        )
    )
    high20 = safe_float(
        first_existing(
            row,
            [
                "High20",
                "high20",
            ],
            0,
        )
    )
    high55 = safe_float(
        first_existing(
            row,
            [
                "High55",
                "high55",
            ],
            0,
        )
    )
    text = combined_reasons(row)
    setup = setup_text(row)
    state = lifecycle_state(row)
    rvol = safe_float(row.get("RVOL", 0))

    risk_pct = 0.0
    reward_pct = 0.0

    if price > 0 and stop_loss > 0 and stop_loss < price:
        risk_pct = (price - stop_loss) / price * 100

    if price > 0 and target > 0 and target > price:
        reward_pct = (target - price) / price * 100

    if risk_pct <= 0 and price > 0 and atr > 0:
        risk_pct = atr / price * 100 * 1.25

    if risk_pct <= 0 and distance_ema20 > 0:
        risk_pct = max(
            2.0,
            min(
                distance_ema20 + 1.25,
                12.0,
            ),
        )

    if risk_pct <= 0 and price > 0 and low90 > 0 and low90 < price:
        low90_risk = (price - low90) / price * 100

        if low90_risk <= 18:
            risk_pct = low90_risk

    if risk_pct <= 0:
        if contains_any(
            text,
            [
                "PRICE TOO FAR FROM EMA20",
                "FAR FROM EMA20",
            ],
        ) or state == "EXTENDED":
            risk_pct = 8.0
        elif "SLIGHTLY EXTENDED FROM EMA20" in text:
            risk_pct = 5.5
        elif contains_any(
            text,
            [
                "NEAR EMA20",
                "NOT EXTENDED FROM EMA20",
                "CLOSE RECLAIMED EMA20",
            ],
        ):
            risk_pct = 4.0
        else:
            risk_pct = 5.0

    if price > 0 and risk_pct > 0:
        risk_pct = max(
            risk_pct,
            0.75,
        )

    risk_pct = clamp(risk_pct, 0, 25)

    if reward_pct <= 0:
        multiplier = 2.2

        if "BREAKOUT" in setup:
            multiplier = 3.0
        elif "PULLBACK" in setup:
            multiplier = 2.5
        elif "MOMENTUM" in setup:
            multiplier = 2.4
        elif "EARLY" in setup:
            multiplier = 2.2
        elif state == "EXTENDED":
            multiplier = 1.4

        if rvol >= 3:
            multiplier += 0.2

        reward_pct = risk_pct * multiplier

        if price > 0 and high20 > price:
            reward_pct = max(
                reward_pct,
                (high20 - price) / price * 100,
            )

        if price > 0 and high55 > price:
            reward_pct = max(
                reward_pct,
                (high55 - price) / price * 100,
            )

    reward_pct = clamp(reward_pct, 0, 75)
    rr = reward_pct / risk_pct if risk_pct > 0 else 0
    rr = clamp(
        rr,
        0,
        10,
    )

    return {
        "RiskPct": round(risk_pct, 2),
        "RewardPct": round(reward_pct, 2),
        "RR": round(rr, 2),
    }


def risk_reward_score(row):

    ratio = safe_float(
        row.get(
            "RR",
            risk_reward_details(row)["RR"],
        )
    )

    if ratio >= 3:
        return 96

    if ratio >= 2.5:
        return 88

    if ratio >= 2:
        return 78

    if ratio >= 1:
        return 55 + (ratio - 1) * 20

    return 35


def market_quality_score(row, lookup):

    market = safe_text(
        row.get(
            "Market",
            "",
        )
    ).upper()
    mode = safe_text(
        row.get(
            "StrategyMode",
            "Standard",
        ),
        "Standard",
    )

    return clamp(
        lookup.get(
            (
                market,
                mode,
            ),
            lookup.get(
                (
                    market,
                    "",
                ),
                50,
            ),
        )
    )


def sector_strength_score(row):

    return 50


def opportunity_grade(score):

    score = safe_float(score)

    if score >= 97:
        return "★★★★★ Strong Buy"

    if score >= 90:
        return "★★★★☆ Buy"

    if score >= 85:
        return "★★★★☆ Watch Closely"

    if score >= 75:
        return "★★★☆☆ Watch"

    if score >= 65:
        return "★★☆☆☆ Early Watch"

    return "★☆☆☆☆ Ignore"


def base_recommended_action(score):

    score = safe_float(score)

    if score >= 97:
        return "Strong Buy"

    if score >= 90:
        return "Buy"

    if score >= 85:
        return "Watch Closely"

    if score >= 75:
        return "Watch"

    if score >= 65:
        return "Early Watch"

    return "Ignore"


def recommended_action(score, row):

    action = base_recommended_action(score)
    signal = signal_text(row)
    state = lifecycle_state(row)
    expansion_score = safe_float(row.get("ExpansionScore", 0))
    strategy_mode = safe_text(row.get("StrategyMode", "")).upper()

    if "SEED BUY" in signal and score >= 88 and action not in {
        "Strong Buy",
    }:
        action = "Buy"
    elif "SEED WATCH" in signal and score >= 82 and action in {
        "Watch",
        "Early Watch",
        "Ignore",
    }:
        action = "Watch Closely"
    elif "EARLY BUY" in signal and score >= 88 and action not in {
        "Strong Buy",
    }:
        action = "Buy"
    elif "BUY" in signal and score >= 85 and action in {
        "Watch",
        "Early Watch",
        "Ignore",
    }:
        action = "Watch Closely"

    if state == "EXTENDED" and action == "Strong Buy":
        action = "Buy"

    if "SKIP" in signal and action in {
        "Strong Buy",
        "Buy",
    }:
        action = "Watch"

    if (
        "PURE EARLY" in strategy_mode
        and (
            state in {
                "MOMENTUM",
                "EXTENDED",
            }
            or expansion_score >= 70
        )
    ):
        action = "Ignore"

    return action


def market_quality_label(score):

    score = safe_float(score)

    if score >= 80:
        return "Strong"

    if score >= 60:
        return "Healthy"

    if score >= 40:
        return "Mixed"

    if score >= 20:
        return "Weak"

    return "Avoid"


def score_penalties(row):

    penalties = []
    signal = signal_text(row)
    state = lifecycle_state(row)
    rsi = safe_float(row.get("RSI", 0))
    rvol = safe_float(row.get("RVOL", 0))
    expansion_score = safe_float(row.get("ExpansionScore", 0))
    strategy_mode = safe_text(row.get("StrategyMode", "")).upper()

    if rsi > 75:
        penalties.append(
            (
                "RSIOverbought",
                min(12, 3 + (rsi - 75) * 1.4),
            )
        )
    elif rsi > 70:
        penalties.append(
            (
                "RSIAbovePureEarlyZone",
                4,
            )
        )

    distance_penalty = ema_distance_penalty(row)

    if distance_penalty:
        penalties.append(
            (
                "ExtendedFromEMA20",
                distance_penalty,
            )
        )

    if state == "EXTENDED":
        penalties.append(
            (
                "ExtendedLifecycle",
                14,
            )
        )

    if "PURE EARLY" in strategy_mode and state in {
        "MOMENTUM",
        "EXTENDED",
    }:
        penalties.append(
            (
                "AlreadyRunningInSeedMode",
                28 if state == "MOMENTUM" else 36,
            )
        )

    if expansion_score >= 70:
        penalties.append(
            (
                "ExpansionAlreadyStarted",
                min(
                    42,
                    18 + expansion_score * 0.24,
                ),
            )
        )
    elif expansion_score >= 35:
        penalties.append(
            (
                "ExpansionRisk",
                min(
                    18,
                    6 + expansion_score * 0.18,
                ),
            )
        )

    setup = setup_text(row)

    if "BREAKOUT" in setup and "PRE-BREAKOUT" not in setup:
        penalties.append(
            (
                "BreakoutSetup",
                8,
            )
        )

    if rvol < 1:
        penalties.append(
            (
                "LowRVOL",
                8,
            )
        )
    elif rvol < 1.2:
        penalties.append(
            (
                "SoftRVOL",
                4,
            )
        )

    if "SKIP" in signal:
        penalties.append(
            (
                "SkipSignal",
                35,
            )
        )

    return penalties


def score_bonuses(row):

    bonuses = []
    signal = signal_text(row)
    state = lifecycle_state(row)
    previous = safe_text(
        row.get(
            "PreviousLifecycleState",
            "",
        )
    ).upper()
    days = safe_float(row.get("DaysInState", 0))
    rvol = safe_float(row.get("RVOL", 0))

    if "BUY" in signal and state in {
        "EARLY",
        "BREAKOUT",
        "MOMENTUM",
    }:
        bonuses.append(
            (
                "AlignedBuySignal",
                2.5,
            )
        )

    if state == "EARLY" and days <= 3:
        bonuses.append(
            (
                "FreshEarlyState",
                1.5,
            )
        )

    if previous == "SKIP" and state in {
        "EARLY",
        "BREAKOUT",
        "MOMENTUM",
    }:
        bonuses.append(
            (
                "FreshTransition",
                1.0,
            )
        )

    if rvol >= 3:
        bonuses.append(
            (
                "HighRVOL",
                1.0,
            )
        )

    return bonuses


def tie_break_adjustment(row, component_scores):

    symbol = safe_text(row.get("Symbol", ""))
    rvol = safe_float(row.get("RVOL", 0))
    days = safe_float(row.get("DaysInState", 0))
    symbol_hash = sum(ord(char) for char in symbol) % 97
    fresh_bonus = max(0, 8 - days) / 8 * 0.12

    return round(
        min(rvol, 8) * 0.035
        + component_scores["RSIZone"] / 100 * 0.20
        + component_scores["DecisionScore"] / 100 * 0.15
        + fresh_bonus
        + symbol_hash / 1000,
        4,
    )


def opportunity_reasons(row, component_scores, penalties=None):

    reasons = []
    penalties = penalties or []
    signal = signal_text(row)
    lifecycle = lifecycle_state(row)
    previous = safe_text(
        row.get(
            "PreviousLifecycleState",
            "",
        )
    ).upper()
    setup = safe_text(
        first_existing(
            row,
            [
                "StrategySetup",
                "Setup",
            ],
            "",
        )
    )
    text = combined_reasons(row)
    rsi = safe_float(
        row.get(
            "RSI",
            0,
        )
    )
    rvol = safe_float(
        row.get(
            "RVOL",
            0,
        )
    )
    risk_pct = safe_float(row.get("RiskPct", 0))
    reward_pct = safe_float(row.get("RewardPct", 0))
    rr = safe_float(row.get("RR", 0))
    market_quality = safe_float(
        component_scores.get(
            "MarketQuality",
            0,
        )
    )

    if signal:
        reasons.append(f"✓ {signal} signal")

    if "SEED" in signal or "SEED" in setup.upper():
        reasons.append("✓ True early-stage setup")

    if lifecycle in {
        "EARLY",
        "BREAKOUT",
        "MOMENTUM",
    }:
        reasons.append(f"✓ Lifecycle: {lifecycle}")

    if previous and previous != lifecycle and previous != "UNKNOWN":
        reasons.append(f"✓ Previous lifecycle was {previous}")

    if rvol >= 1.5:
        reasons.append(
            f"✓ RVOL {rvol:.2f} shows strong volume expansion"
        )
    elif rvol >= 1.2:
        reasons.append(f"✓ RVOL {rvol:.2f} is expanding")
    elif rvol > 0:
        reasons.append(f"⚠ RVOL {rvol:.2f} is still light")

    if 50 <= rsi <= 75:
        reasons.append(
            f"✓ RSI {rsi:.1f} is in {rsi_zone_label(rsi)} zone"
        )
    elif rsi > 75:
        reasons.append(
            f"⚠ RSI {rsi:.1f} is short-term overbought"
        )
    elif rsi > 0:
        reasons.append(f"⚠ RSI {rsi:.1f} is not in the ideal zone")

    if contains_any(
        text,
        [
            "EMA20 TURNING UP",
            "EMA20 RISING",
            "EMA20 SLOPE TURNED POSITIVE",
        ],
    ):
        reasons.append("✓ EMA20 rising")

    if contains_any(
        text,
        [
            "ABOVE EMA20",
            "CLOSE RECLAIMED EMA20",
            "PRICE ABOVE EMA20",
            "CLOSE NEAR EMA20",
            "CLOSE SLIGHTLY ABOVE EMA20",
        ],
    ):
        reasons.append("✓ Near EMA20")

    if contains_any(
        text,
        [
            "MACD BULLISH",
            "MACD HISTOGRAM POSITIVE",
            "MACD HISTOGRAM IMPROVING",
        ],
    ):
        reasons.append("✓ MACD momentum improving")

    if setup:
        reasons.append(f"✓ Setup: {setup}")

    if "VOLUME PICKUP WITHOUT BREAKOUT" in text:
        reasons.append("✓ Volume pickup without breakout")

    if "NOT EXTENDED" in text:
        reasons.append("✓ Not extended")

    if rr > 0:
        reasons.append(
            f"✓ Estimated RR {rr:.2f} from {risk_pct:.2f}% risk / {reward_pct:.2f}% reward"
        )

    if market_quality > 0:
        label = market_quality_label(market_quality)

        if market_quality >= 60:
            reasons.append(f"✓ Market Quality is {label}")
        elif market_quality >= 40:
            reasons.append(
                f"⚠ Market Quality is {label}, use selective sizing"
            )
        else:
            reasons.append(f"⚠ Market Quality is {label}")

    for name, _ in penalties:
        if name == "ExtendedFromEMA20":
            reasons.append("⚠ Price extended from EMA20")
        elif name == "ExtendedLifecycle":
            reasons.append("⚠ Lifecycle EXTENDED")
        elif name == "BreakoutSetup":
            reasons.append("⚠ Breakout setup")
        elif name == "RSIAbovePureEarlyZone":
            reasons.append("⚠ RSI above Pure Early zone")
        elif name in {
            "LowRVOL",
            "SoftRVOL",
        }:
            reasons.append("⚠ Low RVOL")
        elif name == "SkipSignal":
            reasons.append("⚠ Strategy signal is SKIP")
        elif name == "AlreadyRunningInSeedMode":
            reasons.append("⚠ Already running in Pure Early mode")
        elif name == "ExpansionAlreadyStarted":
            reasons.append("⚠ Expansion already started")
        elif name == "ExpansionRisk":
            reasons.append("⚠ Expansion risk rising")

    if not reasons:
        reasons.append("✓ Needs more confirmation")

    deduped = []
    seen = set()

    for reason in reasons:
        if reason not in seen:
            deduped.append(reason)
            seen.add(reason)

    return "; ".join(deduped)


def confidence_score(row, component_scores, penalties=None):

    penalties = penalties or []
    strong_components = sum(
        1
        for value in component_scores.values()
        if safe_float(value) >= 70
    )
    consistency = strong_components / max(
        1,
        len(component_scores),
    ) * 100
    signal_strength = component_scores.get(
        "SignalQuality",
        0,
    )
    market_quality = component_scores.get(
        "MarketQuality",
        0,
    )
    penalty_points = sum(
        value
        for _, value in penalties
    )
    penalty_score = clamp(
        100 - penalty_points * 4,
        0,
        100,
    )
    positive_count = sum(
        1
        for key in [
            "DecisionScore",
            "SignalQuality",
            "Lifecycle",
            "RVOL",
            "RSIZone",
            "EMAStrength",
            "SetupQuality",
            "RiskReward",
        ]
        if component_scores.get(key, 0) >= 75
    )
    reason_strength = clamp(
        positive_count * 12,
        0,
        100,
    )
    volume_strength = rvol_score(row)
    rsi_strength = rsi_zone_score(row)
    rr_strength = component_scores.get(
        "RiskReward",
        0,
    )

    return round(
        clamp(
            signal_strength * 0.20
            + consistency * 0.18
            + reason_strength * 0.12
            + penalty_score * 0.12
            + market_quality * 0.10
            + volume_strength * 0.12
            + rsi_strength * 0.10
            + rr_strength * 0.06
        ),
        1,
    )


def merge_lifecycle(scanner_results, lifecycle):

    if lifecycle is None or lifecycle.empty:
        return scanner_results

    data = scanner_results.copy()

    needed = {
        "LifecycleState",
        "PreviousLifecycleState",
        "DaysInState",
        "StateChanged",
    }

    if needed.issubset(data.columns):
        return data

    life = lifecycle.copy()
    rename_map = {
        "CurrentState": "LifecycleState",
        "PreviousState": "PreviousLifecycleState",
    }
    life = life.rename(
        columns=rename_map
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

    if "Symbol" not in merge_columns or "Market" not in merge_columns:
        return data

    data = data.merge(
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
            "_Lifecycle",
        ),
    )

    for column in needed:
        fallback = f"{column}_Lifecycle"

        if column not in data.columns and fallback in data.columns:
            data[column] = data[fallback]
        elif fallback in data.columns:
            data[column] = data[column].fillna(
                data[fallback]
            )

    return data.drop(
        columns=[
            column
            for column in data.columns
            if column.endswith("_Lifecycle")
        ],
        errors="ignore",
    )


def calculate_opportunities(
    scanner_results,
    lifecycle=None,
    market_quality=None,
    weights=None,
):

    if scanner_results is None:
        return pd.DataFrame()

    data = scanner_results.copy()

    if data.empty:
        return data

    data = merge_lifecycle(
        data,
        lifecycle,
    )
    data = data.drop(
        columns=[
            column
            for column in OPPORTUNITY_COLUMNS
            if column in data.columns
        ],
        errors="ignore",
    )
    weights = normalize_weights(weights)
    quality_lookup = market_quality_lookup(market_quality)
    rows = []

    for _, row in data.iterrows():
        risk_details = risk_reward_details(row)
        enriched_row = row.copy()

        for key, value in risk_details.items():
            enriched_row[key] = value

        component_scores = {
            "DecisionScore": decision_score(enriched_row),
            "SignalQuality": signal_quality_score(enriched_row),
            "Lifecycle": lifecycle_score(enriched_row),
            "RVOL": rvol_score(enriched_row),
            "RSIZone": rsi_zone_score(enriched_row),
            "EMAStrength": ema_strength_score(enriched_row),
            "SetupQuality": setup_quality_score(enriched_row),
            "MarketQuality": market_quality_score(
                enriched_row,
                quality_lookup,
            ),
            "RiskReward": risk_reward_score(enriched_row),
        }
        base_score = sum(
            component_scores[key] * weights.get(
                key,
                0,
            )
            for key in component_scores
        )
        penalties = score_penalties(enriched_row)
        bonuses = score_bonuses(enriched_row)
        score = (
            base_score
            - sum(value for _, value in penalties)
            + sum(value for _, value in bonuses)
            + tie_break_adjustment(
                enriched_row,
                component_scores,
            )
        )
        score = round(
            clamp(score),
            2,
        )
        rows.append({
            "OpportunityScore": score,
            "OpportunityGrade": opportunity_grade(score),
            "Confidence": confidence_score(
                enriched_row,
                component_scores,
                penalties=penalties,
            ),
            "RecommendedAction": recommended_action(
                score,
                enriched_row,
            ),
            "OpportunityReasons": opportunity_reasons(
                enriched_row,
                component_scores,
                penalties=penalties,
            ),
            **risk_details,
        })

    scored = pd.concat(
        [
            data.reset_index(drop=True),
            pd.DataFrame(rows),
        ],
        axis=1,
    )
    scored = scored.sort_values(
        [
            "OpportunityScore",
            "StrategyScore"
            if "StrategyScore" in scored.columns
            else "Score",
        ],
        ascending=[
            False,
            False,
        ],
    ).reset_index(drop=True)
    scored["OpportunityRank"] = range(
        1,
        len(scored) + 1,
    )

    return scored


def save_opportunities(opportunities, path=OPPORTUNITY_FILE):

    path = Path(path)
    path.parent.mkdir(
        exist_ok=True
    )
    opportunities.to_csv(
        path,
        index=False,
    )

    return path


def load_opportunities(path=OPPORTUNITY_FILE):

    path = Path(path)

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
