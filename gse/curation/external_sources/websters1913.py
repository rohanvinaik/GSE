"""Native historical dictionary definitions from explicit, hashed local snapshots.

The site's meaning/hw/pos/def tags provide structure. English text and variant
spellings never supply bank assignments or authorize copying another definition.
Loading reads only the configured manifest and snapshots; it never downloads.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

WEBSTERS_MANIFEST = Path(__file__).resolve().parents[3] / "data/external/websters1913/manifest.json"
_POS = {"n.": "noun", "v.": "verb", "a.": "adj", "adv.": "adv"}


@dataclass(frozen=True)
class WebsterDefinition:
    entry_id: str
    lemma: str
    word: str
    pos: str
    definition: str
    native_id: str
    native_pos: str
    native_entry_text: str
    source_url: str
    source_sha256: str
    source_html: str
    retrieved_utc: str
    definition_index: int
    identity_scheme: str = "gse.websters1913-native-definition/1"


class _Meanings(HTMLParser):
    """Read source-declared definition units, preserving the whole entry text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = []
        self.current = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag == "meaning":
            if self.current is not None:
                raise ValueError("WEBSTERS_NESTED_MEANING")
            self.current = {"text": [], "hw": [], "pos": [], "definitions": []}
            self.stack = [tag]
        elif self.current is not None:
            self.stack.append(tag)
            if tag == "def":
                self.current["definitions"].append([])

    def handle_endtag(self, tag):
        if self.current is None:
            return
        if not self.stack or self.stack[-1] != tag:
            raise ValueError("WEBSTERS_MALFORMED_MEANING_TAGS")
        self.stack.pop()
        if tag == "meaning":
            self.records.append(self.current)
            self.current = None

    def handle_data(self, data):
        if self.current is None:
            return
        self.current["text"].append(data)
        for field in ("hw", "pos"):
            if field in self.stack:
                self.current[field].append(data)
        if "def" in self.stack:
            self.current["definitions"][-1].append(data)

    def close(self):
        super().close()
        if self.current is not None:
            raise ValueError("WEBSTERS_UNCLOSED_MEANING")


class Websters1913Parser:
    def __init__(self, data_path: str | Path | None = None):
        self.data_path = Path(data_path) if data_path is not None else WEBSTERS_MANIFEST
        self.entries: dict[str, list[WebsterDefinition]] = {}
        self._loaded = False

    def load(self) -> bool:
        document = json.loads(self.data_path.read_text(encoding="utf-8"))
        if (
            not isinstance(document, dict)
            or set(document) != {"format", "records"}
            or document["format"] != "gse.websters1913-snapshots/1"
            or not isinstance(document["records"], list)
            or not document["records"]
        ):
            raise ValueError("INVALID_WEBSTERS_MANIFEST")
        entries = {}
        identities = set()
        for record in document["records"]:
            if (
                not isinstance(record, dict)
                or set(record) != {"native_id", "url", "file", "sha256", "retrieved_utc"}
                or any(not isinstance(value, str) or not value.strip() for value in record.values())
            ):
                raise ValueError("INVALID_WEBSTERS_SOURCE_RECORD")
            source = (self.data_path.parent / record["file"]).resolve()
            if not source.is_relative_to(self.data_path.parent.resolve()):
                raise ValueError("WEBSTERS_SNAPSHOT_OUTSIDE_MANIFEST")
            raw = source.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != record["sha256"]:
                raise ValueError("WEBSTERS_SOURCE_HASH_MISMATCH")
            html = raw.decode("utf-8")
            parsed = _Meanings()
            parsed.feed(html)
            parsed.close()
            if not parsed.records:
                raise ValueError("WEBSTERS_MISSING_NATIVE_MEANING")
            for meaning in parsed.records:
                word = "".join(meaning["hw"]).strip()
                pos = "".join(meaning["pos"]).strip()
                text = "".join(meaning["text"]).strip()
                if not word or pos not in _POS or not meaning["definitions"]:
                    raise ValueError("WEBSTERS_MISSING_DEFINITION_IDENTITY")
                for index, parts in enumerate(meaning["definitions"]):
                    definition = " ".join("".join(parts).split())
                    if not definition:
                        raise ValueError("WEBSTERS_EMPTY_NATIVE_DEFINITION")
                    payload = json.dumps([record["native_id"], word, pos, text, index, definition], ensure_ascii=False)
                    identity = hashlib.sha256(payload.encode()).hexdigest()
                    entry_id = f"websters1913:{quote(record['native_id'], safe='')}:{identity}"
                    if entry_id in identities:
                        raise ValueError("WEBSTERS_DUPLICATE_NATIVE_DEFINITION")
                    identities.add(entry_id)
                    entry = WebsterDefinition(
                        entry_id,
                        word.lower(),
                        word,
                        _POS[pos],
                        definition,
                        record["native_id"],
                        pos,
                        text,
                        record["url"],
                        digest,
                        html,
                        record["retrieved_utc"],
                        index,
                    )
                    entries.setdefault(entry.lemma, []).append(entry)
        self.entries = entries
        self._loaded = True
        return True

    def get_all_words(self) -> set[str]:
        return set(self.entries)

    def get_entries(self, word: str) -> list[WebsterDefinition]:
        return list(self.entries.get(word.lower(), ()))

    def get_definition_entries(self, words):
        for word in sorted(set(words)):
            yield from self.get_entries(word)

    def to_primitives(self, word: str) -> dict[str, int]:
        return {}

    def to_primitives_with_confidence(self, word: str) -> dict[str, tuple[int, float]]:
        return {}

    def to_primitives_for_entry(self, entry: WebsterDefinition) -> dict[str, int]:
        if not isinstance(entry, WebsterDefinition):
            raise ValueError("INVALID_WEBSTERS_DEFINITION")
        return {}
