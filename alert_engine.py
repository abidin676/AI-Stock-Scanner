import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from fresh_cross_candidates import fresh_cross_candidates
from notification.console_notifier import ConsoleNotifier
from notification.line_notifier import LineNotifier
from notification.telegram_notifier import TelegramNotifier
from watchlist import load_watchlist


SNAPSHOT_FILE = Path("data") / "watchlist_scan_snapshot.csv"
ALERT_FILE = Path("data") / "watchlist_alerts.csv"
PRIORITY_RESULTS_FILE = Path("output") / "priority_results.csv"
SEED_ALERT_HISTORY_FILE = Path("data") / "alert_history.csv"
SEED_ALERT_OUTPUT_FILE = Path("output") / "seed_alerts.csv"
SEED_ALERT_COLUMNS = [
    "AlertTime",
    "ScanDate",
    "AlertKey",
    "Symbol",
    "Market",
    "Signal",
    "Action",
    "CrossAge",
    "CrossStatus",
    "CrossDate",
    "LatestPriceDate",
    "SeedScore",
    "PatternName",
    "FreshnessScore",
    "ExpansionScore",
    "RR",
    "Reason",
    "Message",
    "SourceFile",
]
ALERT_COLUMNS = [
    "AlertTime",
    "AlertKey",
    "Symbol",
    "Market",
    "AlertType",
    "Message",
    "OldValue",
    "NewValue",
    "Signal",
    "Score",
    "Price",
    "Setup",
    "LifecycleState",
    "PreviousLifecycleState",
    "StrategyMode",
    "StrategySignal",
    "StrategyScore",
    "StrategySetup",
    "Channel",
    "Delivered",
]
SNAPSHOT_COLUMNS = [
    "Symbol",
    "Market",
    "Signal",
    "SignalGroup",
    "Score",
    "Price",
    "Setup",
    "LifecycleState",
    "PreviousLifecycleState",
    "DaysInState",
    "StateChanged",
    "StrategyMode",
    "StrategySignal",
    "StrategyScore",
    "StrategySetup",
    "StopLoss",
    "Target",
    "LastAlertKey",
    "ScanTime",
]
LIFECYCLE_TRANSITIONS = {
    ("EARLY", "BREAKOUT"),
    ("BREAKOUT", "MOMENTUM"),
    ("MOMENTUM", "EXTENDED"),
    ("WATCH", "EARLY"),
    ("SKIP", "EARLY"),
    ("SKIP", "BREAKOUT"),
}


class DashboardAlertNotifier:

    channel = "dashboard"

    def send(self, alerts):

        return alerts


def dispatch_alerts(alerts, notifier=None):

    notifier = notifier or DashboardAlertNotifier()

    if alerts.empty:
        return alerts

    alerts = alerts.copy()
    alerts["Channel"] = notifier.channel
    alerts["Delivered"] = False

    return notifier.send(alerts)


def _empty_alerts():

    return pd.DataFrame(
        columns=ALERT_COLUMNS
    )


def _empty_snapshot():

    return pd.DataFrame(
        columns=SNAPSHOT_COLUMNS
    )


def _safe_float(value, default=0.0):

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):

    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_bool(value):

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    return str(value).strip().upper() in {
        "TRUE",
        "1",
        "YES",
        "Y",
    }


def _safe_text(value, default=""):

    if pd.isna(value):
        return default

    return str(value).strip()


def _format_score(value, digits=0):

    number = _safe_float(value)

    if digits <= 0:
        return f"{number:.0f}"

    return f"{number:.{digits}f}"


def _normalize_state(value):

    state = str(value or "UNKNOWN").strip().upper()

    if not state or state == "NAN":
        return "UNKNOWN"

    return state


def signal_group(signal):

    signal = str(signal).upper()

    if "BUY" in signal:
        return "BUY"

    if "WATCH" in signal:
        return "WATCH"

    if "EARLY" in signal:
        return "EARLY"

    if "EXTENDED" in signal:
        return "EXTENDED"

    if "SKIP" in signal:
        return "SKIP"

    return "OTHER"


def is_breakout(setup):

    return "BREAKOUT" in str(setup).upper()


def empty_seed_alerts():

    return pd.DataFrame(
        columns=SEED_ALERT_COLUMNS
    )


def ensure_seed_alert_columns(df):

    data = df.copy()

    for column in SEED_ALERT_COLUMNS:
        if column not in data.columns:
            data[column] = ""

    return data[SEED_ALERT_COLUMNS]


def save_seed_alerts(df, path=SEED_ALERT_OUTPUT_FILE):

    path.parent.mkdir(
        exist_ok=True
    )
    ensure_seed_alert_columns(df).to_csv(
        path,
        index=False,
    )


def load_alert_history(path=SEED_ALERT_HISTORY_FILE):

    path.parent.mkdir(
        exist_ok=True
    )

    if not path.exists():
        save_seed_alert_history(
            empty_seed_alerts(),
            path=path,
        )
        return empty_seed_alerts()

    try:
        return ensure_seed_alert_columns(
            pd.read_csv(path)
        )
    except pd.errors.EmptyDataError:
        return empty_seed_alerts()


def save_seed_alert_history(df, path=SEED_ALERT_HISTORY_FILE):

    path.parent.mkdir(
        exist_ok=True
    )
    ensure_seed_alert_columns(df).to_csv(
        path,
        index=False,
    )


def load_priority_results(path=PRIORITY_RESULTS_FILE):

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def scan_date_for_file(path=PRIORITY_RESULTS_FILE):

    if path.exists():
        return datetime.fromtimestamp(
            path.stat().st_mtime
        ).strftime("%Y-%m-%d")

    return datetime.now().strftime("%Y-%m-%d")


def valid_seed_candidates(priority_results):

    if priority_results.empty:
        return priority_results.copy()

    data = fresh_cross_candidates(priority_results)

    for column in [
        "Symbol",
        "Market",
        "LifecycleState",
        "StrategySignal",
        "RecommendedAction",
    ]:
        if column not in data.columns:
            data[column] = ""

    lifecycle = data["LifecycleState"].astype(str).str.upper()
    signal = data["StrategySignal"].astype(str).str.upper()
    action = data["RecommendedAction"].astype(str).str.upper()
    valid = data[
        data["FreshCrossEligible"]
        & (lifecycle == "SEED")
        & signal.str.contains("SEED", regex=False, na=False)
        & ~signal.str.contains(
            "MOMENTUM|EXTENDED|SKIP",
            regex=True,
            na=False,
        )
        & (action != "IGNORE")
    ].copy()

    if valid.empty:
        return valid

    if "PriorityRank" in valid.columns:
        valid["_alert_rank"] = pd.to_numeric(
            valid["PriorityRank"],
            errors="coerce",
        ).fillna(999999)
    else:
        valid["_alert_rank"] = 999999

    if "PriorityScore" in valid.columns:
        valid["_alert_score"] = pd.to_numeric(
            valid["PriorityScore"],
            errors="coerce",
        ).fillna(0)
    else:
        valid["_alert_score"] = pd.to_numeric(
            valid["SeedScore"]
            if "SeedScore" in valid.columns
            else pd.Series(0, index=valid.index),
            errors="coerce",
        ).fillna(0)

    return valid.sort_values(
        [
            "_alert_rank",
            "_alert_score",
        ],
        ascending=[
            True,
            False,
        ],
    )


def seed_alert_action(row):

    signal = _safe_text(
        row.get(
            "StrategySignal",
            row.get("Signal", ""),
        )
    ).upper()

    if "SEED BUY" in signal:
        return "BUY"

    if "SEED WATCH" in signal:
        return "WATCH"

    action = _safe_text(row.get("RecommendedAction", "WATCH")).upper()

    if "BUY" in action:
        return "BUY"

    if "WATCH" in action:
        return "WATCH"

    return action or "WATCH"


def seed_alert_reason(row):

    setup = _safe_text(
        row.get(
            "StrategySetup",
            row.get("Setup", "Seed"),
        ),
        "Seed",
    )
    base_days = _safe_int(row.get("BaseDays", 0))
    dry_days = _safe_int(row.get("DryVolumeDays", 0))
    parts = []

    fresh_reason = _safe_text(row.get("FreshCrossReason", ""))
    if fresh_reason:
        parts.append(fresh_reason)

    if setup:
        parts.append(setup)

    if base_days > 0:
        parts.append(f"Base {base_days}d")

    if dry_days > 0:
        parts.append(f"Dry volume {dry_days}d")

    return " · ".join(parts)


def seed_alert_message(row, action, reason):

    symbol = _safe_text(row.get("Symbol", "")).upper()
    seed_score = _format_score(row.get("SeedScore", 0))
    pattern = _safe_text(row.get("PatternName", "Seed"), "Seed")
    freshness = _format_score(row.get("FreshnessScore", 0))
    expansion = _format_score(row.get("ExpansionScore", 0))
    rr = _format_score(row.get("RR", 0), digits=1)
    cross_age = _safe_text(row.get("CrossAgeLabel", "-"), "-")
    cross_status = _safe_text(
        row.get("FreshCrossStatusLabel", "Fresh Cross"),
        "Fresh Cross",
    )
    cross_date = _safe_text(row.get("CrossDate", "-"), "-")
    latest_price_date = _safe_text(
        row.get("LatestPriceDate", "-"),
        "-",
    )

    return "\n".join(
        [
            "🌱 River Alpha Seed Alert",
            f"Symbol: {symbol}",
            f"Action: {action}",
            f"Cross: {cross_age} ({cross_status})",
            f"Cross date: {cross_date}",
            f"Latest price date: {latest_price_date}",
            f"Seed: {seed_score}",
            f"Pattern: {pattern}",
            f"Fresh: {freshness}",
            f"Expansion: {expansion}",
            f"RR: {rr}",
            f"Reason: {reason}",
        ]
    )


def seed_alert_row(row, scan_date, source_file=PRIORITY_RESULTS_FILE):

    signal = _safe_text(
        row.get(
            "StrategySignal",
            row.get("Signal", ""),
        )
    ).upper()
    symbol = _safe_text(row.get("Symbol", "")).upper()
    market = _safe_text(row.get("Market", "")).upper()
    action = seed_alert_action(row)
    reason = seed_alert_reason(row)
    alert_key = f"{symbol}|{scan_date}|{signal}"

    return {
        "AlertTime": datetime.now().isoformat(timespec="seconds"),
        "ScanDate": scan_date,
        "AlertKey": alert_key,
        "Symbol": symbol,
        "Market": market,
        "Signal": signal,
        "Action": action,
        "CrossAge": _safe_text(row.get("CrossAgeLabel", "-"), "-"),
        "CrossStatus": _safe_text(
            row.get("FreshCrossStatusLabel", ""),
        ),
        "CrossDate": _safe_text(row.get("CrossDate", "")),
        "LatestPriceDate": _safe_text(
            row.get("LatestPriceDate", ""),
        ),
        "SeedScore": _format_score(row.get("SeedScore", 0)),
        "PatternName": _safe_text(row.get("PatternName", "")),
        "FreshnessScore": _format_score(row.get("FreshnessScore", 0)),
        "ExpansionScore": _format_score(row.get("ExpansionScore", 0)),
        "RR": _format_score(row.get("RR", 0), digits=1),
        "Reason": reason,
        "Message": seed_alert_message(row, action, reason),
        "SourceFile": str(source_file),
    }


def generate_seed_alerts(
    priority_results=None,
    scan_date=None,
    history=None,
    source_file=PRIORITY_RESULTS_FILE,
    force=False,
):

    priority_results = (
        load_priority_results(source_file)
        if priority_results is None
        else priority_results
    )
    scan_date = scan_date or scan_date_for_file(source_file)
    history = load_alert_history() if history is None else history
    existing_keys = set(
        history.get(
            "AlertKey",
            pd.Series(dtype=str),
        )
        .dropna()
        .astype(str)
    )
    rows = []
    generated_keys = set()

    for _, row in valid_seed_candidates(priority_results).iterrows():
        alert = seed_alert_row(
            row,
            scan_date,
            source_file=source_file,
        )

        if alert["AlertKey"] in generated_keys:
            continue

        if not force and alert["AlertKey"] in existing_keys:
            continue

        generated_keys.add(alert["AlertKey"])
        rows.append(alert)

    if not rows:
        return empty_seed_alerts()

    return ensure_seed_alert_columns(pd.DataFrame(rows))


def run_seed_alert_engine(
    priority_path=PRIORITY_RESULTS_FILE,
    output_path=SEED_ALERT_OUTPUT_FILE,
    history_path=SEED_ALERT_HISTORY_FILE,
    force=False,
    reset_history=False,
):

    if reset_history:
        history = empty_seed_alerts()
        save_seed_alert_history(
            history,
            path=history_path,
        )
    else:
        history = load_alert_history(history_path)

    priority_results = load_priority_results(priority_path)
    alerts = generate_seed_alerts(
        priority_results=priority_results,
        scan_date=scan_date_for_file(priority_path),
        history=history,
        source_file=priority_path,
        force=force,
    )
    save_seed_alerts(
        alerts,
        path=output_path,
    )

    if not alerts.empty:
        updated_history = pd.concat(
            [
                history,
                alerts,
            ],
            ignore_index=True,
        ).drop_duplicates(
            subset=["AlertKey"],
            keep="first",
        )
        save_seed_alert_history(
            updated_history,
            path=history_path,
        )
    else:
        save_seed_alert_history(
            history,
            path=history_path,
        )

    return alerts


def build_notifier(name="console"):

    key = str(name or "console").strip().lower()

    if key == "console":
        return ConsoleNotifier()

    if key == "line":
        return LineNotifier()

    if key == "telegram":
        return TelegramNotifier()

    raise ValueError(f"Unknown notifier: {name}")


def notify_seed_alerts(alerts, notifier):

    if alerts.empty:
        return

    for message in alerts["Message"].dropna().astype(str):
        if message.strip():
            notifier.send(message)


def lifecycle_alert_key(symbol, old_state, new_state):

    return (
        f"LIFECYCLE:{str(symbol).upper().strip()}:"
        f"{old_state}>{new_state}"
    )


def existing_alert_keys():

    alerts = load_alerts()

    if alerts.empty or "AlertKey" not in alerts.columns:
        return set()

    return {
        str(value)
        for value in alerts["AlertKey"].dropna()
        if str(value).strip()
    }


def load_alerts():

    ALERT_FILE.parent.mkdir(
        exist_ok=True
    )

    if not ALERT_FILE.exists():
        save_alerts(_empty_alerts())
        return _empty_alerts()

    df = pd.read_csv(ALERT_FILE)

    for column in ALERT_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    return df[ALERT_COLUMNS]


def save_alerts(df):

    ALERT_FILE.parent.mkdir(
        exist_ok=True
    )

    df = df.copy()

    for column in ALERT_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df[ALERT_COLUMNS].to_csv(
        ALERT_FILE,
        index=False,
    )


def load_snapshot():

    SNAPSHOT_FILE.parent.mkdir(
        exist_ok=True
    )

    if not SNAPSHOT_FILE.exists():
        return _empty_snapshot()

    df = pd.read_csv(SNAPSHOT_FILE)
    numeric_columns = (
        "Score",
        "Price",
        "StopLoss",
        "Target",
        "StrategyScore",
        "DaysInState",
    )

    for column in SNAPSHOT_COLUMNS:
        if column not in df.columns:
            df[column] = 0 if column in numeric_columns else ""

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0).astype(float)

    return df[SNAPSHOT_COLUMNS]


def save_snapshot(df):

    SNAPSHOT_FILE.parent.mkdir(
        exist_ok=True
    )

    df = df.copy()
    numeric_columns = (
        "Score",
        "Price",
        "StopLoss",
        "Target",
        "StrategyScore",
        "DaysInState",
    )

    for column in SNAPSHOT_COLUMNS:
        if column not in df.columns:
            df[column] = 0 if column in numeric_columns else ""

    df[SNAPSHOT_COLUMNS].to_csv(
        SNAPSHOT_FILE,
        index=False,
    )


def build_current_snapshot(scanner_results, watchlist):

    if scanner_results.empty or watchlist.empty:
        return _empty_snapshot()

    scan = scanner_results.copy()
    watch = watchlist.copy()

    if "StrategyMode" not in scan.columns:
        scan["StrategyMode"] = "Standard"

    if "StrategySignal" not in scan.columns:
        scan["StrategySignal"] = scan.get("Signal", "")

    if "StrategyScore" not in scan.columns:
        scan["StrategyScore"] = scan.get("Score", 0)

    if "StrategySetup" not in scan.columns:
        scan["StrategySetup"] = scan.get("Setup", "")

    if "LifecycleState" not in scan.columns:
        scan["LifecycleState"] = "UNKNOWN"

    if "PreviousLifecycleState" not in scan.columns:
        scan["PreviousLifecycleState"] = "UNKNOWN"

    if "DaysInState" not in scan.columns:
        scan["DaysInState"] = 0

    if "StateChanged" not in scan.columns:
        scan["StateChanged"] = False

    for df in (scan, watch):
        df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
        df["Market"] = df["Market"].astype(str).str.upper().str.strip()

    current = scan.merge(
        watch[
            [
                "Symbol",
                "Market",
                "StopLoss",
                "Target",
            ]
        ],
        on=[
            "Symbol",
            "Market",
        ],
        how="inner",
    )

    if current.empty:
        return _empty_snapshot()

    current["Signal"] = current["StrategySignal"]
    current["Setup"] = current["StrategySetup"]
    current["Score"] = current["StrategyScore"]
    current["SignalGroup"] = current["Signal"].apply(signal_group)
    current["Score"] = pd.to_numeric(
        current["Score"],
        errors="coerce",
    ).fillna(0).astype(float)
    current["Price"] = pd.to_numeric(
        current["Price"],
        errors="coerce",
    ).fillna(0).astype(float)
    current["StopLoss"] = pd.to_numeric(
        current["StopLoss"],
        errors="coerce",
    ).fillna(0).astype(float)
    current["Target"] = pd.to_numeric(
        current["Target"],
        errors="coerce",
    ).fillna(0).astype(float)
    current["ScanTime"] = datetime.now().isoformat(
        timespec="seconds"
    )
    current["StrategyScore"] = current["Score"]
    current["LifecycleState"] = current["LifecycleState"].apply(
        _normalize_state
    )
    current["PreviousLifecycleState"] = current[
        "PreviousLifecycleState"
    ].apply(
        _normalize_state
    )
    current["DaysInState"] = current["DaysInState"].apply(
        _safe_int
    )
    current["StateChanged"] = current["StateChanged"].apply(
        _safe_bool
    )
    current["LastAlertKey"] = ""

    return current[SNAPSHOT_COLUMNS]


def alert_row(
    row,
    alert_type,
    message,
    old_value,
    new_value,
    alert_key="",
):

    return {
        "AlertTime": datetime.now().isoformat(timespec="seconds"),
        "AlertKey": alert_key,
        "Symbol": row["Symbol"],
        "Market": row["Market"],
        "AlertType": alert_type,
        "Message": message,
        "OldValue": old_value,
        "NewValue": new_value,
        "Signal": row["Signal"],
        "Score": row["Score"],
        "Price": row["Price"],
        "Setup": row["Setup"],
        "LifecycleState": row.get("LifecycleState", "UNKNOWN"),
        "PreviousLifecycleState": row.get(
            "PreviousLifecycleState",
            "UNKNOWN",
        ),
        "StrategyMode": row.get("StrategyMode", "Standard"),
        "StrategySignal": row.get("StrategySignal", row["Signal"]),
        "StrategyScore": row.get("StrategyScore", row["Score"]),
        "StrategySetup": row.get("StrategySetup", row["Setup"]),
        "Channel": "dashboard",
        "Delivered": False,
    }


def build_alerts(current, previous):

    if current.empty or previous.empty:
        return _empty_alerts()

    previous_lookup = previous.set_index(
        [
            "Symbol",
            "Market",
        ]
    )
    rows = []
    alert_keys = existing_alert_keys()
    generated_keys = set()

    for _, row in current.iterrows():
        key = (
            row["Symbol"],
            row["Market"],
        )

        if key not in previous_lookup.index:
            continue

        old = previous_lookup.loc[key]
        old_signal = str(old["SignalGroup"])
        new_signal = str(row["SignalGroup"])
        old_score = _safe_float(old["Score"])
        new_score = _safe_float(row["Score"])
        old_price = _safe_float(old["Price"])
        new_price = _safe_float(row["Price"])
        stop_loss = _safe_float(row["StopLoss"])
        target = _safe_float(row["Target"])
        old_lifecycle = _normalize_state(
            old.get(
                "LifecycleState",
                "",
            )
        )
        new_lifecycle = _normalize_state(
            row.get(
                "LifecycleState",
                "UNKNOWN",
            )
        )
        scan_previous_lifecycle = _normalize_state(
            row.get(
                "PreviousLifecycleState",
                "UNKNOWN",
            )
        )

        if (
            old_lifecycle == "UNKNOWN"
            and scan_previous_lifecycle != "UNKNOWN"
        ):
            old_lifecycle = scan_previous_lifecycle

        if old_signal != new_signal:
            rows.append(
                alert_row(
                    row,
                    "SIGNAL_CHANGE",
                    f"{row['Symbol']} signal changed from {old_signal} to {new_signal}",
                    old_signal,
                    new_signal,
                )
            )

        lifecycle_transition = (
            old_lifecycle,
            new_lifecycle,
        )

        if lifecycle_transition in LIFECYCLE_TRANSITIONS:
            key_value = lifecycle_alert_key(
                row["Symbol"],
                old_lifecycle,
                new_lifecycle,
            )

            if (
                key_value not in alert_keys
                and key_value not in generated_keys
            ):
                rows.append(
                    alert_row(
                        row,
                        "LIFECYCLE_CHANGE",
                        (
                            f"{row['Symbol']} lifecycle changed from "
                            f"{old_lifecycle} to {new_lifecycle}"
                        ),
                        old_lifecycle,
                        new_lifecycle,
                        alert_key=key_value,
                    )
                )
                generated_keys.add(key_value)

        score_change = new_score - old_score

        if abs(score_change) >= 5:
            rows.append(
                alert_row(
                    row,
                    "SCORE_CHANGE",
                    f"{row['Symbol']} score changed by {score_change:.1f}",
                    old_score,
                    new_score,
                )
            )

        if is_breakout(row["Setup"]) and not is_breakout(old["Setup"]):
            rows.append(
                alert_row(
                    row,
                    "NEW_BREAKOUT",
                    f"{row['Symbol']} has a new breakout setup",
                    old["Setup"],
                    row["Setup"],
                )
            )

        if stop_loss > 0 and old_price > stop_loss >= new_price:
            rows.append(
                alert_row(
                    row,
                    "STOP_LOSS",
                    f"{row['Symbol']} broke stop loss {stop_loss:.2f}",
                    old_price,
                    new_price,
                )
            )

        if target > 0 and old_price < target <= new_price:
            rows.append(
                alert_row(
                    row,
                    "TARGET_HIT",
                    f"{row['Symbol']} reached target {target:.2f}",
                    old_price,
                    new_price,
                )
            )

    if not rows:
        return _empty_alerts()

    return pd.DataFrame(rows)[ALERT_COLUMNS]


def append_alerts(alerts):

    if alerts.empty:
        return

    existing = load_alerts()
    save_alerts(
        pd.concat(
            [
                existing,
                alerts,
            ],
            ignore_index=True,
        )
    )


def run_watchlist_alert_check(scanner_results):

    watchlist = load_watchlist()
    current = build_current_snapshot(
        scanner_results,
        watchlist,
    )
    previous = load_snapshot()
    alerts = build_alerts(
        current,
        previous,
    )
    alerts = dispatch_alerts(alerts)

    if not alerts.empty:
        append_alerts(alerts)

    save_snapshot(current)

    return alerts


def parse_args():

    parser = argparse.ArgumentParser(
        description="River Alpha local dry-run alert engine."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Generate alerts even if the alert key already exists in history.",
    )
    parser.add_argument(
        "--reset-history",
        action="store_true",
        help="Clear data/alert_history.csv before running.",
    )
    parser.add_argument(
        "--send-line",
        action="store_true",
        help="Placeholder for future LINE delivery. Does not send yet.",
    )
    parser.add_argument(
        "--notifier",
        choices=[
            "console",
            "line",
            "telegram",
        ],
        default="console",
        help="Notification backend to use for alert messages.",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    seed_alerts = run_seed_alert_engine(
        force=args.force,
        reset_history=args.reset_history,
    )
    notifier_name = "line" if args.send_line else args.notifier
    notifier = build_notifier(notifier_name)

    try:
        notify_seed_alerts(
            seed_alerts,
            notifier,
        )
    except NotImplementedError as exc:
        if args.send_line:
            print("LINE sending is not implemented yet.")
        else:
            print(str(exc))

    print(
        f"Seed alerts generated: {len(seed_alerts)}"
    )
    print(
        f"Output: {SEED_ALERT_OUTPUT_FILE}"
    )
    print(
        f"History: {SEED_ALERT_HISTORY_FILE}"
    )


if __name__ == "__main__":

    main()
