from pathlib import Path

import pandas as pd
import streamlit as st

from data import get_history
from portfolio import (
    PORTFOLIO_FILE,
    add_position,
    close_position,
    load_portfolio,
)


SCANNER_FILE = Path("output") / "scanner_results.xlsx"


@st.cache_data(ttl=900)
def get_latest_price(symbol, market):

    df = get_history(
        symbol,
        market,
        period="5d",
    )

    if df.empty:
        return None

    return round(
        float(df.iloc[-1]["close"]),
        2,
    )


def load_scanner_candidates():

    if not SCANNER_FILE.exists():
        return pd.DataFrame()

    return pd.read_excel(SCANNER_FILE)


def enrich_open_positions(df):

    if df.empty:
        return df

    rows = []

    for _, row in df.iterrows():

        latest_price = get_latest_price(
            row["Symbol"],
            row["Market"],
        )

        entry_price = float(row["EntryPrice"])
        shares = float(row["Shares"])
        total_cost = entry_price * shares

        if latest_price is None:
            current_value = None
            pnl_pct = None
        else:
            current_value = latest_price * shares
            pnl_pct = (
                (current_value - total_cost)
                / total_cost
                * 100
            )

        data = row.to_dict()
        data["LastPrice"] = latest_price
        data["TotalCost"] = round(total_cost, 2)
        data["CurrentValue"] = (
            round(current_value, 2)
            if current_value is not None
            else None
        )
        data["Unrealized P/L %"] = (
            round(pnl_pct, 2)
            if pnl_pct is not None
            else None
        )
        rows.append(data)

    return pd.DataFrame(rows)


def render_add_form():

    st.subheader("Add Position")

    candidates = load_scanner_candidates()
    candidate_labels = ["Manual"]

    if not candidates.empty:
        for _, row in candidates.head(100).iterrows():
            candidate_labels.append(
                f"{row['Symbol']} | {row['Market']} | "
                f"{row['Setup']} | Score {row['Score']}"
            )

    selected = st.selectbox(
        "Scanner Candidate",
        candidate_labels,
    )

    selected_row = None

    if selected != "Manual" and not candidates.empty:
        selected_symbol = selected.split("|")[0].strip()
        selected_row = candidates[
            candidates["Symbol"] == selected_symbol
        ].iloc[0]

    with st.form("add_position_form"):

        symbol = st.text_input(
            "Symbol",
            value=selected_row["Symbol"]
            if selected_row is not None
            else "",
        )

        market = st.selectbox(
            "Market",
            [
                "SET",
                "USA",
            ],
            index=0
            if selected_row is None
            or selected_row["Market"] == "SET"
            else 1,
        )

        entry_price = st.number_input(
            "Entry Price",
            min_value=0.0,
            value=float(selected_row["Price"])
            if selected_row is not None
            else 0.0,
            step=0.01,
        )

        shares = st.number_input(
            "Shares",
            min_value=0.0,
            value=0.0,
            step=1.0,
        )

        setup = st.text_input(
            "Setup",
            value=selected_row["Setup"]
            if selected_row is not None
            else "",
        )

        score = st.number_input(
            "Score",
            min_value=0.0,
            max_value=100.0,
            value=float(selected_row["Score"])
            if selected_row is not None
            else 0.0,
            step=1.0,
        )

        submitted = st.form_submit_button(
            "Add to Portfolio"
        )

    if submitted:

        if not symbol or entry_price <= 0 or shares <= 0:
            st.error("Symbol, Entry Price, and Shares are required")
            return

        add_position(
            symbol,
            market,
            entry_price,
            shares,
            setup,
            score,
        )

        st.success(f"Added {symbol.upper()} to portfolio")
        st.cache_data.clear()
        st.rerun()


def render_close_form(open_positions):

    if open_positions.empty:
        return

    st.subheader("Close Position")

    symbols = sorted(
        open_positions["Symbol"].unique()
    )

    with st.form("close_position_form"):

        symbol = st.selectbox(
            "Open Symbol",
            symbols,
        )

        exit_price = st.number_input(
            "Exit Price",
            min_value=0.0,
            step=0.01,
        )

        submitted = st.form_submit_button(
            "Close Position"
        )

    if submitted:

        if exit_price <= 0:
            st.error("Exit Price is required")
            return

        close_position(
            symbol,
            exit_price,
        )

        st.success(f"Closed {symbol}")
        st.cache_data.clear()
        st.rerun()


def portfolio_page():

    st.title("Portfolio Manager")
    st.caption(f"Saved at: {PORTFOLIO_FILE}")

    portfolio = load_portfolio()

    open_positions = portfolio[
        portfolio["Status"] == "OPEN"
    ].copy()
    closed_positions = portfolio[
        portfolio["Status"] == "CLOSED"
    ].copy()

    enriched_open = enrich_open_positions(
        open_positions
    )

    total_cost = (
        enriched_open["TotalCost"].sum()
        if "TotalCost" in enriched_open
        else 0
    )
    current_value = (
        enriched_open["CurrentValue"].sum()
        if "CurrentValue" in enriched_open
        else 0
    )
    pnl_pct = (
        (current_value - total_cost)
        / total_cost
        * 100
        if total_cost
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Positions", len(open_positions))
    c2.metric("Total Cost", f"{total_cost:,.2f}")
    c3.metric("Current Value", f"{current_value:,.2f}")
    c4.metric("Unrealized P/L %", f"{pnl_pct:.2f}%")

    st.divider()

    form_cols = st.columns(2)

    with form_cols[0]:
        render_add_form()

    with form_cols[1]:
        render_close_form(open_positions)

    st.divider()

    st.subheader("Open Positions")

    if enriched_open.empty:
        st.info("No open positions")
    else:
        st.dataframe(
            enriched_open,
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Closed Positions")

    if closed_positions.empty:
        st.info("No closed positions")
    else:
        st.dataframe(
            closed_positions,
            use_container_width=True,
            hide_index=True,
        )
