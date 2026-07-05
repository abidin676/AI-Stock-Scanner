from datetime import date, timedelta

import pandas as pd
import streamlit as st

from backtest_engine import (
    EQUITY_FILE,
    SUMMARY_FILE,
    TRADES_FILE,
    run_backtest,
)


SUMMARY_METRICS = [
    "Total Trades",
    "Win Rate",
    "Avg Gain",
    "Avg Loss",
    "Avg Return",
    "Best Trade",
    "Worst Trade",
    "Profit Factor",
    "Expectancy",
    "Max Drawdown",
]


def render_summary(summary):

    if summary.empty:
        st.info("No summary")
        return

    row = summary.iloc[0]
    cols = st.columns(5)

    for index, metric in enumerate(SUMMARY_METRICS):
        value = row.get(
            metric,
            0,
        )
        suffix = "%" if metric in (
            "Win Rate",
            "Avg Gain",
            "Avg Loss",
            "Avg Return",
            "Best Trade",
            "Worst Trade",
            "Expectancy",
            "Max Drawdown",
        ) else ""

        cols[index % 5].metric(
            metric,
            f"{value:,.2f}{suffix}",
        )


def render_equity_curve(equity_curve):

    st.subheader("Equity Curve")

    if equity_curve.empty:
        st.info("No equity curve")
        return

    chart = equity_curve.copy()
    chart["ExitDate"] = pd.to_datetime(chart["ExitDate"])
    chart = chart.set_index("ExitDate")

    st.line_chart(
        chart["Equity"],
        use_container_width=True,
    )

    st.dataframe(
        equity_curve,
        use_container_width=True,
        hide_index=True,
    )


def backtest_page():

    st.title("Backtest")
    st.caption(
        f"Trades: {TRADES_FILE} | Summary: {SUMMARY_FILE} | Equity: {EQUITY_FILE}"
    )

    today = date.today()
    default_start = today - timedelta(days=365)

    with st.form("backtest_form"):
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
            holding_days = st.number_input(
                "Holding Days",
                min_value=1,
                value=10,
                step=1,
            )
            min_score = st.number_input(
                "Min Score",
                min_value=0.0,
                max_value=100.0,
                value=70.0,
                step=1.0,
            )

        signal_filter = st.multiselect(
            "Signal Filter",
            [
                "BUY",
                "WATCH",
                "EARLY",
                "EXTENDED",
                "SKIP",
            ],
            default=[
                "BUY",
            ],
        )

        submitted = st.form_submit_button(
            "Run Backtest"
        )

    if not submitted:
        return

    if not symbol.strip():
        st.error("Symbol is required")
        return

    if start_date >= end_date:
        st.error("Start Date must be before End Date")
        return

    with st.spinner("Running backtest..."):
        trades, summary, equity_curve = run_backtest(
            symbol=symbol,
            market=market,
            start_date=start_date,
            end_date=end_date,
            holding_days=holding_days,
            min_score=min_score,
            signal_filter=signal_filter,
        )

    st.success("Backtest completed")

    st.subheader("Summary Metrics")
    render_summary(summary)

    st.subheader("Trades")

    if trades.empty:
        st.info("No trades matched the filters")
    else:
        st.dataframe(
            trades,
            use_container_width=True,
            hide_index=True,
        )

    render_equity_curve(equity_curve)
