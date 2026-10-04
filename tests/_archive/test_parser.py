import pytest
from gse.parser import POS, Parser


@pytest.fixture
def parser():
    try:
        return Parser()
    except OSError:
        pytest.skip("SpaCy model not found. Run 'python -m spacy download en_core_web_sm'")

def test_basic_parse(parser):
    result = parser.parse_single("The dog runs.")
    assert len(result.tokens) == 4  # The, dog, runs, .
    # Lemma might vary slightly depending on Spacy version, but dog->dog, runs->run usually.
    # Note: Spacy usually lemmatizes 'The' to 'the'.
    assert result.tokens[1].lemma == "dog"
    assert result.tokens[2].lemma == "run"

def test_pos_tagging(parser):
    result = parser.parse_single("The big dog runs quickly.")
    # result.tokens[0] is 'The' (DET)
    assert result.tokens[1].pos == POS.ADJ  # big
    assert result.tokens[2].pos == POS.NOUN  # dog
    assert result.tokens[3].pos == POS.VERB  # runs
    assert result.tokens[4].pos == POS.ADV   # quickly

def test_dependency_structure(parser):
    result = parser.parse_single("The dog chased the cat.")
    # Find tokens by lemma
    # Note: chase->chase
    dog = [t for t in result.tokens if t.lemma == "dog"][0]
    chased = [t for t in result.tokens if t.lemma == "chase"][0]
    cat = [t for t in result.tokens if t.lemma == "cat"][0]

    # Dog should depend on chased (subject)
    assert dog.head_idx == chased.idx
    # Cat should depend on chased (object)
    assert cat.head_idx == chased.idx

def test_semantic_roles(parser):
    result = parser.parse_single("John gave Mary a book.")

    role_map = {r.role: result.tokens[r.token_idx].lemma for r in result.roles}

    # nsubj -> agent
    assert "agent" in role_map
    assert role_map["agent"] == "john"

    # dative/iobj -> recipient
    # gave Mary -> Mary is recipient
    assert "recipient" in role_map
    assert role_map["recipient"] == "mary"

def test_bottom_up_order(parser):
    result = parser.parse_single("The big dog runs.")
    order = result.bottom_up_order()

    # Leaves should come before their heads
    # The -> dog
    # big -> dog
    # dog -> runs

    the_idx = [t.idx for t in result.tokens if t.surface == "The"][0]
    dog_idx = [t.idx for t in result.tokens if t.lemma == "dog"][0]
    runs_idx = [t.idx for t in result.tokens if t.lemma == "run"][0]

    assert order.index(the_idx) < order.index(dog_idx)
    assert order.index(dog_idx) < order.index(runs_idx)

def test_multiple_sentences(parser):
    results = parser.parse("The dog runs. The cat sleeps.")
    assert len(results) == 2
