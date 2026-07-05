import pandas as pd



def get_stage(df: pd.DataFrame):

    if len(df) < 250:
        return "UNKNOWN"

    last = df.iloc[-1]

    price = last["close"]

    ema50 = last["ema50"]
    ema200 = last["ema200"]

    ema50_prev = df["ema50"].iloc[-20]
    ema200_prev = df["ema200"].iloc[-20]

    ema50_up = ema50 > ema50_prev
    ema200_up = ema200 > ema200_prev

    # -------------------------
    # Stage 2
    # -------------------------

    if (
        price > ema50
        and ema50 > ema200
        and ema50_up
    ):
        return "STAGE_2"

    # -------------------------
    # Stage 4
    # -------------------------

    if (
        price < ema50
        and ema50 < ema200
        and not ema200_up
    ):
        return "STAGE_4"

    # -------------------------
    # Stage 1
    # -------------------------

    if (
        abs(price - ema200) / ema200 < 0.10
    ):
        return "STAGE_1"

    # -------------------------
    # Stage 3
    # -------------------------

    return "STAGE_3"