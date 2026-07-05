from strategy_engine.stage_analysis import get_stage


ENGINE_ORDER = (
    "trend",
    "momentum",
    "volume",
    "base",
    "price",
    "stage",
    "breakout",
)


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

    elif stage == "STAGE_4":
        score = -30
        reasons.append("Stage 4")

    else:
        score = 0
        reasons.append("Stage Unknown")

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


def calculate_weighted_score(engine_results, weights):

    raw_total_score = 0
    raw_max_score = 0
    weighted_total_score = 0
    weighted_breakdown = {}

    active_weights = {
        engine: float(weights.get(engine, 0))
        for engine in ENGINE_ORDER
        if engine in engine_results
    }

    total_weight = sum(active_weights.values())

    if total_weight <= 0:
        active_weights = {
            engine: float(result.get("max_score", 0))
            for engine, result in engine_results.items()
        }
        total_weight = sum(active_weights.values())

    for engine in ENGINE_ORDER:

        if engine not in engine_results:
            continue

        result = engine_results[engine]
        score = float(result.get("score", 0))
        max_score = float(result.get("max_score", 0))
        raw_total_score += score
        raw_max_score += max_score

        configured_weight = active_weights.get(engine, 0)

        if total_weight > 0:
            weight = configured_weight / total_weight * 100
        else:
            weight = 0

        if max_score > 0:
            score_ratio = score / max_score
        else:
            score_ratio = 0

        score_ratio = max(
            -1,
            min(score_ratio, 1)
        )

        weighted_score = score_ratio * weight
        weighted_total_score += weighted_score

        weighted_breakdown[engine] = {
            "score": score,
            "max_score": max_score,
            "weight": round(weight, 2),
            "weighted_score": round(weighted_score, 2),
        }

    if raw_max_score > 0:
        raw_score_percent = round(
            raw_total_score / raw_max_score * 100
        )
    else:
        raw_score_percent = 0

    bounded_weighted_score = max(
        0,
        min(weighted_total_score, 100)
    )

    return {
        "raw_total_score": round(raw_total_score, 2),
        "raw_max_score": round(raw_max_score, 2),
        "raw_score_percent": raw_score_percent,
        "weighted_total_score": round(bounded_weighted_score, 2),
        "weighted_max_score": 100,
        "score_percent": round(bounded_weighted_score),
        "weighted_breakdown": weighted_breakdown,
    }
