def volume_score(last):

    score = 0
    reasons = []

    rvol = last["rvol"]

    # ======================================
    # Relative Volume (20)
    # ======================================

    if rvol >= 5:
        score += 20
        reasons.append("Explosive Volume")

    elif rvol >= 3:
        score += 18
        reasons.append("Exceptional Volume")

    elif rvol >= 2:
        score += 15
        reasons.append("Very High Volume")

    elif rvol >= 1.5:
        score += 10
        reasons.append("Strong Volume")

    elif rvol >= 1.2:
        score += 6
        reasons.append("Good Volume")

    elif rvol >= 1.0:
        score += 3
        reasons.append("Average Volume")

    elif rvol < 0.8:
        score -= 10
        reasons.append("Weak Volume")

    # ======================================
    # Dry Up Volume (5)
    # ======================================

    if last["dry_volume"]:
        score += 5
        reasons.append("Volume Dry Up")

    # ======================================
    # Quality
    # ======================================

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
        "score": min(score, 20),
        "max_score": 20,
        "quality": quality,
        "reasons": reasons,
    }