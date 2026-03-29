# autoresearch

This is an experiment to have the LLM do its own research, using the scientific method.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `mar5`). The branch `autoresearch/<tag>` must not already exist — this is a fresh run.
2. **Create the branch**: `git checkout -b autoresearch/<tag>` from current master.
3. **Read the in-scope files**: The repo is small. Read these files for full context:
   - `README.md` — repository context.
   - `prepare.py` — fixed constants, data prep, tokenizer, dataloader, evaluation. Do not modify.
   - `train.py` — the file you modify. Model architecture, optimizer, training loop.
   - `lib/` — harness library. Read all files for context on the scientific method tools available.
4. **Verify data exists**: Check that `~/.cache/autoresearch/` contains data shards and a tokenizer. If not, tell the human to run `uv run prepare.py`.
5. **Initialize tracking files**:
   - Create `results.tsv` with just the header row.
   - Create empty `audit.jsonl` if it doesn't exist: `touch audit.jsonl`
6. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment runs on a single GPU. The training script runs for a **fixed time budget of 5 minutes** (wall clock training time, excluding startup/compilation). You launch it simply as: `uv run train.py`.

**What you CAN do:**
- Modify `train.py` — this is the only file you edit. Everything is fair game: model architecture, optimizer, hyperparameters, training loop, batch size, model size, etc.

**What you CANNOT do:**
- Modify `prepare.py`. It is read-only. It contains the fixed evaluation, data loading, tokenizer, and training constants (time budget, sequence length, etc).
- Modify files in `lib/`. The harness library is fixed infrastructure.
- Install new packages or add dependencies. You can only use what's already in `pyproject.toml`.
- Modify the evaluation harness. The `evaluate_bpb` function in `prepare.py` is the ground truth metric.

**The goal is simple: get the lowest val_bpb.** Since the time budget is fixed, you don't need to worry about training time — it's always 5 minutes. Everything is fair game: change the architecture, the optimizer, the hyperparameters, the batch size, the model size. The only constraint is that the code runs without crashing and finishes within the time budget.

**VRAM** is a soft constraint. Some increase is acceptable for meaningful val_bpb gains, but it should not blow up dramatically.

**Simplicity criterion**: All else being equal, simpler is better. A small improvement that adds ugly complexity is not worth it. Conversely, removing something and getting equal or better results is a great outcome — that's a simplification win. When evaluating whether to keep a change, weigh the complexity cost against the improvement magnitude. A 0.001 val_bpb improvement that adds 20 lines of hacky code? Probably not worth it. A 0.001 val_bpb improvement from deleting code? Definitely keep. An improvement of ~0 but much simpler code? Keep.

**The first run**: Your very first run should always be to establish the baseline, so you will run the training script as is. Log it as the baseline experiment in the audit log with hypothesis "Establish baseline metric for comparison."

## Output format

Once the script finishes it prints a summary like this:

```
---
val_bpb:          0.997900
training_seconds: 300.1
total_seconds:    325.9
peak_vram_mb:     45060.2
mfu_percent:      39.80
total_tokens_M:   499.6
num_steps:        953
num_params_M:     50.3
depth:            8
```

Note that the script is configured to always stop after 5 minutes, so depending on the computing platform of this computer the numbers might look different. You can extract the key metric from the log file:

```
grep "^val_bpb:" run.log
```

## Logging results

When an experiment is done, log it to BOTH `results.tsv` AND `audit.jsonl`.

### results.tsv

Tab-separated, NOT comma-separated — commas break in descriptions. Header row and 5 columns:

```
commit	val_bpb	memory_gb	status	description
```

1. git commit hash (short, 7 chars)
2. val_bpb achieved (e.g. 1.234567) — use 0.000000 for crashes
3. peak memory in GB, round to .1f (e.g. 12.3 — divide peak_vram_mb by 1024) — use 0.0 for crashes
4. status: `keep`, `discard`, or `crash`
5. short text description of what this experiment tried

### audit.jsonl

Use the harness library to log structured audit events. See the experiment loop below for details on when and how to log.

## The Experiment Loop — Scientific Method

The experiment runs on a dedicated branch (e.g. `autoresearch/mar5`).

Every experiment follows the scientific method through five agent roles. You must complete each phase before moving to the next. This is not optional — the structure ensures every experiment is documented, reasoned, and comparable.

---

### Phase 1: ANALYST — Analyze the last result

*Skip this phase on the very first run (baseline).*

Review the outcome of the last experiment:

1. Read the last experiment's result from the audit log:
   ```
   python3 -c "from lib.history import recent_experiments; import json; exps = recent_experiments(1); print(json.dumps(exps[0], indent=2) if exps else 'No experiments yet')"
   ```

2. Compare the actual result to the prediction:
   - Was the direction correct? (Did val_bpb move the way you predicted?)
   - Was the magnitude roughly right?
   - What does this tell you about the model's behavior?

3. Check your overall prediction accuracy:
   ```
   python3 -c "from lib.history import get_prediction_accuracy; print(get_prediction_accuracy())"
   ```

4. Reflect briefly: What did you learn from the last experiment that informs the next one?

---

### Phase 2: HISTORIAN — Check experiment history

Query the history to make an informed decision about what to try next:

1. Get the current best result:
   ```
   python3 -c "from lib.history import get_best_result; import json; b = get_best_result(); print(json.dumps({'val_bpb': b['result']['val_bpb'], 'desc': b['what']['description']}, indent=2) if b else 'No results yet')"
   ```

2. Review recent experiments:
   ```
   python3 -c "from lib.report import session_report; print(session_report())"
   ```

3. If you have a candidate parameter to change, check what's been tried:
   ```
   python3 -c "from lib.history import summarize_param; print(summarize_param('MATRIX_LR'))"
   ```

4. Check for duplicates before committing to an idea:
   ```
   python3 -c "from lib.history import detect_duplicate; import json; print(json.dumps(detect_duplicate({'MATRIX_LR': {'old': 0.04, 'new': 0.06}}), indent=2))"
   ```

Use this information to identify promising unexplored directions. Avoid repeating what's already been tried.

---

### Phase 3: THEORIST — Form a hypothesis

Based on the Analyst and Historian phases, propose your next experiment:

1. **State a specific, falsifiable hypothesis.** Not "try a different learning rate" but "Increasing MATRIX_LR from 0.04 to 0.06 will improve convergence because the current LR may be too conservative for the model size, leaving optimization progress on the table in the fixed 5-minute budget."

2. **Cite your evidence.** Prior experiments, reasoning about the architecture, or domain knowledge.

3. **Make a testable prediction.** State the expected direction (decrease/increase) and approximate magnitude.

4. **Validate your proposal:**
   ```
   python3 -c "
   from lib.experiment import ExperimentProposal, validate_proposal
   from lib.audit import new_experiment_id
   import subprocess
   parent_commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
   p = ExperimentProposal(
       experiment_id=new_experiment_id(),
       parent_experiment_id=None,  # set to last experiment_id if not baseline
       parent_commit=parent_commit,
       hypothesis='YOUR HYPOTHESIS HERE',
       evidence=['YOUR EVIDENCE HERE'],
       prediction='val_bpb will decrease by ~X.XXX',
       prediction_direction='decrease',
       prediction_magnitude=0.002,
       config_changes={'PARAM': {'old': OLD_VAL, 'new': NEW_VAL}},
       description='short description for TSV',
   )
   errors = validate_proposal(p)
   if errors:
       print('INVALID:', errors)
   else:
       print('VALID')
       print(f'experiment_id={p.experiment_id}')
   "
   ```

5. If validation fails, refine and retry. Do not proceed to Phase 4 with an invalid proposal.

**Single-variable principle**: Change at most 3 related parameters at once. If you want to test two unrelated ideas, run them as separate experiments.

---

### Phase 4: EXPERIMENTALIST — Execute the experiment

1. **Extract the current config** (so you can compute the diff later):
   ```
   python3 -c "from lib.config_extract import extract_config; import json; print(json.dumps(extract_config(), indent=2))"
   ```

2. **Apply your changes** to `train.py`. Make exactly the changes described in your proposal.

3. **git commit** with a commitlint-formatted message:
   ```
   git commit -am "feat(exp): <description>

   Hypothesis: <your hypothesis>
   Prediction: <your prediction>"
   ```

4. **Log the proposal** to the audit log:
   ```
   python3 -c "
   from lib.audit import create_event, append_event
   event = create_event(
       experiment_id='YOUR_EXPERIMENT_ID',
       parent_experiment_id=None,  # or previous experiment_id
       parent_commit='PARENT_COMMIT_HASH',
       what={
           'description': 'short description',
           'config_diff': {'PARAM': {'old': OLD, 'new': NEW}},
           'code_diff_summary': 'one-line summary of code changes'
       },
       why={
           'hypothesis': 'your hypothesis',
           'evidence': ['your evidence'],
           'prediction': 'your prediction',
           'prediction_direction': 'decrease',
           'prediction_magnitude': 0.002
       },
   )
   append_event(event)
   print('Proposal logged')
   "
   ```

5. **Run the experiment**:
   ```
   uv run train.py > run.log 2>&1
   ```
   Redirect everything — do NOT use tee or let output flood your context.

6. **Read the results**:
   ```
   grep "^val_bpb:\|^peak_vram_mb:\|^training_seconds:\|^num_steps:" run.log
   ```
   If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to read the stack trace.

---

### Phase 5: JUDGE — Evaluate and decide

1. **Compare result to prediction**: Was the direction correct? Was the magnitude roughly right?

2. **Compare val_bpb to current best**: Did we improve?

3. **Apply simplicity criterion**: If the improvement is tiny but the code change is complex, consider discarding.

4. **Make your decision**: `keep`, `discard`, or `crash`.

5. **Log the full audit event** (overwrite the proposal event with complete data):
   ```
   python3 -c "
   from lib.audit import create_event, append_event
   event = create_event(
       experiment_id='YOUR_EXPERIMENT_ID',
       parent_experiment_id=None,
       parent_commit='PARENT_COMMIT_HASH',
       what={
           'description': 'short description',
           'config_diff': {'PARAM': {'old': OLD, 'new': NEW}},
           'code_diff_summary': 'one-line summary'
       },
       why={
           'hypothesis': 'your hypothesis',
           'evidence': ['your evidence'],
           'prediction': 'your prediction',
           'prediction_direction': 'decrease',
           'prediction_magnitude': 0.002
       },
       result={
           'val_bpb': ACTUAL_VAL_BPB,
           'peak_vram_mb': ACTUAL_VRAM,
           'training_seconds': ACTUAL_SECONDS,
           'num_steps': ACTUAL_STEPS,
           'crashed': False,
           'prediction_correct': True  # was direction correct?
       },
       finality={
           'decision': 'keep',  # or 'discard' or 'crash'
           'commit': 'COMMIT_HASH',
           'reasoning': 'why this decision was made'
       },
   )
   append_event(event)
   print('Result logged')
   "
   ```

6. **Execute the decision**:
   - If **keep**: the git commit stays. Record in results.tsv with status `keep`.
   - If **discard**: `git reset --hard HEAD~1`. Record in results.tsv with status `discard`.
   - If **crash**: `git reset --hard HEAD~1`. Record in results.tsv with status `crash`.

7. **Record in results.tsv** (NOTE: do not commit results.tsv, leave it untracked by git).

---

## Loop Control

**Timeout**: Each experiment should take ~5 minutes total (+ a few seconds for startup and eval overhead). If a run exceeds 10 minutes, kill it and treat it as a failure (discard and revert).

**Crashes**: If a run crashes (OOM, or a bug, or etc.), use your judgment: If it's something dumb and easy to fix (e.g. a typo, a missing import), fix it and re-run. If the idea itself is fundamentally broken, just skip it, log "crash" as the status, and move on.

**NEVER STOP**: Once the experiment loop has begun (after the initial setup), do NOT pause to ask the human if you should continue. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be asleep, or gone from a computer and expects you to continue working *indefinitely* until you are manually stopped. You are autonomous. If you run out of ideas, think harder — read papers referenced in the code, re-read the in-scope files for new angles, try combining previous near-misses, try more radical architectural changes. The loop runs until the human interrupts you, period.

As an example use case, a user might leave you running while they sleep. If each experiment takes you ~5 minutes then you can run approx 12/hour, for a total of about 100 over the duration of the average human sleep. The user then wakes up to experimental results, all completed by you while they slept!
