"""Verify host evidence handling without accessing AWS, Docker or public URLs."""

import base64
import copy
import gzip
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if not SCRIPTS.is_dir():
    SCRIPTS = SCRIPTS.parent / "student-Ethan Ting/scripts"


def load(name):
    spec = importlib.util.spec_from_file_location("test_" + name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def payload():
    sample = {"current_release": "/example/release", "boot_id": "same-boot",
        "oom_kill_counter": 5, "public_home_status": 200,
        "containers": [{"service": "ethan-backend", "id": "example-container",
            "status": "running", "health": "healthy", "restart_count": 0,
            "started_at": "original-start", "oom_killed": False,
            "ai_flags": {name: "false" for name in ("AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED")}}]}
    return {"observation_seconds": 120, "samples": [copy.deepcopy(sample) for _ in range(3)]}


def test_payload_decode_round_trip(payload):
    module = load("assemble_cloud_observation")
    encoded = base64.b64encode(gzip.compress(json.dumps(payload).encode())).decode()
    assert module.decode_capture("ASD_READONLY_EVIDENCE_GZIP_BASE64=" + encoded) == payload


@pytest.mark.parametrize("text", ["no evidence", "ASD_READONLY_EVIDENCE_GZIP_BASE64=" + "a" * 20001])
def test_missing_or_oversized_payload_rejected(text):
    with pytest.raises(ValueError):
        load("assemble_cloud_observation").decode_capture(text)


def test_duplicate_payload_rejected(payload):
    encoded = base64.b64encode(gzip.compress(json.dumps(payload).encode())).decode()
    text = "ASD_READONLY_EVIDENCE_GZIP_BASE64=" + encoded
    with pytest.raises(ValueError, match="duplicate"):
        load("assemble_cloud_observation").decode_capture(text + "\n" + text)


def test_decompression_budget_is_bounded():
    encoded = base64.b64encode(gzip.compress(b"x" * (256 * 1024 + 1))).decode()
    with pytest.raises(ValueError, match="uncompressed"):
        load("assemble_cloud_observation").decode_capture("ASD_READONLY_EVIDENCE_GZIP_BASE64=" + encoded)


def test_stable_observation(payload):
    assert load("assemble_cloud_observation").health_fields(payload) == {
        "new_oom_events": 0, "unexpected_restarts": 0,
        "containers_healthy": True, "container_count": 1}


def test_new_oom_not_hidden(payload):
    payload["samples"][-1]["oom_kill_counter"] += 1
    assert load("assemble_cloud_observation").health_fields(payload)["new_oom_events"] == 1


def test_restart_not_hidden(payload):
    payload["samples"][-1]["containers"][0]["restart_count"] = 1
    assert load("assemble_cloud_observation").health_fields(payload)["unexpected_restarts"] > 0


@pytest.mark.parametrize("field,value", [("boot_id", "new-boot"), ("current_release", "/different/release"), ("oom_kill_counter", 0)])
def test_incomparable_observation_rejected(payload, field, value):
    payload["samples"][-1][field] = value
    with pytest.raises(ValueError):
        load("assemble_cloud_observation").health_fields(payload)


def test_short_window_rejected(payload):
    payload["observation_seconds"] = 10
    with pytest.raises(ValueError, match="120-second"):
        load("assemble_cloud_observation").health_fields(payload)


@pytest.mark.parametrize("kind", ["flag", "container", "public", "missing"])
def test_health_failures_not_hidden(payload, kind):
    last = payload["samples"][-1]
    if kind == "flag":
        last["containers"][0]["ai_flags"]["RAG_ENABLED"] = "true"
    elif kind == "container":
        last["containers"][0]["health"] = "unhealthy"
    elif kind == "public":
        last["public_home_status"] = 503
    else:
        last["containers"] = []
    assert load("assemble_cloud_observation").health_fields(payload)["containers_healthy"] is False


def test_host_reader_rejects_other_release(tmp_path, monkeypatch):
    module = load("observe_cloud_host")
    monkeypatch.setattr(module, "DIRECTORY", tmp_path)
    (tmp_path / "runtime.json").write_text(json.dumps({"source_sha": "different", "release_id": module.RELEASE}))
    with pytest.raises(ValueError, match="another release"):
        module.selected_json("runtime.json")
