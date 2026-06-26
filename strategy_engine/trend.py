def trend_score(last):

    score = 0
    reasons = []

    # ======================================
    # EMA Alignment (12)
    # ======================================

    if last["ema20"] > last["ema50"]:
        score += 6
        reasons.append("EMA20 > EMA50")

    if last["ema50"] > last["ema200"]:
        score += 6
        reasons.append("EMA50 > EMA200")

    # ======================================
    # EMA Slope (10)
    # ======================================

    if last["ema20_slope"] > 0:
        score += 5
        reasons.append("EMA20 Turning Up")

    if last["ema50_slope"] > 0:
        score += 5
        reasons.append("EMA50 Turning Up")

    # ======================================
    # Structure (8)
    # ======================================

    if last["higher_low"]:
        score += 3
        reasons.append("Higher Low")

    if last["higher_high"]:
        score += 2
        reasons.append("Higher High")

    if last["trend_change"]:
        score += 3
        reasons.append("Trend Change")

    # ======================================
    # Quality
    # ======================================

    if score >= 27:
        quality = "EXCELLENT"

    elif score >= 22:
        quality = "STRONG"

    elif score >= 16:
        quality = "GOOD"

    elif score >= 10:
        quality = "NORMAL"

    else:
        quality = "WEAK"

    return {
        "score": score,
        "max_score": 30,
        "quality": quality,
        "reasons": reasons,
    }