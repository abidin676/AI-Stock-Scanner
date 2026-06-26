def build_signal(score):

    if score >= 90:
        signal = "🚀 ELITE"

    elif score >= 80:
        signal = "🟢 BUY"

    elif score >= 70:
        signal = "👀 WATCH"

    elif score >= 60:
        signal = "🌱 EARLY"

    else:
        signal = "SKIP"

    passed = score >= 80

    return {
        "engine": "stage",
        "score": score,
        "reasons": reasons,
    }