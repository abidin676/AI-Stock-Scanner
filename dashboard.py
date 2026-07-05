import streamlit as st

from views.backtest import backtest_page
from views.portfolio import portfolio_page
from views.scanner import scanner_page
from views.watchlist import watchlist_page


st.set_page_config(
    page_title="River Alpha Scanner",
    page_icon="RA",
    layout="wide",
)

page = st.sidebar.radio(
    "Page",
    [
        "Scanner",
        "Watchlist",
        "Portfolio",
        "Backtest",
    ],
)

if page == "Backtest":
    backtest_page()
elif page == "Portfolio":
    portfolio_page()
elif page == "Watchlist":
    watchlist_page()
else:
    scanner_page()
