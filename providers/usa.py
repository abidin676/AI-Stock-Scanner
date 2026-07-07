from pathlib import Path


BASES = [
    Path(__file__).parent.parent / "watchlists",
    Path(__file__).parent / "lists",
]


def load_list(filename):

    path = None

    for base in BASES:
        candidate = base / filename

        if candidate.exists() and candidate.stat().st_size > 0:
            path = candidate
            break

    if path is None:
        raise FileNotFoundError(f"Watchlist not found: {filename}")

    with open(path, "r", encoding="utf-8") as file:
        return [
            line.strip().upper()
            for line in file
            if line.strip()
        ]


def dedupe(symbols):

    seen = set()
    result = []

    for symbol in symbols:
        if symbol in seen:
            continue

        seen.add(symbol)
        result.append(symbol)

    return result


def get_symbols(index="US100"):

    index = index.upper().replace("_", " ")
    mapping = {
        "US100": "us100.txt",
        "SP500": "sp500.txt",
        "DOW30": "dow30.txt",
        "USA WATCHLIST": "current.txt",
    }

    if index == "USA ALL":
        symbols = []

        for filename in (
            "us100.txt",
            "sp500.txt",
            "dow30.txt",
        ):
            symbols.extend(
                load_list(filename)
            )

        return dedupe(symbols)

    if index not in mapping:
        raise ValueError(f"Unknown index: {index}")

    return load_list(mapping[index])
