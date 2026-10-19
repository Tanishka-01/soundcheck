# Soundcheck

Does Claude Code integrate AssemblyAI correctly on the first try, with vs
without the official [AssemblyAI skill](https://github.com/AssemblyAI/assemblyai-skill)?

Built as portfolio proof for an "Agent Experience" engineering role at
AssemblyAI. The goal is an honest answer, not a flattering one.

**Results of the real 18-run batch are in [FINDINGS.md](FINDINGS.md).**

## What it measures

3 tasks x 2 setups x 3 trials = 18 runs, one at a time, interleaved (not
grouped by setup, so one setup never runs all in a row and a mid-session
blip doesn't bias one condition).

**Tasks** (the prompt says WHAT is wanted, never HOW to call AssemblyAI):
- `transcribe` — transcribe `data/sample.wav`
- `speakers` — transcribe and label who said what (2 distinct speakers)
- `streaming` — transcribe the same file using AssemblyAI's real-time
  streaming API, not the pre-recorded/async one

**Setups:**
- `no_docs` — no web tools (`WebFetch`/`WebSearch` disallowed), no skill.
  **Caveat:** code the agent runs via Bash can still reach the internet
  (e.g. `pip install`), so this is "no documentation help," not "no network."
- `skill` — the official skill cloned into `.claude/skills/assemblyai/` for
  that run only. Commit pinned: `ef37bb36fe454a4a97a73dab308d805566118329`.

Each run: fresh temp folder with a copy of the sample audio, `claude -p`
headless with an isolated `CLAUDE_CONFIG_DIR` (so your real `~/.claude`
skills/settings never leak in — only `.credentials.json` is copied over for
auth), told to write `solution.py` and run it before finishing. The harness
then re-runs `solution.py` itself and checks: did it print one valid JSON
line, do enough reference keywords appear, and (for `speakers`) are there
>=2 distinct speaker labels.

A simple regex lint also flags three AssemblyAI deprecations confirmed
against live docs on 2026-10-17 (not training data): the singular
`speech_model` param on the async endpoint (should be plural
`speech_models`), legacy bare model names (`"best"`, `"universal"`), and
the old `v2/realtime/ws` streaming endpoint.

Runs that hit a rate limit, network error, or exhausted AssemblyAI credits
are tagged `infra_error` and excluded from the pass rate — they are not
held against the agent. The batch stops early if credits run out.

## Sample audio

`data/sample.wav` is **synthetic**: a ~62s two-speaker conversation about
planning a team offsite, generated locally with Windows SAPI (two distinct
installed voices, David/male and Zira/female) and stitched together with
`generate_audio.py`. The exact script is in `data/reference.txt`; the 12
keywords the grader checks for are in `data/keywords.txt`.

Being synthetic and clean (no background noise, no overlapping speech,
no accents), this makes transcription and diarization easier than real
audio would be. Results here are an upper bound, not a guarantee of
real-world accuracy.

## Running it

Requires Python 3.10+, Windows, and Claude Code installed (PATH or the
VS Code extension's bundled binary — `find_claude_exe()` checks both).

```powershell
python -m venv .venv
.venv\Scripts\pip install assemblyai pytest
```

Put your key in `.env`:
```
ASSEMBLYAI_API_KEY=your_key_here
```

25 offline tests of the grading logic first (no key, no real `claude` calls):
```powershell
.venv\Scripts\python -m pytest tests/ -v
```

One real run, cheap, to sanity-check the pipeline:
```powershell
.venv\Scripts\python soundcheck.py --single --max-cost 0.5
```

Full batch:
```powershell
.venv\Scripts\python soundcheck.py --trials 3 --max-cost 0.5
```

Outputs: `results/runs.jsonl` (one line per run, appended immediately — a
crash mid-batch never loses finished runs), `results/summary.md` (written
once at the end), `results/artifacts/<run_id>/` (saved `solution.py`, the
full agent transcript, stderr — API key regex-redacted before anything
touches disk).

## Known limitations

- **n=3 per cell.** Treat any pass-rate difference as a small-sample
  signal, not a proven result.
- **One model** (`claude-sonnet-5`), one machine, one network. This
  environment has intermittent DNS resolution blips (`getaddrinfo failed`)
  on the first network call of a fresh process — it happened twice in
  the real batch, and both times, re-running the exact same flagged
  `solution.py` unmodified passed cleanly right after. That flakiness
  looks specific to this box, not AssemblyAI or Claude.
- **The infra-error classifier itself needed a fix mid-project.** An
  earlier version matched Claude Code's own benign internal
  `"rate_limit_event"` usage-tracking telemetry (present in every session,
  `status: "allowed"`) as if it were a real rate-limit failure. Fixed by
  reading the CLI's actual final-result `is_error`/`subtype` fields and
  real process `stderr` instead of regex-scanning the whole noisy
  stream-json transcript. Worth knowing before trusting `infra_error`
  counts from any one run.
- **Zero agent-caused failures occurred in the actual 18-run batch** — see
  FINDINGS.md. That's a genuine result, not a bug, but it means pass/fail
  alone was not where the interesting signal showed up this time.
- `soundcheck.py` is ~240 lines, not the ~150 originally targeted — the
  isolation, infra-classification, and lint logic needed the room.
