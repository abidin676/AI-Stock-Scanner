def price_score(last):
    """
    River Alpha Price Engine
    """

    score = 0
    reasons = []

    distance20 = (
        (last["close"] - last["ema20"])
        / last["ema20"]
    )

    # --------------------------------------
    # Above EMA20
    # --------------------------------------

    if last["close"] > last["ema20"]:
        score += 5
        reasons.append("Above EMA20")

    # --------------------------------------
    # Near EMA20
    # --------------------------------------

    if distance20 <= 0.03:
        score += 5
        reasons.append("Near EMA20")

    # --------------------------------------
    # Quality
    # --------------------------------------

    if score == 10:
        quality = "EXCELLENT"

    elif score == 5:
        quality = "GOOD"

    else:
        quality = "WEAK"

    return {
        "engine": "price",
        "score": score,
        "max_score": 10,
        "quality": quality,
        "reasons": reasons,
    }