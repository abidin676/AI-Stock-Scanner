def mandatory_filters(last):

    # ======================================
    # Price too far from EMA20
    # ======================================

    distance20 = (
        last["close"] - last["ema20"]
    ) / last["ema20"]

    if distance20 > 0.08:

        return {
            "passed": False,
            "signal": "EXTENDED",
            "reason": "Price too far from EMA20"
        }

    # ======================================
    # RSI Overheated
    # ======================================

    if last["rsi"] >= 75:

        return {
            "passed": False,
            "signal": "EXTENDED",
            "reason": "RSI Overbought"
        }

    # ======================================
    # Too Far From Base
    # ======================================

    if last["move_from_low90"] > 80:

        return {
            "passed": False,
            "signal": "EXTENDED",
            "reason": "Too Far From Base"
        }

    # ======================================
    # Major Downtrend
    # ======================================

    if (
        last["close"] < last["ema200"]
        and last["ema20"] < last["ema50"]
        and last["ema50"] < last["ema200"]
    ):

        return {
            "passed": False,
            "signal": "SKIP",
            "reason": "Major Downtrend"
        }

    return {
        "passed": True
    }