import streamlit as st

from portfolio import add_position
from watchlist import (
    WATCHLIST_FILE,
    WATCHLIST_STATUSES,
    load_watchlist,
    mark_bought,
    update_watchlist_item,
)


DISPLAY_COLUMNS = [
    "Symbol",
    "Market",
    "AddedDate",
    "Price",
    "Setup",
    "Score",
    "Signal",
    "Status",
    "Note",
]


def available_columns(df, columns):

    return [
        column
        for column in columns
        if column in df.columns
    ]


def candidate_label(row):

    return (
        f"{row['Symbol']} | {row['Market']} | "
        f"{row['Status']} | {row['Setup']} | Score {row['Score']}"
    )


def selected_watchlist_row(df, selected):

    if df.empty or not selected:
        return None

    symbol, market = [
        part.strip()
        for part in selected.split("|")[:2]
    ]

    matches = df[
        (df["Symbol"] == symbol)
        &
        (df["Market"] == market)
    ]

    if matches.empty:
        return None

    return matches.iloc[0]


def render_edit_form(watchlist):

    st.subheader("Edit Watchlist")

    labels = [
        candidate_label(row)
        for _, row in watchlist.iterrows()
    ]

    selected = st.selectbox(
        "Watchlist Symbol",
        labels,
        key="watchlist_edit_symbol",
    )
    row = selected_watchlist_row(
        watchlist,
        selected,
    )

    if row is None:
        return

    status_index = (
        WATCHLIST_STATUSES.index(row["Status"])
        if row["Status"] in WATCHLIST_STATUSES
        else 0
    )

    with st.form("edit_watchlist_form"):
        status = st.selectbox(
            "Status",
            WATCHLIST_STATUSES,
            index=status_index,
        )
        note = st.text_area(
            "Note",
            value=row["Note"],
        )
        submitted = st.form_submit_button(
            "Save Watchlist"
        )

    if submitted:
        update_watchlist_item(
            row["Symbol"],
            row["Market"],
            note=note,
            status=status,
        )
        st.success(f"Updated {row['Symbol']}")
        st.rerun()


def render_buy_form(watchlist):

    st.subheader("Buy From Watchlist")

    buyable = watchlist[
        watchlist["Status"] != "BOUGHT"
    ].copy()

    if buyable.empty:
        st.info("No buyable watchlist items")
        return

    labels = [
        candidate_label(row)
        for _, row in buyable.iterrows()
    ]

    selected = st.selectbox(
        "Buy Symbol",
        labels,
        key="watchlist_buy_symbol",
    )
    row = selected_watchlist_row(
        buyable,
        selected,
    )

    if row is None:
        return

    with st.form("buy_watchlist_form"):
        entry_price = st.number_input(
            "Entry Price",
            min_value=0.0,
            value=float(row["Price"]),
            step=0.01,
        )
        shares = st.number_input(
            "Shares",
            min_value=0.0,
            value=0.0,
            step=1.0,
        )
        submitted = st.form_submit_button(
            "Buy"
        )

    if submitted:
        if entry_price <= 0 or shares <= 0:
            st.error("Entry Price and Shares are required")
            return

        add_position(
            row["Symbol"],
            row["Market"],
            entry_price,
            shares,
            row["Setup"],
            row["Score"],
        )
        mark_bought(
            row["Symbol"],
            row["Market"],
        )
        st.success(f"Bought {row['Symbol']} and added to Portfolio")
        st.rerun()


def watchlist_page():

    st.title("Watchlist")
    st.caption(f"Saved at: {WATCHLIST_FILE}")

    watchlist = load_watchlist()

    if watchlist.empty:
        st.info("No watchlist items yet. Add candidates from Scanner.")
        return

    watchlist = watchlist.sort_values(
        [
            "Status",
            "Score",
        ],
        ascending=[
            True,
            False,
        ],
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Watching", len(watchlist))
    c2.metric("Ready", int((watchlist["Status"] == "READY").sum()))
    c3.metric("Bought", int((watchlist["Status"] == "BOUGHT").sum()))

    st.dataframe(
        watchlist[
            available_columns(
                watchlist,
                DISPLAY_COLUMNS,
            )
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    left, right = st.columns(2)

    with left:
        render_edit_form(watchlist)

    with right:
        render_buy_form(watchlist)
