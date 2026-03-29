"""
AST-based hyperparameter extraction from train.py.

Parses the file and extracts all UPPER_CASE top-level assignments
from the hyperparameters section. Enables automatic config diffing
between experiments.
"""

import ast
import os

TRAIN_PY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "train.py")

# Known hyperparameter names (for robust extraction even if AST parsing is partial)
KNOWN_PARAMS = {
    "ASPECT_RATIO", "HEAD_DIM", "WINDOW_PATTERN",
    "TOTAL_BATCH_SIZE", "EMBEDDING_LR", "UNEMBEDDING_LR",
    "MATRIX_LR", "SCALAR_LR", "WEIGHT_DECAY", "ADAM_BETAS",
    "WARMUP_RATIO", "WARMDOWN_RATIO", "FINAL_LR_FRAC",
    "DEPTH", "DEVICE_BATCH_SIZE",
}


def extract_config(path: str | None = None) -> dict:
    """Parse train.py and extract UPPER_CASE hyperparameter assignments.

    Returns dict like {"ASPECT_RATIO": 64, "MATRIX_LR": 0.04, ...}.
    Returns partial results on parse errors rather than crashing.
    """
    path = path or TRAIN_PY_PATH
    with open(path, "r") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    config = {}
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        # Get the target name
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign) and node.target:
            target = node.target
        else:
            continue

        if not isinstance(target, ast.Name):
            continue

        name = target.id
        # Only extract UPPER_CASE names that look like hyperparameters
        if not name.isupper() or name.startswith("_"):
            continue
        # Skip constants from prepare.py imports and non-hyperparameter constants
        if name in ("H100_BF16_PEAK_FLOPS",):
            continue

        # Try to evaluate the value
        try:
            value = ast.literal_eval(node.value)
            config[name] = value
        except (ValueError, TypeError):
            # Complex expressions (e.g., 2**19) — try compile+eval
            try:
                value = eval(compile(ast.Expression(node.value), "<ast>", "eval"))
                config[name] = value
            except Exception:
                pass

    return config


def diff_configs(old: dict, new: dict) -> dict:
    """Return {key: {"old": v1, "new": v2}} for all changed keys.

    Also includes keys present in only one config.
    """
    all_keys = set(old) | set(new)
    diff = {}
    for key in sorted(all_keys):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            diff[key] = {"old": old_val, "new": new_val}
    return diff
