import os
import pandas as pd

from backtest_engine import run_backtest

# ==========================================
# SETTINGS
# ==========================================

SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "META",
    "AMD",
]

OUTPUT_DIR = "output"

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

# ==========================================
# STORAGE
# ==========================================

summary = []

all_trades = []

all_scores = []

# ==========================================
# RUN BACKTEST
# ==========================================

for symbol in SYMBOLS:

    print("=" * 60)

    print(symbol)

    trades, scores = run_backtest(
        symbol,
        "USA"
    )

    if trades.empty:

        print("No Trades")

        continue

    trades = trades.copy()

    trades["Symbol"] = symbol

    scores = scores.copy()

    scores["Symbol"] = symbol

    all_trades.append(trades)

    all_scores.append(scores)

    summary.append({

    "Symbol": symbol,

    "Trades": len(trades),

    "Win Rate (%)":
        round(
            trades["Win"].mean() * 100,
            2
        ),

    "Average Return (%)":
        round(
            trades["Return"].mean(),
            2
        ),

    "Best Trade (%)":
        round(
            trades["Return"].max(),
            2
        ),

    "Worst Trade (%)":
        round(
            trades["Return"].min(),
            2
        ),

    "Average Holding":
        round(
            trades["Holding"].mean(),
            2
        ),

    "Total Return (%)":
        round(
            trades["Return"].sum(),
            2
        ),

    "Average Win (%)":
        round(
            trades.loc[
                trades["Win"],
                "Return"
            ].mean(),
            2
        ),

    "Average Loss (%)":
        round(
            trades.loc[
                ~trades["Win"],
                "Return"
            ].mean(),
            2
        ),

    "Profit Factor":
        round(
            trades.loc[
                trades["Return"] > 0,
                "Return"
            ].sum()
            /
            abs(
                trades.loc[
                    trades["Return"] < 0,
                    "Return"
                ].sum()
            ),
            2
        ),

    "Expectancy":
        round(
            trades["Return"].mean(),
            2
        )

})

# ==========================================
# DATAFRAME
# ==========================================

summary_df = pd.DataFrame(summary)

if len(all_trades):

    trades_df = pd.concat(
        all_trades,
        ignore_index=True
    )

else:

    trades_df = pd.DataFrame()

if len(all_scores):

    scores_df = pd.concat(
        all_scores,
        ignore_index=True
    )

else:

    scores_df = pd.DataFrame()

print()

print("========== SUMMARY ==========")

print(summary_df)

print()

print("========== TRADES ==========")

print(trades_df.head())

# ==========================================
# MONTHLY RETURN
# ==========================================

if not trades_df.empty:

    trades_df["ExitDate"] = pd.to_datetime(
        trades_df["ExitDate"]
    )

    monthly_df = (
        trades_df
        .groupby(
            trades_df["ExitDate"].dt.to_period("M")
        )
        .agg(
            Trades=("Return", "count"),
            AvgReturn=("Return", "mean"),
            TotalReturn=("Return", "sum"),
        )
        .reset_index()
    )

    monthly_df["ExitDate"] = (
        monthly_df["ExitDate"]
        .astype(str)
    )

else:

    monthly_df = pd.DataFrame()

    # ==========================================
# YEARLY RETURN
# ==========================================

if not trades_df.empty:

    yearly_df = (
        trades_df
        .groupby(
            trades_df["ExitDate"].dt.year
        )
        .agg(
            Trades=("Return", "count"),
            AvgReturn=("Return", "mean"),
            TotalReturn=("Return", "sum"),
        )
        .reset_index()
    )

else:

    yearly_df = pd.DataFrame()

    # ==========================================
# EXIT STATS
# ==========================================

if not trades_df.empty:

    exit_df = (
        trades_df
        .groupby("ExitReason")
        .agg(
            Trades=("ExitReason", "count"),
            AvgReturn=("Return", "mean"),
            WinRate=("Win", "mean"),
        )
        .reset_index()
    )

    exit_df["WinRate"] *= 100

else:

    exit_df = pd.DataFrame()

    # ==========================================
# SCORE STATS
# ==========================================

if not scores_df.empty:

    score_df = (
        scores_df
        .groupby("Score")
        .size()
        .reset_index(name="Days")
        .sort_values("Score")
    )

else:

    score_df = pd.DataFrame()

    # ==========================================
# BEST / WORST
# ==========================================

top_win_df = trades_df.nlargest(
    20,
    "Return"
)

top_loss_df = trades_df.nsmallest(
    20,
    "Return"
)

# ==========================================
# EXPORT
# ==========================================

excel_file = os.path.join(
    OUTPUT_DIR,
    "backtest_report.xlsx"
)

with pd.ExcelWriter(
    excel_file,
    engine="openpyxl"
) as writer:

    summary_df.to_excel(
        writer,
        sheet_name="Summary",
        index=False
    )

    trades_df.to_excel(
        writer,
        sheet_name="Trades",
        index=False
    )

    monthly_df.to_excel(
        writer,
        sheet_name="Monthly",
        index=False
    )

    yearly_df.to_excel(
        writer,
        sheet_name="Yearly",
        index=False
    )

    exit_df.to_excel(
        writer,
        sheet_name="Exit Stats",
        index=False
    )

    score_df.to_excel(
        writer,
        sheet_name="Score Stats",
        index=False
    )

    top_win_df.to_excel(
        writer,
        sheet_name="Top Winners",
        index=False
    )

    top_loss_df.to_excel(
        writer,
        sheet_name="Top Losers",
        index=False
    )

print()

print("=" * 60)
print("Backtest Report Saved")
print(excel_file)
print("=" * 60)