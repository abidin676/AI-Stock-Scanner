import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "output" / "scanner_benchmark.csv"
PRICE_CACHE_DIR = ROOT / "data" / "price_cache"
MODES = [
    "SET50",
    "SET100",
    "SET All",
    "USA All",
    "ALL",
]
CSV_COLUMNS = [
    "RunTimestamp",
    "Mode",
    "RunType",
    "Workers",
    "Symbols",
    "DownloadTime",
    "ProcessingTime",
    "TotalTime",
    "Success",
    "Error",
]
STATE_FILES = [
    ROOT / "output" / "scanner_results.csv",
    ROOT / "output" / "scanner_results.xlsx",
    ROOT / "output" / "market_quality.csv",
    ROOT / "data" / "watchlist_alerts.csv",
    ROOT / "data" / "watchlist_scan_snapshot.csv",
]
TOTAL_ROW_PATTERN = re.compile(
    r"^\s*TOTAL\s+ALL\s+"
    r"(?P<symbols>\d+)\s+"
    r"(?P<download>[-+]?\d+(?:\.\d+)?)\s+"
    r"(?P<processing>[-+]?\d+(?:\.\d+)?)\s+"
    r"(?P<total>[-+]?\d+(?:\.\d+)?)\s*$"
)


def snapshot_state():

    snapshots = {}

    for path in STATE_FILES:
        snapshots[path] = (
            path.read_bytes()
            if path.exists()
            else None
        )

    return snapshots


def restore_state(snapshots):

    for path, content in snapshots.items():
        if content is None:
            continue

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_bytes(content)


def clear_price_cache():

    if PRICE_CACHE_DIR.exists():
        shutil.rmtree(PRICE_CACHE_DIR)


def scanner_command(mode, workers, force_refresh):

    command = [
        sys.executable,
        "scanner.py",
        "--mode",
        mode,
        "--workers",
        str(workers),
    ]

    if force_refresh:
        command.append("--force-refresh")

    return command


def parse_duration(output):

    for line in output.splitlines():
        match = TOTAL_ROW_PATTERN.match(line)

        if match:
            return {
                "Symbols": int(match.group("symbols")),
                "DownloadTime": float(match.group("download")),
                "ProcessingTime": float(match.group("processing")),
                "TotalTime": float(match.group("total")),
            }

    raise ValueError("Could not parse SCAN DURATION SUMMARY total row")


def compact_error(stdout, stderr, exception=None):

    if exception is not None:
        return str(exception)

    text = "\n".join(
        part
        for part in [
            stderr,
            stdout,
        ]
        if part
    ).strip()

    if not text:
        return ""

    return text[-1000:].replace(
        "\r",
        "",
    )


def run_scanner(mode, run_type, workers):

    force_refresh = run_type == "Cold"

    if force_refresh:
        clear_price_cache()

    command = scanner_command(
        mode,
        workers,
        force_refresh,
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        output = (
            (completed.stdout or "")
            + "\n"
            + (completed.stderr or "")
        )
        duration = parse_duration(output)
        success = completed.returncode == 0
        error = (
            ""
            if success
            else compact_error(
                completed.stdout,
                completed.stderr,
            )
        )
    except Exception as error:
        duration = {
            "Symbols": 0,
            "DownloadTime": 0.0,
            "ProcessingTime": 0.0,
            "TotalTime": 0.0,
        }
        success = False
        error = compact_error(
            "",
            "",
            exception=error,
        )

    return {
        "RunTimestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Mode": mode,
        "RunType": run_type,
        "Workers": int(workers),
        "Symbols": duration["Symbols"],
        "DownloadTime": duration["DownloadTime"],
        "ProcessingTime": duration["ProcessingTime"],
        "TotalTime": duration["TotalTime"],
        "Success": success,
        "Error": error,
    }


def write_results(rows):

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=CSV_COLUMNS,
        )
        writer.writeheader()
        writer.writerows(rows)


def format_seconds(value):

    if value is None:
        return "N/A"

    return f"{float(value):.2f}s"


def build_summary(rows, modes=None):

    modes = modes or MODES

    by_mode = {
        mode: {}
        for mode in modes
    }

    for row in rows:
        run_type = row["RunType"]
        current = by_mode.setdefault(
            row["Mode"],
            {},
        ).get(run_type)

        if current and float(current["TotalTime"]) <= float(row["TotalTime"]):
            continue

        by_mode.setdefault(
            row["Mode"],
            {},
        )[run_type] = row

    summary = []

    for mode in modes:
        cold = by_mode.get(
            mode,
            {},
        ).get("Cold")
        warm = by_mode.get(
            mode,
            {},
        ).get("Warm")
        cold_total = (
            float(cold["TotalTime"])
            if cold
            else None
        )
        warm_total = (
            float(warm["TotalTime"])
            if warm
            else None
        )
        speedup = (
            cold_total / warm_total
            if cold_total is not None
            and warm_total
            and warm_total > 0
            else None
        )
        summary.append(
            {
                "Mode": mode,
                "Cold Total": format_seconds(cold_total),
                "Warm Total": format_seconds(warm_total),
                "Speedup": (
                    f"{speedup:.2f}x"
                    if speedup is not None
                    else "N/A"
                ),
            }
        )

    return summary


def build_worker_summary(rows):

    grouped = {}

    for row in rows:
        if not row["Success"]:
            continue

        workers = int(row["Workers"])
        grouped.setdefault(
            workers,
            [],
        ).append(float(row["TotalTime"]))

    summary = []

    for workers, totals in sorted(grouped.items()):
        total_time = sum(totals)
        avg_time = total_time / len(totals)
        summary.append({
            "Workers": workers,
            "Runs": len(totals),
            "Avg Total": f"{avg_time:.2f}s",
            "Combined Total": f"{total_time:.2f}s",
            "_avg": avg_time,
        })

    return summary


def print_worker_summary(rows):

    summary = build_worker_summary(rows)

    if not summary:
        return

    best = min(
        summary,
        key=lambda row: row["_avg"],
    )
    display = [
        {
            key: value
            for key, value in row.items()
            if key != "_avg"
        }
        for row in summary
    ]

    print("\nWorker Benchmark")
    print_table(
        display,
        [
            "Workers",
            "Runs",
            "Avg Total",
            "Combined Total",
        ],
    )
    print(f"\nBest worker count: {best['Workers']}")


def parse_worker_values(raw):

    values = []

    for part in str(raw).split(","):
        part = part.strip()

        if not part:
            continue

        values.append(int(part))

    if not values:
        raise ValueError("No worker values provided")

    return values


def parse_modes(raw):

    if not raw:
        return MODES

    requested = [
        part.strip()
        for part in str(raw).split(",")
        if part.strip()
    ]
    invalid = [
        mode
        for mode in requested
        if mode not in MODES
    ]

    if invalid:
        valid = ", ".join(MODES)
        raise ValueError(
            f"Unknown mode(s): {', '.join(invalid)}. Valid modes: {valid}"
        )

    return requested


def print_table(rows, columns):

    widths = {
        column: len(column)
        for column in columns
    }

    for row in rows:
        for column in columns:
            widths[column] = max(
                widths[column],
                len(str(row[column])),
            )

    header = " | ".join(
        column.ljust(widths[column])
        for column in columns
    )
    divider = "-+-".join(
        "-" * widths[column]
        for column in columns
    )

    print(header)
    print(divider)

    for row in rows:
        print(
            " | ".join(
                str(row[column]).ljust(widths[column])
                for column in columns
            )
        )


def parse_args():

    parser = argparse.ArgumentParser(
        description="Benchmark River Alpha Scanner performance."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Worker count passed to scanner.py.",
    )
    parser.add_argument(
        "--skip-cold",
        action="store_true",
        help="Skip force-refresh cold runs.",
    )
    parser.add_argument(
        "--skip-warm",
        action="store_true",
        help="Skip cached warm runs.",
    )
    parser.add_argument(
        "--worker-suite",
        action="store_true",
        help="Run benchmark for multiple worker counts.",
    )
    parser.add_argument(
        "--worker-values",
        default="4,8,12,16",
        help="Comma-separated worker counts for --worker-suite.",
    )
    parser.add_argument(
        "--modes",
        default=",".join(MODES),
        help="Comma-separated modes to run.",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    if args.skip_cold and args.skip_warm:
        raise SystemExit("Nothing to run: both --skip-cold and --skip-warm set")

    snapshots = snapshot_state()
    rows = []
    modes = parse_modes(args.modes)
    workers_list = (
        parse_worker_values(args.worker_values)
        if args.worker_suite
        else [
            args.workers,
        ]
    )

    try:
        for workers in workers_list:
            for mode in modes:
                if not args.skip_cold:
                    print(f"\n[{mode}] Cold run | workers={workers}")
                    rows.append(
                        run_scanner(
                            mode,
                            "Cold",
                            workers,
                        )
                    )

                if not args.skip_warm:
                    print(f"\n[{mode}] Warm run | workers={workers}")
                    rows.append(
                        run_scanner(
                            mode,
                            "Warm",
                            workers,
                        )
                    )
    finally:
        restore_state(snapshots)

    write_results(rows)

    print(f"\nSaved benchmark: {OUTPUT_FILE}")
    print("\nMode | Cold Total | Warm Total | Speedup")
    print_table(
        build_summary(rows, modes),
        [
            "Mode",
            "Cold Total",
            "Warm Total",
            "Speedup",
        ],
    )
    print_worker_summary(rows)


if __name__ == "__main__":
    main()
