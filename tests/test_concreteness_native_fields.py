"""The local concreteness source columns must retain their original units."""

from __future__ import annotations

from pathlib import Path

import pytest

from gse.curation.external_sources.concreteness import ConcretenessParser


def test_total_is_rating_count_and_percent_known_is_not_total(tmp_path: Path) -> None:
    source = tmp_path / "concreteness.csv"
    source.write_text(
        "Word,Bigram,Conc.M,Conc.SD,Unknown,Total,Percent_known,SUBTLEX\n"
        "same,0,2.64,1.45,18,5894,0.9969460468272819,21276\n",
        encoding="utf-8",
    )
    parser = ConcretenessParser(data_path=str(source))
    assert parser.load()
    entry = parser.entries["same"]
    assert entry.concreteness == 2.64
    assert entry.n_ratings == 5894
    assert entry.known_percent == pytest.approx(99.69460468272819)


def test_changed_source_columns_refuse_load(tmp_path: Path) -> None:
    source = tmp_path / "concreteness.csv"
    source.write_text("Word,Conc.M,Total\nsame,2.64,5894\n", encoding="utf-8")
    parser = ConcretenessParser(data_path=str(source))
    assert not parser.load()
    assert parser.entries == {}
