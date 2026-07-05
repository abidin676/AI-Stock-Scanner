import streamlit as st

from views.scanner import scanner_page


st.set_page_config(
    page_title="River Alpha Scanner",
    page_icon="RA",
    layout="wide",
)

scanner_page()
