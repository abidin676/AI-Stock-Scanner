def check_extended(row):

    reasons = []

    extended = False

    # ==========================
    # RSI
    # ==========================

    if row["rsi"] > 70:

        extended = True

        reasons.append("RSI > 70")

    # ==========================
    # EMA20 Distance
    # ==========================

    if row["distance_ema20"] > 8:

        extended = True

        reasons.append("Far From EMA20")

    # ==========================
    # Move From 90 Day Low
    # ==========================

    if row["move_from_low90"] > 40:

        extended = True

        reasons.append("Extended From Low90")

    return extended, reasons