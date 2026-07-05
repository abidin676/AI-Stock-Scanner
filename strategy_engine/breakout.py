def breakout_score(last):

    score = 0
    reasons = []

    if last.get("break20", False):
        score += 4
        reasons.append("Break 20 Day High")

    if last.get("break55", False):
        score += 6
        reasons.append("Break 55 Day High")

    if last.get("pocket_pivot", False):
        score += 5
        reasons.append("Pocket Pivot")

    if last.get("strong_close", False):
        score += 3
        reasons.append("Strong Close")

    if last.get("close_above_prev_high", False):
        score += 2
        reasons.append("Close Above Previous High")

    if last.get("volume_breakout", False):
        score += 3
        reasons.append("Volume Breakout")

    if last.get("near_pivot", False):
        score += 2
        reasons.append("Near Pivot")

    if last.get("nr7", False):
        score += 2
        reasons.append("NR7")

    if last.get("inside_bar", False):
        score += 3
        reasons.append("Inside Bar")

    if score >= 24:
        quality = "EXCELLENT"
    elif score >= 18:
        quality = "STRONG"
    elif score >= 12:
        quality = "GOOD"
    elif score >= 6:
        quality = "NORMAL"
    else:
        quality = "WEAK"

    return {
        "engine": "breakout",
        "score": score,
        "max_score": 30,
        "quality": quality,
        "reasons": reasons,
    }