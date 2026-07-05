from strategy_engine.stage_analysis import get_stage


def calculate_score(df):

    score = 0
    reasons = []

    stage = get_stage(df)

    if stage == "STAGE_2":
        score = 20
        reasons.append("Stage 2")

    elif stage == "STAGE_1":
        score = 5
        reasons.append("Stage 1")

    elif stage == "STAGE_3":
        score = -10
        reasons.append("Stage 3")

    else:
        score = -30
        reasons.append("Stage 4")

    # -------------------------
    # Quality
    # -------------------------

    if score >= 20:
        quality = "EXCELLENT"

    elif score >= 5:
        quality = "GOOD"

    elif score >= 0:
        quality = "NORMAL"

    else:
        quality = "WEAK"

    return {
        "engine": "stage",
        "score": score,
        "max_score": 20,
        "quality": quality,
        "reasons": reasons,
    }