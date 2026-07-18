import streamlit as st

from views.approval_queue import approval_queue_page
from views.backtest import backtest_page
from views.paper_broker import paper_broker_page
from views.paper_trading import paper_trading_page
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
        "Approval Queue",
        "Paper Trading",
        "Paper Broker",
        "Strategy Lab",
    ],
)

if page == "Strategy Lab":
    backtest_page()
elif page == "Paper Trading":
    paper_trading_page()
elif page == "Paper Broker":
    paper_broker_page()
elif page == "Approval Queue":
    approval_queue_page()
elif page == "Portfolio":
    portfolio_page()
elif page == "Watchlist":
    watchlist_page()
else:
    scanner_page()
