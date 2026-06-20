import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

WATCHLIST_DIR = Path(PROJECT_ROOT) / "watchlists"

FILES = [
    
    "set.txt",
    "us100.txt",
    "sp500.txt",
    "dow30.txt",
]

print("=" * 50)
print("WATCHLIST VALIDATOR")
print("=" * 50)

for filename in FILES:

    path = WATCHLIST_DIR / filename

    if not path.exists():
        print(f"❌ {filename:<12} NOT FOUND")
        continue

    with open(path, "r", encoding="utf-8") as f:
        symbols = [
            line.strip().upper()
            for line in f
            if line.strip()
        ]

    duplicates = len(symbols) - len(set(symbols))

    print(f"\n📄 {filename}")
    print(f"   Symbols    : {len(symbols)}")
    print(f"   Duplicates : {duplicates}")

    if symbols:
        print(f"   First 5    : {symbols[:5]}")
        print(f"   Last 5     : {symbols[-5:]}")

print("\n✅ Validation Finished")