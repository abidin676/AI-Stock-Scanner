import pandas as pd


def calculate_metrics(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    start_capital: float = 100000,
):

    metrics = {}

    # -----------------------
    # Ending Capital
    # -----------------------

    ending = equity["Capital"].iloc[-1]

    metrics["Ending Capital"] = round(
        ending,
        2
    )

    # -----------------------
    # Total Return
    # -----------------------

    total_return = (
        ending / start_capital - 1
    ) * 100

    metrics["Total Return"] = round(
        total_return,
        2
    )

    # -----------------------
    # Trades
    # -----------------------

    metrics["Trades"] = len(trades)

    # -----------------------
    # Win Rate
    # -----------------------

    metrics["Win Rate"] = round(
        trades["Win"].mean() * 100,
        2
    )

    # -----------------------
    # Average Win
    # -----------------------

    metrics["Average Win"] = round(

        trades.loc[
            trades["Win"],
            "Return"
        ].mean(),

        2
    )

    # -----------------------
    # Average Loss
    # -----------------------

    metrics["Average Loss"] = round(

        trades.loc[
            ~trades["Win"],
            "Return"
        ].mean(),

        2
    )

    # -----------------------
    # Profit Factor
    # -----------------------

    gross_profit = trades.loc[
        trades["Return"] > 0,
        "Return"
    ].sum()

    gross_loss = abs(

        trades.loc[
            trades["Return"] < 0,
            "Return"
        ].sum()

    )

    metrics["Profit Factor"] = round(
        gross_profit / gross_loss,
        2
    )

    # -----------------------
    # Max Drawdown
    # -----------------------

    metrics["Max Drawdown"] = round(
        equity["Drawdown"].min(),
        2
    )

    return metrics