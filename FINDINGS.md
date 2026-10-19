# Findings

Run on 2026-10-17. Model: `claude-sonnet-5`. Skill commit:
`ef37bb36fe454a4a97a73dab308d805566118329`.

**Summary.** Ran 18 real AssemblyAI integration attempts by Claude
Sonnet 5 (3 tasks x 2 setups x 3 trials: `no_docs` vs the official
AssemblyAI skill). Pass/fail was identical either way — both setups
solved everything that wasn't blocked by infra issues. The skill's
actual, visible effect was getting every streaming solution to
explicitly pin a specific, recent model name; the no-skill runs always
left it unset. n=3 per cell and synthetic audio mean this is a
directional signal, not a proven result — see Limitations.

## What I tested

Whether Claude Code, given a WHAT-not-HOW prompt, correctly integrates
AssemblyAI for transcribe / speaker labels / real-time streaming, with
vs without the skill. Before any agent ran, I made one direct call per
task type myself against the same audio, confirming AssemblyAI's live
docs and that the sample audio diarizes into exactly 2 speakers.

## Results

| Task | Setup | Pass | Total (excl. infra_error) |
|---|---|---|---|
| transcribe | no_docs | 3 | 3 |
| transcribe | skill | 3 | 3 |
| speakers | no_docs | 3 | 3 |
| speakers | skill | 2 | 2 |
| streaming | no_docs | 3 | 3 |
| streaming | skill | 1 | 1 |

15 pass, 3 non-pass, **0 of the non-passes were agent mistakes**:
- 2 `streaming`/`skill` runs hit a `getaddrinfo failed` DNS error while
  running the agent's own `solution.py`. I re-ran each one's saved code
  unmodified right after — both passed cleanly. Looks like a transient
  DNS issue on my machine, not an AssemblyAI or Claude problem.
- 1 `streaming`/`skill` run did not finish within budget (13 turns, hit
  my own `--max-cost 0.5` cap) before producing a final `solution.py`.

Average cost per run: **$0.24 (`no_docs`) vs $0.30 (`skill`)** — a
difference of about $0.06/run. `skill` runs loaded more context per turn
despite using slightly fewer turns on average (8.4 vs 9.3).

## What this suggests

**1. The skill got agents to pin a specific, recent model name; the
no-skill runs never set one.** All 3 `no_docs` streaming solutions
omitted `speech_model` and let the connection default. All 3 `skill`
streaming solutions explicitly set `speech_model="universal-3-6-pro"`.
Per the skill's own changelog, that model was released 2026-09-29
([AssemblyAI/assemblyai-skill@ef37bb3, SKILL.md](https://github.com/AssemblyAI/assemblyai-skill/blob/ef37bb36fe454a4a97a73dab308d805566118329/skills/assemblyai/SKILL.md)) —
which may be newer than Sonnet 5's stated training cutoff (January
2026), so this may not be something the model could type unprompted.
Both versions passed *today* because AssemblyAI's current server-side
default happens to be that same model — but AssemblyAI's own docs
describe a similar default changing before, on the pre-recorded
endpoint ("the default will be updated to universal-3-5-pro on August 7",
[assemblyai.com/docs/llms-full.txt](https://www.assemblyai.com/docs/llms-full.txt)).
An explicit pin survives that kind of change; an omitted parameter
doesn't. This suggests the skill's value here is future-proofing, not a
pass-rate lift — it did not show up in the Results table above.

**2. One of AssemblyAI's own quickstart pages uses the SDK's old class
name; the skill does not.** `llms-full.txt` shows two different names
for the same streaming client in two different sections — one
quickstart uses `StreamingClient`/`StreamingParameters`, another uses
`RealTimeTranscriber`/`RealTimeParameters`. Confirmed in code (not from
docs) against `assemblyai` 1.6.5: `StreamingClient is RealTimeTranscriber`
is `True`, the actual `class` statement in the SDK source
(`assemblyai/streaming/v3/client.py`) defines `RealTimeTranscriber`, with
`StreamingClient = RealTimeTranscriber` added right after it, commented
`# Alias: the former name for RealTimeTranscriber`. The SDK's own
`MIGRATION.md` lists `StreamingClient`/`StreamingClientOptions` under
"0.x pattern" and `RealTimeTranscriber`/`RealTimeTranscriberOptions`
under "1.0 best practice". So `RealTimeTranscriber` is current;
`StreamingClient` is the old name, still working as an alias. Of the 3
`no_docs` streaming solutions (all 3 used the SDK), 2 used the old name
and 1 used the current one. Of the 3 `skill` solutions, 1 used the SDK
(current name) and 2 used raw websockets instead, sidestepping the
question. Neither is a correctness bug — both names work — but it's a
concrete instance of one AssemblyAI quickstart page lagging behind the
SDK's own migration guide.

## What I'd change

- In AssemblyAI's docs: the most prominent streaming quickstart could be
  updated to the current model name and the SDK's current class names
  (`RealTimeTranscriber`/`RealTimeParameters`, per the SDK's own
  `MIGRATION.md`), matching what the skill and the SDK's other pages
  already use.
- In the skill: nothing needs fixing for correctness in this sample. The
  one run that didn't finish within budget was visibly trying multiple
  implementation approaches (SDK vs raw websocket) before settling on
  one — being more prescriptive about a single recommended streaming
  path might reduce that.
- In my own harness: give the hardest cell (`streaming` + `skill`) a
  higher `--max-cost` than the rest — it's demonstrably the most
  turn-hungry combination.

## Limitations

- n=3 per cell — directional, not statistically meaningful, especially
  since both setups passed everything that wasn't blocked by infra.
- Synthetic, clean TTS audio (see README) — easier than real speech.
- One model, one machine, one point in time (2026-10-17); results may
  differ later as training data and AssemblyAI's own docs both catch up.
- My own infra-error classifier had a real bug mid-project (it initially
  matched Claude Code's own benign telemetry as a false rate-limit
  failure, caught and fixed before the full batch) — treat `infra_error`
  tags as best-effort, not independently audited for every pattern.
- 25 offline tests cover the grading logic itself, not whether these
  specific conclusions generalize.
- Zero agent-caused failures means this task set isn't very
  discriminating at this model's capability level right now.
