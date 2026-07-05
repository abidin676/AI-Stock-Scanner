from pathlib import Path
from datetime import datetime
import html

import pandas as pd
import streamlit as st

from watchlist import add_to_watchlist


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
    "BUY": "#dcfce7",
    "WATCH": "#dbeafe",
    "EARLY": "#fef9c3",
    "EXTENDED": "#ffedd5",
    "SKIP": "#f3f4f6",
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


def safe_number(value):

    if pd.isna(value):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def watchlist_label(row):

    return (
        f"{row['Symbol']} | {row['Market']} | "
        f"{row['Signal']} | {row['Setup']} | Score {row['Score']}"
    )


def first_existing_number(row, columns):

    for column in columns:
        if column in row:
            return safe_number(row.get(column, 0.0))

    return 0.0


def selected_candidate_row(candidates, selected):

    symbol, market = [
        part.strip()
        for part in selected.split("|")[:2]
    ]

    return candidates[
        (candidates["Symbol"] == symbol)
        &
        (candidates["Market"] == market)
    ].iloc[0]


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


def render_table(df):

    columns = visible_columns(df)

    header = "".join(
        f"<th>{html.escape(column)}</th>"
        for column in columns
    )

    rows = []

    for _, row in df.iterrows():

        group = row.get("_signal_group", "OTHER")
        background = ROW_COLORS.get(
            group,
            "#ffffff",
        )

        cell_style = (
            f"background-color: {background}; "
            "color: #111827 !important; "
            "font-weight: 700; "
            "padding: 9px 12px; "
            "border-top: 1px solid rgba(17, 24, 39, 0.12); "
            "white-space: nowrap;"
        )

        cells = "".join(
            f"<td style='{cell_style}'>{html.escape(str(row[column]))}</td>"
            for column in columns
        )

        rows.append(
            f"<tr style='background-color: {background}; color: #111827;'>"
            f"{cells}</tr>"
        )

    st.markdown(
        """
        <style>
        .ra-table-wrap {
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 6px;
            max-height: 680px;
            overflow: auto;
        }
        .ra-table {
            border-collapse: collapse;
            width: 100%;
            min-width: 760px;
            font-size: 14px;
        }
        .ra-table th {
            background-color: #111827;
            color: #f9fafb;
            font-weight: 700;
            padding: 10px 12px;
            position: sticky;
            top: 0;
            text-align: left;
            z-index: 1;
        }
        .ra-table td {
            border-top: 1px solid rgba(17, 24, 39, 0.12);
            color: #111827;
            font-weight: 650;
            padding: 9px 12px;
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='ra-table-wrap'>"
        "<table class='ra-table'>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>",
        unsafe_allow_html=True,
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

    render_table(top)


def render_add_to_watchlist(df):

    candidates = df[
        df["_signal_group"] != "SKIP"
    ].copy()

    if candidates.empty:
        return

    st.subheader("Watchlist")

    labels = [
        watchlist_label(row)
        for _, row in candidates.iterrows()
    ]

    with st.form("scanner_add_watchlist_form"):
        selected = st.selectbox(
            "Candidate",
            labels,
        )
        row = selected_candidate_row(
            candidates,
            selected,
        )
        stop_loss_default = first_existing_number(
            row,
            [
                "StopLoss",
                "Stop Loss",
                "Stop_Loss",
                "SL",
            ],
        )
        target_default = first_existing_number(
            row,
            [
                "Target",
                "TakeProfit",
                "Take Profit",
                "TP",
            ],
        )
        note = st.text_input(
            "Note",
            value="",
        )
        stop_loss = st.number_input(
            "Stop Loss",
            min_value=0.0,
            value=stop_loss_default,
            step=0.01,
        )
        target = st.number_input(
            "Target",
            min_value=0.0,
            value=target_default,
            step=0.01,
        )
        submitted = st.form_submit_button(
            "Add to Watchlist"
        )

    if not submitted:
        return

    add_to_watchlist(
        row["Symbol"],
        row["Market"],
        price=safe_number(row.get("Price", 0.0)),
        setup=row.get("Setup", ""),
        score=safe_number(row.get("Score", 0.0)),
        signal=row.get("Signal", ""),
        stop_loss=stop_loss,
        target=target,
        note=note,
    )

    st.success(f"Added {row['Symbol']} to Watchlist")


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

    render_add_to_watchlist(filtered)

    render_table(filtered)
