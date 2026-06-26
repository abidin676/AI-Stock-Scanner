from strategy_engine.stage_analysis import get_stage


def analyze(df):

    score = 0

    reasons = []

    # ==========================
    # Stage Analysis
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
        reasons.append("Stage 3")

    else:

        score -= 30
        reasons.append("Stage 4")

    # ==========================
    # Trend
    # ==========================

    last = df.iloc[-1]

    if last["ema20"] > last["ema50"] > last["ema200"]:

        score += 20
        reasons.append("EMA Alignment")

    # ==========================
    # EMA Slope
    # ==========================

    if (
        last["ema20_slope"] > 0
        and last["ema50_slope"] > 0
    ):

        score += 10
        reasons.append("EMA Rising")

    # ==========================
    # Higher High / Higher Low
    # ==========================

    if last["higher_high"]:

        score += 10
        reasons.append("Higher High")

    if last["higher_low"]:

        score += 10
        reasons.append("Higher Low")

    # ==========================
    # Dry Volume
    # ==========================

    if last["dry_volume"]:

        score += 10
        reasons.append("Volume Dry Up")

    # ==========================
    # ATR Compression
    # ==========================

    if last["atr_compression"]:

        score += 10
        reasons.append("ATR Compression")

    # ==========================
    # Risk
    # ==========================

    score = max(0, min(score, 100))

    if score >= 90:

        signal = "🚀 ELITE"

    elif score >= 75:

        signal = "🟢 BUY"

    elif score >= 60:

        signal = "👀 WATCH"

    else:

        signal = "❌ SKIP"

    last = df.iloc[-1]

    return {

    "score": score,

    "signal": signal,

    "stage": stage,

    "price": round(last["close"], 2),

    "rsi": round(last["rsi"], 2),

    "rvol": round(last["rvol"], 2),

    "reasons": reasons

    }