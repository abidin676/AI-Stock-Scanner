import pandas as pd


from strategy_engine.decision_engine import make_decision
from strategy_engine.filters import mandatory_filters
from strategy_engine.setup import detect_setup
from strategy_engine.price import price_score


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

def trend_start(
    df,
    market="SET",
):

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
            "reasons": ["Not enough data"],
        }

    # --------------------------------------
    # Last Candle
    # --------------------------------------

    last = df.iloc[-1]
    price_engine = price_score(last)

    price = round(float(last["close"]), 2)
    rsi = round(float(last["rsi"]), 1)
    rvol = round(float(last["rvol"]), 2)

    distance20 = (
        last["close"] - last["ema20"]
    ) / last["ema20"]

    # --------------------------------------
    # Setup
    # --------------------------------------

    setup = detect_setup(
        last,
        distance20,
    )

    # --------------------------------------
    # Mandatory Filters
    # --------------------------------------


    filter_result = mandatory_filters(
        last,
        market=market
    )

    # --------------------------------------
    # Decision Engine
    # --------------------------------------

    decision = make_decision(
        df=df,
        ema_cross_func=ema_cross_within,
        symbol=last.get("symbol", ""),
        market=market,
    )

    # --------------------------------------
    # Override by Filters
    # --------------------------------------

    if not filter_result["passed"]:

        decision["signal"] = filter_result["signal"]
        decision["passed"] = False

        if "reasons" in filter_result:
            decision["reasons"].extend(
                filter_result["reasons"]
            )

    # --------------------------------------
    # Score Breakdown
    # --------------------------------------

    score_breakdown = {

        "Trend": decision["trend"],

        "Momentum": decision["momentum"],

        "Volume": decision["volume"],

        "Base": decision["base"],

        "Breakout": decision["breakout"],

        "Price": decision["price"],

        "Stage": decision["stage"],

    }

    # --------------------------------------
    # Return
    # --------------------------------------

    return {

        "signal": decision["signal"],

        "setup": setup,

        "passed": decision["passed"],

        "score": decision["score_percent"],

        "price": price,

        "rsi": rsi,

        "rvol": rvol,

        "score_breakdown": score_breakdown,

        "reasons": decision["reasons"],

    }
