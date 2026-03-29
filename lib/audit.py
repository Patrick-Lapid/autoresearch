"""
Append-only audit log for experiment tracking.

Stores structured JSONL events in audit.jsonl at the repo root.
Each experiment produces one event with WHAT/WHY/RESULT/FINALITY sections.
"""

import json
import os
import uuid
from datetime import datetime, timezone

AUDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit.jsonl")

REQUIRED_FIELDS = {"id", "timestamp", "experiment_id"}
VALID_DECISIONS = {"keep", "discard", "crash"}
VALID_DIRECTIONS = {"decrease", "increase", "neutral"}


def new_event_id() -> str:
    return str(uuid.uuid4())


def new_experiment_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_event(
    experiment_id: str,
    parent_experiment_id: str | None = None,
    parent_commit: str | None = None,
    what: dict | None = None,
    why: dict | None = None,
    result: dict | None = None,
    finality: dict | None = None,
) -> dict:
    """Create a new audit event with required fields populated."""
    event = {
        "id": new_event_id(),
        "timestamp": now_iso(),
        "experiment_id": experiment_id,
        "parent_experiment_id": parent_experiment_id,
        "parent_commit": parent_commit,
        "what": what or {},
        "why": why or {},
        "result": result or {},
        "finality": finality or {},
    }
    return event


def validate_event(event: dict) -> list[str]:
    """Return list of validation errors. Empty means valid."""
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in event or not event[field]:
            errors.append(f"Missing required field: {field}")

    if event.get("why", {}).get("prediction_direction"):
        if event["why"]["prediction_direction"] not in VALID_DIRECTIONS:
            errors.append(f"Invalid prediction_direction: {event['why']['prediction_direction']}")

    if event.get("finality", {}).get("decision"):
        if event["finality"]["decision"] not in VALID_DECISIONS:
            errors.append(f"Invalid decision: {event['finality']['decision']}")

    return errors


def append_event(event: dict) -> None:
    """Append one event to the audit log. Validates before writing."""
    errors = validate_event(event)
    if errors:
        raise ValueError(f"Invalid audit event: {'; '.join(errors)}")

    line = json.dumps(event, separators=(",", ":")) + "\n"
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(line)


def read_events() -> list[dict]:
    """Read all events from the audit log."""
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
    events = []
    with open(AUDIT_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def get_experiment(experiment_id: str) -> dict | None:
    """Get the event for a specific experiment."""
    for event in reversed(read_events()):
        if event["experiment_id"] == experiment_id:
            return event
    return None


def get_latest_kept() -> dict | None:
    """Get the most recent experiment with decision=keep."""
    for event in reversed(read_events()):
        if event.get("finality", {}).get("decision") == "keep":
            return event
    return None


def get_finalized_experiments() -> list[dict]:
    """Get all experiments that have a finality decision."""
    return [e for e in read_events() if e.get("finality", {}).get("decision")]
