"""Typed pattern VARIABLES for GSE — the Genesis rule-authoring extension.

Genesis commonsense rules use typed pattern variables ("If a person harms a king then ..."),
but spaCy mangles placeholder tokens (X, XX) before GSE's symbolic core sees them. So a variable
is substituted BEFORE the parse with a clean sentinel noun (which parses as a distinct, empty-thread
entity), then restored to a typed variable-ref in the emit contract — leaving the deterministic
pipeline (encode → resolve → emit) entirely unchanged.

Two authoring formats, one mechanism:

  Winston (human):  declarations `X is a person.` + rules `If X harms Y then Y harms X.`
                    → call with variables={"X": "person", "Y": "person"}
  Inline (scripts): `${x:founder} exposes ${y:pain}` → self-described; no external map needed.

Each DISTINCT variable name → a distinct sentinel, so same-name mentions coref into one variable,
while two distinct names of the same type stay distinct (the dual format's payoff). The declared
TYPE's WordNet thread is attached on restore — the sentinel itself contributes none — which is the
guard version-space generalization climbs.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# Sentinels: must parse as clean, DISTINCT NOUN entities across any verb. Verified: pure-nonce
# `ent…` tokens stay reliably NOUN (NATO words like "bravo" get mis-tagged as verbs; digits/
# underscores break the parse). Collision with real rule vocab is avoided at substitution time.
_SENTINELS = [
    "entzero", "entone", "enttwo", "entthree", "entfour", "entfive", "entsix", "entseven",
    "enteight", "entnine", "entten", "enteleven", "enttwelve", "entthirteen", "entfourteen",
]
_INLINE = re.compile(r"\$\{(\w+):(\w+)\}")


def substitute(text: str, variables: Optional[dict] = None) -> tuple[str, dict]:
    """`text` + declared `variables` → (substituted_text, {sentinel: (var_name, var_type)}).

    Absorbs inline `${name:type}` markers into the variable set, then replaces each distinct
    variable name (whole-word) with its own sentinel. Distinct names → distinct sentinels.
    """
    merged: dict[str, str] = {}
    for m in _INLINE.finditer(text):                       # inline ${name:type}
        merged.setdefault(m.group(1), m.group(2))
    text = _INLINE.sub(lambda m: m.group(1), text)         # unwrap ${x:person} → x
    for name, vtype in (variables or {}).items():
        merged.setdefault(name, vtype)

    sentinel_map: dict[str, tuple[str, str]] = {}
    pool = [s for s in _SENTINELS if not re.search(rf"\b{s}\b", text)]   # avoid collisions
    for i, (name, vtype) in enumerate(merged.items()):
        if i >= len(pool):
            raise ValueError(f"too many variables (>{len(pool)}) in one clause")
        sent = pool[i]
        sentinel_map[sent] = (name, vtype)
        text = re.sub(rf"\b{re.escape(name)}\b", sent, text)
    return text, sentinel_map


def restore(contract: Any, sentinel_map: dict) -> Any:
    """Walk the emit contract; replace each sentinel entity-ref with a typed variable-ref:
    `lemma="$name"`, `type_thread=[declared_type]` (the guard version-space climbs), plus
    `variable`/`var_type` fields. The declared type is the guard — no WordNet thread (which
    mis-senses, e.g. "founder"→horse-laminitis); a story `king` carries `person` in *its* thread,
    so the version-space match happens there."""
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            lemma = node.get("lemma")
            if isinstance(lemma, str) and lemma in sentinel_map:
                name, vtype = sentinel_map[lemma]
                node = {**node, "lemma": f"${name}", "type_thread": [vtype],
                        "variable": name, "var_type": vtype}
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(contract)


def emit_contract_with_variables(encoder, text: str, variables: Optional[dict] = None) -> Any:
    """The variable-aware emit: substitute declared variables → run the unchanged GSE pipeline →
    restore typed variable-refs. `encoder` is a live `gse.api.GSEEncoder`."""
    from gse.symbolic import from_trace, resolve, evaluate_tree, resolve_references, GenealogyStore
    from gse.symbolic.emit import emit_contract

    sub_text, sentinel_map = substitute(text, variables)
    tree = evaluate_tree(resolve(from_trace(encoder.encode(sub_text))))
    resolved = resolve_references(tree, GenealogyStore())
    contract = emit_contract(resolved)
    return restore(contract, sentinel_map)
