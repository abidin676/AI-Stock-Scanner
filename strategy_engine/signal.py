"""
River Alpha Signal Engine
"""

from strategy_engine.market_profiles import get_profile


def build_signal(
    total_score: int,
    max_score: int,
    market: str = "USA",
):
    """
    Convert score into signal using market profile.
    """

    if max_score <= 0:
        score_percent = 0
    else:
        score_percent = round(
            total_score / max_score * 100
        )

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