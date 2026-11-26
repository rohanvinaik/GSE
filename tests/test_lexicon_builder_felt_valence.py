from GSE.curation.lexicon_builder.felt_valence import feeling_sense, felt_valence


def _signs(swn=None, usas=None, vad=None):
    return (swn or {}), (usas or {}), (vad or {})


def test_a_feeling_noun_takes_the_converging_sign():
    signs = _signs({"wordnet:hatred:hate.n.01": -1}, {"hatred": {-1}}, {"hatred": -1})
    assert felt_valence("wordnet:hatred:hate.n.01", signs) == (-1, {"sentiwordnet": -1, "usas": -1, "nrc_vad": -1})


def test_lemma_sources_never_decide_without_the_sense_located_source():
    assert felt_valence("wordnet:pet:pet.n.03", _signs({}, {"pet": {1}}, {"pet": 1})) is None


def test_any_disagreement_leaves_the_cell_open():
    signs = _signs({"wordnet:relief:relief.n.01": 1}, {"relief": {1}}, {"relief": -1})
    assert felt_valence("wordnet:relief:relief.n.01", signs) is None


def test_only_nouns_whose_own_denotation_is_a_feeling():
    assert feeling_sense("anger.n.01") and not feeling_sense("dog.n.01")
    assert felt_valence("wordnet:dog:dog.n.01", _signs({"wordnet:dog:dog.n.01": 1}, {}, {"dog": 1})) is None


def test_a_sense_takes_the_felt_valence_its_members_agree_on():
    from GSE.curation.lexicon_builder.word_senses import Definition, Sense, sense_felt_valence

    def member(entry):
        return Definition(entry, 1, "noun", {"FEEL": 1}, {"FEEL": (1, 1.0, "wordnet", "ASSERTION")})

    signs = ({"wordnet:grief:grief.n.01": -1, "wordnet:joy:joy.n.01": 1}, {"grief": {-1}, "joy": {1}}, {})
    assert sense_felt_valence(Sense(members=[member("wordnet:grief:grief.n.01")]), signs)[0] == -1
    mixed = Sense(members=[member("wordnet:grief:grief.n.01"), member("wordnet:joy:joy.n.01")])
    assert sense_felt_valence(mixed, signs) is None
