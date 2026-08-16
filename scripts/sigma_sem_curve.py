#!/usr/bin/env python3
"""The per-scale σ_sem instrument — resolution collapse as specification scale expands (SSL `05`).

DISCRETE by construction. GSE's thesis is that meaning is STRUCTURE, not vector proximity
(GSE Proof Packet §1 the null axis, §8 negation-blindness, §10 meaning-*equality* not similarity).
So the resolver here is GSE's REAL one — ``_select_by_coherence`` (grounding.py:323-334): a noun's
sense is the candidate IS-A type-thread with the highest ``_jaccard`` NODE-overlap against the union
of the *other grounded entities' thread nodes*. Pure discrete set-overlap over the WordNet/genealogy
IS-A structure. There is NO cosine in this instrument; sense_resonance (the guarded HDC re-ranker
leg) is deliberately not used as the resolver — it is a secondary confirmation, never the yardstick.

Understanding IS the σ-trajectory (`00`): the ordered constraints driving conceptual entropy
H = log₂|surviving readings| to zero. The constraints are graded by SCALE — how wide the structural
context is:

    sentence  →  document  →  world (grounded proper-noun IS-A type threads, sparse-wiki)

A competitor sense c is RULED OUT at scale s when the gold thread is structurally more coherent with
the scale-s context than c is:  ``_jaccard(gold_nodes, ctx_s) > _jaccard(c_nodes, ctx_s)`` (GSE's own
coherence primitive). Ruling-out ACCUMULATES (a reading removed stays removed — the σ-trajectory is
monotone). σ_sem(token) = the minimal scale that makes the gold unique. A competitor that shares the
gold's IS-A structure so closely that NO scale separates them is a SURVIVOR — the closed-basis
definitional limit (`feedback_gse_lexicon_definitional_only`; §15): two readings GSE's structure
genuinely does not distinguish, where abstention is correct.

σ_sem cardinality + the bulk/tail phase are read off LintGate's PROVED engine
(``greedy_convergence.analyze_convergence``) on the SCALE-indexed discrete kill-matrix — the same σ
proved a Blum measure = teaching dimension (``Mutation_Theory_proofs/``).

Usage: python scripts/sigma_sem_curve.py [--files N] [--max-sents-per-file M]
"""
import argparse
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "/Users/rohanvinaik/tools/LintGate")  # reuse the proved σ engine

SCALES = ["sentence", "document", "world"]   # ordered, nested structural-context scopes


class _SemProfilingResult:
    """Minimal ProfilingResult shim for LintGate's analyze_convergence (kill_matrix holds only
    killed mutants; survivors counted via total_survived)."""

    def __init__(self, key, killed_matrix, total_mutants, total_survived):
        self.function_key = key
        self.kill_matrix = killed_matrix
        self.total_mutants = total_mutants
        self.total_survived = total_survived
        self.survival_rate = (total_survived / total_mutants) if total_mutants else 0.0


def _greedy_cover(kill_matrix, n_competitors):
    """σ_sem CARDINALITY = min context entities (revealed examples) s.t. every competitor is beaten
    by some chosen entity (greedy set cover, LintGate's algorithm). Returns (sigma, survivor_set)."""
    ent_kills = defaultdict(set)
    for c, ents in kill_matrix.items():
        for e in ents:
            ent_kills[e].add(c)
    survivors = {c for c in range(n_competitors) if not kill_matrix.get(c)}
    remaining = set(range(n_competitors)) - survivors
    chosen = []
    while remaining:
        best_e, best_cov = None, set()
        for e, killed in ent_kills.items():
            cov = killed & remaining
            if len(cov) > len(best_cov):
                best_e, best_cov = e, cov
        if not best_e:
            break
        chosen.append(best_e)
        remaining -= best_cov
    return len(chosen), survivors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=6)
    ap.add_argument("--max-sents-per-file", type=int, default=25)
    args = ap.parse_args()

    import nltk
    for pkg, path in [("semcor", "corpora/semcor"), ("wordnet", "corpora/wordnet")]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)
    from nltk.corpus import semcor, wordnet as wn
    from nltk.corpus.reader.wordnet import Lemma
    from gse.api import GSEEncoder
    from gse.symbolic import evaluate_tree, from_trace, resolve, resolve_document, GenealogyStore
    from gse.symbolic.grounding import (
        _COHERENCE_MARGIN, _collect_entities, _is_proper, _jaccard, _lookup_key,
    )
    try:
        from lintgate.specification.greedy_convergence import analyze_convergence
        _HAVE_LG = True
    except Exception as e:            # pragma: no cover
        print(f"[LintGate engine unavailable: {e}]"); _HAVE_LG = False

    enc = GSEEncoder()
    store = GenealogyStore()
    print("[per-scale σ_sem — DISCRETE _jaccard IS-A coherence (GSE's real resolver); NO cosine]")
    print(f"[scales = {'→'.join(SCALES)}; bulk/tail via LintGate ({'reused' if _HAVE_LG else 'off'})]\n")

    total = 0
    survivors_by_scale = defaultdict(int)
    H_by_scale = defaultdict(float)
    resolved_at = Counter()
    # A (surprise) + B (cardinality) accumulators
    card_hist = Counter()          # σ_sem cardinality (min context entities) -> count
    card_survivor = 0              # tokens with a competitor no entity beats
    card_phase = Counter()
    surprise_sum = 0.0
    override_n = 0                 # tokens where structure overrode the frequency-primary
    override_surprise_sum = 0.0

    def primary_nodes(lemma, pos, proper):
        cands = store.candidates(lemma, pos, proper)
        return set(cands[0]) if cands else set()

    def freq_prior(lemma, synset_names):
        """WordNet frequency prior over the noun's senses (SemCor lemma counts, +1 smoothed)."""
        counts = []
        for sname in synset_names:
            syn = wn.synset(sname)
            counts.append(1 + sum(l.count() for l in syn.lemmas() if l.name().lower() == lemma))
        tot = sum(counts)
        return [c / tot for c in counts]

    for fid in semcor.fileids()[: args.files]:
        raw_sents = semcor.sents(fid)[: args.max_sents_per_file]
        tagged = semcor.tagged_sents(fid, tag="sem")[: args.max_sents_per_file]

        # REAL grounded structure of the passage: per-sentence entity primary-thread node sets,
        # split common-noun (sentence/document scope) vs proper-noun world threads (world scope).
        sent_common = []    # per sentence: list of (lemma, node_set) for common-noun entities
        world_nodes: set = set()
        try:
            trees = [evaluate_tree(resolve(from_trace(enc.encode(" ".join(w))))) for w in raw_sents]
            resolved = resolve_document(trees, store, genre=None)
        except Exception:
            resolved = []
        for tree in resolved:
            ents: list = []
            _collect_entities(tree, ents)
            row = []
            for e in ents:
                lemma = _lookup_key(e)
                pos = getattr(e.head, "pos", "") or ""
                if _is_proper(e):
                    world_nodes |= set(getattr(e, "type_thread", ()) or ())
                elif pos == "NOUN" and lemma:
                    row.append((lemma.lower(), primary_nodes(lemma, pos, False)))
            sent_common.append(row)
        doc_common_nodes = set().union(*[n for row in sent_common for _, n in row]) if sent_common else set()
        # individual context ENTITIES (each a "revealed example" for the cardinality σ_sem): every
        # common-noun entity's thread node-set, plus the proper-noun world profile as one entity.
        doc_entities = [(lm, n) for row in sent_common for lm, n in row if n]
        if world_nodes:
            doc_entities.append(("__world__", world_nodes))

        # gold noun tokens, per sentence (aligned to the sentence's grounded entities by index of sentence)
        for si, sent in enumerate(tagged):
            for chunk in sent:
                if not isinstance(chunk, nltk.Tree):
                    continue
                lab = chunk.label()
                if not isinstance(lab, Lemma):
                    continue
                syn = lab.synset()
                if syn.pos() != "n":
                    continue
                lemma = lab.name().split("%")[0].lower()
                gold = syn.name()
                synsets = [s.name() for s in wn.synsets(lemma, wn.NOUN)]
                if len(synsets) < 2 or gold not in synsets:
                    continue
                cands = [tuple(t) for t in store.candidates(lemma, "NOUN", False)]
                if len(cands) != len(synsets):
                    continue   # thread↔synset alignment not exact → cannot faithfully map
                gold_nodes = set(cands[synsets.index(gold)])
                competitors = [set(cands[i]) for i, s in enumerate(synsets) if s != gold]
                if not competitors:
                    continue
                total += 1

                # scale-scoped DISCRETE context (other entities' IS-A thread nodes, exclude own lemma)
                sent_ctx = set().union(*[n for lm, n in sent_common[si] if lm != lemma]) \
                    if si < len(sent_common) and sent_common[si] else set()
                doc_ctx = doc_common_nodes
                world_ctx = doc_common_nodes | world_nodes
                ctx_by_scale = {"sentence": sent_ctx, "document": doc_ctx, "world": world_ctx}

                # cumulative ruling-out by discrete Jaccard coherence (gold more coherent than c)
                kill_matrix = {i: set() for i in range(len(competitors))}
                ruled_out: set = set()
                sigma_scale = None
                for s in SCALES:
                    ctx = ctx_by_scale[s]
                    gj = _jaccard(gold_nodes, ctx)
                    for i, c in enumerate(competitors):
                        if i in ruled_out:
                            continue
                        if gj > _jaccard(c, ctx):      # gold structurally beats competitor i at scale s
                            kill_matrix[i].add(s)
                            ruled_out.add(i)
                    cum_surv = len(competitors) - len(ruled_out)
                    survivors_by_scale[s] += cum_surv
                    H_by_scale[s] += math.log2(1 + cum_surv)
                    if cum_surv == 0 and sigma_scale is None:
                        sigma_scale = s
                if sigma_scale is not None:
                    resolved_at[sigma_scale] += 1
                else:
                    # a "never" token: split TRUE basis gap (a survivor with an IDENTICAL IS-A
                    # thread — closed basis genuinely cannot distinguish) from structure-silent
                    # (different threads, no discriminating context → GSE falls to the freq-primary).
                    surv_idx = [i for i in range(len(competitors)) if i not in ruled_out]
                    basis_gap = any(_jaccard(gold_nodes, competitors[i]) == 1.0 for i in surv_idx)
                    resolved_at["never:basis-gap" if basis_gap else "never:freq-primary"] += 1

                # --- A · SURPRISE (the resolution signal) ---------------------------------------
                # Structural resolution = GSE's rule: keep the frequency-primary (cands[0]) unless a
                # candidate beats it in IS-A coherence with the full context by the coherence margin.
                all_cands = [set(t) for t in cands]
                scores = [_jaccard(cn, world_ctx) for cn in all_cands]
                best_idx = max(range(len(all_cands)), key=lambda i: scores[i])
                resolved_idx = best_idx if scores[best_idx] > scores[0] + _COHERENCE_MARGIN else 0
                prior = freq_prior(lemma, synsets)
                S = -math.log2(prior[resolved_idx])      # KL(δ_resolved ‖ freq prior) = belief revision
                surprise_sum += S
                if resolved_idx != 0:                    # structure OVERRODE the frequency-primary
                    override_n += 1
                    override_surprise_sum += S

                # --- B · CARDINALITY σ_sem (the teaching dimension) -----------------------------
                # tests = individual context ENTITIES; entity e kills competitor c iff the gold is
                # more IS-A-coherent with e than c is. σ_sem = min entities to make gold unique.
                ent_kill = {i: set() for i in range(len(competitors))}
                for ei, (elm, enodes) in enumerate(doc_entities):
                    if elm == lemma:
                        continue
                    gj_e = _jaccard(gold_nodes, enodes)
                    for i, c in enumerate(competitors):
                        if gj_e > _jaccard(c, enodes):
                            ent_kill[i].add(ei)
                sigma_card, card_surv = _greedy_cover(ent_kill, len(competitors))
                card_hist[sigma_card] += 1
                if card_surv:
                    card_survivor += 1
                if _HAVE_LG and sigma_card > 0:
                    killed = {f"m{i}": {f"e{e}" for e in ks} for i, ks in ent_kill.items() if ks}
                    pr = _SemProfilingResult(f"{lemma}:{gold}", killed, len(competitors), len(card_surv))
                    conv = analyze_convergence(pr, sigma_card)
                    live = len(competitors) - len(card_surv)
                    if conv.steps and conv.steps[0].new_kills >= 0.5 * (live or 1):
                        card_phase["bulk"] += 1
                    else:
                        card_phase["tail"] += 1

    # ---- report ----------------------------------------------------------------
    print(f"RESOLUTION COLLAPSE across specification scale — {total} polysemous grounded noun tokens "
          f"({args.files} SemCor files):\n")
    print(f"  {'scale':10} {'mean |N(T) survivors|':>22} {'mean H=log₂(1+surv)':>22}")
    for s in SCALES:
        ms = survivors_by_scale[s] / max(1, total)
        mh = H_by_scale[s] / max(1, total)
        print(f"  {s:10} {ms:22.3f} {mh:22.3f}  {'█' * int(mh * 12)}")
    print(f"\n  σ_sem = the SCALE at which the gold reading becomes structurally UNIQUE (H → 0):")
    for s in SCALES:
        n = resolved_at.get(s, 0)
        print(f"    resolves @ {s:14}: {n:4d}  {'█' * min(40, n)}")
    nfp = resolved_at.get("never:freq-primary", 0)
    nbg = resolved_at.get("never:basis-gap", 0)
    print(f"    structure-silent → FREQ-PRIMARY: {nfp:4d}  {'█' * min(40, nfp)}  "
          f"(IS-A ties; GSE resolves by the frequency prior — the MFS half of #1)")
    print(f"    closed-basis DEFINITIONAL GAP  : {nbg:4d}  {'█' * min(40, nbg)}  "
          f"(a competitor with an IDENTICAL IS-A thread — the 72-prime basis truly cannot distinguish; §15)")

    # --- B · σ_sem CARDINALITY (teaching dimension: min context entities to make gold unique) ---
    print(f"\n  σ_sem CARDINALITY — min context entities (revealed examples) to make the gold unique")
    print(f"  [the teaching dimension; LintGate greedy-cover on the entity-indexed discrete kill-matrix]:")
    resolvable = total - card_survivor
    for k in sorted(card_hist):
        n = card_hist[k]
        note = "  (0 entities needed — gold already the unique IS-A argmax)" if k == 0 else ""
        print(f"    σ_sem = {k:2d} : {n:4d}  {'█' * min(40, n)}{note}")
    mean_card = sum(k * n for k, n in card_hist.items()) / max(1, resolvable) if resolvable else 0.0
    print(f"    mean σ_sem (over the {resolvable} entity-resolvable tokens) = {mean_card:.2f}   "
          f"| {card_survivor} tokens no entity resolves (structural tie → freq-primary / definitional gap)")
    if card_phase:
        print(f"    phase (LintGate, independent-entity tests): bulk {card_phase['bulk']} / tail {card_phase['tail']}  "
              f"(bulk = one revealed example collapses the majority; tail = one-at-a-time)")

    # --- A · SURPRISE (belief revision off the frequency prior — the resolution signal) ---
    print(f"\n  SURPRISE S_sem = KL(δ_structure ‖ freq-prior) = −log₂ P_freq(resolved reading):")
    print(f"    mean S_sem over all tokens = {surprise_sum / max(1, total):.3f} bits")
    print(f"    structure OVERRODE the frequency-primary on {override_n} tokens "
          f"({100 * override_n / max(1, total):.1f}%) — the learning signal, where context moved the reading;")
    if override_n:
        print(f"      mean surprise on those overrides = {override_surprise_sum / override_n:.3f} bits "
              f"(high = a rare sense promoted by structure).")

    print(f"\n  READING: understanding measured three ways — the σ-TRAJECTORY (H↓ as structural scale widens), "
          f"the σ_sem CARDINALITY (teaching dimension, a Blum measure), and SURPRISE (where structure revises "
          f"the frequency prior). σ_sem is where conceptual entropy reaches 0; the residual is the closed basis's "
          f"honest silence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
