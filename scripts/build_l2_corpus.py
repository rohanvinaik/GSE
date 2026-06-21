#!/usr/bin/env python3
"""Build the L2 register corpus — multi-source text → GSE feature profiles → labeled JSONL.

The training set for the Society-of-Mind register router (and, per register, the
dogfooding failure-list). Each output line:

    {"register_class", "genre", "source", "doc_id", "n_sentences",
     "vector": [...], "banks": {...}}

A top-line ``register_class`` splits SPEECH-derived prose (the Brown corpus —
genre-balanced, curated, public-domain) from NON-SPEECH structured text (words
meant to communicate but not represent literal speech: poetry/verse, reference/
dictionary entries, lists). That axis is the one Brown alone cannot cover.

Crash-safe: appends one line per document, resumes by skipping ``doc_id``s already
present, so a kill loses at most one document.

Usage:
    python scripts/build_l2_corpus.py [--docs-per-genre N] [--max-sents M]
                                      [--out data/l2_corpus.jsonl]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_FIX_SPACING = re.compile(r"\s+([.,;:!?'])")


def _join(sent_words) -> str:
    return " ".join(_FIX_SPACING.sub(r"\1", " ".join(w)) for w in sent_words)


# --- NON-SPEECH: hand-curated list/catalog samples (no dataset exists) ----------
_LISTS = [
    "Milk. Eggs. Bread. Two pounds of apples. Coffee. Paper towels. Chicken. Spinach.",
    "Passport. Phone charger. Three shirts. Toothbrush. Sunscreen. Hiking boots. Rain jacket.",
    "Two cups flour. One teaspoon salt. Three eggs. A cup of sugar. Half a stick of butter.",
    "Call the dentist. Pay the electric bill. Pick up the dry cleaning. Email the landlord.",
    "Model X200. Sixteen gigabytes of memory. A five hundred gigabyte drive. Two USB ports.",
    "Nine o'clock standup. Ten o'clock design review. Noon lunch. Two o'clock client call.",
    "Tomatoes. Onions. Garlic. Olive oil. Pasta. Parmesan. Fresh basil. A loaf of bread.",
    "One ladder. A box of screws. Two paint cans. A roll of tape. Sandpaper. A drop cloth.",
    "Towels. Sheets. A pillow. Soap. Shampoo. A first aid kit. Batteries. A flashlight.",
    "Fever. Sore throat. Headache. A dry cough. Fatigue. Loss of appetite. Body aches.",
    "Aisle four: cereal. Aisle seven: frozen goods. Aisle nine: cleaning supplies. Checkout.",
    "Wrench. Screwdriver. Pliers. A hammer. A level. A tape measure. Safety goggles. Gloves.",
]
_VERSE_FILES = ["blake-poems.txt", "whitman-leaves.txt", "milton-paradise.txt"]
_SHAKESPEARE_FILES = ["shakespeare-macbeth.txt", "shakespeare-hamlet.txt",
                      "shakespeare-caesar.txt"]


def _chunks(sents, max_sents: int, n_chunks: int):
    for ci in range(n_chunks):
        chunk = sents[ci * max_sents:(ci + 1) * max_sents]
        if chunk:
            yield ci, chunk


def _hf_stream(name, cfg, field: str, n: int, max_sents: int, group: int = 1):
    """Yield ``(doc_index, text)`` for up to ``n`` docs streamed from a HuggingFace
    dataset (the contemporary-register augment — modern text vs the 1961 Brown).
    Streaming = no multi-GB download. ``group`` short examples are concatenated into
    one doc (tweets), and each doc is capped at ~``max_sents`` sentences (HF reviews
    can be very long → bound the profile cost)."""
    import datasets
    ds = datasets.load_dataset(name, cfg, split="train", streaming=True)
    it = iter(ds)
    for di in range(n):
        parts = []
        for _ in range(group):
            ex = next(it, None)
            if ex is None:
                break
            t = (ex.get(field) or "").strip()
            if t:
                parts.append(t)
        if not parts:
            break
        sents = re.split(r"(?<=[.!?])\s+", " ".join(parts))
        yield di, " ".join(sents[:max_sents])


def _providers(docs_per_genre: int, max_sents: int):
    """Yield ``(register_class, genre, source, doc_id, text)`` across all sources.

    Genres must be declared in ``gse.discourse.REGISTER_TAXONOMY`` (validated in
    ``main``) so the corpus and the router share one label space.
    """
    from nltk.corpus import brown, gutenberg, nps_chat, reuters

    # SPEECH-derived prose — Brown's genre-balanced documents.
    for cat in brown.categories():
        for fid in brown.fileids(categories=cat)[:docs_per_genre]:
            yield ("speech", cat, "brown", f"brown/{fid}",
                   _join(brown.sents(fid)[:max_sents]))

    # SPEECH · chat — NPS chat posts (fragmentary, conversational), chunked.
    # Strip the corpus's `U\d+` username-anonymization tokens (not chat language).
    _user = re.compile(r"U\d+")
    posts = [[w for w in p if not _user.fullmatch(w)] for p in nps_chat.posts()]
    for ci in range(docs_per_genre):
        chunk = [p for p in posts[ci * max_sents:(ci + 1) * max_sents] if p]
        if chunk:
            yield ("speech", "chat", "nps_chat", f"chat/{ci}", _join(chunk))

    # SPEECH · newswire — Reuters wire stories.
    for fid in reuters.fileids()[:docs_per_genre]:
        yield ("speech", "newswire", "reuters", f"newswire/{fid}",
               _join(reuters.sents(fid)[:max_sents]))

    # SPEECH · archaic_english — the 1611 KJV (long → scales freely).
    for ci, chunk in _chunks(gutenberg.sents("bible-kjv.txt"), max_sents, docs_per_genre):
        yield ("speech", "archaic_english", "gutenberg",
               f"archaic/kjv-{ci}", _join(chunk))

    # SPEECH · shakespeare — Early Modern verse drama (split across the plays).
    sh_per = max(2, docs_per_genre // len(_SHAKESPEARE_FILES))
    for sf in _SHAKESPEARE_FILES:
        for ci, chunk in _chunks(gutenberg.sents(sf), max_sents, sh_per):
            yield ("speech", "shakespeare", "gutenberg",
                   f"shakespeare/{sf}-{ci}", _join(chunk))

    # NON-SPEECH · poetry/verse — gutenberg verse, chunked (split across files).
    po_per = max(2, docs_per_genre // len(_VERSE_FILES))
    for vf in _VERSE_FILES:
        for ci, chunk in _chunks(gutenberg.sents(vf), max_sents, po_per):
            yield ("non_speech", "poetry", "gutenberg",
                   f"poetry/{vf}-{ci}", _join(chunk))

    # NON-SPEECH · reference/wiki — clusters of Wiktionary glosses (plain-text defs).
    kaikki = ROOT / "data" / "external" / "wiktionary" / "kaikki-english.jsonl"
    if kaikki.exists():
        glosses, doc_i = [], 0
        with kaikki.open() as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for s in e.get("senses", []):
                    g = (s.get("glosses") or [None])[0]
                    if g:
                        glosses.append(g)
                if len(glosses) >= 8:
                    yield ("non_speech", "reference", "wiktionary",
                           f"ref/{doc_i}", " ".join(glosses[:8]))
                    glosses, doc_i = [], doc_i + 1
                    if doc_i >= docs_per_genre:
                        break

    # NON-SPEECH · lists — hand-curated (no clean dataset; classical-AI scale).
    for i, txt in enumerate(_LISTS):
        yield ("non_speech", "list", "curated", f"list/{i}", txt)

    # SPEECH · contemporary HF augment — modern text (vs the 1961 Brown), streamed.
    # New super-registers `review`/`social` add SoM specialists; `modern_news` is the
    # diachronic augment of `news` under reportorial.
    for di, text in _hf_stream("ag_news", None, "text", docs_per_genre, max_sents):
        yield ("speech", "modern_news", "ag_news", f"modern_news/{di}", text)
    for di, text in _hf_stream("imdb", None, "text", docs_per_genre, max_sents):
        yield ("speech", "reviews_modern", "imdb", f"reviews_modern/{di}", text)
    for di, text in _hf_stream("tweet_eval", "emotion", "text", docs_per_genre,
                               max_sents, group=15):
        yield ("speech", "twitter", "tweet_eval", f"twitter/{di}", text)


def _already_done(out: Path) -> set:
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                done.add(json.loads(line)["doc_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-per-genre", type=int, default=8)
    ap.add_argument("--max-sents", type=int, default=40)
    ap.add_argument("--out", default=str(ROOT / "data" / "l2_corpus.jsonl"))
    ap.add_argument("--fresh", action="store_true",
                    help="re-encode from scratch: discard the existing corpus first so "
                         "encoder/tokenizer enhancements actually take effect (the "
                         "append/resume default never re-parses already-done docs)")
    args = ap.parse_args()

    import nltk
    for name, path in [("brown", "corpora/brown"), ("gutenberg", "corpora/gutenberg"),
                       ("nps_chat", "corpora/nps_chat"), ("reuters", "corpora/reuters"),
                       ("punkt", "tokenizers/punkt")]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(name, quiet=True)

    from gse.api import GSEEncoder
    from gse.discourse import register_class_of, text_profile

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.fresh and out.exists():
        out.unlink()
        print(f"[fresh] discarded existing corpus → full re-encode ({out})")
    done = _already_done(out)
    enc = GSEEncoder()
    n_written = 0
    with out.open("a") as fh:
        for reg_class, genre, source, doc_id, text in _providers(
                args.docs_per_genre, args.max_sents):
            # Keep providers and the taxonomy in sync: every emitted genre must be
            # declared, and its declared class must match what the provider claims.
            if register_class_of(genre) != reg_class:
                raise ValueError(
                    f"{doc_id}: genre {genre!r} is class {register_class_of(genre)!r}, "
                    f"not {reg_class!r} — fix REGISTER_TAXONOMY or the provider")
            if doc_id in done or not text.strip():
                continue
            p = text_profile(enc, text)
            fh.write(json.dumps({
                "register_class": reg_class, "genre": genre, "source": source,
                "doc_id": doc_id, "n_sentences": p.n_sentences,
                "vector": p.vector(), "banks": p.to_dict(),
            }) + "\n")
            fh.flush()
            n_written += 1
            print(f"  [{reg_class:10s}/{genre:14s}] {doc_id}  ({p.n_sentences} sents)")
    enc.close()
    print(f"\n[done] wrote {n_written} new records → {out} ({len(done) + n_written} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
