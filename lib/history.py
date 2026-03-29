"""
Query functions over the audit log.

Provides the Historian agent role with tools to search experiment history,
detect duplicates, trace lineage, and summarize parameter effects.
"""

from . import audit


def get_lineage(experiment_id: str) -> list[dict]:
    """Walk parent_experiment_id chain to build ancestry (oldest first)."""
    events = audit.read_events()
    by_id = {e["experiment_id"]: e for e in events}

    chain = []
    current_id = experiment_id
    seen = set()
    while current_id and current_id not in seen:
        seen.add(current_id)
        event = by_id.get(current_id)
        if not event:
            break
        chain.append(event)
        current_id = event.get("parent_experiment_id")

    chain.reverse()
    return chain


def find_similar(config_changes: dict) -> list[dict]:
    """Find experiments that changed any of the same parameters.

    Returns list of finalized events sorted by relevance (most overlapping params first).
    """
    if not config_changes:
        return []

    target_params = set(config_changes.keys())
    events = audit.get_finalized_experiments()
    scored = []

    for event in events:
        event_params = set(event.get("what", {}).get("config_diff", {}).keys())
        overlap = target_params & event_params
        if overlap:
            scored.append((len(overlap), event))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [event for _, event in scored]


def get_best_result() -> dict | None:
    """Return the finalized experiment with the lowest val_bpb (decision=keep)."""
    kept = [
        e for e in audit.get_finalized_experiments()
        if e.get("finality", {}).get("decision") == "keep"
        and e.get("result", {}).get("val_bpb") is not None
    ]
    if not kept:
        return None
    return min(kept, key=lambda e: e["result"]["val_bpb"])


def get_prediction_accuracy() -> dict:
    """Return stats on how often predictions were directionally correct."""
    finalized = audit.get_finalized_experiments()
    total = 0
    correct = 0
    for event in finalized:
        pc = event.get("result", {}).get("prediction_correct")
        if pc is not None:
            total += 1
            if pc:
                correct += 1

    return {
        "total_predictions": total,
        "correct_predictions": correct,
        "accuracy": correct / total if total > 0 else None,
    }


def detect_duplicate(config_changes: dict) -> dict | None:
    """Check if this exact set of config changes was already tried.

    Returns the prior experiment if found, None otherwise.
    """
    if not config_changes:
        return None

    target_keys = sorted(config_changes.keys())

    for event in audit.get_finalized_experiments():
        event_diff = event.get("what", {}).get("config_diff", {})
        event_keys = sorted(event_diff.keys())
        if event_keys != target_keys:
            continue
        # Check if all new values match
        match = True
        for key in target_keys:
            if config_changes[key].get("new") != event_diff.get(key, {}).get("new"):
                match = False
                break
        if match:
            return event

    return None


def summarize_param(param_name: str) -> str:
    """Summarize all experiments that changed a given parameter and their outcomes."""
    events = audit.get_finalized_experiments()
    relevant = []
    for event in events:
        diff = event.get("what", {}).get("config_diff", {})
        if param_name in diff:
            relevant.append(event)

    if not relevant:
        return f"No experiments have modified {param_name}."

    lines = [f"Experiments modifying {param_name} ({len(relevant)} total):"]
    for event in relevant:
        diff = event.get("what", {}).get("config_diff", {})
        change = diff[param_name]
        result = event.get("result", {})
        decision = event.get("finality", {}).get("decision", "?")
        val_bpb = result.get("val_bpb")
        bpb_str = f"{val_bpb:.6f}" if val_bpb is not None else "N/A"
        desc = event.get("what", {}).get("description", "")
        lines.append(
            f"  {change.get('old')} -> {change.get('new')} | "
            f"val_bpb={bpb_str} | {decision} | {desc}"
        )

    return "\n".join(lines)


def recent_experiments(n: int = 10) -> list[dict]:
    """Return the last N finalized experiments (most recent first)."""
    finalized = audit.get_finalized_experiments()
    return list(reversed(finalized[-n:]))
