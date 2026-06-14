import json
import sqlite3
import os
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
try:
    import anthropic
except ImportError:
    anthropic = None

from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import SparseVector, PrimitiveBasis, bind, bundle

@dataclass
class LexiconEntry:
    lemma: str
    pos: str
    sense_id: str
    gloss: str
    decomposition: List[Tuple[str, str]]  # [(primitive, role), ...]
    vector: SparseVector
    frequency: float
    source: str  # "manual", "llm", "fallback"
    confidence: float

class LexiconGenerator:
    """Generate GSE lexicon entries using LLM decomposition."""
    
    DECOMPOSITION_PROMPT = '''You are a semantic analyst decomposing words into universal semantic primitives.

PRIMITIVES (use ONLY these):
{primitives}

ROLES (use ONLY these):
{roles}

Decompose the following word into primitive-role pairs. Output ONLY valid JSON.

Word: {word}
Part of speech: {pos}
Definition hint: {definition}

Output format:
{{"decomposition": [{{"primitive": "...", "role": "..."}}, ...]}}

Rules:
1. Use ONLY primitives and roles from the lists above
2. Capture the core meaning, not every nuance
3. 3-8 primitive-role pairs is typical
4. Every decomposition needs at least an action/state and usually an agent or theme

Example for "murder":
{{"decomposition": [
  {{"primitive": "SOMEONE", "role": "agent"}},
  {{"primitive": "DO", "role": "action"}},
  {{"primitive": "SOMEONE", "role": "patient"}},
  {{"primitive": "DIE", "role": "result"}},
  {{"primitive": "WANT", "role": "intention"}},
  {{"primitive": "BAD", "role": "evaluation"}}
]}}

Now decompose "{word}" ({pos}):'''

    def __init__(self, basis: PrimitiveBasis, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.basis = basis
        self.model = model
        if api_key and anthropic:
            self.client = anthropic.Anthropic(api_key=api_key)
        else:
            self.client = None
            if api_key:
                print("Warning: API key provided but anthropic module not found.")
        
    def decompose_word(self, word: str, pos: str, definition: str = "") -> Optional[List[Tuple[str, str]]]:
        """Get LLM decomposition for a word."""
        if not self.client:
            print(f"Error: No LLM client available for decomposing {word}")
            return None
            
        prompt = self.DECOMPOSITION_PROMPT.format(
            primitives=", ".join(PRIMITIVES),
            roles=", ".join(ROLES),
            word=word,
            pos=pos,
            definition=definition
        )
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse JSON response
            text = response.content[0].text.strip()
            # Handle markdown code blocks
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            text = text.strip()
            data = json.loads(text)
            decomposition = [
                (item["primitive"], item["role"])
                for item in data["decomposition"]
            ]
            
            # Validate
            for prim, role in decomposition:
                if prim not in PRIMITIVES:
                    print(f"Warning: Unknown primitive '{prim}' for {word}")
                    return None
                if role not in ROLES:
                    print(f"Warning: Unknown role '{role}' for {word}")
                    return None
            
            return decomposition
            
        except Exception as e:
            print(f"Error decomposing {word}: {e}")
            return None
    
    def encode_decomposition(self, decomposition: List[Tuple[str, str]]) -> SparseVector:
        """
        Convert decomposition to GSE vector with polarity support.

        Negative polarity FLIPS the Hadamard pattern:
        - GOOD+1 and GOOD-1 occupy SAME dimensions with OPPOSITE signs
        - This makes happy/sad have cosine ≈ -1.0 (clear antonyms)

        Full polarity propagation:
        - Negative primitives "infect" co-occurring primitives in coupled banks
        - e.g., "hate" with GOOD-1 also flips FEEL in the Mental bank
        - This ensures antonyms like "love/hate" differ in multiple dimensions
        """
        from gse.primitives import full_canonicalize, Polarity

        # Full canonicalization with polarity propagation
        # This propagates negative polarity to coupled semantic banks
        canonical = full_canonicalize(decomposition)
        
        components = []
        raw_primitives = []
        
        for activation in canonical:
            prim = activation.primitive
            role = activation.role
            polarity = activation.polarity
            
            if prim not in self.basis.primitives:
                continue
            
            prim_vec = self.basis.primitives[prim]
            
            # Apply polarity: negative flips the vector
            if polarity == Polarity.NEGATIVE:
                prim_vec = SparseVector(
                    dimension=prim_vec.dimension,
                    positive_indices=prim_vec.negative_indices.copy(),
                    negative_indices=prim_vec.positive_indices.copy(),
                    bank=prim_vec.bank
                )
            
            raw_primitives.append(prim_vec)
            
            if role in self.basis.roles:
                role_vec = self.basis.roles[role]
                bound = bind(prim_vec, role_vec)
                components.append(bound)
        
        if not components and not raw_primitives:
            return SparseVector.zeros(self.basis.dimension)
        
        all_components = components.copy()
        if raw_primitives:
            all_components.append(bundle(raw_primitives))
        
        return bundle(all_components)
    
    def generate_batch(self, words: List[Dict], output_db: str):
        """
        Generate lexicon entries for a batch of words.
        
        Args:
            words: List of {"word": str, "pos": str, "definition": str, "frequency": float}
            output_db: Path to SQLite database
        """
        conn = sqlite3.connect(output_db)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS lexicon (
                id INTEGER PRIMARY KEY,
                lemma TEXT,
                pos TEXT,
                sense_id TEXT,
                gloss TEXT,
                decomposition TEXT,
                vector BLOB,
                frequency REAL,
                source TEXT,
                confidence REAL,
                UNIQUE(lemma, pos, sense_id)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_lemma ON lexicon(lemma)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_lemma_pos ON lexicon(lemma, pos)')
        
        for i, entry in enumerate(words):
            word = entry["word"]
            pos = entry["pos"]
            definition = entry.get("definition", "")
            frequency = entry.get("frequency", 0.0)
            
            # Check if already exists
            existing = conn.execute(
                'SELECT 1 FROM lexicon WHERE lemma = ? AND pos = ?',
                (word, pos)
            ).fetchone()
            
            if existing:
                continue
            
            # Get decomposition
            if "decomposition" in entry:
                decomposition = entry["decomposition"]
            else:
                decomposition = self.decompose_word(word, pos, definition)
            
            if decomposition:
                vector = self.encode_decomposition(decomposition)
                conn.execute('''
                    INSERT OR REPLACE INTO lexicon 
                    (lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    word,
                    pos,
                    f"{word}.{pos}.01",
                    definition,
                    json.dumps(decomposition),
                    vector.serialize(),
                    frequency,
                    "llm",
                    0.8
                ))
            
            if (i + 1) % 100 == 0:
                print(f"Processed {i + 1}/{len(words)} words")
                conn.commit()
        
        conn.commit()
        conn.close()


class Lexicon:
    """Runtime lexicon for word lookup."""

    def __init__(self, db_path: str, basis: PrimitiveBasis):
        self.db_path = db_path
        self.basis = basis
        self.cache: Dict[Tuple[str, str], LexiconEntry] = {}
        # Create a generator for re-encoding vectors with the fixed method
        self.generator = LexiconGenerator(basis)
        if os.path.exists(db_path):
            self._load_frequent_words()
        # Else we might be testing with empty or non-existent db
    
    def _load_frequent_words(self, top_n: int = 5000):
        """Pre-load frequent words into cache with re-encoded vectors."""
        try:
            conn = sqlite3.connect(self.db_path)
            # Check if table exists
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lexicon'")
            if not cursor.fetchone():
                return

            rows = conn.execute('''
                SELECT lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence
                FROM lexicon
                ORDER BY frequency DESC
                LIMIT ?
            ''', (top_n,)).fetchall()

            for row in rows:
                decomposition = json.loads(row[4])
                # Re-encode vector using the fixed method (includes raw primitives)
                if decomposition and self.generator:
                    vector = self.generator.encode_decomposition(decomposition)
                else:
                    vector = SparseVector.deserialize(row[5])

                entry = LexiconEntry(
                    lemma=row[0],
                    pos=row[1],
                    sense_id=row[2],
                    gloss=row[3],
                    decomposition=decomposition,
                    vector=vector,
                    frequency=row[6],
                    source=row[7],
                    confidence=row[8]
                )
                self.cache[(entry.lemma, entry.pos)] = entry

            conn.close()
            print(f"Loaded {len(self.cache)} frequent words into cache (re-encoded)")
        except sqlite3.Error as e:
            print(f"Error loading lexicon: {e}")
    
    # POS fallback groups: if exact match fails, try related POS tags
    # This handles cases where parser tags "above" as ADV but lexicon has ADP
    POS_FALLBACKS = {
        "ADV": ["ADP", "ADJ"],  # Adverbs may be stored as prepositions or adjectives
        "ADP": ["ADV"],  # Prepositions may be stored as adverbs
        "NOUN": ["PROPN"],  # Common nouns may be proper nouns
        "PROPN": ["NOUN"],  # Proper nouns may be common nouns
        "ADJ": ["ADV", "VERB"],  # Adjectives may be stored as adverbs or verbs
        "VERB": ["ADJ"],  # Verbs may be stored as adjectives (e.g., "live")
    }

    def lookup(self, lemma: str, pos: str, force_reencode: bool = True) -> Optional[LexiconEntry]:
        """
        Look up a word in the lexicon.

        Args:
            lemma: Word lemma
            pos: Part of speech
            force_reencode: If True, re-encode vector from decomposition using current
                          encoding method. This ensures fixes to encode_decomposition
                          take effect without regenerating the database.

        Returns:
            LexiconEntry if found, None otherwise.
            Uses POS fallback mechanism: if exact POS match fails, tries related POS tags.
        """
        lemma_lower = lemma.lower()

        # Try exact match first, then fallbacks
        pos_to_try = [pos] + self.POS_FALLBACKS.get(pos, [])

        for try_pos in pos_to_try:
            key = (lemma_lower, try_pos)

            if key in self.cache:
                return self.cache[key]

            if not os.path.exists(self.db_path):
                continue

            # Check database
            try:
                conn = sqlite3.connect(self.db_path)
                row = conn.execute('''
                    SELECT lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence
                    FROM lexicon
                    WHERE lemma = ? AND pos = ?
                ''', key).fetchone()
                conn.close()

                if row:
                    decomposition = json.loads(row[4])

                    # Re-encode vector from decomposition if requested
                    # This ensures the latest encoding fixes are applied
                    if force_reencode and self.generator and decomposition:
                        vector = self.generator.encode_decomposition(decomposition)
                    else:
                        vector = SparseVector.deserialize(row[5])

                    entry = LexiconEntry(
                        lemma=row[0],
                        pos=row[1],
                        sense_id=row[2],
                        gloss=row[3],
                        decomposition=decomposition,
                        vector=vector,
                        frequency=row[6],
                        source=row[7],
                        confidence=row[8]
                    )
                    # Cache with original requested POS for future lookups
                    self.cache[(lemma_lower, pos)] = entry
                    return entry
            except sqlite3.Error:
                pass

        return None
    
    def get_all_senses(self, lemma: str) -> List[LexiconEntry]:
        """Get all senses for a lemma."""
        if not os.path.exists(self.db_path):
            return []
            
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('''
            SELECT lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence
            FROM lexicon
            WHERE lemma = ?
        ''', (lemma.lower(),)).fetchall()
        conn.close()
        
        return [
            LexiconEntry(
                lemma=row[0],
                pos=row[1],
                sense_id=row[2],
                gloss=row[3],
                decomposition=json.loads(row[4]),
                vector=SparseVector.deserialize(row[5]),
                frequency=row[6],
                source=row[7],
                confidence=row[8]
            )
            for row in rows
        ]
