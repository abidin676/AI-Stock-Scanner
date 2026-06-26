def detect_setup(last, distance20):

    setup = "Unknown"

    if (
        last["rvol"] >= 2
        and last["higher_high"]
    ):
        setup = "🚀 Breakout"

    elif (
        last["trend_change"]
        and last["ema20_slope"] > 0
    ):
        setup = "🌿 Early Reversal"

    elif (
        last["close"] > last["ema20"]
        and distance20 <= 0.03
    ):
        setup = "📈 Pullback"

    elif (
        last["ema_compression"]
        and last["atr_compression"]
    ):
        setup = "🌱 Base Building"

    return setup