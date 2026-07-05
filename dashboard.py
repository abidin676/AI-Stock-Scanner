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

# ==========================================
# FILTER
# ==========================================

st.sidebar.header("⚙️ Filter")

min_score = st.sidebar.slider(
    "Minimum Score",
    min_value=50,
    max_value=100,
    value=90
)


def get_top(data, min_score):

    data = data[data["Score"] >= min_score]

    return (
        data
        .sort_values(
            ["Score", "RVOL", "RSI"],
            ascending=[False, False, True]
        )
        .head(20)
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

set_top = get_top(set_df, min_score)

if set_top.empty:
    st.info(f"ไม่มีหุ้น SET ที่คะแนน ≥ {min_score}")
else:
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

usa_top = get_top(usa_df, min_score)

st.markdown(f"### 🚀 Score ≥ {min_score}")
if usa_top.empty:
    st.info(f"ไม่มีหุ้น USA ที่คะแนน ≥ {min_score}")
else:

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