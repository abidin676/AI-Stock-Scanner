import os
import sys

# เพิ่มโฟลเดอร์โปรเจกต์เข้า Python Path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from providers.thai import get_symbols

symbols = get_symbols("SET")

print(f"Total symbols: {len(symbols)}")
print(symbols)