"""Cell-level comparison of two lexicon-builder builds of the same 1,040 gate words.

old = replay of the recorded baseline commit d2c2e52   (/tmp/gse-subagents/replay/old)
new = the current lexicon-builder worktree build       (/tmp/gse-subagents/replay/new)

Facts only. Nothing here judges whether a difference is right.

Writes, all under /tmp/gse-subagents/replay/:
  comparison.json               complete (never a sample)
  comparison_summary.json       counts
  cells_by_cause.txt            every changed cell in readings present in both builds, grouped by the data's cause
  cells_by_cause_compact.txt    the same groups with cells and reading lists compressed (no information dropped)
  new_only_readings_compact.txt readings present only in the new build, compressed per word
  removed_readings.txt          every reading present only in the old build
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/tmp/gse-subagents/replay")
OLD = ROOT / "old"
NEW = ROOT / "new"
BASELINE_GATE = ROOT / "d2c2e52" / "docs" / "verification" / "lexicon-rebuild" / "closeout-2026-10-25" / "gate"
ABSENT = "<absent>"
NO_FIRED_RULE_CHANGE = "NO_FIRED_RULE_CHANGE"
NO_TRACE = "(no restricting rule in trace)"
CELL_MIRROR_KEYS = ("symbolic_before", "after_closure")


# ---------------------------------------------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------------------------------------------
def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def canon(value) -> str:
    """Key-order-free JSON, the same canonical form the gate hashes."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def state_label(domain) -> str:
    """A cell's state: its single value if resolved, else UNRESOLVED[...] over the remaining domain."""
    if domain == ABSENT:
        return ABSENT
    if not domain:
        return "EMPTY_DOMAIN[]"
    if len(domain) == 1:
        return domain[0]
    return "UNRESOLVED[" + "|".join(domain) + "]"


def dumps_compact(value, indent: int = 0) -> str:
    """Valid JSON; a dict whose values are scalars or lists of scalars, and a list of scalars, stay on one line."""

    def flat(v) -> bool:
        return all(not isinstance(x, (dict, list)) for x in v)

    pad, inner = " " * indent, " " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        if all(not isinstance(v, dict) and (not isinstance(v, list) or flat(v)) for v in value.values()):
            return json.dumps(value, ensure_ascii=False)
        items = [f"{inner}{json.dumps(k, ensure_ascii=False)}: {dumps_compact(v, indent + 1)}" for k, v in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if flat(value):
            return json.dumps(value, ensure_ascii=False)
        return "[\n" + ",\n".join(inner + dumps_compact(v, indent + 1) for v in value) + "\n" + pad + "]"
    return json.dumps(value, ensure_ascii=False)


def rows(counter: Counter, names: tuple) -> list[dict]:
    result = []
    for key, n in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        key = key if isinstance(key, tuple) else (key,)
        result.append({**dict(zip(names, key, strict=True)), "count": n})
    return result


def ranges(numbers: list[int]) -> str:
    nums = sorted(set(numbers))
    out: list[tuple[int, int]] = []
    for n in nums:
        if out and n == out[-1][1] + 1:
            out[-1] = (out[-1][0], n)
        else:
            out.append((n, n))
    return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


# ---------------------------------------------------------------------------------------------------------------
# readings
# ---------------------------------------------------------------------------------------------------------------
def id_parts(word: str, reading_id: str) -> dict:
    """Strip the word by length (never by splitting on ':'); a reading_id not led by the word is kept whole."""
    lead = word + ":"
    leading = reading_id.startswith(lead)
    rest = reading_id[len(lead) :] if leading else reading_id
    parts = rest.split(":")
    return {"word_is_leading": leading, "rest": rest, "prefix1": parts[0], "prefix2": ":".join(parts[:2])}


def frame_split(word: str, reading_id: str):
    """('VERB:class', n) for '<word>:VERB:class:frame-n' ids, else None."""
    head, sep, tail = reading_id.rpartition(":frame-")
    if sep and tail.isdigit() and head.startswith(word + ":"):
        return head[len(word) + 1 :], int(tail)
    return None


def forced_pattern(forced: dict) -> str:
    return ",".join(f"{c}={v}" for c, v in forced.items()) or "(none)"


def reading_info(word: str, r: dict) -> dict:
    p = id_parts(word, r["reading_id"])
    rule_id = r.get("rule_id", ABSENT)
    sel = r.get("after_selection")
    ok = isinstance(sel, dict)
    return {
        "reading_id": r["reading_id"],
        "code": r.get("code", ABSENT),
        "source_scope": r.get("source_scope", ABSENT),
        "rule_id": rule_id,
        "rule_id_family": rule_id.split(":", 1)[0] if rule_id != ABSENT else ABSENT,
        "word_is_leading_in_reading_id": p["word_is_leading"],
        "prefix1": p["prefix1"],
        "prefix2": p["prefix2"],
        "fired_rules": list(sel.get("fired_rules", [])) if ok else ABSENT,
        "resolved_cells": dict(sel["forced"]) if ok else ABSENT,
        "unresolved_cell_count": sum(len(d) > 1 for d in sel["domains"].values()) if ok else ABSENT,
    }


def index_readings(readings: list[dict]):
    """(reading_id, occurrence) -> reading; occurrence only exceeds 0 if a reading_id repeats inside a word."""
    seen: Counter = Counter()
    indexed: dict = {}
    duplicates = []
    for r in readings:
        rid = r["reading_id"]
        occurrence = seen[rid]
        seen[rid] += 1
        if occurrence:
            duplicates.append(rid)
        indexed[(rid, occurrence)] = r
    return indexed, duplicates


# ---------------------------------------------------------------------------------------------------------------
# cells, traces, fired rules
# ---------------------------------------------------------------------------------------------------------------
def trace_by_coordinate(sel: dict) -> dict:
    by: dict = defaultdict(list)
    for t in sel.get("trace") or []:
        by[t["coordinate"]].append((t["rule"], "|".join(t["remaining"])))
    return by


def trace_label(tr_old: list, tr_new: list, same_label: str) -> str:
    """+R: R restricts this coordinate only in the new trace. -R: only in the old trace.
    ~R: R restricts it in both but leaves a different remaining domain."""
    old_rules, new_rules = [r for r, _ in tr_old], [r for r, _ in tr_new]
    newly = sorted(set(new_rules) - set(old_rules))
    gone = sorted(set(old_rules) - set(new_rules))
    shifted = sorted(
        r
        for r in set(old_rules) & set(new_rules)
        if sorted({rem for rr, rem in tr_old if rr == r}) != sorted({rem for rr, rem in tr_new if rr == r})
    )
    parts = [f"+{r}" for r in newly] + [f"-{r}" for r in gone] + [f"~{r}" for r in shifted]
    return " ".join(parts) if parts else same_label


def fmt_trace(tr: list) -> list[str]:
    return [f"{r}->{rem}" for r, rem in tr]


def diff_cells(sel_old: dict, sel_new: dict) -> list[dict]:
    dom_o, dom_n = sel_old["domains"], sel_new["domains"]
    tr_o, tr_n = trace_by_coordinate(sel_old), trace_by_coordinate(sel_new)
    out = []
    for c in list(dom_o) + [c for c in dom_n if c not in dom_o]:
        a, b = dom_o.get(c, ABSENT), dom_n.get(c, ABSENT)
        if a == b:
            continue
        out.append(
            {
                "coordinate": c,
                "old_domain": a,
                "new_domain": b,
                "old_state": state_label(a),
                "new_state": state_label(b),
                "same_states_different_order": a != ABSENT and b != ABSENT and sorted(a) == sorted(b),
                "old_trace": fmt_trace(tr_o.get(c, [])),
                "new_trace": fmt_trace(tr_n.get(c, [])),
                "cause": trace_label(tr_o.get(c, []), tr_n.get(c, []), "TRACE_UNCHANGED_FOR_COORDINATE"),
            }
        )
    return out


def diff_trace_only(sel_old: dict, sel_new: dict) -> list[dict]:
    """Cells whose domain is identical in both builds but whose restricting-rule trace differs."""
    dom_o, dom_n = sel_old["domains"], sel_new["domains"]
    tr_o, tr_n = trace_by_coordinate(sel_old), trace_by_coordinate(sel_new)
    out = []
    for c in dom_o:
        if c not in dom_n or dom_o[c] != dom_n[c]:
            continue
        a, b = tr_o.get(c, []), tr_n.get(c, [])
        if a != b:
            out.append(
                {
                    "coordinate": c,
                    "state": state_label(dom_o[c]),
                    "old_trace": fmt_trace(a),
                    "new_trace": fmt_trace(b),
                    "cause": trace_label(a, b, "TRACE_ORDER_OR_MULTIPLICITY_ONLY"),
                }
            )
    return out


def diff_fired(fr_o: list, fr_n: list) -> dict:
    so, sn = set(fr_o), set(fr_n)
    d = {
        "added": sorted(sn - so),
        "removed": sorted(so - sn),
        "count_changed": {r: [fr_o.count(r), fr_n.count(r)] for r in sorted(so & sn) if fr_o.count(r) != fr_n.count(r)},
        "order_changed_only": fr_o != fr_n and Counter(fr_o) == Counter(fr_n),
    }
    d["changed"] = bool(d["added"] or d["removed"] or d["count_changed"] or d["order_changed_only"])
    if d["changed"]:
        d["old"], d["new"] = list(fr_o), list(fr_n)
    return d


def fired_signature(d: dict) -> str:
    if not d["changed"]:
        return NO_FIRED_RULE_CHANGE
    parts = []
    if d["added"]:
        parts.append("added=" + ",".join(d["added"]))
    if d["removed"]:
        parts.append("removed=" + ",".join(d["removed"]))
    if d["count_changed"]:
        parts.append("count_changed=" + ",".join(f"{r}({a}->{b})" for r, (a, b) in d["count_changed"].items()))
    if d["order_changed_only"]:
        parts.append("order_changed_only")
    return "; ".join(parts)


def cell_key(c: dict) -> tuple:
    return (c["coordinate"], c["old_state"], c["new_state"])


# ---------------------------------------------------------------------------------------------------------------
# other keys (names always; contents for bindings / unmapped / small keys)
# ---------------------------------------------------------------------------------------------------------------
def list_diff(o: list, n: list, brief) -> dict:
    co, cn = Counter(canon(x) for x in o), Counter(canon(x) for x in n)
    return {
        "count": [len(o), len(n)],
        "only_in_old": [brief(x) for x in o if co[canon(x)] > cn[canon(x)]],
        "only_in_new": [brief(x) for x in n if cn[canon(x)] > co[canon(x)]],
    }


def binding_brief(b: dict) -> dict:
    return {
        "coordinate": b.get("coordinate"),
        "allowed": b.get("allowed"),
        "rule_ids": b.get("rule_ids"),
        "roles": b.get("roles"),
        "selected_predicates": b.get("selected_predicates"),
        "negated_only": b.get("negated_only"),
    }


def predicate_name(u: dict) -> str:
    pred = (u.get("native") or {}).get("predicate") or {}
    return ("!" if pred.get("bool") == "!" else "") + str(pred.get("value"))


def unmapped_diff(o: list, n: list) -> dict:
    by_o = {u.get("predicate_index"): u for u in o}
    by_n = {u.get("predicate_index"): u for u in n}
    unique = len(by_o) == len(o) and len(by_n) == len(n)
    brief = lambda u: {"predicate_index": u.get("predicate_index"), "code": u.get("code"), "predicate": predicate_name(u)}  # noqa: E731
    both = [i for i in by_o if i in by_n]
    return {
        "count": [len(o), len(n)],
        "predicate_index_unique": unique,
        "removed": [brief(by_o[i]) for i in by_o if i not in by_n],
        "added": [brief(by_n[i]) for i in by_n if i not in by_o],
        "code_changed": [
            {"predicate_index": i, "predicate": predicate_name(by_o[i]), "old_code": by_o[i].get("code"), "new_code": by_n[i].get("code")}
            for i in both
            if by_o[i].get("code") != by_n[i].get("code")
        ],
        "other_content_changed_predicate_indexes": [
            i
            for i in both
            if canon({k: v for k, v in by_o[i].items() if k != "code"}) != canon({k: v for k, v in by_n[i].items() if k != "code"})
        ],
    }


def other_key_detail(name: str, o, n):
    if name == "bindings" and isinstance(o, list) and isinstance(n, list):
        return list_diff(o, n, binding_brief)
    if name == "unmapped" and isinstance(o, list) and isinstance(n, list):
        return unmapped_diff(o, n)
    return {"old": o, "new": n}


# ---------------------------------------------------------------------------------------------------------------
# pair / record comparison
# ---------------------------------------------------------------------------------------------------------------
def compare_pair(key: tuple, o: dict, n: dict) -> dict:
    a_o, a_n = o.get("after_selection"), n.get("after_selection")
    entry: dict = {
        "reading_id": key[0],
        "occurrence": key[1],
        "source_scope": {"old": o.get("source_scope", ABSENT), "new": n.get("source_scope", ABSENT)},
        "rule_id": {"old": o.get("rule_id", ABSENT), "new": n.get("rule_id", ABSENT)},
        "reading_keys_added": [k for k in n if k not in o],
        "reading_keys_removed": [k for k in o if k not in n],
        "reading_code": [o.get("code"), n.get("code")] if o.get("code") != n.get("code") else None,
        "other_top_level_keys_differ": sorted(
            k
            for k in o
            if k in n and k not in ("reading_id", "code", "after_selection") and canon(o[k]) != canon(n[k])
        ),
    }
    entry["other_keys_detail"] = {
        k: other_key_detail(k, o[k], n[k]) for k in entry["other_top_level_keys_differ"] if k not in CELL_MIRROR_KEYS
    }
    entry["added_key_values"] = {k: n[k] for k in entry["reading_keys_added"]}
    if isinstance(a_o, dict) and isinstance(a_n, dict):
        entry["after_selection_code"] = [a_o.get("code"), a_n.get("code")] if a_o.get("code") != a_n.get("code") else None
        entry["after_selection_keys_differ"] = sorted(
            k for k in list(a_o) + [k for k in a_n if k not in a_o] if canon(a_o.get(k)) != canon(a_n.get(k))
        )
        entry["fired_rules"] = diff_fired(list(a_o.get("fired_rules", [])), list(a_n.get("fired_rules", [])))
        entry["cells_changed"] = diff_cells(a_o, a_n)
        entry["cells_unchanged_but_restricting_trace_changed"] = diff_trace_only(a_o, a_n)
    else:
        entry["after_selection_code"] = None
        entry["after_selection_keys_differ"] = [f"not comparable: old {type(a_o).__name__}, new {type(a_n).__name__}"]
        entry["fired_rules"] = {"added": [], "removed": [], "count_changed": {}, "order_changed_only": False, "changed": False}
        entry["cells_changed"] = []
        entry["cells_unchanged_but_restricting_trace_changed"] = []
    for name in CELL_MIRROR_KEYS:
        so, sn = o.get(name), n.get(name)
        if isinstance(so, dict) and isinstance(sn, dict) and "domains" in so and "domains" in sn:
            sc = diff_cells(so, sn)
            if not sc:
                entry[f"{name}_cells_changed"] = "NONE"
            elif [cell_key(c) for c in sc] == [cell_key(c) for c in entry["cells_changed"]]:
                entry[f"{name}_cells_changed"] = "SAME_AS_AFTER_SELECTION"
            else:
                entry[f"{name}_cells_changed"] = sc
        else:
            entry[f"{name}_cells_changed"] = "NOT_COMPARABLE" if canon(so) != canon(sn) else "NONE"
    entry["any_difference"] = bool(
        entry["reading_keys_added"]
        or entry["reading_keys_removed"]
        or entry["reading_code"]
        or entry["other_top_level_keys_differ"]
        or entry["after_selection_keys_differ"]
        or entry["cells_changed"]
        or entry["fired_rules"]["changed"]
    )
    entry["json_differs"] = canon(o) != canon(n)
    return entry


def compare_record(word: str, o: dict, n: dict) -> dict:
    rec: dict = {"word": word}
    rec["record_keys_added"] = [k for k in n if k not in o]
    rec["record_keys_removed"] = [k for k in o if k not in n]
    shared = [k for k in o if k in n]
    rec["record_fields_changed"] = [k for k in shared if canon(o[k]) != canon(n[k])]
    rec["record_code"] = [o["code"], n["code"]] if o["code"] != n["code"] else None
    rec["record_json_identical"] = canon(o) == canon(n)
    rec["differs_only_by_added_keys"] = (
        not rec["record_fields_changed"] and not rec["record_keys_removed"] and bool(rec["record_keys_added"])
    )
    if "structural_entries" in n and "structural_entries" not in o:
        rec["structural_entries_new"] = n["structural_entries"]
    if "withheld_unadmitted_writes" in rec["record_fields_changed"]:
        rec["withheld_unadmitted_writes_diff"] = list_diff(
            o["withheld_unadmitted_writes"],
            n["withheld_unadmitted_writes"],
            lambda w: {
                "family": w.get("family"),
                "reading_id": w.get("reading_id"),
                "rule_ids": w.get("rule_ids"),
                "review_states": w.get("review_states"),
                "would_write": w.get("would_write"),
            },
        )
    if "unhandled_native_alternatives" in rec["record_fields_changed"]:
        rec["unhandled_native_alternatives_diff"] = list_diff(
            o["unhandled_native_alternatives"], n["unhandled_native_alternatives"], lambda u: u
        )
    oidx, odup = index_readings(o["readings"])
    nidx, ndup = index_readings(n["readings"])
    rec["duplicate_reading_ids"] = {"old": odup, "new": ndup}
    only_old = [k for k in oidx if k not in nidx]
    only_new = [k for k in nidx if k not in oidx]
    both = [k for k in oidx if k in nidx]
    rec["readings_count"] = {"old": len(o["readings"]), "new": len(n["readings"]), "paired": len(both)}
    rec["readings_only_in_old"] = [reading_info(word, oidx[k]) for k in only_old]
    rec["readings_only_in_new"] = [reading_info(word, nidx[k]) for k in only_new]
    pairs = [compare_pair(k, oidx[k], nidx[k]) for k in both]
    rec["paired_readings_changed"] = [p for p in pairs if p["any_difference"] or p["json_differs"]]
    rec["paired_readings_unchanged"] = [p["reading_id"] for p in pairs if not (p["any_difference"] or p["json_differs"])]
    return rec


# ---------------------------------------------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------------------------------------------
def source_lock(manifest: dict) -> dict:
    return {
        s["source"]: {"status": s["status"], "files": {f["id"]: f["sha256"] for f in s["files"]}}
        for s in manifest["sources"]
    }


def manifest_diff(mo: dict, mn: dict, baseline_lock: dict) -> dict:
    out: dict = {}
    out["top_level_keys"] = {
        "only_in_old": [k for k in mo if k not in mn],
        "only_in_new": [k for k in mn if k not in mo],
    }
    skip = ("sources", "implementation", "admission", "words", "coordinate_order")
    out["scalar_keys_that_differ"] = {
        k: {"old": mo[k], "new": mn[k]} for k in mo if k in mn and k not in skip and mo[k] != mn[k]
    }
    out["values_only_in_new"] = {k: mn[k] for k in mn if k not in mo}
    out["values_only_in_old"] = {k: mo[k] for k in mo if k not in mn}
    out["words_equal"] = mo["words"] == mn["words"]
    out["coordinate_order_equal"] = mo["coordinate_order"] == mn["coordinate_order"]
    out["basis_id"] = {"old": mo["basis_id"], "new": mn["basis_id"]}
    lock_o, lock_n = source_lock(mo), source_lock(mn)
    out["source_lock"] = {
        "old_equals_new": lock_o == lock_n,
        "old_equals_recorded_baseline_lock": lock_o == baseline_lock,
        "new_equals_recorded_baseline_lock": lock_n == baseline_lock,
        "sources_structure_incl_paths_equal": mo["sources"] == mn["sources"],
    }
    io, inn = mo["implementation"], mn["implementation"]
    out["implementation"] = {
        "only_in_old": sorted(set(io) - set(inn)),
        "only_in_new": sorted(set(inn) - set(io)),
        "changed": sorted(f for f in set(io) & set(inn) if io[f] != inn[f]),
        "unchanged": sorted(f for f in set(io) & set(inn) if io[f] == inn[f]),
    }
    ao, an = mo["admission"], mn["admission"]
    fams = list(ao["admitted"]) + [f for f in an["admitted"] if f not in ao["admitted"]]
    adm: dict = {"policy": {"old": ao["policy"], "new": an["policy"]}, "families": {}}
    for fam in fams:
        aa, na = set(ao["admitted"].get(fam, [])), set(an["admitted"].get(fam, []))
        aw, nw = set(ao["withheld"].get(fam, [])), set(an["withheld"].get(fam, []))
        adm["families"][fam] = {
            "admitted_old_count": len(aa),
            "admitted_new_count": len(na),
            "admitted_added": sorted(na - aa),
            "admitted_removed": sorted(aa - na),
            "withheld_old_count": len(aw),
            "withheld_new_count": len(nw),
            "withheld_added": sorted(nw - aw),
            "withheld_removed": sorted(aw - nw),
        }
    out["admission"] = adm
    return out


def forced_consistent(sel: dict) -> bool:
    return sel.get("forced") == {c: d[0] for c, d in sel["domains"].items() if len(d) == 1}


def build_files(path: Path) -> list[dict]:
    result = []
    for f in sorted(path.iterdir()):
        entry = {"file": f.name, "bytes": f.stat().st_size}
        if f.suffix == ".jsonl":
            entry["lines"] = len(f.read_text(encoding="utf-8").splitlines())
        result.append(entry)
    return result


# ---------------------------------------------------------------------------------------------------------------
# text listings
# ---------------------------------------------------------------------------------------------------------------
def compress_cells(cells: list[dict]) -> list[str]:
    groups: dict = defaultdict(list)
    for c in cells:
        groups[(c["old_state"], c["new_state"], c["cause"])].append(c["coordinate"])
    return [f"{','.join(coords)}: {old} -> {new}   [{cause}]" for (old, new, cause), coords in groups.items()]


def compress_trace_only(items: list[dict]) -> list[str]:
    groups: dict = defaultdict(list)
    for c in items:
        groups[(c["state"], tuple(c["old_trace"]), tuple(c["new_trace"]), c["cause"])].append(c["coordinate"])
    return [
        f"{','.join(coords)}: {state} -> {state} (domain unchanged)   old trace: {'; '.join(ot) or NO_TRACE} | new trace: {'; '.join(nt) or NO_TRACE}   [{cause}]"
        for (state, ot, nt, cause), coords in groups.items()
    ]


def compress_readings(items: list[tuple[str, str]]) -> list[str]:
    """One line per word: frame readings as 'VERB:class frames a-b', other readings by full id."""
    per_word: dict = {}
    for word, rid in items:
        slot = per_word.setdefault(word, {"frames": {}, "plain": []})
        fs = frame_split(word, rid)
        if fs is None:
            slot["plain"].append(rid)
        else:
            slot["frames"].setdefault(fs[0], []).append(fs[1])
    lines = []
    for word, slot in per_word.items():
        parts = [f"{cls} frames {ranges(nums)}" for cls, nums in slot["frames"].items()] + slot["plain"]
        lines.append(f"    {word}: " + "; ".join(parts))
    return lines


def other_detail_summary(members: list) -> list[str]:
    """Aggregate, over a group's readings, what changed inside bindings / unmapped / other differing keys."""
    unm_removed, unm_added, unm_code, bind_new, bind_old, others = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    for _, p in members:
        for k, d in p["other_keys_detail"].items():
            if k == "unmapped":
                for u in d["removed"]:
                    unm_removed[(u["code"], u["predicate"])] += 1
                for u in d["added"]:
                    unm_added[(u["code"], u["predicate"])] += 1
                for u in d["code_changed"]:
                    unm_code[(u["old_code"], u["new_code"], u["predicate"])] += 1
            elif k == "bindings":
                for b in d["only_in_new"]:
                    bind_new[(b["coordinate"], ",".join(b["rule_ids"] or []))] += 1
                for b in d["only_in_old"]:
                    bind_old[(b["coordinate"], ",".join(b["rule_ids"] or []))] += 1
            else:
                others[k] += 1
    lines = []
    if bind_new:
        lines.append("  bindings only in new (coordinate, rule_ids): " + "; ".join(f"{c}/{r} x{n}" for (c, r), n in sorted(bind_new.items())))
    if bind_old:
        lines.append("  bindings only in old (coordinate, rule_ids): " + "; ".join(f"{c}/{r} x{n}" for (c, r), n in sorted(bind_old.items())))
    if unm_removed:
        lines.append("  unmapped entries only in old (code, predicate): " + "; ".join(f"{c}/{p} x{n}" for (c, p), n in sorted(unm_removed.items())))
    if unm_added:
        lines.append("  unmapped entries only in new (code, predicate): " + "; ".join(f"{c}/{p} x{n}" for (c, p), n in sorted(unm_added.items())))
    if unm_code:
        lines.append("  unmapped entries whose code changed (old -> new, predicate): " + "; ".join(f"{a} -> {b} / {p} x{n}" for (a, b, p), n in sorted(unm_code.items())))
    for k, n in sorted(others.items()):
        lines.append(f"  key {k} differs in {n} reading(s) (old/new values in comparison.json)")
    return lines


def main() -> None:
    old_records = load_jsonl(OLD / "words.jsonl")
    new_records = load_jsonl(NEW / "words.jsonl")
    old_by = {r["word"]: r for r in old_records}
    new_by = {r["word"]: r for r in new_records}
    assert len(old_by) == len(old_records) and len(new_by) == len(new_records), "duplicate words"
    words_only_old = [w for w in old_by if w not in new_by]
    words_only_new = [w for w in new_by if w not in old_by]
    word_order_equal = [r["word"] for r in old_records] == [r["word"] for r in new_records]

    mo = json.loads((OLD / "manifest.json").read_text())
    mn = json.loads((NEW / "manifest.json").read_text())
    baseline_lock = json.loads((BASELINE_GATE / "sources.lock.json").read_text())
    mdiff = manifest_diff(mo, mn, baseline_lock)

    records = [compare_record(w, old_by[w], new_by[w]) for w in old_by if w in new_by]

    # ---- sanity ----------------------------------------------------------------------------------------------
    sanity = {
        "forced_inconsistent_with_domains": {"old": 0, "new": 0},
        "paired_readings_where_categorized_difference_disagrees_with_json_difference": 0,
        "after_selection_objects_checked": {"old": 0, "new": 0},
    }
    for label, recs in (("old", old_records), ("new", new_records)):
        for r in recs:
            for x in r["readings"]:
                sel = x.get("after_selection")
                if isinstance(sel, dict):
                    sanity["after_selection_objects_checked"][label] += 1
                    if not forced_consistent(sel):
                        sanity["forced_inconsistent_with_domains"][label] += 1
    for rec in records:
        for p in rec["paired_readings_changed"]:
            if p["any_difference"] != p["json_differs"]:
                sanity["paired_readings_where_categorized_difference_disagrees_with_json_difference"] += 1

    # ---- the gate's own report for the new build --------------------------------------------------------------
    frozen = NEW / "frozen_report.json"
    if frozen.exists():
        fr = json.loads(frozen.read_text())
        differing_words = [r["word"] for r in records if not r["record_json_identical"]]
        sanity["gate_frozen_report_for_new_build"] = {
            "status": fr.get("status"),
            "summary_changed": fr.get("summary_changed"),
            "word_list_changed": fr.get("word_list_changed"),
            "baseline_records": fr.get("baseline_records"),
            "current_records": fr.get("current_records"),
            "changed_records_listed": len(fr.get("changed_records", [])),
            "changed_records_equal_words_whose_record_json_differs_in_this_comparison": fr.get("changed_records") == differing_words,
        }

    # ---- aggregates ------------------------------------------------------------------------------------------
    S: dict = {}
    S["builds"] = {
        "old": {
            "records": len(old_records),
            "readings": sum(len(r["readings"]) for r in old_records),
            "summary_json": json.loads((OLD / "summary.json").read_text()),
            "files": build_files(OLD),
        },
        "new": {
            "records": len(new_records),
            "readings": sum(len(r["readings"]) for r in new_records),
            "summary_json": json.loads((NEW / "summary.json").read_text()),
            "files": build_files(NEW),
        },
        "word_lists_equal_and_same_order": word_order_equal,
        "words_only_in_old": words_only_old,
        "words_only_in_new": words_only_new,
    }
    status_rows = Counter(
        (
            bool(old_by[r["word"]]["readings"]),
            bool(r["paired_readings_changed"]),
            bool(r["readings_only_in_new"]),
            bool(r["readings_only_in_old"]),
        )
        for r in records
    )
    S["records"] = {
        "joined": len(records),
        "json_identical": sum(r["record_json_identical"] for r in records),
        "json_different": sum(not r["record_json_identical"] for r in records),
        "keys_added": rows(Counter(k for r in records for k in r["record_keys_added"]), ("key",)),
        "keys_removed": rows(Counter(k for r in records for k in r["record_keys_removed"]), ("key",)),
        "shared_fields_whose_value_differs": rows(
            Counter(k for r in records for k in r["record_fields_changed"]), ("field",)
        ),
        "differ_only_by_added_keys": sum(r["differs_only_by_added_keys"] for r in records),
        "differ_only_by_added_keys_which": rows(
            Counter(tuple(r["record_keys_added"]) for r in records if r["differs_only_by_added_keys"]), ("added_keys",)
        ),
        "record_code_transitions": rows(
            Counter((old_by[r["word"]]["code"], new_by[r["word"]]["code"]) for r in records), ("old_code", "new_code")
        ),
        "records_by_reading_status": rows(
            status_rows,
            ("had_old_readings", "has_changed_paired_readings", "has_readings_only_in_new", "has_readings_only_in_old"),
        ),
        "records_with_structural_entries_in_new": sum(bool(r.get("structural_entries_new")) for r in records),
        "structural_entries_new_total": sum(len(r.get("structural_entries_new", [])) for r in records),
        "structural_entries_new_by_code": rows(
            Counter(e.get("code") for r in records for e in r.get("structural_entries_new", [])), ("code",)
        ),
        "withheld_unadmitted_writes_changed_records": sum("withheld_unadmitted_writes_diff" in r for r in records),
        "withheld_unadmitted_writes_only_in_old": rows(
            Counter(
                (w["family"], ",".join(w["rule_ids"] or []))
                for r in records
                for w in r.get("withheld_unadmitted_writes_diff", {}).get("only_in_old", [])
            ),
            ("family", "rule_ids"),
        ),
        "withheld_unadmitted_writes_only_in_new": rows(
            Counter(
                (w["family"], ",".join(w["rule_ids"] or []))
                for r in records
                for w in r.get("withheld_unadmitted_writes_diff", {}).get("only_in_new", [])
            ),
            ("family", "rule_ids"),
        ),
        "unhandled_native_alternatives_changed": [
            {"word": r["word"], **r["unhandled_native_alternatives_diff"]}
            for r in records
            if "unhandled_native_alternatives_diff" in r
        ],
    }

    only_new = [(r["word"], i) for r in records for i in r["readings_only_in_new"]]
    only_old = [(r["word"], i) for r in records for i in r["readings_only_in_old"]]
    paired_changed = [(r["word"], p) for r in records for p in r["paired_readings_changed"]]
    paired_total = sum(r["readings_count"]["paired"] for r in records)
    dup_old = sum(len(r["duplicate_reading_ids"]["old"]) for r in records)
    dup_new = sum(len(r["duplicate_reading_ids"]["new"]) for r in records)

    def group_readings(items: list) -> dict:
        return {
            "total": len(items),
            "by_source_scope": rows(Counter(i["source_scope"] for _, i in items), ("source_scope",)),
            "by_reading_id_prefix1": rows(Counter(i["prefix1"] for _, i in items), ("prefix1",)),
            "by_source_scope_and_prefix1": rows(
                Counter((i["source_scope"], i["prefix1"]) for _, i in items), ("source_scope", "prefix1")
            ),
            "by_reading_id_prefix2": rows(Counter(i["prefix2"] for _, i in items), ("prefix2",)),
            "by_source_scope_and_rule_id_family": rows(
                Counter((i["source_scope"], i["rule_id_family"]) for _, i in items), ("source_scope", "rule_id_family")
            ),
            "by_code": rows(Counter((i["source_scope"], i["code"]) for _, i in items), ("source_scope", "code")),
            "by_source_scope_prefix1_and_resolved_cells": rows(
                Counter((i["source_scope"], i["prefix1"], forced_pattern(i["resolved_cells"])) for _, i in items),
                ("source_scope", "prefix1", "resolved_cells"),
            ),
            "by_source_scope_and_unresolved_cell_count": rows(
                Counter((i["source_scope"], i["unresolved_cell_count"]) for _, i in items),
                ("source_scope", "unresolved_cell_count"),
            ),
            "reading_id_not_led_by_word": sum(not i["word_is_leading_in_reading_id"] for _, i in items),
            "readings_in_which_each_rule_fired": rows(
                Counter(rule for _, i in items for rule in sorted(set(i["fired_rules"])) if i["fired_rules"] != ABSENT),
                ("rule",),
            ),
            "readings_with_no_fired_rule": sum(i["fired_rules"] == [] for _, i in items),
        }

    S["readings"] = {
        "old_total": S["builds"]["old"]["readings"],
        "new_total": S["builds"]["new"]["readings"],
        "paired_in_both": paired_total,
        "only_in_old": group_readings(only_old),
        "only_in_new": group_readings(only_new),
        "duplicate_reading_ids_within_a_word": {"old": dup_old, "new": dup_new},
    }

    pair_scope = Counter()
    pair_scope_changed = Counter()
    for rec in records:
        for p in rec["paired_readings_changed"]:
            pair_scope_changed[p["source_scope"]["old"]] += 1
    for w, r in old_by.items():
        if w not in new_by:
            continue
        new_ids = {x["reading_id"] for x in new_by[w]["readings"]}
        for x in r["readings"]:
            if x["reading_id"] in new_ids:
                pair_scope[x.get("source_scope", ABSENT)] += 1
    cells_all = [(w, p, c) for w, p in paired_changed for c in p["cells_changed"]]
    trace_only_all = [(w, p, c) for w, p in paired_changed for c in p["cells_unchanged_but_restricting_trace_changed"]]
    sig_counter = Counter(fired_signature(p["fired_rules"]) for _, p in paired_changed)
    sig_scope_counter = Counter((p["source_scope"]["old"], fired_signature(p["fired_rules"])) for _, p in paired_changed)
    added_rule_counter = Counter(rule for _, p in paired_changed for rule in p["fired_rules"]["added"])
    removed_rule_counter = Counter(rule for _, p in paired_changed for rule in p["fired_rules"]["removed"])

    def detail_counts(kind: str) -> dict:
        un_removed, un_added, un_code, b_new, b_old = Counter(), Counter(), Counter(), Counter(), Counter()
        for _, p in paired_changed:
            d = p["other_keys_detail"].get(kind)
            if d is None:
                continue
            if kind == "unmapped":
                un_removed.update((u["code"], u["predicate"]) for u in d["removed"])
                un_added.update((u["code"], u["predicate"]) for u in d["added"])
                un_code.update((u["old_code"], u["new_code"], u["predicate"]) for u in d["code_changed"])
            else:
                b_new.update((b["coordinate"], ",".join(b["rule_ids"] or [])) for b in d["only_in_new"])
                b_old.update((b["coordinate"], ",".join(b["rule_ids"] or [])) for b in d["only_in_old"])
        if kind == "unmapped":
            return {
                "entries_only_in_old": rows(un_removed, ("code", "predicate")),
                "entries_only_in_new": rows(un_added, ("code", "predicate")),
                "code_changed": rows(un_code, ("old_code", "new_code", "predicate")),
            }
        return {
            "entries_only_in_new": rows(b_new, ("coordinate", "rule_ids")),
            "entries_only_in_old": rows(b_old, ("coordinate", "rule_ids")),
        }

    S["paired_readings"] = {
        "total": paired_total,
        "by_source_scope_old": [
            {
                "source_scope": s,
                "paired": n,
                "changed": pair_scope_changed.get(s, 0),
                "unchanged": n - pair_scope_changed.get(s, 0),
            }
            for s, n in sorted(pair_scope.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "changed": len(paired_changed),
        "unchanged": paired_total - len(paired_changed),
        "changed_grouped_by_fired_rules_added_removed": rows(sig_counter, ("fired_rules_delta",)),
        "changed_grouped_by_source_scope_and_fired_rules_delta": rows(
            sig_scope_counter, ("source_scope", "fired_rules_delta")
        ),
        "readings_in_which_each_rule_was_added": rows(added_rule_counter, ("rule",)),
        "readings_in_which_each_rule_was_removed": rows(removed_rule_counter, ("rule",)),
        "reading_code_changes": rows(
            Counter((tuple(p["reading_code"]) if p["reading_code"] else ("(unchanged)",)) for _, p in paired_changed),
            ("old_new_code",),
        ),
        "after_selection_code_changes": rows(
            Counter(
                (tuple(p["after_selection_code"]) if p["after_selection_code"] else ("(unchanged)",))
                for _, p in paired_changed
            ),
            ("old_new_code",),
        ),
        "other_top_level_keys_differ": rows(
            Counter(k for _, p in paired_changed for k in p["other_top_level_keys_differ"]), ("key",)
        ),
        "reading_keys_added": rows(Counter(k for _, p in paired_changed for k in p["reading_keys_added"]), ("key",)),
        "reading_keys_removed": rows(Counter(k for _, p in paired_changed for k in p["reading_keys_removed"]), ("key",)),
        "after_selection_keys_differ": rows(
            Counter(k for _, p in paired_changed for k in p["after_selection_keys_differ"]), ("key",)
        ),
        "changed_readings_with_cell_change": sum(bool(p["cells_changed"]) for _, p in paired_changed),
        "changed_readings_with_no_cell_change": sum(not p["cells_changed"] for _, p in paired_changed),
        "changed_readings_with_trace_change_but_no_cell_change": sum(
            (not p["cells_changed"]) and "trace" in p["after_selection_keys_differ"] for _, p in paired_changed
        ),
        "symbolic_before_cells_changed": rows(
            Counter(
                v if isinstance(v, str) else "OTHER" for v in (p["symbolic_before_cells_changed"] for _, p in paired_changed)
            ),
            ("value",),
        ),
        "after_closure_cells_changed": rows(
            Counter(v if isinstance(v, str) else "OTHER" for v in (p["after_closure_cells_changed"] for _, p in paired_changed)),
            ("value",),
        ),
        "unmapped_changes": detail_counts("unmapped"),
        "bindings_changes": detail_counts("bindings"),
        "coverage_gap_changes": [
            {"word": w, "reading_id": p["reading_id"], **p["other_keys_detail"]["coverage_gap"]}
            for w, p in paired_changed
            if "coverage_gap" in p["other_keys_detail"]
        ],
        "reading_keys_added_values": rows(
            Counter((k, canon(v)) for _, p in paired_changed for k, v in p["added_key_values"].items()),
            ("key", "value_json"),
        ),
    }
    S["cells"] = {
        "changed_cells_total": len(cells_all),
        "readings_with_changed_cells": sum(bool(p["cells_changed"]) for _, p in paired_changed),
        "cells_with_same_states_different_order": sum(c["same_states_different_order"] for _, _, c in cells_all),
        "by_coordinate": rows(Counter(c["coordinate"] for _, _, c in cells_all), ("coordinate",)),
        "by_old_state_to_new_state": rows(
            Counter((c["old_state"], c["new_state"]) for _, _, c in cells_all), ("old_state", "new_state")
        ),
        "by_coordinate_old_state_new_state": rows(
            Counter(cell_key(c) for _, _, c in cells_all), ("coordinate", "old_state", "new_state")
        ),
        "by_cause": rows(Counter(c["cause"] for _, _, c in cells_all), ("cause",)),
        "by_cause_and_old_state_new_state": rows(
            Counter((c["cause"], c["old_state"], c["new_state"]) for _, _, c in cells_all),
            ("cause", "old_state", "new_state"),
        ),
        "by_source_scope": rows(Counter(p["source_scope"]["old"] for _, p, _ in cells_all), ("source_scope",)),
        "by_source_scope_and_cause": rows(
            Counter((p["source_scope"]["old"], c["cause"]) for _, p, c in cells_all), ("source_scope", "cause")
        ),
        "unchanged_domain_but_restricting_trace_changed_total": len(trace_only_all),
        "unchanged_domain_but_restricting_trace_changed_by_coordinate_and_cause": rows(
            Counter((c["coordinate"], c["state"], c["cause"]) for _, _, c in trace_only_all),
            ("coordinate", "state", "cause"),
        ),
    }

    fired_old = Counter(rule for r in old_records for x in r["readings"] for rule in set(x["after_selection"]["fired_rules"]))
    fired_new = Counter(rule for r in new_records for x in r["readings"] for rule in set(x["after_selection"]["fired_rules"]))
    S["fired_rules_over_all_readings"] = [
        {"rule": rule, "readings_in_old_build": fired_old.get(rule, 0), "readings_in_new_build": fired_new.get(rule, 0)}
        for rule in sorted(set(fired_old) | set(fired_new))
    ]
    S["fired_rules_summary"] = {
        "rules_fired_only_in_new_build_count": len(set(fired_new) - set(fired_old)),
        "rules_fired_only_in_old_build": sorted(set(fired_old) - set(fired_new)),
        "rules_fired_in_both_builds": sorted(set(fired_old) & set(fired_new)),
        "rules_fired_only_in_new_build_by_family": rows(
            Counter(r.split(":", 1)[0] for r in set(fired_new) - set(fired_old)), ("rule_family_before_first_colon",)
        ),
        "rules_fired_only_in_new_build_without_colon": sorted(r for r in set(fired_new) - set(fired_old) if ":" not in r),
        "rules_fired_only_in_new_build_with_NATIVE_prefix": sorted(r for r in set(fired_new) - set(fired_old) if r.startswith("NATIVE:")),
    }
    S["manifest_diff"] = mdiff
    S["sanity"] = sanity
    S["definitions"] = {
        "old": "replay of baseline commit d2c2e52 at /tmp/gse-subagents/replay/old (frozen build check: IDENTICAL)",
        "new": "current lexicon-builder worktree build at /tmp/gse-subagents/replay/new",
        "cell": "one coordinate of one reading's after_selection.domains; a cell changed when its list of remaining states differs",
        "cell_state": "'+1' '-1' '0' 'empty' when the domain has exactly one state; UNRESOLVED[a|b|c] when several states remain",
        "paired_reading": "same reading_id (and same occurrence index if an id repeats) inside the same word in both builds",
        "reading_id_prefix": "rest = reading_id[len(word)+1:] if reading_id starts with word+':' else the whole reading_id; "
        "prefix1 = rest.split(':')[0]; prefix2 = ':'.join(rest.split(':')[:2])",
        "absent_bucket": "'<absent>' marks a key a reading does not carry (e.g. adjective source-rule readings have no source_scope; head-contract readings have no rule_id)",
        "fired_rules_delta": "set difference of after_selection.fired_rules (added = in new only, removed = in old only); "
        "count_changed lists rules present in both with a different number of occurrences; "
        "order_changed_only = same multiset in a different order; NO_FIRED_RULE_CHANGE when none of these",
        "cell_cause": "derived from after_selection.trace entries (rule, coordinate, remaining) for that coordinate: "
        "+RULE = restricts the coordinate only in the new trace; -RULE = only in the old trace; "
        "~RULE = restricts it in both but with a different remaining domain; TRACE_UNCHANGED_FOR_COORDINATE otherwise",
        "unchanged_domain_but_restricting_trace_changed": "coordinate whose domain list is identical in both builds but whose trace entries differ; same +/-/~ notation",
        "changed_paired_reading": "a paired reading whose sorted-key JSON differs between the builds",
        "resolved_cells": "after_selection.forced of a reading: the coordinates whose domain holds exactly one state",
    }

    # ---- write JSON ------------------------------------------------------------------------------------------
    full = {
        "meta": {
            "definitions": S["definitions"],
            "old_dir": str(OLD),
            "new_dir": str(NEW),
            "record_count": len(records),
        },
        "manifest_diff": mdiff,
        "sanity": sanity,
        "records": records,
    }
    (ROOT / "comparison.json").write_text(dumps_compact(full) + "\n", encoding="utf-8")
    (ROOT / "comparison_summary.json").write_text(dumps_compact(S) + "\n", encoding="utf-8")
    assert json.loads((ROOT / "comparison.json").read_text(encoding="utf-8")) == json.loads(json.dumps(full))
    assert json.loads((ROOT / "comparison_summary.json").read_text(encoding="utf-8")) == json.loads(json.dumps(S))

    # ---- groups of identical change patterns --------------------------------------------------------------------
    groups: dict = defaultdict(list)
    for w, p in paired_changed:
        key = (
            fired_signature(p["fired_rules"]),
            json.dumps(p["reading_code"]),
            json.dumps(p["after_selection_code"]),
            tuple(p["reading_keys_added"]),
            tuple(p["reading_keys_removed"]),
            tuple(p["other_top_level_keys_differ"]),
            tuple(p["after_selection_keys_differ"]),
            tuple(
                (c["coordinate"], c["old_state"], c["new_state"], tuple(c["old_trace"]), tuple(c["new_trace"]))
                for c in p["cells_changed"]
            ),
            tuple(
                (c["coordinate"], c["state"], tuple(c["old_trace"]), tuple(c["new_trace"]))
                for c in p["cells_unchanged_but_restricting_trace_changed"]
            ),
        )
        groups[key].append((w, p))
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    header = [
        "CHANGED CELLS IN READINGS PRESENT IN BOTH BUILDS (old = d2c2e52 replay, new = current worktree)",
        f"paired readings: {paired_total}; changed paired readings: {len(paired_changed)}; changed cells: {len(cells_all)}; "
        f"cells with unchanged domain but changed restricting-rule trace: {len(trace_only_all)}",
        f"groups (readings sharing identical fired-rule delta, code changes, differing keys, cell changes and trace-only changes): {len(ordered)}",
        "cell state: single value if resolved, else UNRESOLVED[remaining states]. trace notation: RULE->remaining state(s).",
        "cause: +RULE restricts the coordinate only in the new trace; -RULE only in the old trace; ~RULE both, different remaining.",
        "",
    ]

    def group_head(gi: int, key: tuple, members: list) -> list[str]:
        sig, rcode, scode, kadd, krem, other, selkeys, cells, trace_only = key
        scopes = Counter(
            p["source_scope"]["old"]
            + (" -> " + p["source_scope"]["new"] if p["source_scope"]["old"] != p["source_scope"]["new"] else "")
            for _, p in members
        )
        added_values = Counter(canon(v) for _, p in members for v in p["added_key_values"].values())
        lines = [
            "=" * 110,
            f"GROUP {gi}: {len(members)} reading(s); {len(cells)} changed cell(s) per reading; "
            f"{len(trace_only)} unchanged-domain cell(s) with changed trace; source_scope: {dict(scopes)}",
            f"  fired rules delta        : {sig}",
            f"  reading code             : {'unchanged' if rcode == 'null' else rcode}",
            f"  after_selection code     : {'unchanged' if scode == 'null' else scode}",
            f"  reading keys added       : {list(kadd) or 'none'}" + (f" (values: {dict(added_values)})" if added_values else ""),
            f"  reading keys removed     : {list(krem) or 'none'}",
            f"  other top-level keys that differ: {list(other) or 'none'}",
            f"  after_selection keys that differ: {list(selkeys) or 'none'}",
        ]
        lines.extend(other_detail_summary(members))
        return lines

    # full listing ------------------------------------------------------------------------------------------------
    lines = list(header)
    for gi, (key, members) in enumerate(ordered, 1):
        lines.extend(group_head(gi, key, members))
        example = members[0][1]
        if example["cells_changed"]:
            lines.append("  changed cells (identical in every reading of the group):")
            for c in example["cells_changed"]:
                old_t = "; ".join(c["old_trace"]) or NO_TRACE
                new_t = "; ".join(c["new_trace"]) or NO_TRACE
                lines.append(
                    f"    {c['coordinate']}: {c['old_state']} -> {c['new_state']}   | cause {c['cause']} | old trace: {old_t} | new trace: {new_t}"
                )
        else:
            lines.append("  changed cells: none")
        if example["cells_unchanged_but_restricting_trace_changed"]:
            lines.append("  cells with unchanged domain but changed restricting-rule trace (identical in every reading of the group):")
            for c in example["cells_unchanged_but_restricting_trace_changed"]:
                old_t = "; ".join(c["old_trace"]) or NO_TRACE
                new_t = "; ".join(c["new_trace"]) or NO_TRACE
                lines.append(f"    {c['coordinate']}: {c['state']} (unchanged) | cause {c['cause']} | old trace: {old_t} | new trace: {new_t}")
        lines.append("  readings:")
        for w, p in members:
            lines.append(f"    {w} | {p['reading_id']}")
        lines.append("")
    (ROOT / "cells_by_cause.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # compact listing ---------------------------------------------------------------------------------------------
    clines = list(header)
    for gi, (key, members) in enumerate(ordered, 1):
        clines.extend(group_head(gi, key, members))
        example = members[0][1]
        clines.append("  changed cells (identical in every reading of the group):")
        clines.extend("    " + s for s in compress_cells(example["cells_changed"]) or ["none"])
        if example["cells_unchanged_but_restricting_trace_changed"]:
            clines.append("  unchanged-domain cells whose restricting-rule trace changed (identical in every reading of the group):")
            clines.extend("    " + s for s in compress_trace_only(example["cells_unchanged_but_restricting_trace_changed"]))
        clines.append(f"  readings ({len(members)}), per word:")
        clines.extend(compress_readings([(w, p["reading_id"]) for w, p in members]))
        clines.append("")
    (ROOT / "cells_by_cause_compact.txt").write_text("\n".join(clines) + "\n", encoding="utf-8")

    # new-only readings, compressed per word ----------------------------------------------------------------------
    nl = [f"READINGS PRESENT ONLY IN THE NEW BUILD: {len(only_new)} (frames compressed as class frames a-b)", ""]
    per_word_new: dict = defaultdict(list)
    for w, i in only_new:
        per_word_new[w].append(i)
    for w, infos in per_word_new.items():
        nl.append(f"{w}   [record code {old_by[w]['code']} -> {new_by[w]['code']}]")
        by_scope: dict = defaultdict(list)
        for i in infos:
            by_scope[i["source_scope"]].append(i)
        for scope, items in by_scope.items():
            if scope == "LEMMA_POS_HEAD_CONTRACT":
                nl.append(f"    {scope}: " + ", ".join(i["prefix1"] for i in items))
            elif scope == "NATIVE_CLASS_FRAME":
                nl.extend(compress_readings([(w, i["reading_id"]) for i in items]))
            else:
                nl.append(f"    {scope}: " + "; ".join(f"{i['reading_id']} [{i['code']}; rule {i['rule_id']}]" for i in items))
        nl.append("")
    (ROOT / "new_only_readings_compact.txt").write_text("\n".join(nl) + "\n", encoding="utf-8")

    # removed readings ----------------------------------------------------------------------------------------------
    rl = [f"READINGS PRESENT ONLY IN THE OLD BUILD: {len(only_old)}", "word | reading_id | code | source_scope | rule_id | fired_rules", ""]
    for w, i in only_old:
        rl.append(
            f"{w} | {i['reading_id']} | {i['code']} | {i['source_scope']} | {i['rule_id']} | {','.join(i['fired_rules']) if i['fired_rules'] != ABSENT else ABSENT}"
        )
    (ROOT / "removed_readings.txt").write_text("\n".join(rl) + "\n", encoding="utf-8")

    print("records joined", len(records), "paired", paired_total, "changed paired", len(paired_changed), "cells", len(cells_all))
    print("trace-only cells", len(trace_only_all), "only_old", len(only_old), "only_new", len(only_new), "groups", len(ordered))
    print("sanity", json.dumps(sanity))


if __name__ == "__main__":
    main()
