"""
Wiktionary Local Dump Parser

Parses pre-processed Wiktionary dump for:
- Definitions (gloss text analysis)
- Etymology (derivation patterns)
- Part of speech
- Semantic relationships (synonyms, antonyms)

Explicit native mode streams complete local JSON records and sense identities.
The historical SQLite API remains available only through its separate mode.
Data source: kaikki.org pre-processed JSON dumps.
"""

import hashlib
import json
import logging
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Literal, Optional, TypedDict

from GSE.curation.external_sources.base_parser import BaseExternalParser
from GSE.namespace import current_id, identity_form

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external"
WIKTIONARY_DIR = DATA_DIR / "wiktionary"
WIKTIONARY_DB = WIKTIONARY_DIR / "wiktionary-en.sqlite"
WIKTIONARY_DUMP = WIKTIONARY_DIR / "kaikki-english.jsonl"


@dataclass
class WiktionaryEntry:
    """Entry from Wiktionary."""

    word: str
    pos: str
    definition: str
    etymology: Optional[str]
    synonyms: List[str]
    antonyms: List[str]


@dataclass(frozen=True)
class WiktionaryDefinition:
    """One native sense, with complete sense and enclosing record context."""

    entry_id: str
    lemma: str
    word: str
    pos: str
    definition: str
    native_id: str
    senseid_path: tuple[str, ...]
    identity_scheme: str
    native_sense: dict
    record_context: dict
    record_sha256: str
    source_sha256: str
    source_line: int
    sense_index: int
    sense_count: int


_NativeReferenceKind = Literal["alt_of", "form_of"]
_NativeReferenceCode = Literal[
    "TARGET_DEFINITIONS_AVAILABLE",
    "TARGET_NOT_FOUND",
    "TARGET_HAS_ONLY_OTHER_POS",
    "TARGET_IS_REFERENCE",
    "AMBIGUOUS_TARGET_SENSES",
]


class _PendingNativeReference(TypedDict):
    source_entry: dict
    relation: _NativeReferenceKind
    link: dict


class WiktionaryDefinitionReference(_PendingNativeReference):
    """A one-hop native reference packet; no sense choice or bank assertion."""

    format: Literal["GSE.wiktionary-definition-reference/1"]
    code: _NativeReferenceCode
    target_word: str
    target_lookup: str
    target_entries: list[dict]
    other_pos_entries: list[dict]
    source_sha256: str


def _native_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(identity_form(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def _lookup_form(word: str) -> str:
    return word.strip().lower().replace("_", " ")


def _source_identity(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _native_reference_links(entry: WiktionaryDefinition) -> tuple[tuple[_NativeReferenceKind, dict], ...]:
    """Validate explicit native links, including links on one-hop targets."""
    if not isinstance(entry.native_sense, dict):
        raise ValueError("INVALID_WIKTIONARY_REFERENCE_ENTRY")
    result: list[tuple[_NativeReferenceKind, dict]] = []
    relations: tuple[_NativeReferenceKind, ...] = ("alt_of", "form_of")
    for relation in relations:
        if relation not in entry.native_sense:
            continue
        links = entry.native_sense[relation]
        if not isinstance(links, list):
            raise ValueError(f"MALFORMED_WIKTIONARY_REFERENCE_LINKS:{entry.entry_id}:{relation}")
        for link in links:
            if not isinstance(link, dict):
                raise ValueError(f"MALFORMED_WIKTIONARY_REFERENCE_LINK:{entry.entry_id}:{relation}")
            word = link.get("word")
            if not isinstance(word, str) or not _lookup_form(word).strip():
                raise ValueError(f"MALFORMED_WIKTIONARY_REFERENCE_TARGET:{entry.entry_id}:{relation}")
            result.append((relation, link))
    return tuple(result)


def _native_reference_record(entry: WiktionaryDefinition, source_sha256: str) -> dict:
    """Copy a complete, internally consistent native leaf into JSON data."""
    if entry.source_sha256 != source_sha256:
        raise ValueError("WIKTIONARY_REFERENCE_SOURCE_MISMATCH")
    try:
        record = json.loads(json.dumps(asdict(entry), ensure_ascii=False, allow_nan=False))
        expected_id = "wiktionary:" + entry.native_id + ":" + _native_digest(
            {"record_context": entry.record_context, "native_sense": entry.native_sense}
        )
        valid = (
            entry.entry_id == expected_id
            and current_id(entry.identity_scheme) == "GSE.wiktionary-native-leaf/1"
            and entry.native_id == entry.native_sense["id"]
            and entry.word == entry.record_context["word"]
            and entry.lemma == _lookup_form(entry.word)
            and entry.pos == entry.record_context["pos"]
            and entry.definition == "\n".join(entry.native_sense.get("glosses", []))
            and tuple(entry.senseid_path) == tuple(entry.native_sense.get("senseid", []))
            and type(entry.source_line) is int
            and entry.source_line > 0
            and type(entry.sense_index) is int
            and type(entry.sense_count) is int
            and 0 <= entry.sense_index < entry.sense_count
            and len(entry.record_sha256) == 64
            and all(char in "0123456789abcdef" for char in entry.record_sha256)
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("INVALID_WIKTIONARY_REFERENCE_ENTRY") from error
    if not valid:
        raise ValueError("INVALID_WIKTIONARY_REFERENCE_ENTRY")
    return record


# Definition keywords to primitives mapping
# These patterns extract semantic primitives from definition text
DEFINITION_PATTERNS = {
    # Action/movement words
    r"\bto move\b|\bmoving\b|\bmotion\b": {"MOVE": 1},
    r"\bto run\b|\brunning\b": {"MOVE": 1, "BODY": 1},
    r"\bto walk\b|\bwalking\b": {"MOVE": 1, "BODY": 1},
    # Communication words
    r"\bto say\b|\bsaying\b|\bsaid\b": {"SAY": 1, "WORDS": 1},
    r"\bto tell\b|\btelling\b|\btold\b": {"SAY": 1, "WORDS": 1},
    r"\bto speak\b|\bspeaking\b|\bspoken\b": {"SAY": 1, "WORDS": 1},
    r"\bto write\b|\bwriting\b|\bwritten\b": {"SAY": 1, "WORDS": 1},
    r"\bcommunicat": {"SAY": 1},
    # Cognition words
    r"\bto think\b|\bthinking\b|\bthought\b": {"THINK": 1},
    r"\bto know\b|\bknowing\b|\bknowledge\b": {"KNOW": 1},
    r"\bto understand\b|\bunderstanding\b": {"KNOW": 1, "THINK": 1},
    r"\bto believe\b|\bbelief\b": {"THINK": 1, "MAYBE": 1},
    r"\bto remember\b|\bmemory\b": {"KNOW": 1, "BEFORE": 1},
    r"\bto learn\b|\blearning\b": {"KNOW": 1, "START": 1},
    r"\bmental\b|\bcognitive\b": {"THINK": 1},
    # Emotion/feeling words
    r"\bto feel\b|\bfeeling\b|\bfelt\b": {"FEEL": 1},
    r"\bemotion\b|\bemotional\b": {"FEEL": 1},
    r"\bhappy\b|\bhappiness\b|\bjoy\b": {"FEEL": 1, "GOOD": 1},
    r"\bsad\b|\bsadness\b|\bunhappy\b": {"FEEL": 1, "GOOD": -1},
    r"\banger\b|\bangry\b": {"FEEL": 1, "GOOD": -1},
    r"\bfear\b|\bafraid\b|\bscared\b": {"FEEL": 1, "GOOD": -1},
    r"\blove\b|\bloving\b": {"FEEL": 1, "GOOD": 1, "WANT": 1},
    r"\bhate\b|\bhatred\b": {"FEEL": 1, "GOOD": -1},
    # Perception words
    r"\bto see\b|\bseeing\b|\bsight\b|\bvisual\b": {"SEE": 1},
    r"\bto look\b|\blooking\b": {"SEE": 1, "WANT": 1},
    r"\bto hear\b|\bhearing\b|\bsound\b|\bauditory\b": {"HEAR": 1},
    r"\bto listen\b|\blistening\b": {"HEAR": 1, "WANT": 1},
    r"\bto touch\b|\btouching\b|\btactile\b": {"TOUCH": 1},
    r"\bto smell\b|\bsmelling\b|\bolfactory\b": {"FEEL": 1, "BODY": 1},
    r"\bto taste\b|\btasting\b|\bgustatory\b": {"FEEL": 1, "BODY": 1},
    # Desire/want
    r"\bto want\b|\bwanting\b|\bwish\b|\bdesire\b": {"WANT": 1},
    r"\bto need\b|\bneeding\b|\bnecessity\b": {"WANT": 1, "MUST": 1},
    # Action/doing
    r"\bto do\b|\bdoing\b|\baction\b": {"DO": 1},
    r"\bto make\b|\bmaking\b|\bcreate\b": {"DO": 1, "CAUSE": 1},
    r"\bto use\b|\busing\b": {"DO": 1, "WITH": 1},
    r"\bto work\b|\bworking\b": {"DO": 1},
    # Existence/state
    r"\bto be\b|\bbeing\b|\bstate of\b": {"BE": 1},
    r"\bto exist\b|\bexistence\b": {"EXIST": 1},
    r"\bto live\b|\bliving\b|\blife\b": {"ALIVE": 1, "EXIST": 1},
    r"\bto die\b|\bdying\b|\bdeath\b": {"ALIVE": -1, "END": 1},
    # Possession
    r"\bto have\b|\bhaving\b|\bpossess\b": {"HAVE": 1},
    r"\bto own\b|\bowning\b|\bproperty\b": {"HAVE": 1},
    r"\bto get\b|\bgetting\b|\bobtain\b": {"HAVE": 1, "START": 1},
    r"\bto give\b|\bgiving\b": {"HAVE": -1},
    r"\bto lose\b|\blosing\b|\bloss\b": {"HAVE": -1},
    # Change/happening
    r"\bto happen\b|\bhappening\b|\boccur\b": {"HAPPEN": 1},
    r"\bto change\b|\bchanging\b": {"HAPPEN": 1},
    r"\bto become\b|\bbecoming\b": {"HAPPEN": 1, "START": 1},
    # Evaluative
    r"\bgood\b|\bpositive\b|\bbeneficial\b|\bexcellent\b": {"GOOD": 1},
    r"\bbad\b|\bnegative\b|\bharmful\b|\bterrible\b": {"GOOD": -1},
    r"\bbig\b|\blarge\b|\bgreat\b|\bhuge\b": {"BIG": 1},
    r"\bsmall\b|\blittle\b|\btiny\b|\bminute\b": {"BIG": -1},
    # Spatial/temporal
    r"\babove\b|\bupper\b|\bhigh\b|\btop\b": {"ABOVE": 1},
    r"\bbelow\b|\blower\b|\bunder\b|\bbottom\b": {"BELOW": 1},
    r"\bbefore\b|\bprior\b|\bearlier\b|\bpreceding\b": {"BEFORE": 1},
    r"\bafter\b|\blater\b|\bsubsequent\b|\bfollowing\b": {"AFTER": 1},
    r"\binside\b|\bwithin\b|\binternal\b|\binner\b": {"INSIDE": 1},
    r"\boutside\b|\bexternal\b|\bouter\b": {"OUTSIDE": 1},
    r"\bnear\b|\bclose\b|\badjacent\b": {"NEAR": 1},
    r"\bfar\b|\bdistant\b|\bremote\b": {"FAR": 1},
    # Entity types
    r"\bperson\b|\bhuman\b|\bindividual\b|\bpeople\b": {"SOMEONE": 1},
    r"\bbody\b|\bphysical\b|\bcorporeal\b|\bbodily\b": {"BODY": 1},
    r"\bthing\b|\bobject\b|\bitem\b": {"SOMETHING": 1},
    r"\bplace\b|\blocation\b|\bsite\b": {"WHERE": 1},
    r"\btime\b|\bperiod\b|\bmoment\b": {"WHEN": 1},
    r"\babstract\b|\bconcept\b|\bidea\b": {"THINK": 1},
    # Causation
    r"\bcause\b|\bcausing\b|\bcaused by\b": {"CAUSE": 1},
    r"\bresult\b|\beffect\b|\bconsequence\b": {"CAUSE": 1},
    r"\bbecause\b|\breason\b|\bdue to\b": {"BECAUSE": 1},
    # Modality
    r"\bcan\b|\bable\b|\bcapable\b|\bability\b": {"CAN": 1},
    r"\bmust\b|\bshould\b|\bobligation\b|\brequired\b": {"MUST": 1},
    r"\bmaybe\b|\bperhaps\b|\bpossibly\b|\bmight\b": {"MAYBE": 1},
}

# Etymology patterns to primitives
ETYMOLOGY_PATTERNS = {
    r"negative prefix|un-|in-|dis-|non-": {"NOT": 1},
    r"causative": {"CAUSE": 1},
    r"diminutive": {"BIG": -1},
    r"augmentative": {"BIG": 1},
    r"frequentative": {"INTENSITY": 1},
    r"intensive": {"INTENSITY": 1},
}


def native_person_genus(definition: str, pos: str, native_sense: dict) -> bool:
    """Recognize a single native noun definition whose genus is an explicit person."""
    if (
        pos != "noun"
        or native_sense.get("glosses") != [definition]
        or any(key in native_sense for key in ("alt_of", "form_of"))
    ):
        return False
    head = definition.casefold().split(maxsplit=3)
    if len(head) != 4 or head[:2] != ["a", "person"] or head[2] not in {"who", "that"}:
        return False
    from GSE.nlp.native import _tokenize

    tokens = _tokenize(definition.casefold())
    if tokens and tokens[-1] == ".":
        tokens.pop()
    # An explicit relative clause identifies the person by a property. Reserve
    # coordinated or separately punctuated definitions for further scope review.
    boundary = {",", ";", ":", ".", "!", "?", "/", "(", ")", "[", "]", "and", "or"}
    return len(tokens) > 3 and not boundary.intersection(tokens)


ANATOMICAL_GENERA = frozenset({"artery", "bone", "cartilage", "gland", "ligament", "muscle", "nerve", "organ", "tendon", "vein"})
_ANATOMY_COMPOUNDS = {("nerve", "tissue"), ("nerve", "ending"), ("muscle", "fibre"), ("muscle", "fiber")}
_COORDINATORS = {"and", "or", "nor"}


def _anatomy_head(tokens, start):
    """Read a genus and its exact compound boundary after optional modifiers."""
    index = start
    while index < len(tokens) and tokens[index].pos_ in {"ADJ", "ADV"}:
        index += 1
    if index == len(tokens) or tokens[index].pos_ != "NOUN" or tokens[index].lemma_ not in ANATOMICAL_GENERA:
        return None
    head = tokens[index].lemma_
    if index + 1 < len(tokens) and (head, tokens[index + 1].text.casefold()) in _ANATOMY_COMPOUNDS:
        return head, index + 2, "compound"
    return head, index + 1, "genus"


def _anatomy_boundary(tokens) -> bool:
    if not tokens:
        return True
    first = tokens[0]
    if first.text in {".", ",", ";"}:
        return len(tokens) == 1 or tokens[1].text.casefold() not in _COORDINATORS
    return first.pos_ == "ADP" or first.text.casefold() in {"that", "which", "whose", "where", "with"}


def _anatomy_disjunction(head, tokens) -> bool:
    parenthetical = bool(tokens and tokens[0].text == "(")
    if tokens and tokens[0].text in {",", "("}:
        tokens = tokens[1:]
    if not tokens or tokens[0].text.casefold() != "or":
        return False
    start = 2 if len(tokens) > 1 and tokens[1].text.casefold() in {"a", "an", "the"} else 1
    alternative = _anatomy_head(tokens, start)
    if alternative:
        _, boundary, _ = alternative
    elif parenthetical and head == "bone" and [t.text.casefold() for t in tokens[start : start + 2]] == [
        "bony", "structure",
    ]:
        boundary = start + 2
    else:
        return False
    tail = tokens[boundary:]
    if parenthetical:
        return bool(tail and tail[0].text == ")" and _anatomy_boundary(tail[1:]))
    return not tail or (len(tail) == 1 and tail[0].text == ".") or (
        len(tail) > 1 and tail[0].text == "," and tail[1].text.casefold() in {"especially", "specifically"}
    )


def _skin_fold(tokens) -> bool:
    index = 1
    while index < len(tokens):
        if tokens[index].pos_ in {"ADJ", "ADV"}:
            index += 1
        elif (
            index + 2 < len(tokens)
            and tokens[index].pos_ == "NOUN"
            and tokens[index + 1].text == "-"
            and tokens[index + 2].pos_ == "ADJ"
        ):
            index += 3
        else:
            break
        if index + 1 < len(tokens) and tokens[index].text == "," and tokens[index + 1].pos_ == "ADJ":
            index += 1
    return [t.text.casefold() for t in tokens[index : index + 3]] == ["fold", "of", "skin"] and _anatomy_boundary(
        tokens[index + 3 :]
    )


def native_anatomy_witness(definition: str, pos: str, native_sense: dict) -> tuple[str, str] | None:
    """Return the exact genus and the supported attachment in a native gloss."""
    topics = native_sense.get("topics")
    tags = native_sense.get("tags", [])
    if (
        pos != "noun"
        or native_sense.get("glosses") != [definition]
        or any(key in native_sense for key in ("alt_of", "form_of"))
        or not isinstance(topics, list)
        or "anatomy" not in topics
        or not isinstance(tags, list)
        or any(tag in ("figuratively", "figurative", "metaphorical") for tag in tags)
    ):
        return None
    from GSE.nlp.native import NativeNLP

    tokens = tuple(NativeNLP()(definition))
    if not tokens or tokens[0].pos_ != "DET" or tokens[0].text.casefold() not in {"a", "an", "the"}:
        return None
    if _skin_fold(tokens):
        return "skin", "material_fold"
    witness = _anatomy_head(tokens, 1)
    if witness is None:
        return None
    head, boundary, construction = witness
    following = tokens[boundary:]
    if _anatomy_boundary(following):
        return head, construction
    if _anatomy_disjunction(head, following):
        return head, "disjunction"
    if (
        len(following) > 1 and following[0].pos_ == "VERB"
        and following[0].text.casefold() in {"having", "forming"}
        and following[1].pos_ in {"DET", "NOUN", "ADJ", "NUM"}
    ):
        return head, "participle"
    return None


def native_anatomy_genus(definition: str, pos: str, native_sense: dict) -> str | None:
    witness = native_anatomy_witness(definition, pos, native_sense)
    return witness[0] if witness else None


def native_definition_primitives(definition: str, pos: str, native_sense: dict) -> dict[str, int]:
    """Project the supported bank of an exact native genus."""
    if native_person_genus(definition, pos, native_sense):
        return {"SOMEONE": 1}
    if native_anatomy_genus(definition, pos, native_sense):
        return {"BODY": 1}
    return {}


class WiktionaryParser(BaseExternalParser):
    """Parse Wiktionary local dump and map to GSE primitives."""

    def __init__(self, db_path: Optional[Path] = None, *, data_path: Optional[Path] = None):
        super().__init__()
        self.config.name = "wiktionary"
        self.db_path = db_path or WIKTIONARY_DB
        if db_path is not None and data_path is not None:
            raise ValueError("AMBIGUOUS_WIKTIONARY_INPUT")
        self.data_path = Path(data_path) if data_path is not None else None
        self.source_sha256 = ""
        self._source_stat = None
        self.native_statistics: dict = {}
        self.conn: Optional[sqlite3.Connection] = None
        # Precompile regex patterns for performance
        self._compiled_def_patterns = {
            re.compile(pattern, re.IGNORECASE): prims for pattern, prims in DEFINITION_PATTERNS.items()
        }
        self._compiled_etym_patterns = {
            re.compile(pattern, re.IGNORECASE): prims for pattern, prims in ETYMOLOGY_PATTERNS.items()
        }

    def download_and_process(self) -> bool:
        """
        Download and process Wiktionary dump.

        Uses kaikki.org pre-processed JSON for efficiency.
        """
        try:
            import requests
        except ImportError:
            logger.error("requests library required for download")
            return False

        try:
            # Create directory
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Download pre-processed English dump
            url = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.json"
            logger.info(f"Downloading Wiktionary data from {url}...")
            logger.info("This may take 10-15 minutes...")

            # Stream download to avoid memory issues
            response = requests.get(url, stream=True, timeout=600)
            response.raise_for_status()

            # Process into SQLite
            self._create_database()

            count = 0
            batch = []

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    word = entry.get("word", "").lower()
                    if not word:
                        continue

                    pos = entry.get("pos", "")

                    # Get first definition
                    senses = entry.get("senses", [])
                    definition = ""
                    if senses and "glosses" in senses[0]:
                        definition = senses[0]["glosses"][0] if senses[0]["glosses"] else ""

                    # Get etymology
                    etymology = entry.get("etymology_text", "")

                    # Get related words
                    synonyms = []
                    antonyms = []
                    for sense in senses:
                        synonyms.extend([s.get("word", "") for s in sense.get("synonyms", []) if s.get("word")])
                        antonyms.extend([a.get("word", "") for a in sense.get("antonyms", []) if a.get("word")])

                    batch.append(
                        (
                            word,
                            pos,
                            definition,
                            etymology,
                            json.dumps(synonyms[:10]),  # Limit stored synonyms
                            json.dumps(antonyms[:10]),
                        )
                    )

                    if len(batch) >= 5000:
                        self._insert_batch(batch)
                        count += len(batch)
                        batch = []
                        if count % 50000 == 0:
                            logger.info(f"Processed {count:,} entries...")

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"Error processing entry: {e}")
                    continue

            if batch:
                self._insert_batch(batch)
                count += len(batch)

            logger.info(f"Processed {count:,} Wiktionary entries")
            return True

        except Exception as e:
            logger.error(f"Failed to process Wiktionary: {e}")
            return False

    def _create_database(self):
        """Create SQLite database for Wiktionary data."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL,
                pos TEXT,
                definition TEXT,
                etymology TEXT,
                synonyms TEXT,
                antonyms TEXT
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_word ON entries(word)")
        self.conn.commit()

    def _insert_batch(self, batch: List):
        """Insert batch of entries."""
        connection = self._sqlite_connection()
        connection.executemany(
            """
            INSERT INTO entries (word, pos, definition, etymology, synonyms, antonyms)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            batch,
        )
        connection.commit()

    def _sqlite_connection(self) -> sqlite3.Connection:
        """Legacy queries cannot select a first sense from native records."""
        if self.data_path is not None:
            raise ValueError("WIKTIONARY_NATIVE_REQUIRES_DEFINITION_ID")
        if self.conn is None:
            raise ValueError("WIKTIONARY_SQLITE_NOT_LOADED")
        return self.conn

    def load(self) -> bool:
        """Fingerprint native input, or open the explicitly selected legacy cache."""
        if self.data_path is not None:
            if not self.data_path.is_file():
                return False
            before = _source_identity(self.data_path)
            with self.data_path.open("rb") as stream:
                self.source_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
            self._source_stat = _source_identity(self.data_path)
            if before != self._source_stat:
                raise ValueError("WIKTIONARY_SOURCE_CHANGED")
            self._loaded = True
            return True
        if not self.db_path.exists():
            logger.info("Wiktionary database not found.")
            logger.info("Run download_and_process() to download from kaikki.org")
            logger.info("Or download manually and place at: {self.db_path}")
            return False

        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

            cursor = self.conn.execute("SELECT COUNT(*) FROM entries")
            count = cursor.fetchone()[0]

            logger.info(f"Loaded Wiktionary database with {count:,} entries")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load Wiktionary: {e}")
            return False

    @lru_cache(maxsize=20000)
    def to_primitives(self, word: str) -> Dict[str, int]:
        """Map word to GSE primitives based on definition analysis."""
        if self.data_path is not None:
            # Native definitions are evidence, not bag-of-words assignments.
            return {}
        if not self._loaded:
            if not self.load():
                return {}

        word = word.lower()

        cursor = self._sqlite_connection().execute("SELECT * FROM entries WHERE word = ? LIMIT 5", (word,))
        rows = cursor.fetchall()

        if not rows:
            return {}

        primitives: Dict[str, int] = {}

        for row in rows:
            definition = row["definition"] or ""
            etymology = row["etymology"] or ""

            # Analyze definition text
            for pattern, prims in self._compiled_def_patterns.items():
                if pattern.search(definition):
                    for prim, val in prims.items():
                        if prim not in primitives:
                            primitives[prim] = val

            # Analyze etymology
            for pattern, prims in self._compiled_etym_patterns.items():
                if pattern.search(etymology):
                    for prim, val in prims.items():
                        if prim not in primitives:
                            primitives[prim] = val

        return primitives

    def get_all_words(self) -> List[str]:
        """Get the native vocabulary; the legacy SQLite API retains its cap."""
        if self.data_path is not None:
            return sorted({form for _, record in self._native_records() if (form := _lookup_form(record["word"]))})
        if not self._loaded:
            if not self.load():
                return []

        cursor = self._sqlite_connection().execute("SELECT DISTINCT word FROM entries LIMIT 50000")
        return [row[0] for row in cursor.fetchall()]

    def _native_records(self) -> Iterator[tuple[int, dict]]:
        """Stream full records from an explicitly configured immutable cache."""
        if self.data_path is None:
            raise ValueError("WIKTIONARY_NATIVE_INPUT_REQUIRED")
        if not self._loaded and not self.load():
            raise ValueError("WIKTIONARY_NATIVE_INPUT_UNAVAILABLE")
        if _source_identity(self.data_path) != self._source_stat:
            raise ValueError("WIKTIONARY_SOURCE_CHANGED")
        with self.data_path.open("rb") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError) as error:
                    raise ValueError(f"MALFORMED_WIKTIONARY_JSON:{line_number}") from error
                if not isinstance(record, dict) or not isinstance(record.get("word"), str):
                    raise ValueError(f"MALFORMED_WIKTIONARY_RECORD:{line_number}")
                yield line_number, record
        if _source_identity(self.data_path) != self._source_stat:
            raise ValueError("WIKTIONARY_SOURCE_CHANGED")

    def get_definition_entries(self, words: tuple[str, ...]) -> Iterator[WiktionaryDefinition]:
        """Every native sense for the cohort; no first-sense or target guessing.

        Normalization selects candidate spellings only. Original spelling and
        case remain in native identity and content. Form/alternative links are
        preserved as evidence and never transfer a target's bank assignments.
        Memory holds one source record plus identity digests, not the dump.
        """
        if not isinstance(words, tuple) or any(not isinstance(w, str) or not w.strip() for w in words):
            raise ValueError("INVALID_WIKTIONARY_WORDS")
        wanted = {_lookup_form(word) for word in words}
        seen: set[tuple[str, str]] = set()
        native_ids: set[str] = set()
        stats = {
            "records": 0,
            "definitions": 0,
            "sense_occurrences": 0,
            "identical_duplicate_senses": 0,
            "additional_leaves_sharing_native_id": 0,
            "missing_glosses": 0,
        }
        self.native_statistics = stats
        for line_number, record in self._native_records():
            word = record["word"]
            lemma = _lookup_form(word)
            if lemma not in wanted:
                continue
            if record.get("lang_code") != "en" or record.get("lang") != "English":
                raise ValueError(f"NON_ENGLISH_WIKTIONARY_RECORD:{line_number}")
            pos, senses = record.get("pos"), record.get("senses")
            if not isinstance(pos, str) or not pos.strip() or not isinstance(senses, list) or not senses:
                raise ValueError(f"MALFORMED_WIKTIONARY_SENSES:{line_number}")
            stats["records"] += 1
            context = {key: value for key, value in record.items() if key != "senses"}
            record_digest = _native_digest(record)
            for index, sense in enumerate(senses):
                if not isinstance(sense, dict):
                    raise ValueError(f"MALFORMED_WIKTIONARY_SENSE:{line_number}:{index}")
                sense_id, glosses = sense.get("id"), sense.get("glosses", [])
                if not isinstance(sense_id, str) or not sense_id.strip():
                    raise ValueError(f"MISSING_WIKTIONARY_SENSE_ID:{line_number}:{index}")
                if not isinstance(glosses, list) or any(not isinstance(gloss, str) for gloss in glosses):
                    raise ValueError(f"MALFORMED_WIKTIONARY_GLOSSES:{line_number}:{index}")
                senseid_path = sense.get("senseid", [])
                if not isinstance(senseid_path, list) or any(not isinstance(part, str) for part in senseid_path):
                    raise ValueError(f"MALFORMED_WIKTIONARY_SENSE_PATH:{line_number}:{index}")
                payload_digest = _native_digest({"record_context": context, "native_sense": sense})
                key = (sense_id, payload_digest)
                stats["sense_occurrences"] += 1
                definition = "\n".join(glosses)
                if key in seen:
                    stats["identical_duplicate_senses"] += 1
                else:
                    stats["additional_leaves_sharing_native_id"] += sense_id in native_ids
                    native_ids.add(sense_id)
                    seen.add(key)
                    stats["definitions"] += 1
                    stats["missing_glosses"] += not definition.strip()
                # Native IDs can identify a parent group, not a leaf. Uniform
                # content addressing preserves all distinct leaf/context pairs.
                # This is snapshot identity, not cross-version equivalence.
                # Duplicate witnesses still yield their distinct source locations.
                yield WiktionaryDefinition(
                    "wiktionary:" + sense_id + ":" + payload_digest,
                    lemma,
                    word,
                    pos,
                    definition,
                    sense_id,
                    tuple(senseid_path),
                    "GSE.wiktionary-native-leaf/1",
                    sense,
                    context,
                    record_digest,
                    self.source_sha256,
                    line_number,
                    index,
                    len(senses),
                )

    def to_primitives_for_entry(self, entry: WiktionaryDefinition) -> Dict[str, int]:
        """Project only an exact, independently warranted native sense feature."""
        if not isinstance(entry, WiktionaryDefinition):
            raise ValueError("INVALID_WIKTIONARY_DEFINITION")
        return native_definition_primitives(entry.definition, entry.pos, entry.native_sense)

    def get_definition_references(
        self, entries: tuple[WiktionaryDefinition, ...]
    ) -> tuple[WiktionaryDefinitionReference, ...]:
        """Retrieve one hop of explicit alt/form targets in one native scan.

        Same-POS leaves are candidates, never an implicit first-sense choice.
        Other-POS leaves remain visible for diagnosis. A target that is itself
        a reference is reported as such; chains and cycles are not followed.
        Identical repeated inputs/links are deduplicated, while distinct native
        identities and duplicate witnesses at different source locations remain.
        Neither original records nor bank assignments are changed.
        """
        if not isinstance(entries, tuple) or any(not isinstance(entry, WiktionaryDefinition) for entry in entries):
            raise ValueError("INVALID_WIKTIONARY_REFERENCE_ENTRIES")
        if not entries:
            return ()
        if self.data_path is None:
            raise ValueError("WIKTIONARY_NATIVE_INPUT_REQUIRED")
        if not self._loaded and not self.load():
            raise ValueError("WIKTIONARY_NATIVE_INPUT_UNAVAILABLE")
        if _source_identity(self.data_path) != self._source_stat:
            raise ValueError("WIKTIONARY_SOURCE_CHANGED")
        pending: dict[str, _PendingNativeReference] = {}
        for entry in entries:
            links = _native_reference_links(entry)
            original = _native_reference_record(entry, self.source_sha256)
            for relation, link in links:
                copied_link = json.loads(json.dumps(link, ensure_ascii=False, allow_nan=False))
                item: _PendingNativeReference = {"source_entry": original, "relation": relation, "link": copied_link}
                pending[_native_digest(dict(item))] = item
        if _source_identity(self.data_path) != self._source_stat:
            raise ValueError("WIKTIONARY_SOURCE_CHANGED")
        if not pending:
            return ()
        wanted = tuple(sorted({_lookup_form(item["link"]["word"]) for item in pending.values()}))
        targets: dict[str, dict[str, dict]] = {}
        original_statistics = self.native_statistics
        try:
            for target in self.get_definition_entries(wanted):
                _native_reference_links(target)
                record = _native_reference_record(target, self.source_sha256)
                targets.setdefault(target.lemma, {})[_native_digest(record)] = record
        finally:
            self.native_statistics = original_statistics
        if _source_identity(self.data_path) != self._source_stat:
            raise ValueError("WIKTIONARY_SOURCE_CHANGED")
        result: list[WiktionaryDefinitionReference] = []
        for key in sorted(pending):
            item = pending[key]
            source = item["source_entry"]
            lookup = _lookup_form(item["link"]["word"])
            candidates = targets.get(lookup, {})
            ordered = sorted(
                candidates.values(),
                key=lambda record: (record["entry_id"], record["source_line"], record["sense_index"]),
            )
            matching = [record for record in ordered if record["pos"] == source["pos"]]
            other = [record for record in ordered if record["pos"] != source["pos"]]
            identities = {record["entry_id"] for record in matching}
            code: _NativeReferenceCode
            if len(identities) > 1:
                code = "AMBIGUOUS_TARGET_SENSES"
            elif matching:
                reference = any(record["native_sense"].get(kind) for record in matching for kind in ("alt_of", "form_of"))
                code = "TARGET_IS_REFERENCE" if reference else "TARGET_DEFINITIONS_AVAILABLE"
            else:
                code = "TARGET_HAS_ONLY_OTHER_POS" if other else "TARGET_NOT_FOUND"
            result.append(
                {
                    "format": "GSE.wiktionary-definition-reference/1",
                    "code": code,
                    **item,
                    "target_word": item["link"]["word"],
                    "target_lookup": lookup,
                    "target_entries": matching,
                    "other_pos_entries": other,
                    "source_sha256": self.source_sha256,
                }
            )
        return tuple(result)

    def get_definition(self, word: str) -> Optional[str]:
        """Get the primary definition for a word."""
        if not self._loaded:
            if not self.load():
                return None

        cursor = self._sqlite_connection().execute(
            "SELECT definition FROM entries WHERE word = ? LIMIT 1", (word.lower(),)
        )
        row = cursor.fetchone()
        return row["definition"] if row else None

    def get_synonyms(self, word: str) -> List[str]:
        """Get synonyms for a word."""
        if not self._loaded:
            if not self.load():
                return []

        cursor = self._sqlite_connection().execute(
            "SELECT synonyms FROM entries WHERE word = ? LIMIT 1", (word.lower(),)
        )
        row = cursor.fetchone()
        if row and row["synonyms"]:
            try:
                return json.loads(row["synonyms"])
            except Exception:
                return []
        return []

    def get_antonyms(self, word: str) -> List[str]:
        """Get antonyms for a word."""
        if not self._loaded:
            if not self.load():
                return []

        cursor = self._sqlite_connection().execute(
            "SELECT antonyms FROM entries WHERE word = ? LIMIT 1", (word.lower(),)
        )
        row = cursor.fetchone()
        if row and row["antonyms"]:
            try:
                return json.loads(row["antonyms"])
            except Exception:
                return []
        return []

    def get_etymology(self, word: str) -> Optional[str]:
        """Get etymology for a word."""
        if not self._loaded:
            if not self.load():
                return None

        cursor = self._sqlite_connection().execute(
            "SELECT etymology FROM entries WHERE word = ? AND etymology != '' LIMIT 1", (word.lower(),)
        )
        row = cursor.fetchone()
        return row["etymology"] if row else None

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
        super().close()


def download_wiktionary():
    """Download and process Wiktionary dump."""
    parser = WiktionaryParser()
    if parser.download_and_process():
        print("Wiktionary downloaded and processed successfully")
    else:
        print("Failed to download Wiktionary")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = WiktionaryParser()
    if parser.load():
        # Test some words
        test_words = ["dog", "run", "happy", "think", "person", "love", "water"]
        for word in test_words:
            definition = parser.get_definition(word)
            primitives = parser.to_primitives(word)
            print(f"{word}: primitives={primitives}")
            if definition:
                print(f"  def: {definition[:80]}...")
    else:
        print("Wiktionary not available - run download_wiktionary() to fetch data")
