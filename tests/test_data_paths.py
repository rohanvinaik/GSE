"""The encoder and decoder find GSE's own lexicon from any working directory (#20)."""

from pathlib import Path

import pytest

from gse.api import GSEDecoder, GSEEncoder

LEXICON = (Path(__file__).resolve().parents[1] / "data" / "lexicon_clean.db").resolve()


def test_encoder_default_lexicon_from_another_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    encoder = GSEEncoder()
    assert encoder.db_path.resolve() == LEXICON
    assert encoder.encode("The cell divides.").tokens


def test_decoder_default_lexicon_from_another_directory(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    decoder = GSEDecoder()
    assert decoder.db_path.resolve() == LEXICON
    assert decoder.lexeme_vectors
    assert not (tmp_path / "data" / "lexicon.db").exists()


def test_decoder_missing_lexicon_raises_and_creates_nothing(tmp_path):
    missing = tmp_path / "data" / "lexicon.db"
    missing.parent.mkdir()
    with pytest.raises(FileNotFoundError):
        GSEDecoder(db_path=str(missing))
    assert not missing.exists()
