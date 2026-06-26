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

from datetime import datetime
from collections.abc import Callable
import pandas as pd

def make_decision(
    df: pd.DataFrame,
    price_score: int,
    ema_cross_func: Callable,
    symbol: str = "",
    market: str = "",
) -> dict:
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

    trend = trend_score(last)

    momentum = momentum_score(
        last,
        df,
        ema_cross_func,
    )

    volume = volume_score(last)

    base = base_score(last)

    # -------------------------
    # Quality Gate
    # -------------------------

    gate = quality_gate(
        trend,
        momentum,
        volume,
        base,
        price_score,
    )

    # -------------------------
    # Stage
    # -------------------------

    stage = calculate_score(df)

    stage_score = stage["score"]
    stage_reasons = stage["reasons"]

    # -------------------------
    # Total Score
    # -------------------------

    total_score = (
        trend["score"]
        + momentum["score"]
        + volume["score"]
        + base["score"]
        + stage_score
    )
    max_score = (
        trend["max_score"]
        + momentum["max_score"]
        + volume["max_score"]
        + base["max_score"]
        + stage["max_score"]
    )

    # -------------------------
    # Signal
    # -------------------------

    if gate["passed"]:
        signal = build_signal(total_score)
    else:
        signal = {
            "engine": "signal",
            "signal": "SKIP",
            "passed": False,
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
        gate,
        stage,
    ):
        reasons.extend(engine.get("reasons", []))

    # -------------------------
    # Result
    # -------------------------

    return {

        "total_score": total_score,
        
        "max_score": max_score,

        "signal": signal["signal"],

        "passed": signal["passed"],

        "trend": trend,

        "momentum": momentum,

        "volume": volume,

        "base": base,

        "quality_gate": gate,

        "stage": stage,

        "reasons": reasons,

        "max_score": max_score,

        "metadata": {
            "symbol": symbol,
            "market": market,
            "version": "1.2.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    }