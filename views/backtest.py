from datetime import date, timedelta

import pandas as pd
import streamlit as st

from backtest_engine import (
    EQUITY_FILE,
    SUMMARY_FILE,
    TRADES_FILE,
    run_strategy_lab,
)


SUMMARY_METRICS = [
    "Total Trades",
    "Win Rate",
    "Avg Return",
    "Avg Holding Days",
    "Profit Factor",
    "Max Drawdown",
]


def render_summary(summary):

    if summary.empty:
        st.info("No summary")
        return

    row = summary.iloc[0]
    cols = st.columns(3)

    for index, metric in enumerate(SUMMARY_METRICS):
        value = row.get(
            metric,
            0,
        )
        suffix = "%" if metric in (
            "Win Rate",
            "Avg Return",
            "Max Drawdown",
        ) else ""

        cols[index % 3].metric(
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

    st.title("Strategy Lab")
    st.caption(
        "Phase 2: Buy only when Scanner Decision Engine returns BUY and "
        "Score >= Min Score. Hold while signal remains BUY. Exit when signal "
        "changes to WATCH or SKIP, or when an enabled optional exit rule fires."
    )
    st.caption(
        f"Trades: {TRADES_FILE} | Summary: {SUMMARY_FILE} | Equity: {EQUITY_FILE}"
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
        trades, summary, equity_curve = run_strategy_lab(
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

    st.subheader("Summary Metrics")
    render_summary(summary)

    st.subheader("Trades")

    if trades.empty:
        st.info("No trades matched BUY + Min Score")
    else:
        st.dataframe(
            trades,
            use_container_width=True,
            hide_index=True,
        )

    render_equity_curve(equity_curve)
