from pathlib import Path


BASES = [
    Path(__file__).parent / "lists",
    Path(__file__).parent.parent / "watchlists",
]
MIN_SYMBOL_COUNTS = {
    "SET50": 40,
    "SET100": 80,
    "SET ALL": 500,
    "SET": 500,
}


def warn(message):

    print(f"WARNING: {message}")


def clean_symbol(symbol):

    return str(symbol).strip().upper()


def load_list(filename: str, index="SET"):

    path = None
    fallback_used = False

    for position, base in enumerate(BASES):
        candidate = base / filename

        if candidate.exists() and candidate.stat().st_size > 0:
            path = candidate
            fallback_used = position > 0
            break

    if path is None:
        raise FileNotFoundError(f"{filename} not found")

    if fallback_used:
        warn(
            f"{index} canonical list not found; using fallback sample list: {path}"
        )

    with open(path, "r", encoding="utf-8") as file:
        symbols = [
            clean_symbol(line)
            for line in file
            if clean_symbol(line)
        ]

    validate_symbol_count(
        index,
        symbols,
        path,
    )

    return symbols


def validate_symbol_count(index, symbols, path):

    expected_min = MIN_SYMBOL_COUNTS.get(
        index,
    )

    if expected_min is None:
        return

    if len(symbols) < expected_min:
        warn(
            f"{index} returned only {len(symbols)} symbols from {path}; "
            f"expected at least {expected_min}."
        )


def get_symbols(index="SET"):

    index = index.upper().replace("_", " ")

    mapping = {
        "SET": "set.txt",
        "SET ALL": "set.txt",
        "SET50": "set50.txt",
        "SET100": "set100.txt",
    }

    if index not in mapping:
        raise ValueError(f"Unknown index : {index}")

    return load_list(
        mapping[index],
        index=index,
    )
