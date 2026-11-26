"""Primary NSM chart definitions and frames; no inferred bank assignments."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NSMChartEntry:
    entry_id: str
    unit_id: str
    lemma: str
    pos: str
    definition: str
    definition_kind: str
    chart_heading: str
    forms: tuple[str, ...]
    frame_text: str
    source_reference: dict
    chart_notes: str
    frames_are: str


class NSMChartParser:
    """Expose exact chart units through the ordinary source parser boundary.

    Native equivalents remain native definitions; only the remaining chart
    units are introduced here. Nothing projects participants in a frame into
    its head's lexical vector, and silence never supplies a zero.
    """

    def __init__(self):
        self.entries: dict[str, list[NSMChartEntry]] = {}
        self._loaded = False

    def load(self) -> bool:
        from GSE.curation.external_sources.nsm_chart_data import SOURCE, chart_definition_records

        path = Path(__file__).resolve().parents[3] / SOURCE["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE["sha256"]:
            raise ValueError("NSM_CHART_SOURCE_REVISION_MISMATCH")
        entries: dict[str, list[NSMChartEntry]] = {}
        for record in chart_definition_records():
            entry = NSMChartEntry(**record)
            entries.setdefault(entry.lemma, []).append(entry)
        self.entries = entries
        self._loaded = True
        return True

    def get_all_words(self) -> list[str]:
        if not self._loaded:
            self.load()
        return sorted(self.entries)

    def get_entries(self, word: str) -> tuple[NSMChartEntry, ...]:
        if not self._loaded:
            self.load()
        return tuple(self.entries.get(word.lower(), ()))

    def to_primitives_for_entry(self, entry: NSMChartEntry) -> dict[str, int]:
        if not isinstance(entry, NSMChartEntry) or entry not in self.get_entries(entry.lemma):
            raise ValueError("UNKNOWN_NSM_CHART_DEFINITION")
        return {}

    def to_primitives(self, word: str) -> dict[str, int]:
        return {}
