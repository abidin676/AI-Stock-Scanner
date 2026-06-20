import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from providers.usa import get_symbols

tests = [
    "US100",
    "SP500",
    "DOW30",
    
]

for t in tests:
    symbols = get_symbols(t)
    print(f"{t:<8} : {len(symbols)} symbols")
    print(symbols[:5])
    print("-" * 40)