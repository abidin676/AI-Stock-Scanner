import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from data import get_history

print("Testing data.py...")

df = get_history("AOT", "SET")

print(df.head())
print(df.tail())
print(df.columns)
print(f"Rows: {len(df)}")