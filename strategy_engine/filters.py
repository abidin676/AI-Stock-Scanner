"""
River Alpha Mandatory Filters
"""

from strategy_engine.market_profiles import get_profile


def mandatory_filters(last, market="USA"):

    profile = get_profile(market)

    f = profile["filters"]

    # ======================================
    # Price too far from EMA20
    # ======================================

    distance20 = (
        last["close"] - last["ema20"]
    ) / last["ema20"]

    if distance20 > f["max_distance_ema20"]:

        return {
            "passed": False,
            "signal": "EXTENDED",
            "reasons": [
                "Price too far from EMA20"
            ],
        }

    # ======================================
    # RSI Overheated
    # ======================================

    if last["rsi"] >= f["max_rsi"]:

        return {
            "passed": False,
            "signal": "EXTENDED",
            "reasons": [
                "RSI Overbought"
            ],
        }

    # ======================================
    # Too Far From Base
    # ======================================

    if last["move_from_low90"] > f["max_move_from_low90"]:

        return {
            "passed": False,
            "signal": "EXTENDED",
            "reasons": [
                "Too Far From Base"
            ],
        }

    # ======================================
    # Major Downtrend
    # ======================================

    if (
        last["close"] < last["ema200"]
        and last["ema20"] < last["ema50"]
        and last["ema50"] < last["ema200"]
    ):

        # SET อนุโลม Stage 1 ได้
        if not f["allow_stage1"]:

            return {
                "passed": False,
                "signal": "SKIP",
                "reasons": [
                    "Major Downtrend"
                ],
            }

    return {
        "passed": True,
        "signal": "",
        "reasons": [],
    }