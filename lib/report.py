"""
Human-readable reporting from the audit log.

Generates lineage trees, experiment summaries, and session reports.
"""

from . import audit, history


def lineage_tree() -> str:
    """ASCII tree of experiment lineage showing keep/discard at each node."""
    events = audit.get_finalized_experiments()
    if not events:
        return "No experiments recorded yet."

    # Build parent->children map
    children: dict[str | None, list[dict]] = {}
    for event in events:
        parent = event.get("parent_experiment_id")
        children.setdefault(parent, []).append(event)

    lines = []

    def render(experiment_id: str | None, prefix: str, is_last: bool, depth: int):
        if experiment_id is None:
            # Render root nodes
            roots = children.get(None, [])
            for i, event in enumerate(roots):
                render(event["experiment_id"], "", i == len(roots) - 1, 0)
            return

        event = audit.get_experiment(experiment_id)
        if not event:
            return

        decision = event.get("finality", {}).get("decision", "?")
        val_bpb = event.get("result", {}).get("val_bpb")
        bpb_str = f"{val_bpb:.6f}" if val_bpb is not None else "N/A"
        desc = event.get("what", {}).get("description", "")[:50]
        marker = {"keep": "+", "discard": "-", "crash": "!"}.get(decision, "?")

        connector = "`-- " if is_last else "|-- "
        line = f"{prefix}{connector}[{marker}] {bpb_str} {desc}"
        lines.append(line)

        child_events = children.get(experiment_id, [])
        child_prefix = prefix + ("    " if is_last else "|   ")
        for i, child in enumerate(child_events):
            render(child["experiment_id"], child_prefix, i == len(child_events) - 1, depth + 1)

    render(None, "", True, 0)
    return "\n".join(lines) if lines else "No experiments recorded yet."


def experiment_summary(experiment_id: str) -> str:
    """Full report for one experiment."""
    event = audit.get_experiment(experiment_id)
    if not event:
        return f"Experiment {experiment_id} not found."

    what = event.get("what", {})
    why = event.get("why", {})
    result = event.get("result", {})
    finality = event.get("finality", {})

    lines = [
        f"Experiment: {experiment_id[:8]}",
        f"Time: {event.get('timestamp', 'N/A')}",
        f"Parent: {(event.get('parent_experiment_id') or 'none')[:8]}",
        "",
        "WHAT:",
        f"  {what.get('description', 'N/A')}",
    ]

    config_diff = what.get("config_diff", {})
    if config_diff:
        lines.append("  Config changes:")
        for k, v in config_diff.items():
            lines.append(f"    {k}: {v.get('old')} -> {v.get('new')}")

    lines.extend([
        "",
        "WHY:",
        f"  Hypothesis: {why.get('hypothesis', 'N/A')}",
        f"  Prediction: {why.get('prediction', 'N/A')} ({why.get('prediction_direction', '?')})",
    ])
    evidence = why.get("evidence", [])
    if evidence:
        lines.append("  Evidence:")
        for e in evidence:
            lines.append(f"    - {e}")

    val_bpb = result.get("val_bpb")
    lines.extend([
        "",
        "RESULT:",
        f"  val_bpb: {val_bpb:.6f}" if val_bpb is not None else "  val_bpb: N/A",
        f"  Crashed: {result.get('crashed', False)}",
        f"  Prediction correct: {result.get('prediction_correct', 'N/A')}",
    ])

    lines.extend([
        "",
        "FINALITY:",
        f"  Decision: {finality.get('decision', 'N/A')}",
        f"  Reasoning: {finality.get('reasoning', 'N/A')}",
    ])

    return "\n".join(lines)


def session_report() -> str:
    """Summary of all experiments in the audit log."""
    events = audit.get_finalized_experiments()
    if not events:
        return "No experiments recorded yet."

    total = len(events)
    kept = sum(1 for e in events if e.get("finality", {}).get("decision") == "keep")
    discarded = sum(1 for e in events if e.get("finality", {}).get("decision") == "discard")
    crashed = sum(1 for e in events if e.get("finality", {}).get("decision") == "crash")

    best = history.get_best_result()
    pred = history.get_prediction_accuracy()

    lines = [
        f"Session Report ({total} experiments)",
        f"  Kept: {kept} | Discarded: {discarded} | Crashed: {crashed}",
    ]

    if best:
        lines.append(f"  Best val_bpb: {best['result']['val_bpb']:.6f}")

    if pred["total_predictions"] > 0:
        lines.append(
            f"  Prediction accuracy: {pred['correct_predictions']}/{pred['total_predictions']}"
            f" ({pred['accuracy']:.0%})"
        )

    lines.append("")
    lines.append("Recent experiments:")
    for event in history.recent_experiments(5):
        decision = event.get("finality", {}).get("decision", "?")
        val_bpb = event.get("result", {}).get("val_bpb")
        bpb_str = f"{val_bpb:.6f}" if val_bpb is not None else "N/A"
        desc = event.get("what", {}).get("description", "")[:60]
        marker = {"keep": "+", "discard": "-", "crash": "!"}.get(decision, "?")
        lines.append(f"  [{marker}] {bpb_str} {desc}")

    return "\n".join(lines)
