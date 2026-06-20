import pandas as pd


# ==========================================
# EMA9 Cross EMA20 ภายใน X วัน
# ==========================================
def ema_cross_within(df, days=3):

    if len(df) < days + 2:
        return False

    for i in range(days):

        prev = df.iloc[-(i + 2)]
        curr = df.iloc[-(i + 1)]

        if (
            prev["ema9"] < prev["ema20"]
            and curr["ema9"] > curr["ema20"]
        ):
            return True

    return False


# ==========================================
# Trend Start Strategy V2
# ==========================================
def trend_start(df):

    if len(df) < 200:

        return {
            "signal": "NO DATA",
            "passed": False,
            "score": 0,
            "price": None,
            "rsi": None,
            "rvol": None,
            "reasons": ["Not enough data"]
        }

    last = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0
    reasons = []

    # ==========================
    # Mandatory Filters
    # ==========================

    distance20 = (
        last["close"] - last["ema20"]
    ) / last["ema20"]

    distance50 = (
        last["close"] - last["ema50"]
    ) / last["ema50"]

    # หุ้นขึ้นไกลแล้ว
    if distance20 > 0.05:

        return {
            "signal": "EXTENDED",
            "passed": False,
            "score": 0,
            "price": round(float(last["close"]), 2),
            "rsi": round(float(last["rsi"]), 1),
            "rvol": round(float(last["rvol"]), 2),
            "reasons": ["Price too far from EMA20"]
        }

    # RSI สูงเกิน
    if last["rsi"] > 72:

        return {
            "signal": "EXTENDED",
            "passed": False,
            "score": 0,
            "price": round(float(last["close"]), 2),
            "rsi": round(float(last["rsi"]), 1),
            "rvol": round(float(last["rvol"]), 2),
            "reasons": ["RSI Overbought"]
        }

    # ==========================
    # EMA Cross
    # ==========================

    if ema_cross_within(df, 3):
        score += 35
        reasons.append("EMA9 Cross EMA20")

    # ==========================
    # Trend Alignment
    # ==========================

    if last["ema20"] > prev["ema20"]:
        score += 10
        reasons.append("EMA20 Rising")

    if last["ema20"] > last["ema50"]:
        score += 10
        reasons.append("EMA20 > EMA50")

    if last["ema50"] > last["ema200"]:
        score += 10
        reasons.append("EMA50 > EMA200")

    # ==========================
    # Price
    # ==========================

    if last["close"] > last["ema20"]:
        score += 10
        reasons.append("Close > EMA20")

    if distance20 <= 0.03:
        score += 10
        reasons.append("Near EMA20")

    # ==========================
    # RSI
    # ==========================

    if 55 <= last["rsi"] <= 65:
        score += 10
        reasons.append("Healthy RSI")

    # ==========================
    # Relative Volume
    # ==========================

    if last["rvol"] >= 1.5:
        score += 15
        reasons.append("RVOL > 1.5")

    # ==========================
    # MACD
    # ==========================

    if last["macd"] > last["macd_signal"]:
        score += 5
        reasons.append("MACD Bullish")

    # ==========================
    # Volume Increasing
    # ==========================

    if last["volume"] > prev["volume"]:
        score += 5
        reasons.append("Volume Increasing")

    score = min(score, 100)

    # ==========================
    # Signal
    # ==========================

    if (
        score >= 90
        and ema_cross_within(df, 3)
        and last["rvol"] >= 1.5
    ):

        signal = "EARLY BUY"
        passed = True

    elif score >= 75:

        signal = "WATCH"
        passed = False

    else:

        signal = "SKIP"
        passed = False

    return {

        "signal": signal,

        "passed": passed,

        "score": score,

        "price": round(float(last["close"]), 2),

        "rsi": round(float(last["rsi"]), 1),

        "rvol": round(float(last["rvol"]), 2),

        "reasons": reasons

    }