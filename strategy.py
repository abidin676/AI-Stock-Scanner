import pandas as pd

from strategy_engine.filters import mandatory_filters
from strategy_engine.trend import trend_score
from strategy_engine.momentum import momentum_score
from strategy_engine.volume import volume_score
from strategy_engine.base import base_score
from strategy_engine.signal import build_signal
from strategy_engine.setup import detect_setup


# ==========================================================
# EMA9 Cross EMA20 ภายใน X วัน
# ==========================================================

def ema_cross_within(df, days=3):

    if len(df) < days + 2:
        return False

    for i in range(days):

        prev = df.iloc[-(i + 2)]
        curr = df.iloc[-(i + 1)]

        if (
            prev["ema9"] <= prev["ema20"]
            and curr["ema9"] > curr["ema20"]
        ):
            return True

    return False


# ==========================================================
# River Alpha Strategy Engine
# ==========================================================

def trend_start(df):

    # --------------------------------------
    # Not enough data
    # --------------------------------------

    if len(df) < 200:

        return {

            "signal": "NO DATA",
            "setup": "-",
            "passed": False,

            "score": 0,

            "price": None,
            "rsi": None,
            "rvol": None,

            "score_breakdown": {},

            "reasons": [
                "Not enough data"
            ],

        }

    # --------------------------------------
    # Last Candle
    # --------------------------------------

    last = df.iloc[-1]

    price = round(
        float(last["close"]),
        2
    )

    rsi = round(
        float(last["rsi"]),
        1
    )

    rvol = round(
        float(last["rvol"]),
        2
    )

    distance20 = (
        last["close"] -
        last["ema20"]
    ) / last["ema20"]

    # --------------------------------------
    # Mandatory Filters
    # --------------------------------------

    result = mandatory_filters(last)

    if not result["passed"]:

        return {

            "signal": result["signal"],
            "setup": "-",
            "passed": False,

            "score": 0,

            "price": price,
            "rsi": rsi,
            "rvol": rvol,

            "score_breakdown": {},

            "reasons": [
                result["reason"]
            ],

        }

    # --------------------------------------
    # Initialize
    # --------------------------------------

    reasons = []

        # --------------------------------------
    # Trend
    # --------------------------------------

    trend = trend_score(last)

    reasons.extend(trend["reasons"])

    # --------------------------------------
    # Momentum
    # --------------------------------------

    momentum = momentum_score(
        last,
        df,
        ema_cross_within,
    )

    reasons.extend(momentum["reasons"])

    # --------------------------------------
    # Price
    # --------------------------------------

    price_score = 0

    price_reasons = []

    if last["close"] > last["ema20"]:

        price_score += 5
        price_reasons.append("Above EMA20")

    if distance20 <= 0.03:

        price_score += 5
        price_reasons.append("Near EMA20")

    reasons.extend(price_reasons)

    # --------------------------------------
    # Volume
    # --------------------------------------

    volume = volume_score(last)

    reasons.extend(volume["reasons"])

    # --------------------------------------
    # Base
    # --------------------------------------

    base = base_score(last)

    reasons.extend(base["reasons"])

    # --------------------------------------
    # Overall Score
    # --------------------------------------

    overall = (

        trend["score"]

        + momentum["score"]

        + volume["score"]

        + base["score"]

        + price_score

    )

    overall = max(
        0,
        min(overall, 100)
    )

        # --------------------------------------
    # Signal
    # --------------------------------------

    signal, passed = build_signal(
        overall
    )

    # --------------------------------------
    # Setup
    # --------------------------------------

    setup = detect_setup(
        last,
        distance20,
    )

    # --------------------------------------
    # Debug
    # --------------------------------------

    if last["symbol"] == "ITC":

        print("=" * 60)

        print(last["symbol"])

        print(
            "Trend    :",
            trend["score"]
        )

        print(
            "Momentum :",
            momentum["score"]
        )

        print(
            "Volume   :",
            volume["score"]
        )

        print(
            "Base     :",
            base["score"]
        )

        print(
            "Price    :",
            price_score
        )

        print(
            "TOTAL    :",
            overall
        )

        print()

        print("Reasons")

        for r in reasons:

            print("-", r)

        print("=" * 60)

        # --------------------------------------
    # Score Breakdown
    # --------------------------------------

    score_breakdown = {

        "Trend": trend,

        "Momentum": momentum,

        "Volume": volume,

        "Base": base,

        "Price": {

            "score": price_score,

            "max_score": 10,

            "quality": (

                "EXCELLENT"
                if price_score == 10

                else "GOOD"
                if price_score == 5

                else "WEAK"

            ),

            "reasons": price_reasons,

        },

    }

    # --------------------------------------
    # Return
    # --------------------------------------

    return {

        "signal": signal,

        "setup": setup,

        "passed": passed,

        "score": overall,

        "price": price,

        "rsi": rsi,

        "rvol": rvol,

        "score_breakdown": score_breakdown,

        "reasons": reasons,

    }    