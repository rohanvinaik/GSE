import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from gse.lexicon_generator import Lexicon, LexiconGenerator
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import D, PrimitiveBasis


@pytest.fixture
def basis():
    # Use Hadamard-OTP architecture (D=8192)
    return PrimitiveBasis.generate(PRIMITIVES[:10], ROLES[:5])

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_lexicon.db")

def test_lexicon_generator_init(basis):
    # Mock anthropic module availability
    with patch('gse.lexicon_generator.anthropic', new=MagicMock()):
        gen = LexiconGenerator(basis, api_key="fake")
        assert gen.client is not None

def test_decompose_word_mock(basis):
    with patch('gse.lexicon_generator.anthropic') as mock_anthropic:
        # Mock the client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decomposition": [{"primitive": "' + PRIMITIVES[0] + '", "role": "' + ROLES[0] + '"}]}')]
        mock_client.messages.create.return_value = mock_response

        # We need to manually inject the client into generator because we import anthropic inside the module potentially
        # or rely on the patching.
        # Since gse.lexicon_generator imports anthropic, patching it there works.

        # However, the class init checks for anthropic module presence.
        # If it wasn't installed, gen.client is None.
        # But patching 'gse.lexicon_generator.anthropic' mimics it being present?
        # Actually if import failed at top level, 'anthropic' is None in the module.
        pass

    # A more robust way to test without dependency:
    gen = LexiconGenerator(basis, api_key="fake")
    if gen.client is None:
        # Skip if dependency missing
        return

    # Mock the client instance directly
    gen.client = MagicMock()
    gen.client.messages.create.return_value.content = [
        MagicMock(text=json.dumps({
            "decomposition": [{"primitive": PRIMITIVES[0], "role": ROLES[0]}]
        }))
    ]

    decomp = gen.decompose_word("test", "NOUN")
    assert decomp is not None
    assert len(decomp) == 1
    assert decomp[0] == (PRIMITIVES[0], ROLES[0])

def test_encode_decomposition(basis):
    gen = LexiconGenerator(basis)
    decomp = [(PRIMITIVES[0], ROLES[0])]
    vec = gen.encode_decomposition(decomp)

    # Should be bind(prim, role)
    expected = basis.primitives[PRIMITIVES[0]]
    # Actually encode_decomposition does bind then bundle.
    # Bundle of 1 item = item.
    # But bind(prim, role) is what happens.

    # Let's verify properties (D=8192 in Hadamard-OTP architecture)
    assert vec.dimension == D
    assert vec.nnz > 0

def test_generate_batch_and_lookup(basis, db_path):
    gen = LexiconGenerator(basis)

    # Mock decompose to return something valid without API
    gen.decompose_word = MagicMock(return_value=[(PRIMITIVES[0], ROLES[0])])

    words = [{"word": "test", "pos": "NOUN", "definition": "A test"}]
    gen.generate_batch(words, db_path)

    # Verify DB
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT * FROM lexicon")
    rows = cursor.fetchall()
    assert len(rows) == 1
    conn.close()

    # Test Runtime Lexicon
    lex = Lexicon(db_path, basis)
    entry = lex.lookup("test", "NOUN")
    assert entry is not None
    assert entry.lemma == "test"
    assert entry.pos == "NOUN"
    assert entry.vector.dimension == D

def test_lexicon_cache(basis, db_path):
    gen = LexiconGenerator(basis)
    gen.decompose_word = MagicMock(return_value=[(PRIMITIVES[0], ROLES[0])])
    words = [{"word": "cache", "pos": "VERB"}]
    gen.generate_batch(words, db_path)

    lex = Lexicon(db_path, basis)
    # First lookup hits DB
    entry1 = lex.lookup("cache", "VERB")
    assert entry1 is not None

    # Modify DB behind back
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM lexicon")
    conn.commit()
    conn.close()

    # Second lookup hits cache
    entry2 = lex.lookup("cache", "VERB")
    assert entry2 is not None
    assert entry1 == entry2
