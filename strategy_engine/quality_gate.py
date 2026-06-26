def quality_gate(
    trend,
    momentum,
    volume,
    base,
    price_score,
):

    passed = True
    reasons = []
    grade = "A+"

    # ==========================
    # Trend
    # ==========================

    if trend["score"] < 20:
        passed = False
        reasons.append("Trend too weak")

    # ==========================
    # Momentum
    # ==========================

    if momentum["score"] < 8:
        passed = False
        reasons.append("Momentum too weak")

    # ==========================
    # Volume
    # ==========================

    if volume["score"] < 5:
        passed = False
        reasons.append("Weak Volume")

    # ==========================
    # Price
    # ==========================

    if price_score < 5:
        passed = False
        reasons.append("Price below EMA20")

    # ==========================
    # Base
    # ==========================

    if base["score"] < 5:
        grade = "B"

    if trend["score"] < 25:
        grade = "B"

    if trend["score"] < 20:
        grade = "C"

    if not passed:
        grade = "D"

    return {
        "passed": passed,
        "grade": grade,
        "reasons": reasons,
    }