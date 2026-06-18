import streamlit as st
import pandas as pd

from scanner import scan, load_watchlist

st.set_page_config(
    page_title="AI Stock Scanner",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI Stock Scanner")

# =========================================
# Sidebar
# =========================================

st.sidebar.header("⚙️ Scanner Settings")

market = st.sidebar.selectbox(
    "🌍 Market",
    ["US", "SET100"]
)

signal_filter = st.sidebar.multiselect(
    "📊 Signal",
    ["🟢 BUY", "🟡 WATCH", "🔴 SKIP"],
    default=["🟢 BUY", "🟡 WATCH"]
)

min_score = st.sidebar.slider(
    "⭐ Minimum Score",
    0,
    100,
    50
)

search = st.sidebar.text_input(
    "🔍 Search Symbol"
)

if st.sidebar.button("🔄 Refresh"):
    st.rerun()

# =========================================
# Load Watchlist
# =========================================

try:

    if market == "US":
        symbols = load_watchlist("watchlists/us100.txt")
    else:
        symbols = load_watchlist("watchlists/set100.txt")

except FileNotFoundError:

    st.warning(f"ยังไม่มี Watchlist ของ {market}")
    st.stop()

# =========================================
# Scan
# =========================================

results = []

with st.spinner("🔍 Scanning Stocks..."):

    for symbol in symbols:

        result = scan(symbol)

        if result:
            results.append(result)

if not results:

    st.error("ไม่พบข้อมูล")
    st.stop()

# =========================================
# DataFrame
# =========================================

df = pd.DataFrame(results)

df = df.sort_values("Score", ascending=False)

# Filter Score
df = df[df["Score"] >= min_score]

# Filter Signal
df = df[df["Signal"].isin(signal_filter)]

# Search
if search:
    df = df[df["Symbol"].str.contains(search.upper())]

# =========================================
# Summary
# =========================================

buy_count = len(df[df["Signal"] == "🟢 BUY"])
watch_count = len(df[df["Signal"] == "🟡 WATCH"])
skip_count = len(df[df["Signal"] == "🔴 SKIP"])

if len(df) > 0:
    top_symbol = df.iloc[0]["Symbol"]
    top_score = df.iloc[0]["Score"]
else:
    top_symbol = "-"
    top_score = "-"

c1, c2, c3, c4 = st.columns(4)

c1.metric("🟢 BUY", buy_count)
c2.metric("🟡 WATCH", watch_count)
c3.metric("🔴 SKIP", skip_count)
c4.metric("⭐ TOP", f"{top_symbol} ({top_score})")

st.divider()

# =========================================
# Result
# =========================================

st.success(f"พบหุ้น {len(df)} ตัว")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)
st.divider()

selected = st.selectbox(
    "📈 เลือกหุ้น",
    df["Symbol"]
)
