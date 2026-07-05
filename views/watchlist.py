import streamlit as st

from alert_engine import (
    ALERT_FILE,
    load_alerts,
    run_watchlist_alert_check,
)
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
    "StopLoss",
    "Target",
    "Status",
    "Note",
]
ALERT_COLUMNS = [
    "AlertTime",
    "Symbol",
    "Market",
    "AlertType",
    "Message",
    "OldValue",
    "NewValue",
    "Score",
    "Price",
    "Setup",
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
        stop_loss = st.number_input(
            "Stop Loss",
            min_value=0.0,
            value=float(row["StopLoss"]),
            step=0.01,
        )
        target = st.number_input(
            "Target",
            min_value=0.0,
            value=float(row["Target"]),
            step=0.01,
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
            stop_loss=stop_loss,
            target=target,
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
        if entry_price <= 0:
            st.error("Entry Price must be greater than 0")
            return

        if shares <= 0:
            st.error("Shares must be greater than 0")
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


def render_alerts():

    st.subheader("Watchlist Alerts")
    st.caption(f"Saved at: {ALERT_FILE}")

    alerts = load_alerts()

    if alerts.empty:
        st.info("No watchlist alerts")
        return

    alerts = alerts.tail(50).iloc[::-1]

    st.dataframe(
        alerts[
            available_columns(
                alerts,
                ALERT_COLUMNS,
            )
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_manual_alert_check():

    scanner_file = "output/scanner_results.xlsx"

    if st.button("Check Alerts From Latest Scan"):
        try:
            import pandas as pd

            scanner_results = pd.read_excel(scanner_file)
            alerts = run_watchlist_alert_check(scanner_results)

            if alerts.empty:
                st.info("No watchlist changes")
            else:
                st.success(f"Created {len(alerts)} alert(s)")

            st.rerun()
        except FileNotFoundError:
            st.error("scanner_results.xlsx not found")


def watchlist_page():

    st.title("Watchlist")
    st.caption(f"Saved at: {WATCHLIST_FILE}")

    watchlist = load_watchlist()

    render_manual_alert_check()
    render_alerts()
    st.divider()

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
