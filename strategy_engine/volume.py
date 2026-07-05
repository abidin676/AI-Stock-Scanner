from strategy_engine.market_profiles import MARKET_PROFILES


def volume_score(last, market="SET"):

    profile = MARKET_PROFILES.get(
        market,
        MARKET_PROFILES["SET"],
    )

    score = 0
    reasons = []

    rvol = last["rvol"]

    # ==========================
    # Threshold ตามตลาด
    # ==========================

    strong = profile["RVOL_STRONG"]
    good = profile["RVOL_GOOD"]

    if rvol >= strong * 2.5:
        score += 20
        reasons.append("Explosive Volume")

    elif rvol >= strong * 1.8:
        score += 18
        reasons.append("Exceptional Volume")

    elif rvol >= strong:
        score += 15
        reasons.append("Very High Volume")

    elif rvol >= good:
        score += 10
        reasons.append("Strong Volume")

    elif rvol >= 1.0:
        score += 5
        reasons.append("Average Volume")

    elif rvol < 0.8:
        score -= 10
        reasons.append("Weak Volume")

    # ==========================
    # Dry Up
    # ==========================

    if last["dry_volume"]:
        score += 5
        reasons.append("Volume Dry Up")

    # ==========================
    # Quality
    # ==========================

    if score >= 20:
        quality = "EXCELLENT"

    elif score >= 15:
        quality = "STRONG"

    elif score >= 10:
        quality = "GOOD"

    elif score >= 5:
        quality = "NORMAL"

    else:
        quality = "WEAK"

    return {
        "engine": "volume",
        "score": min(score, 20),
        "max_score": 25,
        "quality": quality,
        "reasons": reasons,
    }