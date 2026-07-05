import streamlit as st

from views.portfolio import portfolio_page
from views.scanner import scanner_page


st.set_page_config(
    page_title="River Alpha Scanner",
    page_icon="RA",
    layout="wide",
)

page = st.sidebar.radio(
    "Page",
    [
        "Scanner",
        "Portfolio",
    ],
)

if page == "Portfolio":
    portfolio_page()
else:
    scanner_page()
