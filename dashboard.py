from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

# ==========================================
# PAGE
# ==========================================

st.set_page_config(
    page_title="AI Stock Scanner",
    page_icon="📈",
    layout="wide"
)

st.title("📈 AI Stock Scanner")

# ==========================================
# LOAD DATA
# ==========================================

FILE = Path("output") / "scanner_results.xlsx"

if not FILE.exists():
    st.error("scanner_results.xlsx not found")
    st.info("Run: python scanner.py")
    st.stop()

df = pd.read_excel(FILE)

last_scan = datetime.fromtimestamp(
    FILE.stat().st_mtime
).strftime("%d/%m/%Y %H:%M:%S")

st.caption(f"Last Scan : {last_scan}")

# ==========================================
# PREPARE DATA
# ==========================================

set_df = df[df["Market"] == "SET"].copy()
usa_df = df[df["Market"] == "USA"].copy()


def get_top10(data):

    return (
        data
        .sort_values(
            ["Score", "RVOL", "RSI"],
            ascending=[False, False, True]
        )
        .head(10)
    )


# ==========================================
# SET
# ==========================================

st.divider()

st.subheader("🇹🇭 SET MARKET")

c1, c2, c3 = st.columns(3)

c1.metric(
    "Stocks",
    len(set_df)
)

c2.metric(
    "🟢 Early Buy",
    len(
        set_df[
            set_df["Signal"] == "EARLY BUY"
        ]
    )
)

c3.metric(
    "🟡 Watch",
    len(
        set_df[
            set_df["Signal"] == "WATCH"
        ]
    )
)

set_top = get_top10(set_df)

st.markdown("### 🏆 Top 10")

st.dataframe(

    set_top[
        [
            "Symbol",
            "Score",
            "Signal",
            "Price",
            "RSI",
            "RVOL"
        ]
    ],

    use_container_width=True,
    hide_index=True

)

# ==========================================
# USA
# ==========================================

st.divider()

st.subheader("🇺🇸 USA MARKET")

c1, c2, c3 = st.columns(3)

c1.metric(
    "Stocks",
    len(usa_df)
)

c2.metric(
    "🟢 Early Buy",
    len(
        usa_df[
            usa_df["Signal"] == "EARLY BUY"
        ]
    )
)

c3.metric(
    "🟡 Watch",
    len(
        usa_df[
            usa_df["Signal"] == "WATCH"
        ]
    )
)

usa_top = get_top10(usa_df)

st.markdown("### 🏆 Top 10")

st.dataframe(

    usa_top[
        [
            "Symbol",
            "Score",
            "Signal",
            "Price",
            "RSI",
            "RVOL"
        ]
    ],

    use_container_width=True,
    hide_index=True

)