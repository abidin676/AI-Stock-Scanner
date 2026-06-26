from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st


def scanner_page():

    st.title("📈 River Alpha Scanner")

    FILE = Path("output") / "scanner_results.xlsx"

    if not FILE.exists():
        st.error("scanner_results.xlsx not found")
        st.info("Run : python scanner.py")
        return

    df = pd.read_excel(FILE)

    last_scan = datetime.fromtimestamp(
        FILE.stat().st_mtime
    ).strftime("%d/%m/%Y %H:%M:%S")

    st.caption(f"Last Scan : {last_scan}")

    set_df = df[df["Market"] == "SET"].copy()
    usa_df = df[df["Market"] == "USA"].copy()

    st.sidebar.header("⚙️ Filter")

    min_score = st.sidebar.slider(
        "Minimum Score",
        50,
        100,
        70
    )

    signal_filter = st.sidebar.multiselect(
        "Signal",
        [
            "🚀 ELITE",
            "🟢 BUY",
            "👀 WATCH",
            "🌱 EARLY"
        ],
        default=[
            "🚀 ELITE",
            "🟢 BUY",
            "👀 WATCH",
            "🌱 EARLY"
        ]
    )

    def get_top(data):

        data = data[data["Score"] >= min_score]

        data = data[
            data["Signal"].isin(signal_filter)
        ]

        return (
            data.sort_values(
                ["Score", "RVOL", "RSI"],
                ascending=[False, False, True]
            )
            .head(20)
        )

    # ==========================
    # SET
    # ==========================

    st.divider()

    st.subheader("🇹🇭 TH SET MARKET")

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Stocks", len(set_df))
    c2.metric("🚀 ELITE", len(set_df[set_df["Signal"] == "🚀 ELITE"]))
    c3.metric("🟢 BUY", len(set_df[set_df["Signal"] == "🟢 BUY"]))
    c4.metric("👀 WATCH", len(set_df[set_df["Signal"] == "👀 WATCH"]))
    c5.metric("🌱 EARLY", len(set_df[set_df["Signal"] == "🌱 EARLY"]))

    set_top = get_top(set_df)

    st.markdown(f"### 🏆 Score ≥ {min_score}")

    if set_top.empty:

        st.info("ไม่มีหุ้น SET ตามเงื่อนไข")

    else:

        columns = [
            "Symbol",
            "Score",
            "Signal",
            "Price",
            "RSI",
            "RVOL",
        ]

        if "Setup" in set_top.columns:
            columns.insert(2, "Setup")

        st.dataframe(
            set_top[columns],
            use_container_width=True,
            hide_index=True
        )

    # ==========================
    # USA
    # ==========================

    st.divider()

    st.subheader("🇺🇸 USA MARKET")

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Stocks", len(usa_df))
    c2.metric("🚀 ELITE", len(usa_df[usa_df["Signal"] == "🚀 ELITE"]))
    c3.metric("🟢 BUY", len(usa_df[usa_df["Signal"] == "🟢 BUY"]))
    c4.metric("👀 WATCH", len(usa_df[usa_df["Signal"] == "👀 WATCH"]))
    c5.metric("🌱 EARLY", len(usa_df[usa_df["Signal"] == "🌱 EARLY"]))

    usa_top = get_top(usa_df)

    st.markdown(f"### 🏆 Score ≥ {min_score}")

    if usa_top.empty:

        st.info("ไม่มีหุ้น USA ตามเงื่อนไข")

    else:

        columns = [
            "Symbol",
            "Score",
            "Signal",
            "Price",
            "RSI",
            "RVOL",
        ]

        if "Setup" in usa_top.columns:
            columns.insert(2, "Setup")

        st.dataframe(
            usa_top[columns],
            use_container_width=True,
            hide_index=True
        )