#!/usr/bin/env python3
"""RohanVoice v2: separately versioned nearest-centroid consumer of GSE evidence.

Fit only an explicit hash-pinned label/split manifest; no private corpus is read
by default. Old models require refitting. Dense-vector/cosine paths are removed.
The inherited feature formulas are a bounded compatibility projection, separate
from the complete source-agnostic voice instrument owned by SquishOS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from gse.lexical_evidence import lookup_lexeme, resource_identity
from gse.nlp.native import NativeNLP
from gse.primitives_v2 import get_all_primitives, get_bank_for_primitive

GSE_REPO = Path(__file__).resolve().parents[1]
MODEL = GSE_REPO / "data" / "voice" / "model.v2.json"
SCHEMA = "gse.rohan-voice/2"
FEATURES = "gse.rohan-voice-features/2"
MANIFEST = "gse.rohan-voice-sources/2"
VOICE_WEIGHT = 2.5
BANK_MAP = {p: bank.name for p in get_all_primitives() if (bank := get_bank_for_primitive(p)) is not None}
BANKS = ["SUBSTANTIVES", "MENTAL", "ACTION", "EVALUATORS", "LOGICAL", "QUANTITY", "TEMPORAL", "SPATIAL"]
CURATED = ["FEEL", "WANT", "THINK", "KNOW", "SAY", "GOOD", "BAD", "DO", "HAPPEN", "SEE", "BIG", "CAN", "GET", "PEOPLE"]
LABELS = frozenset({"authored", "personal", "llm"})

_1P = re.compile(r"\b(i|me|my|mine|myself|i'?m|i'?ve|i'?d|i'?ll)\b", re.I)
_2P = re.compile(r"\b(you|your|yours|you'?re|you'?ll|you'?ve|you'?d)\b", re.I)
_META = re.compile(
    r"\b(let me (?:walk|explain|break|focus|show|dive|clarify|conduct|help|start|unpack)|"
    r"here'?s (?:a|how|the|what|why|my)|below is|i'?ll (?:help|focus|walk|conduct|explain|show|start|dive|break)|"
    r"great question|you'?re (?:absolutely )?(?:right|onto)|to summari|in summary|"
    r"does that (?:make sense|help)|happy to help|i can help|feel free|let'?s (?:dive|break|explore|start|walk))\b",
    re.I,
)
_ENTH = re.compile(r"^\W*(fantastic|excellent|absolutely|certainly|perfect|wonderful|great)\b", re.I | re.M)


def _lexicon_path() -> Path:
    root = Path(os.environ.get("GSE_REPO", str(GSE_REPO)))
    return Path(os.environ.get("GSE_LEXICON", str(root / "data" / "lexicon_clean.db")))


def _model_path() -> Path:
    return Path(os.environ.get("GSE_REPO", str(GSE_REPO))) / "data" / "voice" / "model.v2.json"


def _style_features(banks: dict) -> dict:
    g = lambda k: banks.get(k, 0.0)  # noqa: E731
    return {
        "formality": round(min(1.0, (g("LOGICAL") + g("QUANTITY")) / 2 + (1 - g("EVALUATORS")) / 2), 3),
        "technicality": round(min(1.0, (g("LOGICAL") + g("QUANTITY") + g("SUBSTANTIVES")) / 3), 3),
        "emotionality": round(min(1.0, (g("EVALUATORS") + g("MENTAL")) / 2), 3),
        "narrative_strength": round(min(1.0, (g("TEMPORAL") + g("SPATIAL") + g("ACTION")) / 3), 3),
        "abstract_thinking": round(min(1.0, (g("MENTAL") + g("LOGICAL")) / 2), 3),
        "action_orientation": round(g("ACTION"), 3),
    }


def _mean_std(rows, i, n):
    col = [r[i] for r in rows]
    m = sum(col) / n
    sd = (sum((x - m) ** 2 for x in col) / n) ** 0.5 or 1e-9
    return m, sd


def feature_identity() -> dict:
    """Every code/data input of this explicit feature projection."""
    from nltk import __version__ as nltk_version
    from nltk.corpus import wordnet as wn

    from gse import lexical_evidence, primitives_v2
    from gse.nlp import contractions, morphology, native

    code_paths = [
        Path(__file__).resolve(),
        *(
            Path(module.__file__).resolve()
            for module in (native, morphology, contractions, primitives_v2, lexical_evidence)
        ),
    ]
    try:
        wordnet_path = getattr(getattr(wn.root, "zipfile", None), "filename", None)
        wordnet = {
            "version": wn.get_version(),
            "resource": resource_identity(wordnet_path)
            if wordnet_path
            else {"state": "unread", "reason": "unhashed_wordnet_directory", "path": str(wn.root)},
        }
    except (LookupError, OSError) as exc:
        wordnet = {"state": "unread", "reason": type(exc).__name__}
    return {
        "features": FEATURES,
        "banks": BANKS,
        "curated": CURATED,
        "voice_weight": VOICE_WEIGHT,
        "tokens": "NativeNLP alphabetic surfaces length>=3; selected lemma first-ID; unsigned prime presence",
        "lexicon": resource_identity(_lexicon_path()),
        "wordnet": wordnet,
        "nltk": nltk_version,
        "code": [resource_identity(path) for path in code_paths],
    }


def featurize(text: str) -> dict:
    """Versioned legacy feature projection with explicit lexical populations."""
    tokens = [token for token in NativeNLP()(text) if token.text.isalpha() and len(token.text) >= 3]
    nw = len(tokens)
    if not nw:
        return {"state": "empty", "reason": "no_eligible_source_words", "features": FEATURES}
    prim, bank = defaultdict(int), defaultdict(float)
    populations = {state: 0 for state in ("primes", "no_primes", "no_row", "unread")}
    selected = {}
    for token in tokens:
        if token.lemma_ not in selected:
            selected[token.lemma_] = lookup_lexeme(token.lemma_, _lexicon_path())
        reading = selected[token.lemma_]
        populations[reading["state"]] += 1
        for prime in reading["primitives"]:
            prim[prime] += 1
            if prime in BANK_MAP:
                bank[BANK_MAP[prime]] += 1
    nwp, bank_total = populations["primes"], sum(bank.values())
    if not nwp or not bank_total or populations["unread"]:
        return {
            "state": "unread",
            "reason": "incomplete_lexical_features",
            "features": FEATURES,
            "populations": populations,
        }
    bank_sig = {name: round(bank.get(name, 0) / bank_total, 4) for name in BANKS}
    onep, twop = len(_1P.findall(text)) / nw, len(_2P.findall(text)) / nw
    meta, enth = len(_META.findall(text)) / nw, len(_ENTH.findall(text)) / max(1, text.count("\n") + 1)
    return {
        "state": "read",
        "features": FEATURES,
        "populations": populations,
        "bank": [bank_sig[name] for name in BANKS],
        "dist": [prim.get(prime, 0) / nwp for prime in CURATED],
        "voice": [onep, twop, meta, enth],
        "bank_sig": bank_sig,
        "style_features": _style_features(bank_sig),
        "markers": {
            "first_person_pct": round(onep * 100, 2),
            "second_person_pct": round(twop * 100, 2),
            "assistant_framing_per1k": round(meta * 1000, 2),
            "opening_enthusiasm_pct": round(enth * 100, 2),
        },
    }


def _vector(features: dict) -> list[float]:
    return features["bank"] + features["dist"] + features["voice"]


def _decision(model: dict, features: dict) -> dict:
    vec = _vector(features)
    z = [
        ((value - model["stats"][index][0]) / model["stats"][index][1])
        * (model["voice_weight"] if index >= model["nfeat"] - model["nv"] else 1)
        for index, value in enumerate(vec)
    ]
    distances = {label: math.dist(z, center) for label, center in model["centroids"].items()}
    if any(not math.isfinite(distance) for distance in distances.values()):
        return {
            "state": "abstained",
            "voice": None,
            "reason": "nonfinite_projection",
            "distances": None,
            "scores": {},
            "is_rohan": None,
        }
    minimum = min(distances.values())
    winners = [label for label, distance in distances.items() if distance == minimum]
    weights = {label: math.exp(minimum - distance) for label, distance in distances.items()}
    total = sum(weights.values())
    scores = {label: round(weight / total, 3) for label, weight in weights.items()}
    return {
        "state": "identified" if len(winners) == 1 else "abstained",
        "voice": winners[0] if len(winners) == 1 else None,
        "reason": "nearest_centroid" if len(winners) == 1 else "tied_centroids",
        "distances": distances,
        "scores": scores,
        "score_definition": "normalized exp(-distance), not calibrated probability",
        "is_rohan": round(scores.get("authored", 0) + scores.get("personal", 0), 3),
    }


def _source_metadata_code(record) -> str:
    if not isinstance(record, dict):
        return "malformed_source_record"
    if "group" not in record:
        return "independence_groups_required"
    if "selection" not in record:
        return "selection_evidence_required"
    if (
        set(record) != {"path", "label", "split", "sha256", "group", "selection"}
        or not isinstance(record["path"], str)
        or not record["path"]
        or not isinstance(record["label"], str)
        or record["label"] not in LABELS
        or record["split"] not in ("train", "holdout")
        or not isinstance(record["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
        or not isinstance(record["group"], str)
        or not record["group"].strip()
    ):
        return "malformed_source_record"
    selected = record["selection"]
    if (
        not isinstance(selected, dict)
        or selected.get("method") not in ("human_review", "unfiltered", "recognizer")
        or selected["method"] == "recognizer"
        and (
            not isinstance(selected.get("artifact_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", selected["artifact_sha256"])
        )
    ):
        return "malformed_selection_evidence"
    return "source_metadata_valid"


def _source_group_code(sources) -> str:
    if not isinstance(sources, list):
        return "malformed_source_records"
    groups, paths, hashes = {}, set(), set()
    for record in sources:
        code = _source_metadata_code(record)
        if code != "source_metadata_valid":
            return code
        group, split = record["group"], record["split"]
        if group in groups and groups[group] != split:
            return "source_group_partition_overlap"
        groups[group] = split
        if record["path"] in paths or record["sha256"] in hashes:
            return "duplicate_source_or_content"
        paths.add(record["path"])
        hashes.add(record["sha256"])
        if record["selection"]["method"] == "recognizer" and split == "holdout":
            return "selection_evaluation_overlap"
    return "disjoint_declared_groups"


def _evaluation(model: dict) -> dict:
    """The retained holdout grade is conditional on declared source groups."""
    return {
        "state": "heldout",
        "independence": "declared_source_groups",
        "policy": "gse.rohan-source-groups/1",
        "per_class": model["holdout"],
        "groups": {source["group"]: source["split"] for source in model["sources"]},
        "selection_policy": "recognizer_selected_sources_train_only",
    }


def _manifest(path: Path) -> tuple[dict, list[dict]]:
    document = json.loads(path.read_bytes().decode("utf-8"))
    if (
        not isinstance(document, dict)
        or document.get("schema") != MANIFEST
        or not isinstance(document.get("sources"), list)
    ):
        raise ValueError("malformed_manifest")
    code = _source_group_code(document["sources"])
    if code != "disjoint_declared_groups":
        raise ValueError(code)
    sources, seen_paths, seen_hashes = [], set(), set()
    for record in document["sources"]:
        source = (path.parent / record["path"]).resolve()
        if source in seen_paths or record["sha256"] in seen_hashes:
            raise ValueError("duplicate_source_or_content")
        seen_paths.add(source)
        seen_hashes.add(record["sha256"])
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("source_hash_mismatch")
        text = raw.decode("utf-8")
        sources.append({**record, "path": str(source), "text": text})
    labels = {record["label"] for record in sources}
    if len(labels) < 2 or any(
        not any(record["label"] == label and record["split"] == split for record in sources)
        for label in labels
        for split in ("train", "holdout")
    ):
        raise ValueError("training_and_holdout_required_per_class")
    return document, sources


def fit(manifest_path: str | Path | None = None, *, model_path: str | Path | None = None) -> dict:
    """Fit only an explicit source/label/split manifest; train statistics exclude holdout."""
    if manifest_path is None:
        return {"state": "refused", "reason": "explicit_manifest_required", "schema": SCHEMA}
    path, output = Path(manifest_path).resolve(), Path(model_path or _model_path()).resolve()
    try:
        _, sources = _manifest(path)
        if output == path or any(output == Path(record["path"]) for record in sources):
            return {"state": "refused", "reason": "output_conflicts_source", "schema": SCHEMA}
        observed = []
        for record in sources:
            features = featurize(record["text"])
            if features["state"] != "read":
                return {
                    "state": "refused",
                    "reason": "source_features_unread",
                    "source": record["path"],
                    "evidence": features,
                }
            observed.append((record, features))
        training = [(record, features) for record, features in observed if record["split"] == "train"]
        rows = [_vector(features) for _, features in training]
        nfeat, n = len(rows[0]), len(rows)
        stats = [_mean_std(rows, index, n) for index in range(nfeat)]
        labels = sorted({record["label"] for record, _ in training})
        provenance = feature_identity()
        if (
            provenance["lexicon"]["state"] != "read"
            or provenance["wordnet"].get("resource", {}).get("state") != "read"
            or any(record["state"] != "read" for record in provenance["code"])
        ):
            return {"state": "refused", "reason": "resource_identity_unread", "provenance": provenance}
        model = {
            "schema": SCHEMA,
            "features": FEATURES,
            "provenance": provenance,
            "manifest": resource_identity(path),
            "sources": [{key: value for key, value in record.items() if key != "text"} for record in sources],
            "stats": stats,
            "nfeat": nfeat,
            "nv": 4,
            "voice_weight": VOICE_WEIGHT,
            "n_train": n,
            "labels": {label: sum(record["label"] == label for record, _ in training) for label in labels},
        }
        z = [
            [
                ((value - stats[index][0]) / stats[index][1]) * (VOICE_WEIGHT if index >= nfeat - 4 else 1)
                for index, value in enumerate(row)
            ]
            for row in rows
        ]
        model["centroids"] = {
            label: [
                sum(z[index][dim] for index, (record, _) in enumerate(training) if record["label"] == label)
                / model["labels"][label]
                for dim in range(nfeat)
            ]
            for label in labels
        }
        report = {label: {"identified": 0, "wrong": 0, "abstained": 0, "n": 0} for label in labels}
        for record, features in observed:
            if record["split"] != "holdout":
                continue
            decision = _decision(model, features)
            item = report[record["label"]]
            item["n"] += 1
            item[
                "abstained"
                if decision["state"] == "abstained"
                else "identified"
                if decision["voice"] == record["label"]
                else "wrong"
            ] += 1
        model["holdout"] = report
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".RohanVoice-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write((json.dumps(model, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {
            "state": "fit",
            "schema": SCHEMA,
            "model": str(output),
            "trained_on": n,
            "classes": model["labels"],
            "holdout": report,
            "evaluation": _evaluation(model),
            "manifest": model["manifest"],
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        code = (
            "invalid_utf8"
            if isinstance(exc, UnicodeError)
            else "malformed_manifest"
            if isinstance(exc, json.JSONDecodeError)
            else "source_unread"
            if isinstance(exc, OSError)
            else str(exc)
            if type(exc) is ValueError
            else "malformed_source_record"
        )
        return {"state": "refused", "reason": code, "detail": str(exc), "schema": SCHEMA}


def _artifact_sources_valid(model: dict) -> bool:
    sources = model.get("sources")
    report = model.get("holdout")
    manifest = model.get("manifest")
    if (
        not isinstance(sources, list)
        or not sources
        or not isinstance(report, dict)
        or not isinstance(manifest, dict)
        or not isinstance(manifest.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", manifest["sha256"])
        or _source_group_code(sources) != "disjoint_declared_groups"
    ):
        return False
    labels = set(model["centroids"])
    for source in sources:
        if (
            not isinstance(source, dict)
            or set(source) != {"path", "label", "split", "sha256", "group", "selection"}
            or not isinstance(source["path"], str)
            or source["label"] not in labels
            or source["split"] not in ("train", "holdout")
            or not isinstance(source["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        ):
            return False
    if model.get("n_train") != sum(source["split"] == "train" for source in sources) or set(report) != labels:
        return False
    for label in labels:
        item = report[label]
        heldout = sum(source["label"] == label and source["split"] == "holdout" for source in sources)
        trained = sum(source["label"] == label and source["split"] == "train" for source in sources)
        if (
            not heldout
            or not trained
            or not isinstance(item, dict)
            or set(item) != {"n", "identified", "wrong", "abstained"}
            or any(type(value) is not int or value < 0 for value in item.values())
            or item["n"] != heldout
            or sum(item[key] for key in ("identified", "wrong", "abstained")) != heldout
        ):
            return False
    return True


def _valid_model(model: dict) -> bool:
    n = len(BANKS) + len(CURATED) + 4
    return (
        isinstance(model, dict)
        and model.get("schema") == SCHEMA
        and model.get("features") == FEATURES
        and model.get("nfeat") == n
        and model.get("nv") == 4
        and model.get("voice_weight") == VOICE_WEIGHT
        and isinstance(model.get("stats"), list)
        and len(model["stats"]) == n
        and all(
            isinstance(pair, list)
            and len(pair) == 2
            and all(type(value) in (int, float) and math.isfinite(value) for value in pair)
            and pair[1] > 0
            for pair in model["stats"]
        )
        and isinstance(model.get("centroids"), dict)
        and len(model["centroids"]) >= 2
        and set(model["centroids"]) <= LABELS
        and all(
            isinstance(row, list)
            and len(row) == n
            and all(type(value) in (int, float) and math.isfinite(value) for value in row)
            for row in model["centroids"].values()
        )
        and _artifact_sources_valid(model)
    )


def recognize(text: str, *, model_path: str | Path | None = None) -> dict:
    """Read only a current versioned artifact; stale/legacy models require a refit."""
    path = Path(model_path or _model_path())
    if not path.exists():
        return {"state": "refit_required", "reason": "version_2_model_required", "schema": SCHEMA, "model": str(path)}
    try:
        model = json.loads(path.read_bytes().decode("utf-8"))
        if not _valid_model(model):
            return {"state": "refit_required", "reason": "legacy_or_malformed_model", "schema": SCHEMA}
        if model.get("provenance") != feature_identity():
            return {"state": "refit_required", "reason": "feature_or_resource_identity_changed", "schema": SCHEMA}
        features = featurize(text)
        if features["state"] != "read":
            return {"schema": SCHEMA, **features}
        return {
            "schema": SCHEMA,
            "features": FEATURES,
            **_decision(model, features),
            "bank_signature": features["bank_sig"],
            "style_features": features["style_features"],
            "markers": features["markers"],
            "populations": features["populations"],
            "model": resource_identity(path),
            "provenance": model["provenance"],
            "evaluation": _evaluation(model),
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        return {"state": "unread", "reason": type(exc).__name__, "schema": SCHEMA}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="one UTF-8 file or - for stdin")
    parser.add_argument("--fit", metavar="MANIFEST", help="explicit hash-pinned label/split manifest")
    parser.add_argument("--model", type=Path, default=None)
    args = parser.parse_args()
    if args.fit:
        result = fit(args.fit, model_path=args.model)
    elif args.source:
        try:
            text = sys.stdin.read() if args.source == "-" else Path(args.source).read_bytes().decode("utf-8")
            result = recognize(text, model_path=args.model)
        except (OSError, UnicodeError) as exc:
            result = {"state": "unread", "reason": type(exc).__name__, "schema": SCHEMA}
    else:
        parser.print_help()
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["state"] in ("refused", "unread"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
