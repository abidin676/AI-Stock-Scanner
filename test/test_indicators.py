import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import yfinance as yf

from indicators import add_indicators

# โหลดข้อมูล
df = yf.download(
    "AAPL",
    period="1y",
    interval="1d",
    auto_adjust=True,
    progress=False
)

# รองรับ yfinance MultiIndex
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.droplevel(1)

df.columns = df.columns.str.lower()

# เพิ่ม Indicators
df = add_indicators(df)

print("\n===== Last 5 Rows =====\n")

print(df.tail()[[
    "close",
    "ema20",
    "ema50",
    "ema200",
    "rsi",
    "rvol",
    "ema20_slope",
    "ema50_slope",
    "atr_compression",
    "ema_compression",
    "higher_low",
    "higher_high",
    "trend_change",
    "dry_volume",
    "move_from_low90"
]])

print("\n===== NaN Count =====\n")

print(df.isna().sum())