from strategy_engine.stage_analysis import get_stage


def calculate_score(df):

    score = 0

    reasons = []

    # ==========================
    # Stage
    # ==========================

    stage = get_stage(df)

    if stage == "STAGE_2":

        score += 20

        reasons.append("Stage 2")

    elif stage == "STAGE_1":

        score += 5

        reasons.append("Stage 1")

    elif stage == "STAGE_3":

        score -= 10

    else:

        score -= 30

    return {
        "engine": "stage",
        "score": score,
        "reasons": reasons,
    }