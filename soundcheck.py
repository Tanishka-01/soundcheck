"""Soundcheck: does Claude Code integrate AssemblyAI correctly on the first
try, with vs without the official AssemblyAI skill? See README.md.
"""
import argparse, json, os, re, shutil, subprocess, tempfile, time, uuid
from pathlib import Path

ROOT = Path(__file__).parent
DATA, RESULTS = ROOT / "data", ROOT / "results"
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
SKILL_SRC = ROOT / "vendor" / "assemblyai-skill" / "skills" / "assemblyai"
REAL_CREDS = Path.home() / ".claude" / ".credentials.json"


def load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

_BASE = ("There is an audio file named sample.wav in the current directory. "
         "Write a Python script named solution.py that takes one command-line "
         "argument (the audio file path), transcribes it using AssemblyAI (your "
         "API key is in ASSEMBLYAI_API_KEY), and prints exactly one line of "
         "JSON as the LAST line of stdout: {json}. Run `python solution.py "
         "sample.wav` yourself before you finish, and fix the script if it "
         "errors or does not print valid JSON.")
TASKS = {
    "transcribe": _BASE.format(json='{"text": "<full transcript>"}'),
    "speakers": _BASE.format(json='{"text": "<full transcript>", "speakers": '
        '["A", "B"]} -- there are 2 different speakers in this recording; list '
        "the distinct speaker labels you found"),
    "streaming": _BASE.format(json='{"text": "<final transcript>"}') +
        " You must use AssemblyAI's real-time/streaming speech-to-text API "
        "(not the pre-recorded/asynchronous upload API) -- stream the file's "
        "audio to the real-time API as if it were live audio.",
}
SETUPS = ["no_docs", "skill"]

# Confirmed against live AssemblyAI docs on 2026-10-17 (see FINDINGS.md).
DEPRECATED_CHECKS = {
    "transcribe": [(r"\bspeech_model\b(?!s)", 'singular "speech_model" on the async endpoint (deprecated; use plural "speech_models")')],
    "speakers": [(r"\bspeech_model\b(?!s)", 'singular "speech_model" on the async endpoint (deprecated; use plural "speech_models")')],
    "streaming": [(r"v2/realtime/ws", "legacy v2 realtime endpoint (use wss://streaming.assemblyai.com/v3/ws)")],
}
ALWAYS_CHECKS = [(r'["\']best["\']', 'legacy model name "best"'),
                  (r'["\']universal["\'](?!-)', 'legacy bare "universal" model name')]
INFRA_PATTERNS = [r"getaddrinfo failed", r"ConnectionError", r"ConnectTimeout", r"\b429\b",
                   r"rate.?limit", r"too many requests", r"\b5\d{2}\b", r"insufficient credits",
                   r"payment required", r"\b402\b", r"Temporary failure in name resolution"]
CREDIT_PATTERNS = [r"insufficient credits", r"payment required", r"\b402\b"]


def find_claude_exe() -> str:
    found = shutil.which("claude")
    if found:
        return found
    for d in sorted((Path.home() / ".vscode" / "extensions").glob("anthropic.claude-code-*-win32-x64"), reverse=True):
        exe = d / "resources" / "native-binary" / "claude.exe"
        if exe.exists():
            return str(exe)
    raise SystemExit("claude binary not found; install Claude Code or add it to PATH")


def load_keywords() -> list[str]:
    return (DATA / "keywords.txt").read_text(encoding="utf-8").splitlines()


def keyword_hits(text: str, keywords: list[str]) -> tuple[int, list[str]]:
    lowered = (text or "").lower()
    hits = [k for k in keywords if k.lower() in lowered]
    return len(hits), hits


def redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "[REDACTED]") if text and secret else text


def infra_match(text: str) -> str | None:
    for pat in INFRA_PATTERNS:
        if re.search(pat, text or "", re.IGNORECASE):
            return pat
    return None


def run_agent(task_id: str, setup: str, run_dir: Path, max_cost: float, model: str) -> dict:
    cfg_dir = Path(tempfile.mkdtemp(prefix="cc_cfg_"))
    if REAL_CREDS.exists():
        shutil.copy(REAL_CREDS, cfg_dir / ".credentials.json")
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(cfg_dir))
    env["PATH"] = str(VENV_PY.parent) + os.pathsep + env.get("PATH", "")
    if setup == "skill":
        shutil.copytree(SKILL_SRC, run_dir / ".claude" / "skills" / "assemblyai")

    cmd = [find_claude_exe(), "-p", TASKS[task_id], "--output-format", "stream-json", "--verbose",
           "--permission-mode", "bypassPermissions", "--setting-sources", "project",
           "--strict-mcp-config", "--model", model, "--max-budget-usd", str(max_cost)]
    if setup == "no_docs":
        cmd += ["--disallowedTools", "WebFetch", "WebSearch"]

    t0 = time.time()
    proc = subprocess.run(cmd, cwd=run_dir, env=env, capture_output=True, text=True, timeout=900)
    cost_usd = num_turns = cli_is_error = cli_subtype = api_error_status = None
    # The last "result" line is the CLI's own final summary -- not the noisy
    # per-turn transcript, which also contains benign internal telemetry
    # (e.g. "rate_limit_event" usage-tracking lines unrelated to any failure).
    for line in reversed(proc.stdout.splitlines()):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") == "result":
            cost_usd = obj.get("total_cost_usd", obj.get("cost_usd"))
            num_turns = obj.get("num_turns")
            cli_is_error = obj.get("is_error")
            cli_subtype = obj.get("subtype")
            api_error_status = obj.get("api_error_status")
            break
    used_skill = setup == "skill" and bool(re.search(r'"name"\s*:\s*"Skill"', proc.stdout))
    return {"stdout": proc.stdout, "stderr": proc.stderr, "wall_time_s": round(time.time() - t0, 1),
            "cost_usd": cost_usd, "num_turns": num_turns, "used_skill": used_skill,
            "cli_is_error": cli_is_error, "cli_subtype": cli_subtype, "api_error_status": api_error_status}


def res(status: str, reason: str, deprecated=(), credit=False) -> dict:
    return {"status": status, "reason": reason, "deprecated_used": list(deprecated), "credit_exhausted": credit}


def grade(task_id: str, run_dir: Path, agent_result: dict, keywords: list[str]) -> dict:
    # Agent-level infra check: trust the CLI's own final-result error fields
    # and its real process stderr -- NOT the raw stream-json transcript, which
    # is full of benign internal telemetry (e.g. routine rate-limit-usage
    # tracking lines) that happens to contain words like "rate limit".
    if agent_result.get("cli_is_error") or agent_result.get("api_error_status"):
        signal = f"subtype={agent_result.get('cli_subtype')} api_error_status={agent_result.get('api_error_status')}"
        credit = any(re.search(p, signal, re.IGNORECASE) for p in CREDIT_PATTERNS)
        return res("infra_error", f"claude CLI reported is_error ({signal})", credit=credit)
    pat = infra_match(agent_result.get("stderr") or "")
    if pat:
        credit = any(re.search(p, agent_result["stderr"], re.IGNORECASE) for p in CREDIT_PATTERNS)
        return res("infra_error", f"agent process stderr matched /{pat}/", credit=credit)

    solution = run_dir / "solution.py"
    if not solution.exists():
        return res("fail", "no solution.py written")

    source = solution.read_text(encoding="utf-8", errors="replace")
    deprecated = [label for p, label in DEPRECATED_CHECKS.get(task_id, []) + ALWAYS_CHECKS if re.search(p, source)]

    try:
        proc = subprocess.run([str(VENV_PY), "solution.py", "sample.wav"], cwd=run_dir,
                               capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return res("fail", "solution.py timed out", deprecated)

    out = (proc.stdout or "") + (proc.stderr or "")
    pat = infra_match(out)
    if pat:
        return res("infra_error", f"solution.py run matched /{pat}/", deprecated)

    lines = [l for l in (proc.stdout or "").splitlines() if l.strip()]
    if not lines:
        return res("fail", "solution.py printed nothing", deprecated)
    try:
        obj = json.loads(lines[-1])
    except ValueError:
        return res("fail", "last line of output is not valid JSON", deprecated)

    n, _ = keyword_hits(obj.get("text", ""), keywords)
    if task_id == "speakers":
        n_speakers = len(set(obj.get("speakers") or []))
        if n_speakers < 2:
            return res("fail", f"found {n_speakers} distinct speakers, need >=2", deprecated)
    if n < len(keywords) * 0.6:
        return res("fail", f"only {n}/{len(keywords)} keywords matched", deprecated)
    return res("pass", "ok", deprecated)


def run_one(task_id: str, setup: str, trial: int, max_cost: float, model: str, keywords: list[str], batch: str = "main") -> dict:
    run_id = f"{task_id}_{setup}_{trial}_{uuid.uuid4().hex[:8]}"
    run_dir = Path(tempfile.mkdtemp(prefix=f"sc_{run_id}_"))
    shutil.copy(DATA / "sample.wav", run_dir / "sample.wav")

    agent_result = run_agent(task_id, setup, run_dir, max_cost, model)
    g = grade(task_id, run_dir, agent_result, keywords)

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    artifact_dir = RESULTS / "artifacts" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if (run_dir / "solution.py").exists():
        shutil.copy(run_dir / "solution.py", artifact_dir / "solution.py")
    (artifact_dir / "transcript.txt").write_text(redact(agent_result["stdout"], api_key), encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(redact(agent_result["stderr"], api_key), encoding="utf-8")

    row = {"run_id": run_id, "task": task_id, "setup": setup, "trial": trial, "batch": batch,
           "status": g["status"], "reason": g["reason"], "deprecated_used": g["deprecated_used"],
           "credit_exhausted": g["credit_exhausted"], "used_skill": agent_result["used_skill"],
           "wall_time_s": agent_result["wall_time_s"], "cost_usd": agent_result["cost_usd"],
           "num_turns": agent_result["num_turns"], "model": model, "artifact_dir": str(artifact_dir)}
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    shutil.rmtree(run_dir, ignore_errors=True)
    return row


def write_summary(rows: list[dict]) -> None:
    lines = ["# Soundcheck summary", "", "| Task | Setup | Pass | Total |", "|---|---|---|---|"]
    for task_id in TASKS:
        for setup in SETUPS:
            subset = [r for r in rows if r["task"] == task_id and r["setup"] == setup and r["status"] != "infra_error"]
            passed = sum(1 for r in subset if r["status"] == "pass")
            lines.append(f"| {task_id} | {setup} | {passed} | {len(subset)} |")
    lines += ["", "With only 3 trials per cell, treat any difference as a small-sample signal, not a proven result."]
    (RESULTS / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def build_schedule(trials: int) -> list[tuple[str, str, int]]:
    return [(t, s, trial) for trial in range(1, trials + 1) for t in TASKS for s in SETUPS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--single", action="store_true", help="run only the first scheduled run")
    ap.add_argument("--max-cost", type=float, default=1.0, help="per-run --max-budget-usd")
    ap.add_argument("--model", default="claude-sonnet-5")
    args = ap.parse_args()

    load_dotenv()
    if not os.environ.get("ASSEMBLYAI_API_KEY"):
        raise SystemExit("ASSEMBLYAI_API_KEY is not set.")
    keywords = load_keywords()
    schedule = build_schedule(args.trials)[:1] if args.single else build_schedule(args.trials)
    batch_label = "sanity_check" if args.single else "main"

    rows = []
    for task_id, setup, trial in schedule:
        print(f"--- {task_id} / {setup} / trial {trial} ---")
        row = run_one(task_id, setup, trial, args.max_cost, args.model, keywords, batch=batch_label)
        rows.append(row)
        print(f"{row['status'].upper()}: {row['reason']} (turns={row['num_turns']} cost=${row['cost_usd']})")
        if row["status"] == "infra_error" and row["credit_exhausted"]:
            print("Credits appear exhausted -- stopping the batch.")
            break

    write_summary(rows)
    print(f"\nWrote {RESULTS / 'summary.md'} and {RESULTS / 'runs.jsonl'}")


if __name__ == "__main__":
    main()
