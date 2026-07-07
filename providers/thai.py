from pathlib import Path


BASES = [
    Path(__file__).parent.parent / "watchlists",
    Path(__file__).parent / "lists",
]


def load_list(filename: str):

    path = None

    for base in BASES:
        candidate = base / filename

        if candidate.exists() and candidate.stat().st_size > 0:
            path = candidate
            break

    if path is None:
        raise FileNotFoundError(f"{filename} not found")

    with open(path, "r", encoding="utf-8") as file:
        return [
            line.strip().upper()
            for line in file
            if line.strip()
        ]


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

    return load_list(mapping[index])
