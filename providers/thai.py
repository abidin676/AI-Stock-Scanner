"""
Thai Stock Provider
อ่านรายชื่อหุ้นจาก watchlists/
"""

from pathlib import Path

# โฟลเดอร์ watchlists อยู่ระดับเดียวกับ providers
BASE = Path(__file__).parent.parent / "watchlists"


def load_list(filename: str):
    path = BASE / filename

    if not path.exists():
        raise FileNotFoundError(f"{path} not found")

    with open(path, "r", encoding="utf-8") as f:
        return [
            line.strip().upper()
            for line in f
            if line.strip()
        ]


def get_symbols(index="SET100"):

    index = index.upper()

    mapping = {
        "SET": "set.txt",
       
    }

    if index not in mapping:
        raise ValueError(f"Unknown index : {index}")

    return load_list(mapping[index])