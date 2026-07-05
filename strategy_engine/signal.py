"""
River Alpha Signal Engine
"""

from strategy_engine.market_profiles import get_profile


def build_signal(
    score_percent: int,
    max_score=None,
    market: str = "USA",
):
    """
    Convert weighted score percent into signal using market profile.
    """

    if isinstance(max_score, str):
        market = max_score

    if score_percent is None:
        score_percent = 0

    score_percent = round(float(score_percent))

    profile = get_profile(market)

    t = profile["thresholds"]

    if score_percent >= t["BUY"]:
        signal = "🟢 BUY"

    elif score_percent >= t["WATCH"]:
        signal = "👀 WATCH"

    elif score_percent >= t["EARLY"]:
        signal = "🌱 EARLY"

    else:
        signal = "SKIP"

    return {
        "engine": "signal",
        "signal": signal,
        "passed": signal != "SKIP",
        "score_percent": score_percent,
    }
