from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st


RESULT_FILE = Path("output") / "scanner_results.xlsx"
SIGNAL_ORDER = {
    "BUY": 0,
    "WATCH": 1,
    "EARLY": 2,
    "EXTENDED": 3,
    "SKIP": 4,
    "OTHER": 5,
}
DISPLAY_COLUMNS = [
    "Symbol",
    "Market",
    "Signal",
    "Setup",
    "Score",
    "Price",
    "RSI",
    "RVOL",
]


def signal_group(signal):

    signal = str(signal)

    if "BUY" in signal:
        return "BUY"

    if "WATCH" in signal:
        return "WATCH"

    if "EARLY" in signal:
        return "EARLY"

    if "EXTENDED" in signal:
        return "EXTENDED"

    if "SKIP" in signal:
        return "SKIP"

    return "OTHER"


def prepare_data(df):

    df = df.copy()
    df["_signal_group"] = df["Signal"].apply(signal_group)
    df["_signal_rank"] = df["_signal_group"].map(
        SIGNAL_ORDER
    ).fillna(
        SIGNAL_ORDER["OTHER"]
    )

    return df


def sort_results(df):

    return df.sort_values(
        [
            "_signal_rank",
            "Score",
            "RVOL",
            "RSI",
        ],
        ascending=[
            True,
            False,
            False,
            True,
        ],
    )


def visible_columns(df):

    return [
        column
        for column in DISPLAY_COLUMNS
        if column in df.columns
    ]


def apply_filters(df, market_filter, signal_filter):

    data = df.copy()

    if market_filter != "ALL":
        data = data[data["Market"] == market_filter]

    if "ALL" not in signal_filter:
        data = data[
            data["_signal_group"].isin(signal_filter)
        ]

    return sort_results(data)


def build_market_summary(df):

    rows = []

    for market in ("SET", "USA"):

        data = df[df["Market"] == market]

        rows.append({
            "Market": market,
            "Stocks": len(data),
            "BUY": int((data["_signal_group"] == "BUY").sum()),
            "WATCH": int((data["_signal_group"] == "WATCH").sum()),
            "EARLY": int((data["_signal_group"] == "EARLY").sum()),
            "EXTENDED": int((data["_signal_group"] == "EXTENDED").sum()),
            "SKIP": int((data["_signal_group"] == "SKIP").sum()),
            "Avg Score": round(data["Score"].mean(), 1)
            if not data.empty
            else 0,
            "Max Score": data["Score"].max()
            if not data.empty
            else 0,
        })

    return pd.DataFrame(rows)


def render_summary(df):

    summary = build_market_summary(df)

    st.subheader("Market Summary")

    metric_cols = st.columns(2)

    for index, market in enumerate(("SET", "USA")):

        data = summary[summary["Market"] == market].iloc[0]

        with metric_cols[index]:
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{market} Stocks", int(data["Stocks"]))
            c2.metric(f"{market} BUY", int(data["BUY"]))
            c3.metric(f"{market} Max", int(data["Max Score"]))

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
    )


def render_top_market(df, market):

    st.subheader(f"Top {market}")

    top = sort_results(
        df[
            (df["Market"] == market)
            &
            (df["_signal_group"] != "SKIP")
        ]
    ).head(10)

    if top.empty:
        st.info(f"No {market} results")
        return

    st.dataframe(
        top[visible_columns(top)],
        use_container_width=True,
        hide_index=True,
    )


def scanner_page():

    st.title("River Alpha Scanner")

    if not RESULT_FILE.exists():
        st.error("scanner_results.xlsx not found")
        st.info("Run: python scanner.py")
        return

    df = pd.read_excel(RESULT_FILE)
    df = prepare_data(df)

    last_scan = datetime.fromtimestamp(
        RESULT_FILE.stat().st_mtime
    ).strftime("%d/%m/%Y %H:%M:%S")

    st.caption(f"Last Scan: {last_scan}")

    st.sidebar.header("Filter")

    market_filter = st.sidebar.selectbox(
        "Market",
        [
            "ALL",
            "SET",
            "USA",
        ],
    )

    signal_filter = st.sidebar.multiselect(
        "Signal",
        [
            "ALL",
            "BUY",
            "WATCH",
            "EARLY",
            "EXTENDED",
            "SKIP",
        ],
        default=[
            "BUY",
            "WATCH",
            "EARLY",
            "EXTENDED",
        ],
    )

    render_summary(df)

    st.divider()

    top_cols = st.columns(2)

    with top_cols[0]:
        render_top_market(df, "SET")

    with top_cols[1]:
        render_top_market(df, "USA")

    st.divider()

    filtered = apply_filters(
        df,
        market_filter,
        signal_filter,
    )

    st.subheader("Scanner Results")

    if filtered.empty:
        st.info("No results")
        return

    st.dataframe(
        filtered[visible_columns(filtered)],
        use_container_width=True,
        hide_index=True,
    )
