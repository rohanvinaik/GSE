"""The epoch CLI exposes the existing bounded transport context configuration."""

import hashlib
import json

import pytest

from scripts import run_lexicon_epochs as cli


@pytest.mark.parametrize("requested,expected", [(None, 65536), (81920, 81920)])
def test_real_cli_forwards_context_and_preserves_default(tmp_path, monkeypatch, requested, expected):
    baseline, pointer, plan_path = (tmp_path / name for name in ("baseline.db", "active.json", "plan.json"))
    baseline.write_bytes(b"fixture; model construction precedes database traversal")
    pointer.write_text("fixture")
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    plan_path.write_text(json.dumps({
        "format": "GSE.lexicon-epoch-plan/1", "baseline_sha256": digest(baseline),
        "active_pointer_sha256": digest(pointer), "epochs": 1, "audits_per_epoch": 1,
        "families": [{"id": "body", "antecedent": ["ALIVE", 1], "consequent": ["BODY", 1],
                      "guards": [["pos", "noun"], ["wordnet_native_lemma", "true"], ["wordnet_ancestor:vertebrate.n.01", "true"]],
                      "holdouts": ["held"], "warrant": {}}],
    }))

    class ReachedTransport(Exception):
        pass

    def capture(model, **options):
        assert model == "fixture" and options["context_tokens"] == expected
        assert options["thinking"] is False and options["output_tokens"] == 256
        raise ReachedTransport

    args = ["epoch", "run", "--plan", str(plan_path), "--baseline", str(baseline),
            "--directory", str(tmp_path / "run"), "--policy", "zipf", "--model", "fixture",
            "--model-digest", "a" * 64]
    if requested is not None:
        args.extend(["--model-context-tokens", str(requested)])
    monkeypatch.setattr(cli, "ACTIVE_POINTER", pointer)
    monkeypatch.setattr(cli, "OllamaTransport", capture)
    monkeypatch.setattr("sys.argv", args)
    with pytest.raises(ReachedTransport):
        cli.main()
