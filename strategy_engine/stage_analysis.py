import pandas as pd


def get_stage(df: pd.DataFrame):

    if len(df) < 250:
        return "UNKNOWN"

    price = df["close"].iloc[-1]

    ema50 = df["ema50"].iloc[-1]
    ema200 = df["ema200"].iloc[-1]

    ema50_prev = df["ema50"].iloc[-20]
    ema200_prev = df["ema200"].iloc[-20]

    ema50_up = ema50 > ema50_prev
    ema200_up = ema200 > ema200_prev

    # Stage 2
    if (
        price > ema50 > ema200
        and ema50_up
        and ema200_up
    ):
        return "STAGE_2"

    # Stage 4
    if (
        price < ema50 < ema200
    ):
        return "STAGE_4"

    # Stage 1
    if (
        price < ema200
        and ema50_up
    ):
        return "STAGE_1"

    return "STAGE_3"