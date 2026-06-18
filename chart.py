import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def show_chart(symbol):
    """
    แสดงกราฟราคาหุ้น พร้อม EMA20 / EMA50 / EMA200
    """

    df = yf.download(
        symbol,
        period="6mo",
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    if df.empty:
        st.warning("ไม่พบข้อมูลกราฟ")
        return

    # รองรับ yfinance เวอร์ชันใหม่
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    # EMA
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price"
        ),
        row=1,
        col=1
    )

    # EMA20
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["EMA20"],
            mode="lines",
            name="EMA20"
        ),
        row=1,
        col=1
    )

    # EMA50
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["EMA50"],
            mode="lines",
            name="EMA50"
        ),
        row=1,
        col=1
    )

    # EMA200
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["EMA200"],
            mode="lines",
            name="EMA200"
        ),
        row=1,
        col=1
    )

    # Volume
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Volume"
        ),
        row=2,
        col=1
    )

    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{symbol} Price Chart"
    )

    st.plotly_chart(fig, use_container_width=True)