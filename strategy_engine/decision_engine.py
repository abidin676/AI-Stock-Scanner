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
from strategy_engine.score import calculate_score
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

    # -------------------------
    # Total Score
    # -------------------------

    total_score = (
        trend["score"]
        + momentum["score"]
        + volume["score"]
        + base["score"]
        + breakout["score"]
        + price["score"]
        + stage["score"]
    )
    max_score = (
        trend["max_score"]
        + momentum["max_score"]
        + volume["max_score"]
        + base["max_score"]
        + breakout["max_score"]
        + price["max_score"]
        + stage["max_score"]
    )
# -------------------------
# DEBUG
# -------------------------

    score_percent = round(
        total_score / max_score * 100
    )

    print(
        f"[DEBUG] {symbol} | "
        f"Market={market} | "
        f"Score={total_score}/{max_score} "
        f"({score_percent}%)"
    )
# -------------------------
# Signal
# -------------------------

    score_percent = round(
        total_score / max_score * 100
)

    if gate["passed"]:

        print(
            f"[DEBUG] {symbol}"
        )
        print(
            f"Market   : {market}"
        )
        print(
            f"Score    : {total_score}/{max_score}"
        )
        print(
            f"Percent  : {score_percent}%"
        )

        signal = build_signal(
            total_score,
            max_score,
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
            f"Score    : {total_score}/{max_score}"
        )
        print(
            f"Percent  : {score_percent}%"
        )
        print(
            f"Gate     : FAILED"
        )
        print("-" * 40)

        signal = {
            "engine": "signal",
            "signal": "SKIP",
            "passed": False,
            "score_percent": score_percent,
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

        "total_score": total_score,
        
        "max_score": max_score,
        
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
