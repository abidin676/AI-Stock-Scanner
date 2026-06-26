from pathlib import Path

import pandas as pd
import streamlit as st


def portfolio_page():

    st.title("💼 Portfolio")

    FILE = Path("output") / "portfolio_report.xlsx"

    if not FILE.exists():

        st.warning("portfolio_report.xlsx not found")

        st.info("Run : python portfolio_report.py")

        return

    df = pd.read_excel(FILE)

    if df.empty:

        st.info("Portfolio Empty")

        return

    portfolio_value = df["Value"].sum()

    total_pnl = df["PnL"].sum()

    total_cost = (df["Qty"] * df["Buy"]).sum()

    pnl_pct = total_pnl / total_cost * 100

    positions = len(df)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "💰 Portfolio Value",
        f"${portfolio_value:,.2f}"
    )

    c2.metric(
        "📈 Unrealized P/L",
        f"${total_pnl:,.2f}",
        f"{pnl_pct:.2f}%"
    )

    c3.metric(
        "📦 Positions",
        positions
    )

    winners = len(df[df["PnL"] > 0])

    c4.metric(
        "🟢 Winners",
        winners
    )

    st.divider()

    st.subheader("Current Holdings")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )