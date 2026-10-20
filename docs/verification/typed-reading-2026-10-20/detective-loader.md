# Relative-import target cannot load after a clean regime despite a successful canonical import in the same interpreter

Detective: `9c1276b1f5965ce0bfaf4e6e07851d8ca23b04d9`

Wesker: `9e5023c245b0fe6a55a2bafbff19c6b7f445ed80`

Python: CPython 3.12.12 (macOS arm64). Both tools report version 1.1.1.

Every command below ran with the local checkouts selected by `PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker`, under the target project's own interpreter.

## Verified environment and source

The isolated project uses its own CPython 3.12.12 virtual environment. In that interpreter, `import tools.voice.references` and `import tools.voice.passage` succeeded; their resolved files were the isolated project's `tools/voice/references.py` and `tools/voice/passage.py`. SquishOS resolved to the isolated `src/squishos`, and Detective/Wesker resolved to the declared local tool checkouts. No shadow copy was reported.

The exact installed, staged, validation, and isolated `references.py` bytes matched SHA-256 `2287a01171d964777dc0d05ced37bd6d86bf72d35ef58dead2b744344de2b1f1`. Its actual relative imports are:

```python
from .metrics import METRICS_VERSION, number, profile, select_sentences, source_words
from .passage import freeze
```

This is verified source from the actual module, not a separately executed minimal reduction. The project pytest configuration declares `pythonpath = ["src", "tools/voice"]`, `testpaths = ["tests"]`, and the Detective marker.

## Observed commands and outputs

All tool commands used `PYTHONPATH` pointing to the declared Detective and Wesker checkouts above. This was the same environment used for the successful canonical package import.

Commands below used the same interpreter and project root. Absolute isolated-root paths are normalized to `<project>` in the target-specific JSON transcript.

```sh
.venv/bin/python -m Detective --help
.venv/bin/python -m Detective regime
.venv/bin/python -m Detective diagnose tools/voice/references.py::partition_verdict
```

The initial complete short regime output was:

```text
──────────────────────────────────────────────────────────────────────────────
. — testing regime

  · layout             src
  · suite imports via  src, tools/voice
  · testpaths          tests
  · conftest           (none)
  · detective marker   declared in pyproject.toml

DONE:  this regime resolves cleanly — nothing to migrate. Run `detective audit`,
       `converge`, or `decompose` on a target in it.
```

The following is the complete saved diagnosis transcript copy (including its label and exact printed STOP/Fix block):

```text
Transcript copy of complete stdout returned by exec_command, command:
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/python -m Detective diagnose tools/voice/references.py::partition_verdict
Exit 0; Detective ledger outcome diagnose/fix_load, duration 172283 ms, 2026-10-20T09:10:18Z.

──────────────────────────────────────────────────────────────────────────────
tools/voice/references.py::partition_verdict — diagnose · 127 behaviours · 0 pinned · 127 unpinned

  · test routing       0 candidate · 376 unknown · 0 impossible
                       373 of the unknowns have no static path to this function — not traced (a missed dynamic reacher costs a redundant generated test, never a certificate)
  ✓ value-pinned       0 pin the RETURN VALUE
  ✗ unpinned           127 · ARITHMETIC, BOUNDARY, LOGICAL, STATE, STMT, SWAP, TYPE, VALUE
  · shape              entangled, but structurally one piece — no seam to split
  · parsimony          ⚠ advisory — 3 lenses agree, stylistic (not a proof)
                       overload (127 DOF / 25 ln) · regime (B) · complexity (CC 16)
                       a human/model call — any split still goes through decompose's proof gate

STOP:  the live original could not be loaded: ImportError: attempted relative import with no known parent package

  · Why first          the module would not import, so nothing ran — the counts above
                       are blindness, not a result, and the unpinned behaviours are
                       unpinned because NOTHING could run, not because tests are absent.
  · Not converge       it cannot write a test that runs either; on this target it
                       refuses with the same reason.
  · Fix                run under an interpreter/venv that has the missing dependency
                       (detective regime names the one in use), then: detective diagnose 'tools/voice/references.py::partition_verdict'
```

The diagnosis exited **0**, with the native ledger recording `diagnose/fix_load` and duration 172283 ms. Its counts explicitly state that they are blindness because the live target did not load; they are not a mutation assessment.

I then followed the environment-check direction through documented help and the target-specific regime command:

```sh
.venv/bin/python -m Detective diagnose --help
.venv/bin/python -m Detective regime --help
.venv/bin/python -m Detective regime tools/voice/references.py::partition_verdict --json
```

Complete target-specific JSON transcript, with only absolute project-root paths normalized:

```json
{
  "regime": {
    "root": "<project>",
    "layout": "src",
    "suite_path": [
      "<project>/src",
      "<project>/tools/voice"
    ],
    "testpaths": [
      "tests"
    ],
    "pythonpath": [
      "src",
      "tools/voice"
    ],
    "marker_declared": true,
    "has_config": true,
    "conftests": [],
    "colliding_conftests": [],
    "generated_conftests": [],
    "config_file": "pyproject.toml",
    "root_resolves": false,
    "target": "<project>/tools/voice/references.py",
    "module": "references",
    "shadow": null
  },
  "applied": [],
  "decision": {
    "verb": "regime",
    "code": "clean",
    "route": "",
    "step": {
      "kind": "done",
      "argv": null,
      "then": null,
      "remedy": ""
    },
    "plan": null,
    "residual": null,
    "optional": [],
    "state": {
      "blocked": [],
      "needed": false
    },
    "final": null
  },
  "exit_code": 0,
  "exit_meaning": "clean"
}
```

The target-specific regime reports `clean`, `module: "references"`, `root_resolves: false`, and no shadow. The same interpreter's canonical package import had succeeded. The documented help exposed no loader-name override. No source edit, package marker, import rewrite, or unsupported loading workaround was attempted. Other functions in this module were left unassessed after this module-load prerequisite; no purity or typing conclusion is claimed from the refusal.
