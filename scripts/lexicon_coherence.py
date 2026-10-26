"""Discover source-native conditional relations over shared English words.

Run: uv run python scripts/lexicon_coherence.py --output <directory>
No old lexicon signs or source-to-prime projections enter this analysis.
Each word contributes once per relation. Missing source records are excluded,
never filled with zero. Native alternatives remain alternatives.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

import numpy as np
from scipy import sparse, stats


def binary_entropy(p: float) -> float:
    """Entropy in bits; deterministic endpoints have zero entropy."""
    if not 0 <= p <= 1:
        raise ValueError("probability outside [0, 1]")
    if p in (0, 1):
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def coherence_statistics(n11: int, n10: int, n01: int, n00: int) -> dict:
    """A→B statistics from the four observed cells; missing is not a cell.

    n11=A and B, n10=A and not B, n01=not A and B, n00=neither.
    Signed coherence is mean agreement with the proposed implication among A:
    C = 2 P(B|A) - 1. It retains the sign discarded by |Kuramoto order|.
    Wilson bounds quantify finite sample uncertainty, not semantic truth.
    """
    counts = (n11, n10, n01, n00)
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError("counts must be nonnegative integers")
    n = sum(counts)
    support = n11 + n10
    if not support:
        return {"status": "NO_ANTECEDENT", "population": n, "support": 0}
    p = n11 / support
    baseline = (n11 + n01) / n
    z = 1.959963984540054
    denom = 1 + z * z / support
    center = (p + z * z / (2 * support)) / denom
    spread = z * math.sqrt(p * (1 - p) / support + z * z / (4 * support**2)) / denom
    phi_den = math.sqrt(support * (n01 + n00) * (n11 + n01) * (n10 + n00))
    return {
        "status": "OBSERVED",
        "population": n,
        "support": support,
        "matches": n11,
        "violations": n10,
        "table": [n11, n10, n01, n00],
        "conditional_probability": p,
        "baseline_probability": baseline,
        "risk_difference": p - baseline,
        "lift": p / baseline if baseline else None,
        "signed_coherence": 2 * p - 1,
        "wilson_95": [center - spread, center + spread],
        "phi": (n11 * n00 - n10 * n01) / phi_den if phi_den else 0.0,
        "entropy_before_bits": binary_entropy(baseline),
        "entropy_after_bits": binary_entropy(p),
        "entropy_reduction_bits": binary_entropy(baseline) - binary_entropy(p),
    }


def relation_status(train: dict, heldout: dict, min_support: int) -> str:
    """Select reproducible candidates; never promote a discovered law."""
    if train["support"] < min_support or heldout["support"] < min_support:
        return "INSUFFICIENT_SUPPORT"
    if train["conditional_probability"] < 0.85 or heldout["conditional_probability"] < 0.85:
        return "EXCEPTIONS_TOO_FREQUENT"
    if train["risk_difference"] < 0.10 or heldout["risk_difference"] < 0.10:
        return "BASE_RATE_DOMINATED"
    if abs(train["conditional_probability"] - heldout["conditional_probability"]) > 0.10:
        return "UNSTABLE"
    if train["violations"] == 0 and heldout["violations"] == 0:
        return "EXCEPTION_FREE_OBSERVED_CANDIDATE"
    return "STABLE_ASSOCIATION_CANDIDATE"


def word_key(word: str) -> str:
    return unicodedata.normalize("NFC", word).strip().casefold()


@cache
def fold(word: str) -> int:
    return int.from_bytes(hashlib.sha256(word.encode()).digest()[:8], "big") % 5


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Corpus:
    def __init__(self) -> None:
        self.words: dict[str, set[str]] = defaultdict(set)
        self.numeric: dict[str, dict[str, float]] = defaultdict(dict)
        self.features: dict[str, set[str]] = defaultdict(set)
        self.feature_sources: dict[str, str] = {}
        self.numeric_sources: dict[str, str] = {}
        self.manifest: list[dict] = []
        self.pos: dict[str, set[str]] = defaultdict(set)
        self.fields: dict[str, set[str]] = defaultdict(set)

    def feature(self, source: str, label: str, word: str) -> None:
        self.features[f"{source}:{label}"].add(word)
        self.feature_sources[f"{source}:{label}"] = source

    def number(self, source: str, label: str, word: str, value: str) -> None:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"nonfinite {source}:{label}:{word}")
        self.numeric[f"{source}:{label}"][word] = number
        self.numeric_sources[f"{source}:{label}"] = source

    def snapshot(self, source: str, paths: list[Path], scope: str) -> None:
        h = hashlib.sha256()
        for path in sorted(paths):
            h.update(path.name.encode())
            h.update(bytes.fromhex(digest(path)))
        self.manifest.append(
            {
                "source": source,
                "scope": scope,
                "files": len(paths),
                "sha256": h.hexdigest(),
                "paths": [str(p) for p in paths],
            }
        )


def restrict_to_single_words(c: Corpus) -> None:
    """Keep single word anchors, including apostrophes/hyphens and Unicode letters."""
    allowed = {
        w
        for words in c.words.values()
        for w in words
        if not any(ch.isspace() for ch in w) and "_" not in w and any(ch.isalpha() for ch in w)
    }
    for source in c.words:
        c.words[source].intersection_update(allowed)
    for field in c.numeric:
        c.numeric[field] = {w: v for w, v in c.numeric[field].items() if w in allowed}
    for field in c.features:
        c.features[field].intersection_update(allowed)


def load_corpus(root: Path, nltk_root: Path) -> Corpus:
    c = Corpus()
    definitions = [
        ("concreteness", "concreteness.csv", ",", "Word", {"Conc.M": "mean"}),
        ("lancaster", "lancaster_sensorimotor.csv", ",", "Word", None),
        ("vad", "nrc_vad.txt", "\t", "term", None),
    ]
    for source, filename, delimiter, key, columns in definitions:
        path = root / filename
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                word = word_key(row[key])
                if word in c.words[source]:
                    raise ValueError(f"duplicate native term: {source}:{word}")
                c.words[source].add(word)
                for column, label in (columns or {k: k.removesuffix(".mean") for k in row if k != key}).items():
                    c.number(source, label, word, row[column])
                if source == "vad":
                    for column in ("valence", "arousal", "dominance"):
                        v = float(row[column])
                        if not -1 <= v <= 1:
                            raise ValueError("expected native NRC VAD v2 [-1,1] scale")
                        state = "positive" if v > 0 else "negative" if v < 0 else "zero"
                        c.feature(source, f"{column}_sign={state}", word)
                if source == "lancaster":
                    for fields, name in [
                        (["Auditory", "Gustatory", "Haptic", "Interoceptive", "Olfactory", "Visual"], "sense"),
                        (["Foot_leg", "Hand_arm", "Head", "Mouth", "Torso"], "effector"),
                    ]:
                        values = {k: float(row[k + ".mean"]) for k in fields}
                        top = max(values.values())
                        winners = [k for k, v in values.items() if v == top]
                        c.feature(source, f"dominant_{name}=" + (winners[0] if len(winners) == 1 else "TIE"), word)
        c.snapshot(source, [path], "WORD; native human rating, no prime projection")

    path = root / "nrc_emotion.txt"
    with path.open() as f:
        for word, emotion, association in csv.reader(f, delimiter="\t"):
            word = word_key(word)
            if association not in {"0", "1"}:
                raise ValueError("invalid NRC emotion association")
            c.words["emotion"].add(word)
            c.feature("emotion", f"{emotion}={association}", word)
            c.number("emotion", emotion, word, association)
    c.snapshot("emotion", [path], "WORD; explicit association 0/1, never lexical silence")

    path = root / "usas/semantic_lexicon_en.tsv"
    alternatives: dict[str, set[str]] = defaultdict(set)
    with path.open() as f:
        for row in csv.DictReader(f, delimiter="\t"):
            word, pos = word_key(row["lemma"]), row["pos"]
            c.words["usas"].add(word)
            c.pos[word].add(pos)
            c.feature("usas", f"pos={pos}", word)
            # Space-delimited tags are alternatives; slash means double membership.
            # Preserve both the original alternative and its explicit components.
            for tag in row["semantic_tags"].split():
                alternatives[word].add(tag)
                c.feature("usas", f"alternative={tag}", word)
                for component in tag.split("/"):
                    match = re.match(r"[A-Z]+\d+(?:\.\d+)*[+-]*", component)
                    if match:
                        category = match.group()
                        c.feature("usas", f"category={category}", word)
                        c.feature("usas", f"pos={pos}&category={category}", word)
                        c.feature("usas", f"field={category[0]}", word)
                        c.fields[word].add(category[0])
    for word, tags in alternatives.items():
        if len(tags) == 1:
            c.feature("usas", "single_alternative=" + next(iter(tags)), word)
    c.snapshot("usas", [path], "LEMMA_POS; alternatives unioned for word-level discovery")

    fn = nltk_root / "framenet_v17/luIndex.xml"
    if fn.exists():
        for node in ET.parse(fn).getroot():
            if node.tag.rsplit("}", 1)[-1] != "lu":
                continue
            word = word_key(node.attrib["name"].rsplit(".", 1)[0])
            c.words["framenet"].add(word)
            c.feature("framenet", "frame=" + node.attrib["frameName"], word)
        c.snapshot("framenet", [fn], "LEXICAL_UNIT; frame alternatives unioned, no participant leakage")

    vn_paths = sorted((nltk_root / "verbnet").glob("*.xml"))

    def visit(node: ET.Element, inherited: set[str]) -> None:
        labels = set(inherited)
        labels.add("class=" + node.attrib["ID"])
        for pred in node.findall("./FRAMES/FRAME/SEMANTICS/PRED"):
            labels.add("frame_predicate=" + pred.attrib.get("bool", "") + pred.attrib["value"])
        for role in node.findall("./THEMROLES/THEMROLE"):
            labels.add("argument_role=" + role.attrib["type"])
            for restriction in role.findall(".//SELRESTR"):
                labels.add(
                    "argument_restriction="
                    + role.attrib["type"]
                    + ":"
                    + restriction.attrib["Value"]
                    + restriction.attrib["type"]
                )
        for member in node.findall("./MEMBERS/MEMBER"):
            word = word_key(member.attrib["name"])
            c.words["verbnet"].add(word)
            for label in labels:
                c.feature("verbnet", label, word)
        for child in node.findall("./SUBCLASSES/VNSUBCLASS"):
            visit(child, labels)

    for path in vn_paths:
        visit(ET.parse(path).getroot(), set())
    if vn_paths:
        c.snapshot("verbnet", vn_paths, "CLASS/FRAME; inherited alternative frame predicates and argument restrictions")
    return c


def table(a: set[str], b: set[str], population: set[str]) -> dict:
    aa, bb = a & population, b & population
    both = len(aa & bb)
    return coherence_statistics(both, len(aa) - both, len(bb) - both, len(population - (aa | bb)))


def word_witnesses(c: Corpus, names: list[str], target: str, population: set[str]) -> dict:
    antecedent = set.intersection(*(c.features[n] for n in names)) & population
    matches = sorted(antecedent & c.features[target])
    exceptions = sorted(antecedent - c.features[target])
    return {"supporting_examples": matches[:12], "all_counterexamples": exceptions}


def pair_relations(c: Corpus, min_support: int) -> tuple[list[dict], dict]:
    relations: list[dict] = []
    tested = Counter()
    for sa, sb in itertools.combinations(sorted(c.words), 2):
        population = c.words[sa] & c.words[sb]
        if len(population) < min_support * 2:
            continue
        words = sorted(population)
        index = {w: i for i, w in enumerate(words)}
        groups = [
            [
                k
                for k in sorted(c.features)
                if c.feature_sources[k] == source and len(c.features[k] & population) >= min_support * 2
            ]
            for source in (sa, sb)
        ]
        matrices = []
        for names in groups:
            rr, cc = [], []
            for j, name in enumerate(names):
                for word in c.features[name] & population:
                    rr.append(index[word])
                    cc.append(j)
            matrices.append(
                sparse.csr_matrix((np.ones(len(rr), dtype=np.int64), (rr, cc)), shape=(len(words), len(names)))
            )
        masks = [np.array([fold(w) < 3 for w in words]), np.array([fold(w) >= 3 for w in words])]
        products = [(matrices[0][m].T @ matrices[1][m]).toarray() for m in masks]
        margins = [[np.asarray(x[m].sum(axis=0)).ravel() for x in matrices] for m in masks]
        sizes = [int(m.sum()) for m in masks]
        tested[f"{sa}|{sb}"] = len(groups[0]) * len(groups[1]) * 2
        for i, a in enumerate(groups[0]):
            for j, b in enumerate(groups[1]):
                for reverse in (False, True):
                    cells = []
                    for z in range(2):
                        both = int(products[z][i, j])
                        na, nb = int(margins[z][0][i]), int(margins[z][1][j])
                        cells.append(
                            coherence_statistics(
                                both,
                                (nb if reverse else na) - both,
                                (na if reverse else nb) - both,
                                sizes[z] - na - nb + both,
                            )
                        )
                    status = relation_status(cells[0], cells[1], min_support)
                    if not status.endswith("CANDIDATE"):
                        continue
                    ant, target = (b, a) if reverse else (a, b)
                    overall = table(c.features[ant], c.features[target], population)
                    relations.append(
                        {
                            "antecedents": [ant],
                            "consequent": target,
                            "status": status,
                            "lineage": "SHARED_NRC_FAMILY"
                            if {sa, sb} == {"emotion", "vad"}
                            else "DISTINCT_SOURCE_CHANNELS",
                            "overall": overall,
                            "discovery": cells[0],
                            "heldout": cells[1],
                            **word_witnesses(c, [ant], target, population),
                        }
                    )
    relations.sort(key=lambda r: r["heldout"]["entropy_reduction_bits"] * r["heldout"]["support"], reverse=True)
    return relations, dict(tested)


def numeric_relations(c: Corpus) -> list[dict]:
    result = []
    for a, b in itertools.combinations(sorted(c.numeric), 2):
        if c.numeric_sources[a] == c.numeric_sources[b]:
            continue
        words = sorted(c.numeric[a].keys() & c.numeric[b].keys())
        if len(words) < 200:
            continue
        x, y = np.array([c.numeric[a][w] for w in words]), np.array([c.numeric[b][w] for w in words])
        if np.std(x) == 0 or np.std(y) == 0:
            continue
        rho = float(stats.spearmanr(x, y).statistic)
        folds = []
        for k in range(5):
            m = np.array([fold(w) == k for w in words])
            folds.append(float(stats.spearmanr(x[m], y[m]).statistic))
        slices = {}
        for pos in ("NOUN", "VERB", "ADJ", "ADV"):
            m = np.array([c.pos[w] == {pos} for w in words])
            if m.sum() >= 100 and np.std(x[m]) > 0 and np.std(y[m]) > 0:
                slices[pos] = {"n": int(m.sum()), "spearman": float(stats.spearmanr(x[m], y[m]).statistic)}
        result.append(
            {
                "a": a,
                "b": b,
                "n": len(words),
                "pearson": float(stats.pearsonr(x, y).statistic),
                "spearman": rho,
                "five_word_folds": folds,
                "single_POS_slices": slices,
                "stable_direction": all(v * rho > 0 for v in folds),
                "lineage": "SHARED_NRC_FAMILY"
                if {c.numeric_sources[a], c.numeric_sources[b]} == {"emotion", "vad"}
                else "DISTINCT_SOURCE_CHANNELS",
            }
        )
    return sorted(result, key=lambda r: abs(r["spearman"]), reverse=True)


def conjunction_relations(c: Corpus, min_support: int) -> list[dict]:
    """Test supported cross-source pairs, including zero-marginal bridges.

    No singleton-correlation shortlist: significance-weighting §13 explains
    why either premise can be uninformative until its companion is supplied.
    Sparse cross-products count the observed tuples without enumerating words'
    hypothetical joint assignments. All rates use one triple-source population.
    """
    result: list[dict] = []
    for target_source in ("emotion", "vad", "lancaster"):
        targets = [k for k in sorted(c.features) if c.feature_sources[k] == target_source]
        others = [s for s in sorted(c.words) if s != target_source]
        for sa, sb in itertools.combinations(others, 2):
            population = c.words[sa] & c.words[sb] & c.words[target_source]
            if len(population) < min_support * 2:
                continue
            words = sorted(population)
            index = {w: i for i, w in enumerate(words)}
            groups = [
                [
                    k
                    for k in sorted(c.features)
                    if c.feature_sources[k] == source
                    and "alternative=" not in k
                    and len(c.features[k] & population) >= min_support * 2
                ]
                for source in (sa, sb)
            ]
            if not all(groups):
                continue
            matrices = []
            for names in groups:
                rr, cc = [], []
                for j, name in enumerate(names):
                    for word in c.features[name] & population:
                        rr.append(index[word])
                        cc.append(j)
                matrices.append(
                    sparse.csr_matrix((np.ones(len(rr), dtype=np.int64), (rr, cc)), shape=(len(words), len(names)))
                )
            partitions = [np.array([fold(w) < 3 for w in words]), np.array([fold(w) >= 3 for w in words])]
            counts = [(matrices[0][m].T @ matrices[1][m]).toarray() for m in partitions]
            support_ok = (counts[0] >= min_support) & (counts[1] >= min_support)
            if not np.any(support_ok):
                continue
            sizes = [int(m.sum()) for m in partitions]
            margins = [[np.asarray(x[m].sum(axis=0)).ravel() for x in matrices] for m in partitions]
            for target in targets:
                target_mask = np.array([w in c.features[target] for w in words])
                matches = [
                    (matrices[0][m & target_mask].T @ matrices[1][m & target_mask]).toarray() for m in partitions
                ]
                probabilities = [
                    np.divide(hit, total, out=np.zeros_like(hit, dtype=float), where=total > 0)
                    for hit, total in zip(matches, counts, strict=True)
                ]
                rates = [float(np.sum(m & target_mask)) / size for m, size in zip(partitions, sizes, strict=True)]
                single_probs = []
                for z, m in enumerate(partitions):
                    single_probs.append(
                        [
                            np.divide(
                                np.asarray(x[m & target_mask].sum(axis=0)).ravel(),
                                margin,
                                out=np.zeros_like(margin, dtype=float),
                                where=margin > 0,
                            )
                            for x, margin in zip(matrices, margins[z], strict=True)
                        ]
                    )
                gains = [
                    probabilities[z] - np.maximum(single_probs[z][0][:, None], single_probs[z][1][None, :])
                    for z in range(2)
                ]
                keep = support_ok & (np.abs(probabilities[0] - probabilities[1]) <= 0.10)
                for z in range(2):
                    keep &= (probabilities[z] >= 0.85) & (probabilities[z] - rates[z] >= 0.10) & (gains[z] >= 0.03)
                for i, j in zip(*np.nonzero(keep), strict=True):
                    a, b = groups[0][i], groups[1][j]
                    joint = c.features[a] & c.features[b]
                    sets = [{w for w in population if fold(w) < 3}, {w for w in population if fold(w) >= 3}]
                    reports = [table(joint, c.features[target], p) for p in sets]
                    singles = [[table(c.features[n], c.features[target], p) for n in (a, b)] for p in sets]
                    result.append(
                        {
                            "antecedents": [a, b],
                            "consequent": target,
                            "status": relation_status(*reports, min_support),
                            "overall": table(joint, c.features[target], population),
                            "discovery": reports[0],
                            "heldout": reports[1],
                            "gain_over_best_single_discovery_heldout": [float(g[i, j]) for g in gains],
                            "single_premises_same_population": singles,
                            "conditional_entropy_reduction_bits": [
                                [
                                    binary_entropy(s["conditional_probability"])
                                    - binary_entropy(r["conditional_probability"])
                                    for s in single
                                ]
                                for single, r in zip(singles, reports, strict=True)
                            ],
                            "zero_or_negative_singleton_lift": all(s["risk_difference"] <= 0 for s in singles[0]),
                            **word_witnesses(c, [a, b], target, population),
                        }
                    )
    return sorted(
        result, key=lambda r: r["heldout"]["support"] * min(r["gain_over_best_single_discovery_heldout"]), reverse=True
    )


def write_report(report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    lines = [
        "# Cross-dataset lexical bank coherence — measured run",
        "",
        "These are native-source relations over shared English word keys. No old lexicon vector, gloss parser, model, or source-to-prime map enters the calculation.",
        "",
        "Word key: NFC + casefold + strip; no stemming or synonym expansion. This run keeps single words: no whitespace or underscore, at least one alphabetic character; hyphens, apostrophes and Unicode letters are retained. One word has one vote, regardless of the number of source records. Missing sources are excluded. Space-delimited USAS tags are alternatives, slash components are joint membership. FrameNet/VerbNet features mean a native alternative exists, not that every use has it.",
        "",
        "Discovery uses word-hash folds 0–2; held-out uses 3–4. Candidate gates: ≥40 antecedent words in EACH partition, conditional probability ≥0.85 in both, gain over the target base rate ≥0.10 in both, rate drift ≤0.10. A candidate is never automatically a definitional law. All counterexamples are in results.json.",
        "",
        "C(A→B) = 2P(B|A)−1; information change = H₂(P(B))−H₂(P(B|A)). Positive or negative source-score signs are native score directions, not GSE ternary signs. Zero association, missing, written lexical zero and lexical silence remain distinct.",
        "",
        "## Coverage",
        "",
        "| Source | Distinct words |",
        "|---|---:|",
    ]
    lines.extend(f"| {s} | {n:,} |" for s, n in report["source_counts"].items())
    lines += [
        "",
        f"Words present in at least two sources: **{report['words_in_at_least_two_sources']:,}**.",
        "",
        "| Pair | Shared words |",
        "|---|---:|",
    ]
    lines.extend(f"| {s.replace(' | ', ' ↔ ')} | {n:,} |" for s, n in report["overlaps"].items())
    lines += [
        "",
        "## Continuous relations",
        "",
        "All source-pair numeric tests are recorded, including weak relations. These are the strongest with distinct source channels.",
        "",
        "| Fields | n | Spearman ρ | Five-fold range |",
        "|---|---:|---:|---:|",
    ]
    for r in [r for r in report["numeric_relations"] if r["lineage"] == "DISTINCT_SOURCE_CHANNELS"][:15]:
        lines.append(
            f"| {r['a']} ↔ {r['b']} | {r['n']:,} | {r['spearman']:.3f} | {min(r['five_word_folds']):.3f}…{max(r['five_word_folds']):.3f} |"
        )
    lines += [
        "",
        "## Stable directional candidates",
        "",
        f"{len(report['pair_relations'])} candidates passed the declared discovery/held-out checks; no candidate is promoted to a hard bank law.",
        "",
        "| Antecedent → consequent | Matched / support | Held-out rate | Base rate | Exceptions |",
        "|---|---:|---:|---:|---|",
    ]
    shown = set()
    for r in report["pair_relations"]:
        key = (r["antecedents"][0].split(":")[0], r["consequent"].split(":")[0])
        if sum(x == key for x in shown) > 0:
            continue
        shown.add(key)
        s, h = r["overall"], r["heldout"]
        lines.append(
            f"| {r['antecedents'][0]} → {r['consequent']} | {s['matches']}/{s['support']} | {h['conditional_probability']:.3f} | {h['baseline_probability']:.3f} | {', '.join(r['all_counterexamples'][:5]) or 'none observed'} |"
        )
    lines += [
        "",
        "## Conjunction gains",
        "",
        "Each conjunction uses three different datasets. Both single-premise rates are recomputed on the SAME triple-source population. The conjunction must improve on the stronger single premise by ≥0.03 in both partitions.",
        "",
        "| Premises → consequent | Matched / support | Held-out rate | Held-out gain |",
        "|---|---:|---:|---:|",
    ]
    for r in report["conjunction_relations"][:15]:
        s = r["overall"]
        lines.append(
            f"| {' AND '.join(r['antecedents'])} → {r['consequent']} | {s['matches']}/{s['support']} | {r['heldout']['conditional_probability']:.3f} | +{r['gain_over_best_single_discovery_heldout'][1]:.3f} |"
        )
    lines += [
        "",
        f"Conjunctions with both singleton risk differences ≤0 in discovery: {sum(r['zero_or_negative_singleton_lift'] for r in report['conjunction_relations'])}. The search does not require singleton lift; a separate parity witness tests that a purely complementary pair is discoverable.",
        "",
        "Significance Weighting §§7b and 13 apply to the next rule stage: remeasure marginal resolution after each admitted relation; account for redundant coverage and complementary bridges. The entropy changes here describe native target-state frequencies. They are not an exact measurement of feasible GSE vector configurations or a proof of a greedy guarantee.",
        "",
        "Native contracts: [USAS category guide](https://ucrel.lancs.ac.uk/usas/usas_guide.pdf) defines ranked alternatives and slash membership; [NRC VAD v2 paper](https://arxiv.org/html/2503.23547v1) defines the signed native rating scale. Source snapshot hashes, rather than assumed release names, identify this run.",
    ]
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "A recurring native relation proposes the guard and allowed tuples of a GSE bank law. Definition versus association, participant versus denotatum, POS alternatives and the bank mask contract still determine its exact lexical consequence. Norm correlations alone cannot write FEEL, GOOD, BODY, MOVE or silence. The result is a ranked corpus of rule candidates, including counterexamples, for that symbolic review.",
        "",
        "This run does not contain certified GSE bank states. Measuring relations between the old generated prime signs would reproduce its mistakes. It measures the independent source channels from which those signs and bank relations are to be derived.",
        "",
    ]
    (output / "REPORT.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("data/external"))
    parser.add_argument("--nltk", type=Path, default=Path.home() / "nltk_data/corpora")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    c = load_corpus(args.sources, args.nltk)
    unfiltered_counts = {s: len(w) for s, w in c.words.items()}
    restrict_to_single_words(c)
    print("Native word counts:", {s: len(w) for s, w in c.words.items()}, flush=True)
    pair, tested = pair_relations(c, 40)
    print("Stable directional candidates:", len(pair), flush=True)
    numeric = numeric_relations(c)
    print("Numeric relations:", len(numeric), flush=True)
    conjunction = conjunction_relations(c, 40)
    print("Stable conjunction gains:", len(conjunction), flush=True)
    counts = Counter(w for words in c.words.values() for w in words)
    report = {
        "schema_version": 1,
        "script_sha256": digest(Path(__file__)),
        "sources": c.manifest,
        "source_counts": {s: len(w) for s, w in c.words.items()},
        "unfiltered_source_counts": unfiltered_counts,
        "scope_filter": "single word: no whitespace/underscore, at least one alphabetic character",
        "overlaps": {
            a + " | " + b: len(c.words[a] & c.words[b]) for a, b in itertools.combinations(sorted(c.words), 2)
        },
        "words_in_at_least_two_sources": sum(n >= 2 for n in counts.values()),
        "source_membership_histogram": dict(Counter(counts.values())),
        "candidate_policy": {
            "min_support_each_partition": 40,
            "min_conditional_probability": 0.85,
            "min_risk_difference": 0.10,
            "max_rate_drift": 0.10,
            "split": "sha256(NFC+casefold+strip word) modulo 5; discovery 0..2, heldout 3..4",
            "status": "EXPLORATORY_CANDIDATES; not familywise-confirmed or automatically promoted",
        },
        "tested_directional_candidates": tested,
        "numeric_relations": numeric,
        "pair_relations": pair,
        "conjunction_relations": conjunction,
    }
    write_report(report, args.output)
    print("Wrote", args.output / "REPORT.md", flush=True)


if __name__ == "__main__":
    main()
