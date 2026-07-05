from strategy_engine.market_profiles import get_profile

def momentum_score(last, df, ema_cross_func, market="SET"):

    profile = get_profile(market)

    cfg = profile["momentum"]

    score = 0
    reasons = []

    # ======================================
    # Fresh EMA Cross
    # ======================================

    if ema_cross_func(df, 3):
        score += cfg["fresh_cross"]

    elif ema_cross_func(df, 5):
        score += cfg["recent_cross"]

    # ======================================
    # EMA9 Momentum
    # ======================================

    if last["ema9"] > last["ema20"]:
        score += cfg["ema9_above"]

    # ======================================
    # MACD
    # ======================================

    if last["macd"] > last["macd_signal"]:
        score += cfg["macd_cross"]
        reasons.append("MACD Bullish")

    if last["macd_hist"] > 0:
        score += 2
        reasons.append("MACD Histogram Positive")

    # ======================================
    # RSI
    # ======================================

    if 50 <= last["rsi"] <= 65:
        score += cfg["rsi_strong"]

    elif 45 <= last["rsi"] < 50:
        score += cfg["rsi_recover"]

    # ======================================
    # Quality
    # ======================================

    if score >= 22:
        quality = "EXCELLENT"

    elif score >= 17:
        quality = "STRONG"

    elif score >= 12:
        quality = "GOOD"

    elif score >= 6:
        quality = "NORMAL"

    else:
        quality = "WEAK"

    return {
        "engine": "momentum",
        "score": min(score, 25),
        "max_score": 25,
        "quality": quality,
        "reasons": reasons,
    }
