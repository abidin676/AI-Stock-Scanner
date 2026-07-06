import pandas as pd
import streamlit as st

from data import get_history
from fx_engine import get_fx_rate
from portfolio import (
    PORTFOLIO_FILE,
    add_position,
    close_position,
    load_portfolio,
)
from watchlist import load_watchlist, mark_bought


OPEN_COLUMNS = [
    "Symbol",
    "Market",
    "Currency",
    "EntryDate",
    "EntryPrice",
    "Shares",
    "Setup",
    "Score",
    "Status",
    "BuyAmount",
    "BuyFee",
    "NetCost",
    "LastPrice",
    "CurrentValue",
    "UnrealizedNetPL",
    "UnrealizedNetPLPct",
]
CLOSED_COLUMNS = [
    "Symbol",
    "Market",
    "Currency",
    "EntryDate",
    "EntryPrice",
    "Shares",
    "Setup",
    "Score",
    "Status",
    "ExitDate",
    "ExitPrice",
    "BuyAmount",
    "BuyFee",
    "NetCost",
    "SellAmount",
    "SellFee",
    "NetProceeds",
    "GrossPL",
    "NetPL",
    "NetPLPct",
]


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


@st.cache_data(ttl=3600)
def get_thb_rate(currency):

    return get_fx_rate(
        currency,
        "THB",
    )


def available_columns(df, columns):

    return [
        column
        for column in columns
        if column in df.columns
    ]


def sum_column(df, column):

    if column not in df:
        return 0

    return float(
        pd.to_numeric(
            df[column],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )


def filter_currency(df, currency):

    if df.empty or "Currency" not in df:
        return df.iloc[0:0].copy()

    return df[
        df["Currency"] == currency
    ].copy()


def portfolio_currencies(*dataframes):

    currencies = set()

    for df in dataframes:
        if df.empty or "Currency" not in df:
            continue

        currencies.update(
            currency
            for currency in df["Currency"].dropna().unique()
            if str(currency).strip()
        )

    return sorted(currencies)


def calculate_currency_metrics(
    portfolio,
    open_positions,
    closed_positions,
    currency,
):

    currency_portfolio = filter_currency(
        portfolio,
        currency,
    )
    currency_open = filter_currency(
        open_positions,
        currency,
    )
    currency_closed = filter_currency(
        closed_positions,
        currency,
    )
    total_fees = (
        sum_column(currency_portfolio, "BuyFee")
        + sum_column(currency_closed, "SellFee")
    )
    net_cost = sum_column(
        currency_open,
        "NetCost",
    )
    current_value = sum_column(
        currency_open,
        "CurrentValue",
    )
    unrealized_net_pl = sum_column(
        currency_open,
        "UnrealizedNetPL",
    )
    unrealized_net_pl_pct = (
        unrealized_net_pl
        / net_cost
        * 100
        if net_cost
        else 0
    )
    realized_net_pl = sum_column(
        currency_closed,
        "NetPL",
    )

    return {
        "total_fees": total_fees,
        "net_cost": net_cost,
        "current_value": current_value,
        "unrealized_net_pl": unrealized_net_pl,
        "unrealized_net_pl_pct": unrealized_net_pl_pct,
        "realized_net_pl": realized_net_pl,
    }


def render_total_thb_summary(
    portfolio,
    open_positions,
    closed_positions,
    currencies,
):

    totals = {
        "total_fees": 0,
        "net_cost": 0,
        "current_value": 0,
        "unrealized_net_pl": 0,
        "realized_net_pl": 0,
    }
    fx_notes = []
    missing_rates = []

    for currency in currencies:
        metrics = calculate_currency_metrics(
            portfolio,
            open_positions,
            closed_positions,
            currency,
        )

        try:
            rate = get_thb_rate(currency)
        except Exception as e:
            missing_rates.append(
                f"{currency}: {e}"
            )
            continue

        if currency != "THB":
            fx_notes.append(
                f"{currency}/THB {rate:,.4f}"
            )

        for key in totals:
            totals[key] += metrics[key] * rate

    unrealized_net_pl_pct = (
        totals["unrealized_net_pl"]
        / totals["net_cost"]
        * 100
        if totals["net_cost"]
        else 0
    )

    st.markdown("**Total Portfolio (THB)**")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Fees", f"{totals['total_fees']:,.2f} THB")
    c2.metric("Net Cost", f"{totals['net_cost']:,.2f} THB")
    c3.metric("Current Value", f"{totals['current_value']:,.2f} THB")
    c4.metric("Unrealized Net P/L", f"{totals['unrealized_net_pl']:,.2f} THB")
    c5.metric("Unrealized Net P/L %", f"{unrealized_net_pl_pct:.2f}%")
    c6.metric("Realized Net P/L", f"{totals['realized_net_pl']:,.2f} THB")

    if fx_notes:
        st.caption(
            "FX: "
            + ", ".join(fx_notes)
        )

    if missing_rates:
        st.warning(
            "Cannot convert some currencies to THB: "
            + "; ".join(missing_rates)
        )


def render_currency_summary(portfolio, open_positions, closed_positions):

    currencies = portfolio_currencies(
        portfolio,
        open_positions,
        closed_positions,
    )

    if not currencies:
        st.info("No portfolio currency data")
        return

    st.subheader("Portfolio Summary")
    render_total_thb_summary(
        portfolio,
        open_positions,
        closed_positions,
        currencies,
    )

    st.markdown("**Currency Breakdown**")
    for currency in currencies:
        metrics = calculate_currency_metrics(
            portfolio,
            open_positions,
            closed_positions,
            currency,
        )

        st.markdown(f"**{currency} Portfolio**")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Fees", f"{metrics['total_fees']:,.2f} {currency}")
        c2.metric("Net Cost", f"{metrics['net_cost']:,.2f} {currency}")
        c3.metric("Current Value", f"{metrics['current_value']:,.2f} {currency}")
        c4.metric(
            "Unrealized Net P/L",
            f"{metrics['unrealized_net_pl']:,.2f} {currency}",
        )
        c5.metric(
            "Unrealized Net P/L %",
            f"{metrics['unrealized_net_pl_pct']:.2f}%",
        )
        c6.metric(
            "Realized Net P/L",
            f"{metrics['realized_net_pl']:,.2f} {currency}",
        )


def load_watchlist_candidates():

    watchlist = load_watchlist()

    if watchlist.empty:
        return watchlist

    return watchlist[
        watchlist["Status"] != "BOUGHT"
    ].copy()


def candidate_label(row):

    return (
        f"{row['Symbol']} | {row['Market']} | "
        f"{row['Status']} | {row['Setup']} | Score {row['Score']}"
    )


def enrich_open_positions(df):

    if df.empty:
        return df

    rows = []

    for _, row in df.iterrows():

        latest_price = get_latest_price(
            row["Symbol"],
            row["Market"],
        )

        shares = float(row["Shares"])
        net_cost = float(row["NetCost"])

        if latest_price is None:
            current_value = None
            unrealized_net_pl = None
            unrealized_net_pl_pct = None
        else:
            current_value = latest_price * shares
            unrealized_net_pl = current_value - net_cost
            unrealized_net_pl_pct = (
                unrealized_net_pl
                / net_cost
                * 100
                if net_cost
                else 0
            )

        data = row.to_dict()
        data["LastPrice"] = latest_price
        data["CurrentValue"] = (
            round(current_value, 2)
            if current_value is not None
            else None
        )
        data["UnrealizedNetPL"] = (
            round(unrealized_net_pl, 2)
            if unrealized_net_pl is not None
            else None
        )
        data["UnrealizedNetPLPct"] = (
            round(unrealized_net_pl_pct, 2)
            if unrealized_net_pl_pct is not None
            else None
        )
        rows.append(data)

    return pd.DataFrame(rows)


def render_add_form():

    st.subheader("Add Position")

    candidates = load_watchlist_candidates()
    candidate_labels = ["Manual"]

    if not candidates.empty:
        for _, row in candidates.head(100).iterrows():
            candidate_labels.append(
                candidate_label(row)
            )

    selected = st.selectbox(
        "Source",
        candidate_labels,
    )

    selected_row = None

    if selected != "Manual" and not candidates.empty:
        selected_symbol, selected_market = [
            part.strip()
            for part in selected.split("|")[:2]
        ]
        selected_row = candidates[
            (candidates["Symbol"] == selected_symbol)
            &
            (candidates["Market"] == selected_market)
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

        if selected_row is not None:
            mark_bought(
                symbol,
                market,
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

    render_currency_summary(
        portfolio,
        enriched_open,
        closed_positions,
    )

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
            enriched_open[
                available_columns(
                    enriched_open,
                    OPEN_COLUMNS,
                )
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Closed Positions")

    if closed_positions.empty:
        st.info("No closed positions")
    else:
        st.dataframe(
            closed_positions[
                available_columns(
                    closed_positions,
                    CLOSED_COLUMNS,
                )
            ],
            use_container_width=True,
            hide_index=True,
        )
