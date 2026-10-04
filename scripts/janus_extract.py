"""Janus figure-example extraction pipeline (route B — candidate generation at scale).

Search → Extract → Structure → Store, per ``STRUCTURED_WEB_KNOWLEDGE_EXTRACTION.md``,
shaped by the V1 contract:

  * **LLM-as-parser-not-source** — we fetch reference pages that *discuss a figure* and
    have Ollama extract the example sentences the page presents AS that figure, copied
    verbatim. The model never invents examples; if the page has none, it returns [].
  * **Typed skeleton** — Ollama (`qwen3.5:4b`, native /api/chat, ``format`` = a JSON
    schema, ``think`` off) can only emit the fixed ``{examples:[{text, verbatim}]}``
    shape. The figure is fixed per pass (we fetched its article), so there is no label
    to hallucinate.
  * **Provenance + the two-rater gate** — every candidate stores its source URL and is
    written ``cleared_self=False`` / ``cleared_user=False``: a CANDIDATE POOL, gated out
    of training until both raters clear it (the audit step).

Fetch is the keyless MediaWiki API (clean plaintext). Reproducible, no API keys.

Usage (from repo root):
    python scripts/janus_extract.py --figures metaphor --limit 8 --dry-run   # validate
    python scripts/janus_extract.py --bank similarity --limit 8              # store candidates
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gse.pragmatics.figure_store import (  # noqa: E402
    FigureExample,
    Label,
    ingest_example,
    init_db,
)
from gse.pragmatics.figures import BY_NAME, FIGURE_NAMES, figures_in_bank  # noqa: E402

DB_PATH = str(Path(__file__).resolve().parents[1] / "data" / "janus_figures.db")
_UA = "GSE-Janus-curation/0.1 (research; contact via repo)"
_OLLAMA = "http://localhost:11434/api/chat"
_MODEL = "qwen3.5:4b"
_WIKI = "https://en.wikipedia.org/w/api.php"

# Wikipedia article titles that differ from the figure name (default = Title-case name).
_WIKI_TITLE = {
    "verbal_irony": "Irony",
    "humor_gardenpath": "Garden-path sentence",
    "rhetorical_question": "Rhetorical question",
    "meiosis": "Meiosis (figure of speech)",
    "litotes": "Litotes",
    "metalepsis": "Metalepsis",
    "antonomasia": "Antonomasia",
    "catachresis": "Catachresis",
}

def _parse_examples(content: str) -> list[str]:
    """Lenient parse of the model's JSON: strip markdown fences, accept a bare list or
    ``{examples:[...]}``, and pull text from string or dict items."""
    m = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
    if m:
        content = m.group(1)
    try:
        parsed = json.loads(content.strip())
    except json.JSONDecodeError:
        return []
    items = parsed.get("examples", []) if isinstance(parsed, dict) else parsed
    # Reject definitional glosses ("'the crown' to refer to the monarchy") — Face B needs
    # the figure IN USE in a span, not its definition.
    gloss = (" refer to ", " refers to", " to represent", " stands for ", "used to refer")
    out: list[str] = []
    for it in items if isinstance(items, list) else []:
        if isinstance(it, str):
            t = it.strip()
        elif isinstance(it, dict):
            t = (it.get("text") or it.get("sentence") or it.get("example") or "").strip()
        else:
            t = ""
        if t and not any(g in t.lower() for g in gloss):
            out.append(t)
    return out


def wiki_extract(title: str) -> str | None:
    """Clean plaintext of a Wikipedia article via the MediaWiki API (no scraping)."""
    params = {
        "action": "query", "titles": title, "prop": "extracts",
        "explaintext": "true", "exintro": "false", "format": "json",
        "redirects": "1",
    }
    url = f"{_WIKI}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    for pid, page in data.get("query", {}).get("pages", {}).items():
        if pid != "-1":
            return page.get("extract") or None
    return None


def ollama_extract(figure: str, definition: str, text: str, limit: int) -> list[str]:
    """Pull example sentences the page presents AS this figure (verbatim, no invention)."""
    prompt = (
        f"The text below is an encyclopedia article about the figure of speech "
        f"'{figure}' ({definition}).\n\n"
        f"Extract up to {limit} short example sentences that the article presents as "
        f"INSTANCES of {figure}. Each must be a COMPLETE SENTENCE that USES {figure} in "
        f"context — NOT a definition, gloss, or '\"X\" refers to Y' description. Copy each "
        f"example VERBATIM from the text. Do NOT invent examples, do NOT include the "
        f"article's prose explanation, and if the article gives no clear labelled "
        f"examples use an empty list.\n\n"
        f'Respond with ONLY a JSON object of this exact shape — no markdown, no prose:\n'
        f'{{"examples": ["<verbatim example sentence>", "..."]}}\n\n'
        f"ARTICLE:\n{text[:9000]}"
    )
    payload = json.dumps({
        "model": _MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {"temperature": 0.1, "num_predict": 700, "num_ctx": 12288},
    }).encode()
    req = urllib.request.Request(_OLLAMA, data=payload,
                                headers={"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=180).read())
    return _parse_examples(raw.get("message", {}).get("content", ""))


def fetch_html(url: str) -> str | None:
    """Fetch a non-wiki reference page and strip HTML to readable text (the doc's §4)."""
    import html
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        raw = urllib.request.urlopen(req, timeout=20).read(120_000).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 — a blocked/404 source is skipped, not fatal
        return None
    for tag in ("script", "style", "nav", "header", "footer"):
        raw = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<(?:p|div|br|h[1-6]|li)[^>]*>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<[^>]+>", " ", raw)
    txt = re.sub(r"\n{3,}", "\n\n", html.unescape(raw)).strip()
    return txt or None


# literarydevices.net slugs that differ from the figure name.
_LITDEV_SLUG = {"verbal_irony": "irony", "humor_gardenpath": "", "rhetorical_question": "rhetorical-question"}


def sources(fig: str):
    """Yield (label, url, text) per reference source for a figure (wiki + litdev)."""
    title = _WIKI_TITLE.get(fig, fig.replace("_", " ").title())
    yield (f"Wikipedia: {title}",
           f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}",
           wiki_extract(title))
    slug = _LITDEV_SLUG.get(fig, fig.replace("_", "-"))
    if slug:
        url = f"https://literarydevices.net/{slug}/"
        yield (f"literarydevices.net/{slug}", url, fetch_html(url))


def generate_literal(figure: str, example: str) -> str | None:
    """Generate a matched LITERAL control (same topic, no figure) with the local model.

    Literals are the negative class, not attested figures — so *generation* (not
    extraction) is right: there is no figure to contaminate; the requirement is only
    that the sentence be figure-free and on the same subject.
    """
    prompt = (
        f"Here is a sentence that uses the figure of speech '{figure}':\n\"{example}\"\n\n"
        f"Write ONE plain, LITERAL sentence about the same subject matter that contains NO "
        f"figure of speech at all (no metaphor, simile, irony, hyperbole, …) — just an "
        f"ordinary, factual statement.\n"
        f'Respond with ONLY JSON: {{"literal": "<the sentence>"}}'
    )
    payload = json.dumps({
        "model": _MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0.4, "num_predict": 200, "num_ctx": 2048},
    }).encode()
    req = urllib.request.Request(_OLLAMA, data=payload,
                                headers={"Content-Type": "application/json"})
    try:
        raw = json.loads(urllib.request.urlopen(req, timeout=120).read())
        content = raw.get("message", {}).get("content", "")
        m = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if m:
            content = m.group(1)
        return (json.loads(content.strip()).get("literal") or "").strip() or None
    except Exception:  # noqa: BLE001 — a failed literal is skipped, not fatal
        return None


def resolve_figures(args) -> list[str]:
    if args.bank:
        return [f.name for f in figures_in_bank(args.bank)]
    if args.figures:
        return args.figures
    raise SystemExit("specify --figures or --bank")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--figures", nargs="*", help="figure names to extract")
    ap.add_argument("--bank", help="extract every figure in this bank")
    ap.add_argument("--limit", type=int, default=8, help="max examples per figure")
    ap.add_argument("--dry-run", action="store_true", help="print, do not store")
    ap.add_argument("--literals", action="store_true",
                    help="also generate a matched literal control per figure example")
    args = ap.parse_args()

    figs = resolve_figures(args)
    for f in figs:
        if f not in FIGURE_NAMES:
            raise SystemExit(f"unknown figure {f!r}")

    conn = None if args.dry_run else init_db(DB_PATH)
    total = 0
    for fig in figs:
        meta = BY_NAME[fig]
        fcount, seen = 0, set()
        for label, url, text in sources(fig):
            if not text:
                continue
            try:
                examples = ollama_extract(fig, meta.definition, text, args.limit)
            except Exception as e:  # noqa: BLE001 — surface, skip, continue (bounded register)
                print(f"  [{fig}] {label}: extraction error: {e}")
                continue
            for t in examples:
                key = t.lower().strip()
                if key in seen:
                    continue  # per-figure dedup across sources
                seen.add(key)
                print(f"  [{fig}] {t}   ⟨{label}⟩")
                if conn is not None:
                    ingest_example(conn, FigureExample(
                        text=t, source=label,
                        labeled_by=f"extracted: {label}",
                        labels=[Label(fig, 0.70, f"extracted:{url}",
                                      "candidate — pending two-rater clearance", cleared_self=False)],
                        source_url=url,
                    ), apply=True)
                fcount += 1
                if args.literals:
                    lit = generate_literal(fig, t)
                    if lit and lit.lower().strip() not in seen:
                        seen.add(lit.lower().strip())
                        print(f"      ↳ literal: {lit}")
                        if conn is not None:
                            ingest_example(conn, FigureExample(
                                text=lit, source="generated: ollama qwen3.5:4b",
                                labeled_by="generated literal (matched control)",
                                labels=[Label("literal", 0.70, "generated:ollama",
                                              f"matched literal control for {fig}", cleared_self=False)],
                                matched_to=fig,
                            ), apply=True)
        print(f"[{fig}] {fcount} candidate(s)")
        total += fcount
    where = "DRY-RUN (not stored)" if args.dry_run else DB_PATH
    print(f"\n{total} candidates across {len(figs)} figure(s) → {where}")
    if not args.dry_run:
        print("All candidates uncleared (cleared_self=cleared_user=0) — audit next.")


if __name__ == "__main__":
    main()
