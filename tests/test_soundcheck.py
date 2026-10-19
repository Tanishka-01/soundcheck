"""Offline tests: a fake agent, no ASSEMBLYAI_API_KEY, no real `claude` calls."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import soundcheck as sc


@pytest.fixture
def keywords():
    return ["offsite", "mountain", "budget"]


def fake_agent_result(stdout="", stderr="", used_skill=False, cli_is_error=False,
                       cli_subtype="success", api_error_status=None):
    return {"stdout": stdout, "stderr": stderr, "wall_time_s": 1.0,
            "cost_usd": 0.01, "num_turns": 2, "used_skill": used_skill,
            "cli_is_error": cli_is_error, "cli_subtype": cli_subtype,
            "api_error_status": api_error_status}


def write_solution(run_dir: Path, body: str):
    (run_dir / "solution.py").write_text(body, encoding="utf-8")


# --- keyword_hits / redact -------------------------------------------------

def test_keyword_hits_counts_case_insensitively(keywords):
    n, hits = sc.keyword_hits("We discussed the OFFSITE and the Budget plan.", keywords)
    assert n == 2
    assert set(hits) == {"offsite", "budget"}


def test_redact_removes_secret():
    assert sc.redact("key=abc123 done", "abc123") == "key=[REDACTED] done"
    assert sc.redact("nothing to redact", None) == "nothing to redact"


# --- infra_match -------------------------------------------------------

@pytest.mark.parametrize("text", [
    "httpx.ConnectError: [Errno 11001] getaddrinfo failed",
    "HTTP 429 Too Many Requests",
    "Error: 402 Payment Required",
    "status 500 Internal Server Error",
])
def test_infra_match_detects_known_signatures(text):
    assert sc.infra_match(text) is not None


def test_infra_match_none_for_clean_output():
    assert sc.infra_match("transcript: hello world") is None


# --- grade(): pass / fail / infra_error -------------------------------

def test_grade_fails_when_no_solution_written(tmp_path, keywords):
    g = sc.grade("transcribe", tmp_path, fake_agent_result(), keywords)
    assert g["status"] == "fail"
    assert "no solution.py" in g["reason"]


def test_grade_infra_error_from_agent_stderr(tmp_path, keywords):
    g = sc.grade("transcribe", tmp_path, fake_agent_result(stderr="429 rate limit exceeded"), keywords)
    assert g["status"] == "infra_error"


def test_grade_ignores_benign_rate_limit_telemetry_in_stdout(tmp_path, keywords):
    # Regression: Claude Code's own stream-json includes routine usage-tracking
    # lines like {"type":"rate_limit_event",...,"status":"allowed",...} on
    # every session. These must NOT be misread as a real rate-limit failure.
    noisy_stdout = (
        '{"type":"rate_limit_event","rate_limit_info":{"status":"allowed","overageStatus":"rejected"}}\n'
        '{"type":"result","is_error":false,"subtype":"success","api_error_status":null,"num_turns":5}'
    )
    write_solution(tmp_path, "import json; print(json.dumps({'text': 'the offsite budget mountain'}))")
    g = sc.grade("transcribe", tmp_path, fake_agent_result(stdout=noisy_stdout), keywords)
    assert g["status"] == "pass"


def test_grade_infra_error_when_cli_reports_is_error(tmp_path, keywords):
    g = sc.grade("transcribe", tmp_path, fake_agent_result(cli_is_error=True, cli_subtype="error_during_execution"), keywords)
    assert g["status"] == "infra_error"


def test_grade_credit_exhausted_flagged(tmp_path, keywords):
    g = sc.grade("transcribe", tmp_path, fake_agent_result(stderr="402 Payment Required: insufficient credits"), keywords)
    assert g["status"] == "infra_error"
    assert g["credit_exhausted"] is True


def test_grade_pass_transcribe(tmp_path, keywords):
    write_solution(tmp_path, f"import json; print(json.dumps({{'text': 'we discussed the offsite and the budget plan'}}))")
    g = sc.grade("transcribe", tmp_path, fake_agent_result(), keywords)
    assert g["status"] == "pass"


def test_grade_fail_transcribe_too_few_keywords(tmp_path, keywords):
    write_solution(tmp_path, "import json; print(json.dumps({'text': 'hello there'}))")
    g = sc.grade("transcribe", tmp_path, fake_agent_result(), keywords)
    assert g["status"] == "fail"
    assert "keywords matched" in g["reason"]


def test_grade_fail_not_json(tmp_path, keywords):
    write_solution(tmp_path, "print('not json at all')")
    g = sc.grade("transcribe", tmp_path, fake_agent_result(), keywords)
    assert g["status"] == "fail"
    assert "not valid JSON" in g["reason"]


def test_grade_speakers_needs_two_distinct(tmp_path, keywords):
    write_solution(tmp_path, "import json; print(json.dumps({'text': 'the offsite budget mountain', 'speakers': ['A']}))")
    g = sc.grade("speakers", tmp_path, fake_agent_result(), keywords)
    assert g["status"] == "fail"
    assert "distinct speakers" in g["reason"]


def test_grade_speakers_pass_with_two_distinct(tmp_path, keywords):
    write_solution(tmp_path, "import json; print(json.dumps({'text': 'the offsite budget mountain', 'speakers': ['A', 'B']}))")
    g = sc.grade("speakers", tmp_path, fake_agent_result(), keywords)
    assert g["status"] == "pass"


def test_grade_infra_error_from_solution_run(tmp_path, keywords):
    write_solution(tmp_path, "raise SystemExit('ConnectionError: getaddrinfo failed')")
    g = sc.grade("transcribe", tmp_path, fake_agent_result(), keywords)
    assert g["status"] == "infra_error"


# --- deprecated-usage lint ----------------------------------------------

def test_deprecated_singular_speech_model_flagged_on_transcribe(tmp_path, keywords):
    write_solution(tmp_path, "import json\nspeech_model = 'universal-3-5-pro'\nprint(json.dumps({'text': 'the offsite budget mountain'}))")
    g = sc.grade("transcribe", tmp_path, fake_agent_result(), keywords)
    assert any("speech_model" in d for d in g["deprecated_used"])


def test_plural_speech_models_not_flagged(tmp_path, keywords):
    write_solution(tmp_path, "import json\nspeech_models = ['universal-3-5-pro']\nprint(json.dumps({'text': 'the offsite budget mountain'}))")
    g = sc.grade("transcribe", tmp_path, fake_agent_result(), keywords)
    assert g["deprecated_used"] == []


def test_legacy_model_name_best_flagged(tmp_path, keywords):
    write_solution(tmp_path, "import json\nm = 'best'\nprint(json.dumps({'text': 'the offsite budget mountain'}))")
    g = sc.grade("transcribe", tmp_path, fake_agent_result(), keywords)
    assert any("best" in d for d in g["deprecated_used"])


def test_legacy_v2_realtime_endpoint_flagged_on_streaming(tmp_path, keywords):
    write_solution(tmp_path, "import json\nurl = 'wss://api.assemblyai.com/v2/realtime/ws'\nprint(json.dumps({'text': 'the offsite budget mountain'}))")
    g = sc.grade("streaming", tmp_path, fake_agent_result(), keywords)
    assert any("v2 realtime" in d for d in g["deprecated_used"])


# --- scheduling ----------------------------------------------------------

def test_build_schedule_interleaves_setups_and_tasks():
    schedule = sc.build_schedule(trials=2)
    assert len(schedule) == len(sc.TASKS) * len(sc.SETUPS) * 2
    # first full round (one of each task x setup) comes before trial 2 starts
    first_round = schedule[: len(sc.TASKS) * len(sc.SETUPS)]
    assert all(trial == 1 for _, _, trial in first_round)
    # no setup appears twice in a row for the same task at the start
    assert schedule[0][2] == 1 and schedule[-1][2] == 2


# --- run_one(): end-to-end with a fake agent, no network ----------------

def test_run_one_with_fake_agent_writes_jsonl_and_artifacts(tmp_path, keywords, monkeypatch):
    monkeypatch.setattr(sc, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(sc, "DATA", tmp_path / "data")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sample.wav").write_bytes(b"RIFF....fake-wav....")

    def fake_run_agent(task_id, setup, run_dir, max_cost, model):
        (run_dir / "solution.py").write_text(
            "import json; print(json.dumps({'text': 'the offsite budget mountain'}))", encoding="utf-8"
        )
        return fake_agent_result(stdout='{"type": "result", "total_cost_usd": 0.02, "num_turns": 3}')

    monkeypatch.setattr(sc, "run_agent", fake_run_agent)
    row = sc.run_one("transcribe", "no_docs", 1, max_cost=1.0, model="claude-sonnet-5", keywords=keywords)

    assert row["status"] == "pass"
    jsonl = (tmp_path / "results" / "runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(jsonl) == 1
    assert json.loads(jsonl[0])["run_id"] == row["run_id"]
    artifact = Path(row["artifact_dir"])
    assert (artifact / "solution.py").exists()
    assert (artifact / "transcript.txt").exists()


def test_run_one_never_calls_real_claude_binary(monkeypatch, tmp_path, keywords):
    monkeypatch.setattr(sc, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(sc, "DATA", tmp_path / "data")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sample.wav").write_bytes(b"fake")

    def boom(*a, **k):
        raise AssertionError("find_claude_exe should never be called in offline tests")

    monkeypatch.setattr(sc, "find_claude_exe", boom)
    monkeypatch.setattr(sc, "run_agent", lambda *a, **k: fake_agent_result())
    row = sc.run_one("transcribe", "no_docs", 1, max_cost=1.0, model="claude-sonnet-5", keywords=keywords)
    assert row["status"] == "fail"  # no solution.py written by the fake agent
