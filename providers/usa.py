from pathlib import Path

# โฟลเดอร์ watchlists อยู่ระดับเดียวกับ providers
BASE = Path(__file__).parent.parent / "watchlists"


def load_list(filename):
    path = BASE / filename

    if not path.exists():
        raise FileNotFoundError(f"Watchlist not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return [
            line.strip().upper()
            for line in f
            if line.strip()
        ]


def get_symbols(index="US100"):

    mapping = {
        "US100": "us100.txt",
        "SP500": "sp500.txt",
        "DOW30": "dow30.txt",
        
        
    }

    index = index.upper()

    if index not in mapping:
        raise ValueError(f"Unknown index: {index}")

    return load_list(mapping[index])