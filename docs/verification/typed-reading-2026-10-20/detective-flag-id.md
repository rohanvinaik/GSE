# Prescribed flag command rejects a surviving two-sign OUTPUT mutant ID

Detective: `9c1276b1f5965ce0bfaf4e6e07851d8ca23b04d9`

Wesker: `9e5023c245b0fe6a55a2bafbff19c6b7f445ed80`

Python: CPython 3.12.12 (macOS arm64). Both tools report version 1.1.1.

Every command below ran with the local checkouts selected by `PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker`, under the target project's own interpreter.

## Observed sequence

All tool commands used `PYTHONPATH` pointing to the declared Detective and Wesker checkouts above; the virtual environment did not supply a different installed tool copy.

All commands used one clean isolated project and the same interpreter. `regime` resolved cleanly. Canonical import of the target succeeded. The assessed `tools/voice/passage.py` SHA-256 was `ba9a0a1e46b615f945ced68a293105fc4be0bfb20ec1052b9aae2771ffb47e6b`; its bytes did not change between convergence and flagging. Interpreter spelling below is normalized to the project-relative `.venv/bin/python`; the tool arguments are preserved.

The completed two-sign convergence command had this argv (JSON array, preserving each literal input as one argument):

```json
[
  ".venv/bin/python",
  "-m",
  "Detective",
  "converge",
  "tools/voice/passage.py::supported_key",
  "--two-sign",
  "--full",
  "--verbose",
  "--input",
  "({'claim_key': {'state': 'supported', 'key': ['gse.claim/1', ['type', 'fish'], [['entity', ['referent', None, 'trout']]], []]}},)",
  "--input",
  "({'key_state': 'supported', 'key': ['gse.claim/1', ['type', 'fish'], [['entity', ['referent', None, 'trout']]], []]},)",
  "--input",
  "({'claim_key': {'state': 'unsupported', 'key': ['gse.claim/1', ['type', 'fish'], [['entity', ['referent', None, 'trout']]], []]}},)",
  "--input",
  "({'claim_key': {'state': 'supported', 'key': ['gse.claim/1', ['type', 'fish'], [['entity', ['referent', None, 'trout']]]]}},)",
  "--input",
  "({'claim_key': {'state': 'supported', 'key': ['gse.claim/1', ['type', 'fish'], [['entity', ['referent', None, 'trout']]], [], None]}},)",
  "--input",
  "({'claim_key': {'state': 'supported', 'key': ['wrong', ['type', 'fish'], [['entity', ['referent', None, 'trout']]], []]}},)",
  "--input",
  "({'claim_key': {'state': 'supported', 'key': {0: 'gse.claim/1', 1: ['type', 'fish'], 2: [['entity', ['referent', None, 'trout']]], 3: []}}},)",
  "--input",
  "({'claim_key': {'state': 'supported', 'key': None}},)",
  "--input",
  "({'claim_key': {'state': 'supported'}, 'key': ['gse.claim/1', ['type', 'fish'], [['entity', ['referent', None, 'trout']]], []]},)",
  "--input",
  "({'claim_key': {'key': ['gse.claim/1', ['type', 'fish'], [['entity', ['referent', None, 'trout']]], []]}, 'key_state': 'supported'},)",
  "--input",
  "({'claim_key': {'state': 'unsupported', 'key': ['gse.claim/1', ['type', 'fish'], [['entity', ['referent', None, 'trout']]], []]}, 'key_state': 'supported'},)"
]
```

Its full report listed these surviving candidates, among others:

```text
    → mutant OUTPUT_09171603 [OUTPUT]: - return None  + return type(None)()
    → mutant OUTPUT_92682da6 [OUTPUT]: - return None  + return type(None)()
```

The report explicitly prescribed:

```text
  ▶ boundary-probed and still undistinguished — if you can PROVE one equivalent, record it: `detective flag 'tools/voice/passage.py::supported_key' OUTPUT_09171603 --note "why-equivalent"`   (repeat for: OUTPUT_92682da6, STATE_23855936, STATE_050f518a)
```

I ran the prescribed native command with an explicit proof note:

```sh
.venv/bin/python -m Detective flag tools/voice/passage.py::supported_key OUTPUT_09171603 --note 'The full survivor record changes only line 53 return None to return type(None)(). The whole module has no binding shadowing builtin type. type(None) is NoneType and NoneType() returns the same singleton None without reading the input or changing control flow. Thus every call reaching this branch has the same None return; calls not reaching it are unchanged. This proof uses the ordinary builtins environment of the frozen module, not adversarial monkeypatching of builtins.'
```

Complete short stdout:

```text
no surviving mutant 'OUTPUT_09171603' for supported_key — survivors: STATE_23855936, STATE_050f518a, SWAP_3e339752, SWAP_7c5d0202
```

Complete short stderr:

```text
  … supported_key: tracing 8 function-routed tests
  … supported_key: baseline traced · 8 tests · 0.0s
```

The flag command exited **1**. `flag --help` did not expose a `--two-sign` option. The standard STATE mutant `STATE_23855936` was subsequently accepted through native `flag`; the OUTPUT proof was not recorded. I did not hand-edit equivalence metadata or infer that the refused proof had been accepted. Only `OUTPUT_09171603` was attempted; rejection of the second OUTPUT ID has not been measured.

## Relevant verified source

These are the complete functions from the frozen assessed file. This source is verified; an independently reduced standalone reproducer has **not** been run, and IDs above refer to the original target.

```python
from __future__ import annotations

def freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((key, freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value

def supported_key(claim: dict):
    evidence = claim.get("claim_key", {})
    if evidence.get("state", claim.get("key_state")) != "supported":
        return None
    key = evidence.get("key", claim.get("key"))
    if not isinstance(key, (list, tuple)) or len(key) != 4 or key[0] != "gse.claim/1":
        return None
    return freeze(key)
```

Full convergence stdout/stderr, exact original argv, and the flag refusal are retained in the local evidence bundle. No tool repair or package-layout workaround was performed. The reported issue is the mismatch between the surviving ID named by convergence's prescribed command and the ID accepted by that command.
