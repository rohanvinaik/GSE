"""Latest reports may change without weakening immutable learning checkpoints."""

import json
import subprocess
from importlib import import_module

import pytest

from GSE.curation.lexicon_builder.epoch import record

status_module = import_module(
    "docs.readings.2026-11-13-ssl-explicit-genera.finish_coherence_020"
)
record_status = status_module.record_status


def test_status_replacement_does_not_relax_checkpoint_immutability(tmp_path):
    status = tmp_path / "status.json"
    record_status(status, {"code": "RUNNING"})
    record_status(status, {"code": "VALIDATED"})
    assert json.loads(status.read_text()) == {"code": "VALIDATED"}
    checkpoint = tmp_path / "checkpoint.json"
    record(checkpoint, {"code": "ORIGINAL"})
    with pytest.raises(ValueError, match="EPOCH_CHECKPOINT_CHANGED"):
        record(checkpoint, {"code": "REPLACEMENT"})
    assert json.loads(checkpoint.read_text()) == {"code": "ORIGINAL"}


def test_invalid_json_keeps_previous_status_and_no_temporary(tmp_path):
    status = tmp_path / "status.json"
    record_status(status, {"code": "RUNNING"})
    with pytest.raises(ValueError):
        record_status(status, {"value": float("nan")})
    assert json.loads(status.read_text()) == {"code": "RUNNING"}
    assert set(tmp_path.iterdir()) == {status}


def test_failed_installation_keeps_previous_report_and_cleans_temp(tmp_path, monkeypatch):
    status = tmp_path / "status.json"
    record_status(status, {"code": "RUNNING"})

    def refuse_installation(*_args):
        raise OSError("injected installation failure")

    monkeypatch.setattr(status_module.os, "replace", refuse_installation)
    with pytest.raises(OSError, match="injected installation failure"):
        record_status(status, {"code": "VALIDATED"})
    assert json.loads(status.read_text()) == {"code": "RUNNING"}
    assert set(tmp_path.iterdir()) == {status}


def test_status_symlink_refuses_without_changing_target(tmp_path):
    target = tmp_path / "target.json"
    record_status(target, {"code": "PROTECTED"})
    status = tmp_path / "status.json"
    status.symlink_to(target)
    with pytest.raises(ValueError, match="ROUND_STATUS_MUST_NOT_BE_SYMLINK"):
        record_status(status, {"code": "REPLACEMENT"})
    assert json.loads(target.read_text()) == {"code": "PROTECTED"}


def smb_warning(identity, device):
    return (
        "lsof: WARNING: can't stat() smbfs file system /Volumes/.timemachine/SquishNAS.local/"
        + identity + "/TimeMachine\n      Output information may be incomplete.\n"
        + f'      assuming "dev={device:x}" from mount table\n'
    )


def test_current_unrelated_mount_warning_allows_only_empty_local_selection(tmp_path, monkeypatch):
    path = tmp_path / "candidate.db"
    path.touch()
    for identity in ["30635E43-5F0D-43CF-AFE6-5D8D783ADE5B", "F9347808-F1D2-4199-93FD-B54A62297E9D"]:
        warning = smb_warning(identity, path.stat().st_dev + 1)
        monkeypatch.setattr(status_module.subprocess, "run", lambda *_args, **_kw: subprocess.CompletedProcess([], 1, "", warning))
        result = status_module.no_open_handles(path)
        assert result["code"] == "NO_OPEN_LOCAL_FILE_MATCHES"
        assert identity in result["unrelated_mount"]["path"]


def test_actual_open_handle_blocks_even_with_unrelated_mount_warning(tmp_path, monkeypatch):
    path = tmp_path / "candidate.db"
    path.touch()
    warning = smb_warning("current", path.stat().st_dev + 1)
    monkeypatch.setattr(status_module.subprocess, "run", lambda *_args, **_kw: subprocess.CompletedProcess([], 0, "p123\nncandidate.db\n", warning))
    with pytest.raises(ValueError, match="CHECKPOINT_OPEN_HANDLE_CHECK_FAILED"):
        status_module.no_open_handles(path)


def test_uninspected_target_device_blocks_retirement(tmp_path, monkeypatch):
    path = tmp_path / "candidate.db"
    path.touch()
    warning = smb_warning("current", path.stat().st_dev)
    monkeypatch.setattr(status_module.subprocess, "run", lambda *_args, **_kw: subprocess.CompletedProcess([], 1, "", warning))
    with pytest.raises(ValueError, match="CHECKPOINT_ON_UNINSPECTED_NETWORK_FILESYSTEM"):
        status_module.no_open_handles(path)


def test_unknown_or_additional_lsof_diagnostic_blocks_retirement(tmp_path, monkeypatch):
    path = tmp_path / "candidate.db"
    path.touch()
    for warning in ["lsof: permission denied\n", smb_warning("current", path.stat().st_dev + 1) + "unexpected\n"]:
        monkeypatch.setattr(status_module.subprocess, "run", lambda *_args, **_kw: subprocess.CompletedProcess([], 1, "", warning))
        with pytest.raises(ValueError, match="CHECKPOINT_OPEN_HANDLE_CHECK_FAILED"):
            status_module.no_open_handles(path)
