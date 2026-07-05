def base_score(last, market="SET"):

    market = (market or "SET").upper()

    score = 0
    reasons = []

    # ===============================
    # EMA Compression
    # ===============================

    if last["ema_compression"]:
        score += 3
        reasons.append("EMA Compression")

    # ===============================
    # ATR Compression
    # ===============================

    if last["atr_compression"]:
        score += 3
        reasons.append("ATR Compression")

    # ===============================
    # Dry Volume
    # ===============================

    if last["dry_volume"]:
        score += 2
        reasons.append("Volume Dry Up")

    # ===============================
    # Distance From Base
    # ===============================

    move = last["move_from_low90"]

    if market == "SET":

        if move <= 40:
            score += 6
            reasons.append("Near Base")

        elif move <= 60:
            score += 4
            reasons.append("Still Near Base")

        elif move <= 80:
            score += 2
            reasons.append("Acceptable Extension")

    else:

        if move <= 20:
            score += 6
            reasons.append("Near Base")

        elif move <= 40:
            score += 3
            reasons.append("Still Near Base")

    # ===============================
    # Tight Base
    # ===============================

    if (
        last["ema_compression"]
        and last["atr_compression"]
    ):
        score += 2
        reasons.append("Tight Base")

    # ===============================
    # Quality
    # ===============================

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
