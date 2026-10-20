"""Import-light, named decisions for the supported sentence-head linkers."""


def head_linker_operation(lemma: str, at_head: bool) -> str:
    """Supported discourse reading of a normalized head linker (pure — pinned).

    Mid-clause readings remain local; unknown wording licenses no head relation.

    post: __return__ in ('CONTRAST', 'CONSEQUENCE', 'CLAUSE_COORD', 'TEMPORAL', 'none')
    post: at_head or __return__ == 'none'
    """
    if not at_head:
        return "none"
    if lemma in ("however", "yet", "still", "instead"):
        return "CONTRAST"
    if lemma in ("thus", "therefore", "hence", "consequently"):
        return "CONSEQUENCE"
    if lemma == "and":
        return "CLAUSE_COORD"
    if lemma == "then":
        return "TEMPORAL"
    return "none"
