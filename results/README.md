# results/

The real output of the 19 runs referenced in [`../FINDINGS.md`](../FINDINGS.md)
(the 18-run batch, plus one earlier single sanity-check run done before the
batch was approved — see the note below). Published as-is so the claims in
`FINDINGS.md` can be checked against the actual data, not just taken on faith.

## Files

- **`runs.jsonl`** — one JSON line per run: task, setup, trial, which
  `batch` it belongs to (`main` = the 18-run batch reported in
  `FINDINGS.md`, `sanity_check` = the one extra row below),
  pass/fail/`infra_error` status and reason, deprecated-API-usage flags,
  whether the skill was used, wall time, cost, turn count, model, and a
  path to that run's artifacts. Appended immediately after each run
  finishes, so a crash mid-batch never loses already-finished runs.
- **`summary.md`** — the pass/total table `soundcheck.py` writes itself at
  the end of a batch. Scoped only to the runs from that specific batch
  invocation (so it does not include the extra sanity-check run below).
- **`batch_log.txt`** — raw stdout/stderr of the batch process. Mostly
  empty/buffered; not very informative on its own.
- **`artifacts/<run_id>/`** — one folder per run:
  - `solution.py` — the exact code the agent wrote and ran for that task.
  - `transcript.txt` — the full `claude -p --output-format stream-json`
    transcript: every tool call, tool result, and model message for that
    run.
  - `stderr.txt` — the `claude` process's own stderr (usually empty).

## A data-provenance note

`runs.jsonl` has **19** entries, not 18 — see the `batch` field on each
row. `transcribe_no_docs_1_a45503d1` is tagged `"batch": "sanity_check"`:
a single real run made to confirm a bug fix in the grading harness
*before* the 3-trial batch was approved (see the conversation this
project came out of) — it is not one of the formal 3 trials. The other 18
rows are tagged `"batch": "main"`. `FINDINGS.md`'s results table and the
harness's own `summary.md` both correctly count only the `main` batch;
the sanity-check row is included here for completeness and transparency,
not hidden, but isn't part of the reported n=3-per-cell results.

## What was redacted before publishing

Every `transcript.txt` originally logged this machine's Windows username in
several absolute paths (`cwd`, `scratchpad_path`, `memory_paths`, etc. —
Claude Code's own init message). All 384 occurrences across 19 files were
replaced with `[REDACTED_USER]`; JSON structure was verified intact
afterward (706/706 lines still parse). Three **third-party** email
addresses that leaked in via `pip show` output the agent ran
(package-maintainer/support contacts, not the project owner's data) were
also replaced with `[REDACTED_EMAIL]` (16 occurrences across 6 files). No
API key, OAuth token, or email of the project owner was found anywhere in
`results/` — confirmed by scanning file content and the full git history,
not just spot-checking.

Left in place, intentionally: one `cc-msg-<hex>` string per transcript,
which is a local named-pipe identifier, not a credential.
