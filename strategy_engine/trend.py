from strategy_engine.market_profiles import get_profile

def trend_score(last, market="SET"):

    profile = get_profile(market)

    w = profile["trend"]

    score = 0
    reasons = []

    if last["ema20"] > last["ema50"]:
        score += w["ema20_ema50"]
        reasons.append("EMA20 > EMA50")

    if last["ema50"] > last["ema200"]:
        score += w["ema50_ema200"]
        reasons.append("EMA50 > EMA200")

    if last["ema20_slope"] > 0:
        score += w["ema20_slope"]
        reasons.append("EMA20 Turning Up")

    if last["ema50_slope"] > 0:
        score += w["ema50_slope"]
        reasons.append("EMA50 Turning Up")

    if last["higher_low"]:
        score += w["higher_low"]
        reasons.append("Higher Low")

    if last["higher_high"]:
        score += w["higher_high"]
        reasons.append("Higher High")

    if last["trend_change"]:
        score += w["trend_change"]
        reasons.append("Trend Change")

    return {
        "engine": "trend",
        "score": score,
        "max_score": sum(w.values()),
        "quality": "",
        "reasons": reasons,
    }