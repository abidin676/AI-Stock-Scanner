import math


def calculate_score(row):

    if math.isnan(float(row["EMA200"])):
        return 0, []

    score = 0
    reasons = []

    if row["Close"] > row["EMA20"]:
        score += 15
        reasons.append("ราคาเหนือ EMA20")

    if row["EMA20"] > row["EMA50"]:
        score += 20
        reasons.append("EMA20 > EMA50")

    if row["EMA50"] > row["EMA200"]:
        score += 25
        reasons.append("EMA50 > EMA200")

    if 55 <= row["RSI"] <= 70:
        score += 15
        reasons.append("RSI แข็งแรง")
    elif row["RSI"] > 50:
        score += 10
        reasons.append("RSI เป็นบวก")

    if row["VOL_RATIO"] > 1.2:
        score += 15
        reasons.append(f"Volume สูง ({row['VOL_RATIO']:.2f}x)")

    return score, reasons


def signal(score):
    if score >= 85:
        return "🟢 STRONG BUY"
    elif score >= 70:
        return "🟢 BUY"
    elif score >= 40:
        return "🟡 WATCH"
    else:
        return "🔴 SKIP"