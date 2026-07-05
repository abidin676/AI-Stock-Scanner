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
ROW_COLORS = {
    "BUY": "background-color: #dcfce7",
    "WATCH": "background-color: #dbeafe",
    "EARLY": "background-color: #fef9c3",
    "EXTENDED": "background-color: #ffedd5",
    "SKIP": "background-color: #f3f4f6",
}


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


def apply_filters(df, market_filter, signal_filter, symbol_search):

    data = df.copy()

    if market_filter != "ALL":
        data = data[data["Market"] == market_filter]

    if "ALL" not in signal_filter:
        data = data[
            data["_signal_group"].isin(signal_filter)
        ]

    symbol_search = symbol_search.strip().upper()

    if symbol_search:
        data = data[
            data["Symbol"].astype(str).str.upper().str.contains(
                symbol_search,
                regex=False,
            )
        ]

    return sort_results(data)


def styled_table(df):

    display = df[visible_columns(df)].reset_index(
        drop=True
    )
    groups = df["_signal_group"].reset_index(
        drop=True
    )

    def highlight_row(row):

        style = ROW_COLORS.get(
            groups.iloc[row.name],
            "",
        )

        return [
            style
            for _ in row
        ]

    return display.style.apply(
        highlight_row,
        axis=1,
    )


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
        styled_table(top),
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

    symbol_search = st.sidebar.text_input(
        "Symbol Search",
        value="",
        placeholder="AAPL, PTT, DUK",
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
        symbol_search,
    )

    st.subheader("Scanner Results")

    if filtered.empty:
        st.info("No results")
        return

    st.dataframe(
        styled_table(filtered),
        use_container_width=True,
        hide_index=True,
    )
