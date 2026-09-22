"""Telling an agent that never answered from one that answered badly.

Both failures reached the same dead end: a hold nobody retried, carrying the
word "agent failed" instead of the reason sitting in the envelope.
"""

import json
import subprocess

from discpipe import agent

EXPIRED_TOKEN = ("Failed to authenticate. API Error: 401 OAuth access token "
                 "has expired. Re-authenticate to continue.")
UNREACHABLE = "API Error: Unable to connect to API (ConnectionRefused)"


def envelope(**fields):
    base = {"type": "result", "is_error": True, "api_error_status": None,
            "result": "something went wrong"}
    base.update(fields)
    return json.dumps(base)


def stub_claude(monkeypatch, stdout, stderr="", returncode=0):
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout,
                                           stderr=stderr)
    monkeypatch.setattr(agent.subprocess, "run", fake_run)


def test_an_expired_token_reports_itself_and_can_be_retried(monkeypatch, tmp_path):
    stub_claude(monkeypatch,
                envelope(api_error_status=401, result=EXPIRED_TOKEN),
                returncode=1)

    plan, raw, failure = agent.run("prompt", cwd=tmp_path)

    assert plan is None
    assert failure.message == EXPIRED_TOKEN
    assert failure.retryable is True


def test_an_unreachable_api_is_retryable_without_a_status(monkeypatch, tmp_path):
    """The CLI never reached the API, so there is no HTTP status to read."""
    stub_claude(monkeypatch, envelope(result=UNREACHABLE))

    plan, raw, failure = agent.run("prompt", cwd=tmp_path)

    assert failure.message == UNREACHABLE
    assert failure.retryable is True


def test_a_nonzero_exit_does_not_discard_the_envelope(monkeypatch, tmp_path):
    """The reason was on stdout; only stderr was read, and it was empty."""
    stub_claude(monkeypatch,
                envelope(api_error_status=401, result=EXPIRED_TOKEN),
                stderr="", returncode=1)

    plan, raw, failure = agent.run("prompt", cwd=tmp_path)

    assert failure.message != "agent failed"
    assert "OAuth access token has expired" in failure.message


def test_a_nonzero_exit_with_nothing_to_read_still_says_something(monkeypatch, tmp_path):
    stub_claude(monkeypatch, "", stderr="", returncode=2)

    plan, raw, failure = agent.run("prompt", cwd=tmp_path)

    assert failure.message == "agent exited 2"
    assert failure.retryable is False


def test_a_refused_request_is_not_retried(monkeypatch, tmp_path):
    """A 400 will fail again on the same input; only transport faults clear."""
    stub_claude(monkeypatch, envelope(api_error_status=400, result="bad request"))

    plan, raw, failure = agent.run("prompt", cwd=tmp_path)

    assert failure.retryable is False


def test_an_agent_that_answered_badly_is_not_retried(monkeypatch, tmp_path):
    stub_claude(monkeypatch, json.dumps({"structured_output": {"nope": 1}}))

    plan, raw, failure = agent.run("prompt", cwd=tmp_path)

    assert failure.message == "agent plan had no items"
    assert failure.retryable is False


def test_a_timeout_is_retryable(monkeypatch, tmp_path):
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1800)
    monkeypatch.setattr(agent.subprocess, "run", fake_run)

    plan, raw, failure = agent.run("prompt", cwd=tmp_path, timeout=1800)

    assert failure.message == "agent timed out after 1800s"
    assert failure.retryable is True


def test_a_good_plan_reports_no_failure(monkeypatch, tmp_path):
    stub_claude(monkeypatch, json.dumps(
        {"structured_output": {"items": [{"action": "feature"}]}}))

    plan, raw, failure = agent.run("prompt", cwd=tmp_path)

    assert failure is None
    assert plan["items"] == [{"action": "feature"}]
