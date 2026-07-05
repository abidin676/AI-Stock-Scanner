from datetime import datetime
from pathlib import Path

import pandas as pd

from watchlist import load_watchlist


SNAPSHOT_FILE = Path("data") / "watchlist_scan_snapshot.csv"
ALERT_FILE = Path("data") / "watchlist_alerts.csv"
ALERT_COLUMNS = [
    "AlertTime",
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
    "StopLoss",
    "Target",
    "ScanTime",
]


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

    for column in SNAPSHOT_COLUMNS:
        if column not in df.columns:
            df[column] = 0 if column in ("Score", "Price", "StopLoss", "Target") else ""

    for column in ("Score", "Price", "StopLoss", "Target"):
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

    for column in SNAPSHOT_COLUMNS:
        if column not in df.columns:
            df[column] = 0 if column in ("Score", "Price", "StopLoss", "Target") else ""

    df[SNAPSHOT_COLUMNS].to_csv(
        SNAPSHOT_FILE,
        index=False,
    )


def build_current_snapshot(scanner_results, watchlist):

    if scanner_results.empty or watchlist.empty:
        return _empty_snapshot()

    scan = scanner_results.copy()
    watch = watchlist.copy()

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

    return current[SNAPSHOT_COLUMNS]


def alert_row(row, alert_type, message, old_value, new_value):

    return {
        "AlertTime": datetime.now().isoformat(timespec="seconds"),
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
