from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping
import uuid

import pandas as pd


APPROVAL_QUEUE_VERSION = "1.0"
APPROVAL_QUEUE_FILE = Path("data") / "approval_queue.csv"
APPROVAL_HISTORY_FILE = Path("data") / "approval_history.csv"
DEFAULT_EXPIRE_HOURS = 24

QUEUE_STATUSES = {
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "EXPIRED",
    "CANCELLED",
    "EXECUTED",
}

TERMINAL_STATUSES = {
    "APPROVED",
    "REJECTED",
    "EXPIRED",
    "CANCELLED",
    "EXECUTED",
}

ACTIONABLE_ACTIONS = {
    "BUY",
    "ADD",
    "REDUCE",
    "EXIT",
}

QUEUE_COLUMNS = [
    "ProposalId",
    "Symbol",
    "Market",
    "Action",
    "Quantity",
    "EntryPrice",
    "StopPrice",
    "TargetPrice",
    "RiskScore",
    "AIConfidence",
    "ProposedOrderValue",
    "EstimatedCommission",
    "EstimatedSlippage",
    "EstimatedTotalCost",
    "CreatedTime",
    "ExpireTime",
    "Status",
    "ApprovedBy",
    "ApprovedTime",
    "ExecutedTime",
    "PaperOrderId",
    "FillId",
    "RejectedReason",
    "SourceDecision",
    "AIReason",
    "AIBlockers",
    "RiskLevel",
    "RiskRewardRatio",
    "RiskBudget",
    "PositionSizeMethod",
    "CashAfterOrder",
    "RiskManagerStatus",
    "RiskManagerReason",
    "RiskManagerWarnings",
    "ProposalPriority",
    "PriorityScore",
    "OpportunityScore",
    "LifecycleState",
    "ApprovalQueueVersion",
    "LastUpdatedTime",
]

HISTORY_COLUMNS = [
    "HistoryId",
    "ProposalId",
    "Symbol",
    "Market",
    "Action",
    "FromStatus",
    "ToStatus",
    "ChangedTime",
    "ChangedBy",
    "Reason",
    "Notes",
    "ApprovalQueueVersion",
]


class ApprovalQueueError(ValueError):
    pass


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def safe_upper(value: Any, default: str = "") -> str:
    return safe_text(value, default).upper()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return safe_upper(value) in {"TRUE", "YES", "Y", "1"}


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def parse_time(value: Any, fallback: datetime | None = None) -> datetime:
    text = safe_text(value)
    if text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return fallback or datetime.now()


def normalize_queue_frame(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=QUEUE_COLUMNS)

    data = df.copy()

    for column in QUEUE_COLUMNS:
        if column not in data.columns:
            data[column] = "" if column not in numeric_queue_columns() else 0

    for column in numeric_queue_columns():
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)

    for column in QUEUE_COLUMNS:
        if column not in numeric_queue_columns():
            data[column] = data[column].fillna("").astype(str).str.strip()

    data["Status"] = data["Status"].str.upper().where(data["Status"].str.upper().isin(QUEUE_STATUSES), "PENDING_APPROVAL")
    data["Action"] = data["Action"].str.upper()
    data["Market"] = data["Market"].str.upper()

    return data[QUEUE_COLUMNS]


def numeric_queue_columns() -> set[str]:
    return {
        "Quantity",
        "EntryPrice",
        "StopPrice",
        "TargetPrice",
        "RiskScore",
        "AIConfidence",
        "ProposedOrderValue",
        "EstimatedCommission",
        "EstimatedSlippage",
        "EstimatedTotalCost",
        "RiskRewardRatio",
        "RiskBudget",
        "CashAfterOrder",
        "ProposalPriority",
        "PriorityScore",
        "OpportunityScore",
    }


def normalize_history_frame(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    data = df.copy()

    for column in HISTORY_COLUMNS:
        if column not in data.columns:
            data[column] = ""

    for column in HISTORY_COLUMNS:
        data[column] = data[column].fillna("").astype(str).str.strip()

    return data[HISTORY_COLUMNS]


def load_approval_queue(path: Path = APPROVAL_QUEUE_FILE) -> pd.DataFrame:
    if not path.exists():
        save_approval_queue(pd.DataFrame(columns=QUEUE_COLUMNS), path)
        return pd.DataFrame(columns=QUEUE_COLUMNS)

    try:
        return normalize_queue_frame(pd.read_csv(path))
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=QUEUE_COLUMNS)


def save_approval_queue(df: pd.DataFrame, path: Path = APPROVAL_QUEUE_FILE) -> Path:
    data = normalize_queue_frame(df)
    data = sort_queue(data)
    atomic_write_csv(data, path)
    return path


def load_approval_history(path: Path = APPROVAL_HISTORY_FILE) -> pd.DataFrame:
    if not path.exists():
        save_approval_history(pd.DataFrame(columns=HISTORY_COLUMNS), path)
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    try:
        return normalize_history_frame(pd.read_csv(path))
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=HISTORY_COLUMNS)


def save_approval_history(df: pd.DataFrame, path: Path = APPROVAL_HISTORY_FILE) -> Path:
    atomic_write_csv(normalize_history_frame(df), path)
    return path


def atomic_write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")

    try:
        df.to_csv(tmp_path, index=False)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    return path


def append_history(
    records: Iterable[Mapping[str, Any]],
    history_path: Path = APPROVAL_HISTORY_FILE,
) -> pd.DataFrame:
    records = list(records)
    history = load_approval_history(history_path)

    if not records:
        return history

    new_rows = normalize_history_frame(pd.DataFrame(records))
    history = pd.concat([history, new_rows], ignore_index=True)
    save_approval_history(history, history_path)
    return history


def history_record(
    row: Mapping[str, Any],
    from_status: str,
    to_status: str,
    changed_by: str,
    reason: str,
    notes: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    return {
        "HistoryId": str(uuid.uuid4()),
        "ProposalId": safe_text(row.get("ProposalId")),
        "Symbol": safe_text(row.get("Symbol")).upper(),
        "Market": safe_text(row.get("Market")).upper(),
        "Action": safe_text(row.get("Action")).upper(),
        "FromStatus": safe_text(from_status).upper(),
        "ToStatus": safe_text(to_status).upper(),
        "ChangedTime": now_iso(now),
        "ChangedBy": safe_text(changed_by, "system"),
        "Reason": safe_text(reason),
        "Notes": safe_text(notes),
        "ApprovalQueueVersion": APPROVAL_QUEUE_VERSION,
    }


def sort_queue(df: pd.DataFrame) -> pd.DataFrame:
    data = normalize_queue_frame(df)

    status_order = {
        "PENDING_APPROVAL": 1,
        "APPROVED": 2,
        "REJECTED": 3,
        "EXPIRED": 4,
        "CANCELLED": 5,
        "EXECUTED": 6,
    }

    data["_StatusOrder"] = data["Status"].map(status_order).fillna(9)
    data = data.sort_values(
        ["_StatusOrder", "ProposalPriority", "CreatedTime", "ProposalId"],
        ascending=[True, True, False, True],
        kind="mergesort",
    )
    return data.drop(columns=["_StatusOrder"]).reset_index(drop=True)


def proposal_status_from_risk(row: Mapping[str, Any]) -> str:
    status = safe_upper(row.get("ProposalStatus"))
    action = safe_upper(row.get("ProposalAction"))

    if action not in ACTIONABLE_ACTIONS:
        return ""

    if status == "REJECTED":
        return "REJECTED"

    if status in {"PENDING_APPROVAL", "APPROVED_FOR_PAPER"} and safe_bool(row.get("RiskApproved")):
        return "PENDING_APPROVAL"

    if status == "EXPIRED":
        return "EXPIRED"

    if status == "CANCELLED":
        return "CANCELLED"

    return ""


def queue_row_from_risk_proposal(
    row: Mapping[str, Any],
    now: datetime | None = None,
    expire_hours: int = DEFAULT_EXPIRE_HOURS,
) -> dict[str, Any] | None:
    action = safe_upper(row.get("ProposalAction"))
    status = proposal_status_from_risk(row)

    if action not in ACTIONABLE_ACTIONS or not status:
        return None

    proposal_id = safe_text(row.get("ProposalId"))
    if not proposal_id:
        return None

    created_dt = parse_time(row.get("ProposalTime"), fallback=now or datetime.now())
    expire_dt = created_dt + timedelta(hours=max(int(expire_hours), 1))
    risk_reason = safe_text(row.get("RejectReason"), "NONE") or "NONE"

    return {
        "ProposalId": proposal_id,
        "Symbol": safe_text(row.get("Symbol")).upper(),
        "Market": safe_text(row.get("Market")).upper(),
        "Action": action,
        "Quantity": safe_float(row.get("ProposedQty")),
        "EntryPrice": safe_float(row.get("EntryPrice")),
        "StopPrice": safe_float(row.get("StopPrice")),
        "TargetPrice": safe_float(row.get("TargetPrice")),
        "RiskScore": safe_float(row.get("RiskScore")),
        "AIConfidence": safe_float(row.get("AIConfidence")),
        "ProposedOrderValue": safe_float(row.get("ProposedOrderValue")),
        "EstimatedCommission": safe_float(row.get("EstimatedCommission")),
        "EstimatedSlippage": safe_float(row.get("EstimatedSlippage")),
        "EstimatedTotalCost": safe_float(row.get("EstimatedTotalCost")),
        "CreatedTime": created_dt.isoformat(timespec="seconds"),
        "ExpireTime": expire_dt.isoformat(timespec="seconds"),
        "Status": status,
        "ApprovedBy": "",
        "ApprovedTime": "",
        "RejectedReason": risk_reason if status == "REJECTED" else "",
        "SourceDecision": safe_upper(row.get("SourceDecision", row.get("AIDecision"))),
        "AIReason": safe_text(row.get("AIReason")),
        "AIBlockers": safe_text(row.get("AIBlockers")),
        "RiskLevel": safe_upper(row.get("RiskLevel")),
        "RiskRewardRatio": safe_float(row.get("RiskRewardRatio")),
        "RiskBudget": safe_float(row.get("RiskBudget")),
        "PositionSizeMethod": safe_text(row.get("PositionSizeMethod")),
        "CashAfterOrder": safe_float(row.get("CashAfterOrder")),
        "RiskManagerStatus": safe_upper(row.get("ProposalStatus")),
        "RiskManagerReason": risk_reason,
        "RiskManagerWarnings": safe_text(row.get("RiskWarnings"), "NONE") or "NONE",
        "ProposalPriority": safe_float(row.get("ProposalPriority"), 5),
        "PriorityScore": safe_float(row.get("PriorityScore")),
        "OpportunityScore": safe_float(row.get("OpportunityScore")),
        "LifecycleState": safe_upper(row.get("LifecycleState")),
        "ApprovalQueueVersion": APPROVAL_QUEUE_VERSION,
        "LastUpdatedTime": now_iso(now),
    }


def expire_pending_proposals(
    queue_df: pd.DataFrame,
    now: datetime | None = None,
    changed_by: str = "system",
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    data = normalize_queue_frame(queue_df)
    current = now or datetime.now()
    records: list[dict[str, Any]] = []

    if data.empty:
        return data, records

    for idx, row in data.iterrows():
        if row["Status"] not in {"PENDING_APPROVAL", "APPROVED"}:
            continue

        expire_time = parse_time(row["ExpireTime"], fallback=current + timedelta(hours=1))
        if expire_time >= current:
            continue

        previous = row["Status"]
        data.at[idx, "Status"] = "EXPIRED"
        data.at[idx, "LastUpdatedTime"] = now_iso(current)
        records.append(
            history_record(
                data.loc[idx].to_dict(),
                previous,
                "EXPIRED",
                changed_by,
                "proposal_expired",
                now=current,
            )
        )

    return data, records


def sync_approval_queue(
    risk_proposals: pd.DataFrame,
    queue_path: Path = APPROVAL_QUEUE_FILE,
    history_path: Path = APPROVAL_HISTORY_FILE,
    now: datetime | None = None,
    expire_hours: int = DEFAULT_EXPIRE_HOURS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    queue = load_approval_queue(queue_path)
    queue, expire_records = expire_pending_proposals(queue, now=now)
    records: list[dict[str, Any]] = list(expire_records)

    if risk_proposals is None or risk_proposals.empty:
        save_approval_queue(queue, queue_path)
        history = append_history(records, history_path)
        return queue, history

    existing_ids = set(queue["ProposalId"].astype(str))
    queue_rows = []

    for _, proposal in risk_proposals.iterrows():
        new_row = queue_row_from_risk_proposal(
            proposal.to_dict(),
            now=now,
            expire_hours=expire_hours,
        )
        if new_row is None:
            continue

        proposal_id = new_row["ProposalId"]

        if proposal_id in existing_ids:
            current_idx = queue.index[queue["ProposalId"] == proposal_id]
            if len(current_idx) == 0:
                continue

            idx = current_idx[0]
            current_status = queue.at[idx, "Status"]

            if current_status in TERMINAL_STATUSES:
                continue

            if new_row["Status"] == "REJECTED" and current_status == "PENDING_APPROVAL":
                queue.at[idx, "Status"] = "REJECTED"
                queue.at[idx, "RejectedReason"] = new_row["RejectedReason"]
                queue.at[idx, "RiskManagerStatus"] = new_row["RiskManagerStatus"]
                queue.at[idx, "RiskManagerReason"] = new_row["RiskManagerReason"]
                queue.at[idx, "RiskManagerWarnings"] = new_row["RiskManagerWarnings"]
                queue.at[idx, "LastUpdatedTime"] = now_iso(now)
                records.append(
                    history_record(
                        queue.loc[idx].to_dict(),
                        current_status,
                        "REJECTED",
                        "risk_manager",
                        new_row["RiskManagerReason"],
                        now=now,
                    )
                )

            continue

        existing_ids.add(proposal_id)
        queue_rows.append(new_row)
        records.append(
            history_record(
                new_row,
                "",
                new_row["Status"],
                "risk_manager",
                "imported_from_risk_manager",
                notes=new_row["RiskManagerReason"],
                now=now,
            )
        )

    if queue_rows:
        queue = pd.concat([queue, pd.DataFrame(queue_rows)], ignore_index=True)

    queue = normalize_queue_frame(queue).drop_duplicates("ProposalId", keep="first")
    save_approval_queue(queue, queue_path)
    history = append_history(records, history_path)

    return load_approval_queue(queue_path), history


def find_queue_index(queue: pd.DataFrame, proposal_id: str) -> int:
    proposal_id = safe_text(proposal_id)
    matches = queue.index[queue["ProposalId"] == proposal_id].tolist()

    if not matches:
        raise ApprovalQueueError(f"Proposal not found: {proposal_id}")

    return matches[0]


def transition_proposal(
    proposal_id: str,
    to_status: str,
    changed_by: str = "manual",
    reason: str = "",
    queue_path: Path = APPROVAL_QUEUE_FILE,
    history_path: Path = APPROVAL_HISTORY_FILE,
    now: datetime | None = None,
) -> dict[str, Any]:
    to_status = safe_upper(to_status)
    if to_status not in QUEUE_STATUSES:
        raise ApprovalQueueError(f"Invalid approval status: {to_status}")

    queue = load_approval_queue(queue_path)
    queue, expire_records = expire_pending_proposals(queue, now=now, changed_by="system")
    idx = find_queue_index(queue, proposal_id)
    row = queue.loc[idx].to_dict()
    current_status = row["Status"]
    current_time = now or datetime.now()

    if current_status == "EXPIRED":
        save_approval_queue(queue, queue_path)
        append_history(expire_records, history_path)
        raise ApprovalQueueError("Expired proposal cannot be changed.")

    if current_status in {"CANCELLED", "EXECUTED"}:
        raise ApprovalQueueError(f"{current_status} proposal cannot be changed.")

    if current_status == "REJECTED":
        raise ApprovalQueueError("Rejected proposal cannot be sent forward.")

    if current_status == "APPROVED" and to_status == "APPROVED":
        raise ApprovalQueueError("Proposal is already approved.")

    if to_status == "APPROVED" and current_status != "PENDING_APPROVAL":
        raise ApprovalQueueError(f"Only pending proposals can be approved. Current status: {current_status}")

    if to_status == "REJECTED" and current_status != "PENDING_APPROVAL":
        raise ApprovalQueueError(f"Only pending proposals can be rejected. Current status: {current_status}")

    if to_status == "CANCELLED" and current_status not in {"PENDING_APPROVAL", "APPROVED"}:
        raise ApprovalQueueError(f"Only pending or approved proposals can be cancelled. Current status: {current_status}")

    if to_status == "EXECUTED" and current_status != "APPROVED":
        raise ApprovalQueueError(f"Only approved proposals can be marked executed. Current status: {current_status}")

    queue.at[idx, "Status"] = to_status
    queue.at[idx, "LastUpdatedTime"] = now_iso(current_time)

    if to_status == "APPROVED":
        queue.at[idx, "ApprovedBy"] = safe_text(changed_by, "manual")
        queue.at[idx, "ApprovedTime"] = now_iso(current_time)

    if to_status == "EXECUTED":
        queue.at[idx, "ExecutedTime"] = now_iso(current_time)

    if to_status == "REJECTED":
        queue.at[idx, "RejectedReason"] = safe_text(reason, "Manual rejection")

    record = history_record(
        queue.loc[idx].to_dict(),
        current_status,
        to_status,
        changed_by,
        reason or to_status.lower(),
        now=current_time,
    )
    save_approval_queue(queue, queue_path)
    append_history([*expire_records, record], history_path)

    return queue.loc[idx].to_dict()


def approve_proposal(
    proposal_id: str,
    approved_by: str = "manual",
    queue_path: Path = APPROVAL_QUEUE_FILE,
    history_path: Path = APPROVAL_HISTORY_FILE,
    now: datetime | None = None,
) -> dict[str, Any]:
    return transition_proposal(
        proposal_id,
        "APPROVED",
        changed_by=approved_by,
        reason="manual_approval",
        queue_path=queue_path,
        history_path=history_path,
        now=now,
    )


def reject_proposal(
    proposal_id: str,
    rejected_by: str = "manual",
    reason: str = "Manual rejection",
    queue_path: Path = APPROVAL_QUEUE_FILE,
    history_path: Path = APPROVAL_HISTORY_FILE,
    now: datetime | None = None,
) -> dict[str, Any]:
    return transition_proposal(
        proposal_id,
        "REJECTED",
        changed_by=rejected_by,
        reason=reason,
        queue_path=queue_path,
        history_path=history_path,
        now=now,
    )


def cancel_proposal(
    proposal_id: str,
    cancelled_by: str = "manual",
    reason: str = "Manual cancellation",
    queue_path: Path = APPROVAL_QUEUE_FILE,
    history_path: Path = APPROVAL_HISTORY_FILE,
    now: datetime | None = None,
) -> dict[str, Any]:
    return transition_proposal(
        proposal_id,
        "CANCELLED",
        changed_by=cancelled_by,
        reason=reason,
        queue_path=queue_path,
        history_path=history_path,
        now=now,
    )


def ready_for_paper_broker(queue_df: pd.DataFrame | None = None) -> pd.DataFrame:
    queue = normalize_queue_frame(queue_df if queue_df is not None else load_approval_queue())
    ready = queue[queue["Status"] == "APPROVED"].copy()
    return sort_queue(ready)


def mark_proposal_executed(
    proposal_id: str,
    paper_order_id: str,
    fill_id: str,
    changed_by: str = "paper_broker",
    queue_path: Path = APPROVAL_QUEUE_FILE,
    history_path: Path = APPROVAL_HISTORY_FILE,
    now: datetime | None = None,
) -> dict[str, Any]:
    queue = load_approval_queue(queue_path)
    queue, expire_records = expire_pending_proposals(queue, now=now, changed_by="system")
    idx = find_queue_index(queue, proposal_id)
    row = queue.loc[idx].to_dict()
    current_status = row["Status"]
    current_time = now or datetime.now()

    if current_status != "APPROVED":
        save_approval_queue(queue, queue_path)
        append_history(expire_records, history_path)
        raise ApprovalQueueError(f"Only approved proposals can be marked executed. Current status: {current_status}")

    queue.at[idx, "Status"] = "EXECUTED"
    queue.at[idx, "PaperOrderId"] = safe_text(paper_order_id)
    queue.at[idx, "FillId"] = safe_text(fill_id)
    queue.at[idx, "ExecutedTime"] = now_iso(current_time)
    queue.at[idx, "LastUpdatedTime"] = now_iso(current_time)

    record = history_record(
        queue.loc[idx].to_dict(),
        current_status,
        "EXECUTED",
        changed_by,
        "paper_execution_completed",
        notes=f"PaperOrderId={paper_order_id}; FillId={fill_id}",
        now=current_time,
    )
    save_approval_queue(queue, queue_path)
    append_history([*expire_records, record], history_path)

    return queue.loc[idx].to_dict()


def build_approval_summary(queue_df: pd.DataFrame | None = None) -> pd.DataFrame:
    queue = normalize_queue_frame(queue_df if queue_df is not None else load_approval_queue())

    counts = queue["Status"].value_counts().to_dict() if not queue.empty else {}
    ready = ready_for_paper_broker(queue)

    row = {
        "RunTime": now_iso(),
        "TotalProposals": int(len(queue)),
        "Pending": int(counts.get("PENDING_APPROVAL", 0)),
        "Approved": int(counts.get("APPROVED", 0)),
        "Rejected": int(counts.get("REJECTED", 0)),
        "Expired": int(counts.get("EXPIRED", 0)),
        "Cancelled": int(counts.get("CANCELLED", 0)),
        "Executed": int(counts.get("EXECUTED", 0)),
        "ReadyForPaperBroker": int(len(ready)),
        "PendingOrderValue": round(safe_float(queue.loc[queue["Status"] == "PENDING_APPROVAL", "ProposedOrderValue"].sum()), 6) if not queue.empty else 0,
        "ApprovedOrderValue": round(safe_float(queue.loc[queue["Status"] == "APPROVED", "ProposedOrderValue"].sum()), 6) if not queue.empty else 0,
        "ApprovalQueueVersion": APPROVAL_QUEUE_VERSION,
    }

    return pd.DataFrame([row])
