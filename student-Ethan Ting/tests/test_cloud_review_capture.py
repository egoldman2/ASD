"""No live GitHub/AWS calls: verify the read-only cloud capture's archive guard."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import stat
from zipfile import ZipFile, ZipInfo

import pytest


HELPER = Path(__file__).resolve().parents[1] / "scripts/capture_cloud_review.py"
if not HELPER.is_file():
    HELPER = HELPER.parent.parent / "student-Ethan Ting/scripts/capture_cloud_review.py"


@pytest.fixture
def helper():
    spec = importlib.util.spec_from_file_location("ethan_cloud_capture", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive(tmp_path, entries):
    path = tmp_path / "native.zip"
    with ZipFile(path, "w") as zipped:
        for name, value in entries:
            zipped.writestr(name, value)
    return path, "sha256:" + sha256(path.read_bytes()).hexdigest()


def test_extract_retains_exact_native_bytes(helper, tmp_path):
    raw = b'{"source_sha":"native fixture"}\n'
    path, digest = archive(tmp_path, [("deployment-report.json", raw)])
    destination = tmp_path / "captured"
    assert helper.extract(path, digest, {"deployment-report.json"}, destination) == ["deployment-report.json"]
    assert (destination / "deployment-report.json").read_bytes() == raw


def test_extract_rejects_wrong_digest_before_writing(helper, tmp_path):
    path, _ = archive(tmp_path, [("runtime.json", "{}")])
    with pytest.raises(ValueError, match="SHA-256"):
        helper.extract(path, "sha256:" + "0" * 64, {"runtime.json"}, tmp_path / "captured")
    assert not (tmp_path / "captured").exists()


@pytest.mark.parametrize("name", ["../runtime.json", "/runtime.json", "private.env"])
def test_extract_rejects_unlisted_paths(helper, tmp_path, name):
    path, digest = archive(tmp_path, [(name, "{}")])
    with pytest.raises(ValueError, match="Unexpected"):
        helper.extract(path, digest, {"runtime.json"}, tmp_path / "captured")


def test_extract_rejects_duplicate_members(helper, tmp_path):
    with pytest.warns(UserWarning, match="Duplicate"):
        path, digest = archive(tmp_path, [("runtime.json", "{}"), ("runtime.json", "{}")])
    with pytest.raises(ValueError, match="duplicate"):
        helper.extract(path, digest, {"runtime.json"}, tmp_path / "captured")


def test_extract_rejects_symlink_member(helper, tmp_path):
    info = ZipInfo("runtime.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    path, digest = archive(tmp_path, [(info, "{}")])
    with pytest.raises(ValueError, match="symlink"):
        helper.extract(path, digest, {"runtime.json"}, tmp_path / "captured")


def test_extract_does_not_replace_previous_capture(helper, tmp_path):
    path, digest = archive(tmp_path, [("runtime.json", "{}")])
    destination = tmp_path / "captured"
    helper.extract(path, digest, {"runtime.json"}, destination)
    with pytest.raises(FileExistsError):
        helper.extract(path, digest, {"runtime.json"}, destination)


def test_save_preserves_previous_evidence(helper, tmp_path):
    path = tmp_path / "capture.json"
    helper.save(path, {"original": True})
    with pytest.raises(FileExistsError):
        helper.save(path, {"original": False})
    assert json.loads(path.read_text()) == {"original": True}


def test_capture_rejects_different_source_before_writing(helper, tmp_path, monkeypatch):
    monkeypatch.setattr(helper, "git", lambda *args: "" if args[0] == "diff" else "a" * 40)
    monkeypatch.setattr(helper, "api", lambda _: {"head_sha": "b" * 40})
    with pytest.raises(ValueError, match="committed HEAD"):
        helper.capture(tmp_path / "captured", 1)
    assert not (tmp_path / "captured").exists()


def test_capture_refuses_tracked_source_edits(helper, tmp_path, monkeypatch):
    monkeypatch.setattr(helper, "git", lambda *args: "app.py")
    monkeypatch.setattr(helper, "api", lambda _: pytest.fail("Dirty source must not contact GitHub."))
    with pytest.raises(ValueError, match="Tracked source edits"):
        helper.capture(tmp_path / "captured", 1)
