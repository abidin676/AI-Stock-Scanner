def base_score(last):

    score = 0
    reasons = []

    # ======================================
    # EMA Compression (3)
    # ======================================

    if last["ema_compression"]:
        score += 3
        reasons.append("EMA Compression")

    # ======================================
    # ATR Compression (3)
    # ======================================

    if last["atr_compression"]:
        score += 3
        reasons.append("ATR Compression")

    # ======================================
    # Dry Volume (2)
    # ======================================

    if last["dry_volume"]:
        score += 2
        reasons.append("Volume Dry Up")

    # ======================================
    # Distance From Base (6)
    # ======================================

    move = last["move_from_low90"]

    if move <= 20:
        score += 4
        reasons.append("Near Base")

    elif move <= 40:
        score += 2
        reasons.append("Still Near Base")

    # ======================================
    # Tight Base (1)
    # ======================================

    if (
        last["ema_compression"]
        and last["atr_compression"]
    ):
        score += 1
        reasons.append("Tight Base")

    # ======================================
    # Quality
    # ======================================

    if score >= 13:
        quality = "EXCELLENT"

    elif score >= 10:
        quality = "STRONG"

    elif score >= 7:
        quality = "GOOD"

    elif score >= 4:
        quality = "NORMAL"

    else:
        quality = "WEAK"

    return {
        "engine": "base",
        "score": score,
        "max_score": 15,
        "quality": quality,
        "reasons": reasons,
    }