"""
Experiment proposal dataclass — enforces scientific method before each run.

Every experiment must have a hypothesis, evidence, and testable prediction
before it can proceed.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class ExperimentProposal:
    experiment_id: str
    parent_experiment_id: str | None
    parent_commit: str
    hypothesis: str
    evidence: list[str]
    prediction: str
    prediction_direction: str  # "decrease" | "increase" | "neutral"
    prediction_magnitude: float | None
    config_changes: dict  # {param: {"old": val, "new": val}}
    description: str  # short summary for results.tsv

    def to_dict(self) -> dict:
        return asdict(self)


def validate_proposal(proposal: ExperimentProposal) -> list[str]:
    """Return list of validation errors. Empty means valid."""
    errors = []

    if not proposal.hypothesis or len(proposal.hypothesis.strip()) < 20:
        errors.append("Hypothesis must be substantive (>20 chars)")

    if not proposal.prediction or len(proposal.prediction.strip()) < 5:
        errors.append("Prediction is required")

    if proposal.prediction_direction not in ("decrease", "increase", "neutral"):
        errors.append(f"prediction_direction must be decrease/increase/neutral, got: {proposal.prediction_direction}")

    if not proposal.config_changes and not proposal.description:
        errors.append("Must specify config_changes or describe code changes in description")

    if len(proposal.config_changes) > 3:
        errors.append(f"Single-variable principle: change at most 3 related params at once (got {len(proposal.config_changes)})")

    if not proposal.parent_commit:
        errors.append("parent_commit is required (current git HEAD)")

    return errors


def proposal_to_commit_message(proposal: ExperimentProposal) -> str:
    """Generate a commitlint-formatted git commit message from a proposal."""
    lines = [f"feat(exp): {proposal.description}"]
    lines.append("")
    lines.append(f"Hypothesis: {proposal.hypothesis}")
    lines.append(f"Prediction: {proposal.prediction}")
    if proposal.config_changes:
        changes = ", ".join(
            f"{k}: {v['old']} -> {v['new']}" for k, v in proposal.config_changes.items()
        )
        lines.append(f"Changes: {changes}")
    return "\n".join(lines)
