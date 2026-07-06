from datetime import date, timedelta

import pandas as pd
import streamlit as st

from backtest_engine import (
    EQUITY_FILE,
    MONTHLY_FILE,
    SUMMARY_FILE,
    TRADES_FILE,
    run_strategy_lab,
)


try:
    import plotly.express as px

    PLOTLY_AVAILABLE = True
except Exception:
    px = None
    PLOTLY_AVAILABLE = False


SUMMARY_METRICS = [
    "Initial Capital",
    "Final Equity",
    "Total Return %",
    "Max Drawdown %",
    "Total Trades",
    "Win Rate",
    "Profit Factor",
    "Avg Win",
    "Avg Loss",
    "Best Trade",
    "Worst Trade",
    "Avg Holding Days",
]
PERCENT_METRICS = {
    "Total Return %",
    "Max Drawdown %",
    "Win Rate",
    "Avg Win",
    "Avg Loss",
    "Best Trade",
    "Worst Trade",
}
MONTHLY_COLUMNS = [
    "Year",
    "Month",
    "MonthlyReturnPct",
]
TRADE_ANALYSIS_COLUMNS = [
    "Symbol",
    "EntryDate",
    "ExitDate",
    "EntryPrice",
    "ExitPrice",
    "HoldingDays",
    "EntryScore",
    "ExitScore",
    "ExitReason",
    "NetReturnPct",
    "WinLoss",
]


def available_columns(df, columns):

    return [
        column
        for column in columns
        if column in df.columns
    ]


def render_summary_cards(summary):

    if summary.empty:
        st.info("No summary")
        return

    row = summary.iloc[0]
    columns = st.columns(4)

    for index, metric in enumerate(SUMMARY_METRICS):
        value = row.get(
            metric,
            0,
        )
        suffix = "%" if metric in PERCENT_METRICS else ""
        columns[index % 4].metric(
            metric,
            f"{float(value):,.2f}{suffix}",
        )


def render_line_chart(df, x, y, title):

    st.subheader(title)

    if df.empty:
        st.info(f"No {title.lower()}")
        return

    chart = df.copy()
    chart[x] = pd.to_datetime(
        chart[x],
        errors="coerce",
    )
    chart = chart.dropna(
        subset=[
            x,
        ]
    )

    if chart.empty:
        st.info(f"No {title.lower()}")
        return

    if PLOTLY_AVAILABLE:
        fig = px.line(
            chart,
            x=x,
            y=y,
            markers=True,
            title=title,
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    st.line_chart(
        chart.set_index(x)[y],
        use_container_width=True,
    )


def render_monthly_chart(monthly):

    st.subheader("Monthly Returns")

    if monthly.empty:
        st.info("No monthly returns")
        return

    chart = monthly.copy()
    chart["Period"] = (
        chart["Year"].astype(str)
        + "-"
        + chart["Month"].astype(int).astype(str).str.zfill(2)
    )

    if PLOTLY_AVAILABLE:
        fig = px.bar(
            chart,
            x="Period",
            y="MonthlyReturnPct",
            title="Monthly Returns",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    st.bar_chart(
        chart.set_index("Period")["MonthlyReturnPct"],
        use_container_width=True,
    )


def render_win_loss_distribution(trades):

    st.subheader("Win/Loss Distribution")

    if trades.empty:
        st.info("No win/loss data")
        return

    distribution = (
        trades["WinLoss"]
        .value_counts()
        .rename_axis("WinLoss")
        .reset_index(name="Trades")
    )

    if PLOTLY_AVAILABLE:
        fig = px.bar(
            distribution,
            x="WinLoss",
            y="Trades",
            title="Win/Loss Distribution",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    st.bar_chart(
        distribution.set_index("WinLoss")["Trades"],
        use_container_width=True,
    )


def render_return_distribution(trades):

    st.subheader("Return Distribution")

    if trades.empty:
        st.info("No return data")
        return

    data = trades.copy()
    data["NetReturnPct"] = pd.to_numeric(
        data["NetReturnPct"],
        errors="coerce",
    ).fillna(0)

    if PLOTLY_AVAILABLE:
        fig = px.histogram(
            data,
            x="NetReturnPct",
            nbins=20,
            title="Return Distribution",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
        return

    buckets = pd.cut(
        data["NetReturnPct"],
        bins=10,
    )
    distribution = buckets.value_counts().sort_index()
    distribution.index = distribution.index.astype(str)
    st.bar_chart(
        distribution,
        use_container_width=True,
    )


def filter_trade_analysis(trades):

    filtered = trades.copy()
    c1, c2, c3 = st.columns(3)

    with c1:
        show_wins = st.checkbox(
            "Show only wins",
            value=False,
        )

    with c2:
        show_losses = st.checkbox(
            "Show only losses",
            value=False,
        )

    with c3:
        reasons = sorted(
            filtered["ExitReason"].dropna().unique()
        )
        selected_reasons = st.multiselect(
            "Filter by ExitReason",
            reasons,
            default=reasons,
        )

    if show_wins and not show_losses:
        filtered = filtered[
            filtered["WinLoss"] == "WIN"
        ]
    elif show_losses and not show_wins:
        filtered = filtered[
            filtered["WinLoss"] == "LOSS"
        ]

    if selected_reasons:
        filtered = filtered[
            filtered["ExitReason"].isin(selected_reasons)
        ]
    else:
        filtered = filtered.iloc[0:0]

    return filtered


def render_performance_dashboard(trades, summary, equity_curve, monthly):

    st.header("Performance Dashboard")

    if trades.empty:
        st.info(
            "No trades found. Try lowering Min Score or expanding date range."
        )
        return

    render_summary_cards(summary)

    chart_left, chart_right = st.columns(2)

    with chart_left:
        render_line_chart(
            equity_curve,
            "ExitDate",
            "Equity",
            "Equity Curve",
        )
        render_monthly_chart(monthly)
        render_win_loss_distribution(trades)

    with chart_right:
        render_line_chart(
            equity_curve,
            "ExitDate",
            "DrawdownPct",
            "Drawdown Curve",
        )
        render_return_distribution(trades)

    st.subheader("Monthly Performance")

    st.dataframe(
        monthly[
            available_columns(
                monthly,
                MONTHLY_COLUMNS,
            )
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Trade Analysis")
    filtered_trades = filter_trade_analysis(trades)

    if filtered_trades.empty:
        st.info("No trades match the selected filters")
    else:
        st.dataframe(
            filtered_trades[
                available_columns(
                    filtered_trades,
                    TRADE_ANALYSIS_COLUMNS,
                )
            ],
            use_container_width=True,
            hide_index=True,
        )


def backtest_page():

    st.title("Strategy Lab")
    st.caption(
        "Phase 2.1: Performance Dashboard uses Strategy Lab trades, equity, "
        "and monthly performance without changing the trading logic."
    )
    st.caption(
        f"Trades: {TRADES_FILE} | Summary: {SUMMARY_FILE} | "
        f"Equity: {EQUITY_FILE} | Monthly: {MONTHLY_FILE}"
    )

    today = date.today()
    default_start = today - timedelta(days=365)

    with st.form("strategy_lab_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            market = st.selectbox(
                "Market",
                [
                    "SET",
                    "USA",
                ],
            )
            symbol = st.text_input(
                "Symbol",
                value="YONG"
                if market == "SET"
                else "AEP",
            )

        with c2:
            start_date = st.date_input(
                "Start Date",
                value=default_start,
            )
            end_date = st.date_input(
                "End Date",
                value=today,
            )

        with c3:
            min_score = st.number_input(
                "Min Score",
                min_value=0.0,
                max_value=100.0,
                value=70.0,
                step=1.0,
            )

        st.subheader("Exit Rules")
        st.caption(
            "Signal Changed is always active. Optional rules below run before "
            "Signal Changed and the matched rule is recorded as ExitReason."
        )

        r1, r2, r3, r4 = st.columns(4)

        with r1:
            enable_stop_loss = st.checkbox(
                "Stop Loss",
                value=False,
            )
            stop_loss_pct = st.number_input(
                "Stop Loss %",
                min_value=0.1,
                value=8.0,
                step=0.5,
            )

        with r2:
            enable_target = st.checkbox(
                "Target",
                value=False,
            )
            target_pct = st.number_input(
                "Target %",
                min_value=0.1,
                value=20.0,
                step=0.5,
            )

        with r3:
            enable_max_holding_days = st.checkbox(
                "Max Holding Days",
                value=False,
            )
            max_holding_days = st.number_input(
                "Max Days",
                min_value=1,
                value=20,
                step=1,
            )

        with r4:
            enable_trailing_stop = st.checkbox(
                "Trailing Stop",
                value=False,
            )
            trailing_stop_pct = st.number_input(
                "Trailing Stop %",
                min_value=0.1,
                value=10.0,
                step=0.5,
            )

        submitted = st.form_submit_button(
            "Run Strategy Lab"
        )

    if not submitted:
        return

    if not symbol.strip():
        st.error("Symbol is required")
        return

    if start_date >= end_date:
        st.error("Start Date must be before End Date")
        return

    with st.spinner("Running Strategy Lab..."):
        trades, summary, equity_curve, monthly = run_strategy_lab(
            symbol=symbol,
            market=market,
            start_date=start_date,
            end_date=end_date,
            min_score=min_score,
            enable_stop_loss=enable_stop_loss,
            stop_loss_pct=stop_loss_pct,
            enable_target=enable_target,
            target_pct=target_pct,
            enable_max_holding_days=enable_max_holding_days,
            max_holding_days=max_holding_days,
            enable_trailing_stop=enable_trailing_stop,
            trailing_stop_pct=trailing_stop_pct,
        )

    st.success("Strategy Lab completed")
    render_performance_dashboard(
        trades,
        summary,
        equity_curve,
        monthly,
    )
