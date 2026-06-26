import streamlit as st

from views.scanner import scanner_page
from views.backtest import backtest_page
from views.portfolio import portfolio_page
from views.performance import performance_page


st.set_page_config(
    page_title="River Alpha",
    page_icon="📈",
    layout="wide"
)


page = st.sidebar.radio(
    "📂 Menu",
    [
        "📈 Scanner",
        "📊 Backtest",
        "💼 Portfolio",
        "📉 Performance",
    ]
)


if page == "📈 Scanner":
    scanner_page()

elif page == "📊 Backtest":
    backtest_page()

elif page == "💼 Portfolio":
    portfolio_page()

elif page == "📉 Performance":
    performance_page()