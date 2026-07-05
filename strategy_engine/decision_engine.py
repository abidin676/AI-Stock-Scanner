"""
River Alpha Decision Engine

This module orchestrates all strategy engines.

It does NOT implement any scoring logic.

Responsibilities
----------------
- Call Trend Engine
- Call Momentum Engine
- Call Volume Engine
- Call Base Engine
- Call Quality Gate
- Call Stage Engine
- Call Signal Engine

The Decision Engine only aggregates results.
"""


from strategy_engine.momentum import momentum_score
from strategy_engine.volume import volume_score
from strategy_engine.base import base_score
from strategy_engine.quality_gate import quality_gate
from strategy_engine.market_profiles import get_profile
from strategy_engine.score import calculate_score, calculate_weighted_score
from strategy_engine.signal import build_signal
from strategy_engine.price import price_score
from strategy_engine.trend import trend_score
from strategy_engine.breakout import breakout_score

from datetime import datetime
from collections.abc import Callable
import pandas as pd

def make_decision(
    df,
    ema_cross_func,
    symbol="",
    market="",
):
    
    """
    Build one unified decision object.

    Parameters
    ----------
    df : pandas.DataFrame
        Price history with indicators.

    price_score : int
        Existing price score.

    ema_cross_func : callable
        EMA cross detection function.

    symbol : str
        Optional symbol.

    market : str
        Optional market.

    Returns
    -------
    dict
    """
    if df.empty:
        raise ValueError("DataFrame is empty.")

    last = df.iloc[-1]


    # -------------------------
    # Strategy Engines
    # -------------------------

    trend = trend_score(
        last,
        market=market,
    )
    momentum = momentum_score(
        last,
        df,
        ema_cross_func,
        market=market,
    )

    volume = volume_score(
        last,
        market=market,
    )

    base = base_score(
        last,
        market=market,
    )
    price = price_score(last)
    breakout = breakout_score(last)

    # -------------------------
    # Quality Gate
    # -------------------------

    gate = quality_gate(
        trend,
        momentum,
        volume,
        base,
        price["score"],
    )

    # -------------------------
    # Stage
    # -------------------------

    stage = calculate_score(df)

    engine_results = {
        "trend": trend,
        "momentum": momentum,
        "volume": volume,
        "base": base,
        "price": price,
        "stage": stage,
        "breakout": breakout,
    }

    # -------------------------
    # Weighted Score
    # -------------------------

    profile = get_profile(market)

    score = calculate_weighted_score(
        engine_results,
        profile["weights"],
    )

    for engine, weighted in score["weighted_breakdown"].items():
        engine_results[engine]["weight"] = weighted["weight"]
        engine_results[engine]["weighted_score"] = weighted["weighted_score"]

# -------------------------
# DEBUG
# -------------------------

    print(
        f"[DEBUG] {symbol} | "
        f"Market={market} | "
        f"Raw={score['raw_total_score']}/{score['raw_max_score']} "
        f"({score['raw_score_percent']}%) | "
        f"Weighted={score['weighted_total_score']}/100 "
        f"({score['score_percent']}%)"
    )
# -------------------------
# Signal
# -------------------------

    if gate["passed"]:

        print(
            f"[DEBUG] {symbol}"
        )
        print(
            f"Market   : {market}"
        )
        print(
            f"Raw Score: {score['raw_total_score']}/{score['raw_max_score']}"
        )
        print(
            f"Weighted : {score['weighted_total_score']}/100"
        )

        signal = build_signal(
            score["weighted_total_score"],
            score["weighted_max_score"],
            market,
        )

        print(
            f"Signal   : {signal['signal']}"
        )
        print("-" * 40)

    else:

        print(
            f"[DEBUG] {symbol}"
        )
        print(
            f"Market   : {market}"
        )
        print(
            f"Raw Score: {score['raw_total_score']}/{score['raw_max_score']}"
        )
        print(
            f"Weighted : {score['weighted_total_score']}/100"
        )
        print(
            f"Gate     : FAILED"
        )
        print("-" * 40)

        signal = {
            "engine": "signal",
            "signal": "SKIP",
            "passed": False,
            "score_percent": score["score_percent"],
        }

    # -------------------------
    # Reasons
    # -------------------------

    reasons = []

    for engine in (
        trend,
        momentum,
        volume,
        base,
        price,
        gate,
        stage,
        breakout
    ):
        reasons.extend(engine.get("reasons", []))

    # -------------------------
    # Result
    # -------------------------

    return {

        "total_score": score["raw_total_score"],
        
        "max_score": score["raw_max_score"],

        "raw_score_percent": score["raw_score_percent"],

        "weighted_score": score["weighted_total_score"],

        "weighted_max_score": score["weighted_max_score"],

        "weighted_breakdown": score["weighted_breakdown"],
        
        "score_percent": signal["score_percent"],

        "signal": signal["signal"],

        "passed": signal["passed"],

        "trend": trend,

        "momentum": momentum,

        "volume": volume,

        "base": base,

        "breakout": breakout,

        "quality_gate": gate,

        "stage": stage,

        "reasons": reasons,

        "price": price,

        "metadata": {
            "symbol": symbol,
            "market": market,
            "version": "1.2.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    }
