#!/usr/bin/env python3
"""
Build Wiktionary Primitive Resolver Database

Downloads Wiktionary data from kaikki.org and builds a dictionary-encoded
database for fast primitive resolution.

Architecture inspired by Sparse Wiki:
- Dictionary encoding for common patterns (stored once, referenced by ID)
- Genus extraction from definitions (IS-A relationships)
- Pre-computed primitive assignments for all words
- Semantic relation spreading (synonyms/antonyms)

Usage:
    python scripts/build_wiktionary_primitives.py --download   # Download data
    python scripts/build_wiktionary_primitives.py --build      # Build database
    python scripts/build_wiktionary_primitives.py --all        # Both
    python scripts/build_wiktionary_primitives.py --test       # Test queries
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

# Setup paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "external" / "wiktionary"
DB_PATH = DATA_DIR / "wiktionary_primitives.db"
RAW_JSON_PATH = DATA_DIR / "kaikki-english.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# PRIMITIVE FEATURE PATTERNS
# =============================================================================

# Keywords in definitions that map to primitives
KEYWORD_PRIMITIVES = {
    # Entity types
    "person": {"SOMEONE": 1, "ALIVE": 1},
    "human": {"SOMEONE": 1, "ALIVE": 1},
    "people": {"SOMEONE": 1, "PEOPLE": 1, "ALIVE": 1},
    "individual": {"SOMEONE": 1},
    "animal": {"ALIVE": 1, "BODY": 1},
    "mammal": {"ALIVE": 1, "BODY": 1},
    "bird": {"ALIVE": 1, "BODY": 1, "MOVE": 1},
    "fish": {"ALIVE": 1, "BODY": 1},
    "insect": {"ALIVE": 1, "BODY": 1},
    "plant": {"ALIVE": 1},
    "organism": {"ALIVE": 1},
    "creature": {"ALIVE": 1, "BODY": 1},
    "thing": {"SOMETHING": 1},
    "object": {"SOMETHING": 1},
    "item": {"SOMETHING": 1},
    "substance": {"SOMETHING": 1},
    "material": {"SOMETHING": 1},
    "device": {"SOMETHING": 1, "DO": 1},
    "tool": {"SOMETHING": 1, "DO": 1},
    "machine": {"SOMETHING": 1, "DO": 1},
    "instrument": {"SOMETHING": 1, "DO": 1},
    "place": {"WHERE": 1},
    "location": {"WHERE": 1},
    "area": {"WHERE": 1},
    "region": {"WHERE": 1},
    "space": {"WHERE": 1},
    "building": {"WHERE": 1, "SOMETHING": 1},
    "room": {"WHERE": 1, "INSIDE": 1},
    "time": {"WHEN": 1},
    "period": {"WHEN": 1},
    "moment": {"WHEN": 1, "MOMENT": 1},
    "event": {"HAPPEN": 1, "WHEN": 1},
    "action": {"DO": 1},
    "act": {"DO": 1},
    "activity": {"DO": 1},
    "process": {"DO": 1, "HAPPEN": 1},
    "state": {"BE": 1},
    "condition": {"BE": 1},
    "quality": {"BE": 1},
    "property": {"BE": 1, "HAVE": 1},
    "feeling": {"FEEL": 1},
    "emotion": {"FEEL": 1},
    "sensation": {"FEEL": 1, "BODY": 1},
    "thought": {"THINK": 1},
    "idea": {"THINK": 1},
    "concept": {"THINK": 1},
    "belief": {"THINK": 1, "MAYBE": 1},
    "knowledge": {"KNOW": 1},
    "information": {"KNOW": 1},
    "word": {"WORDS": 1, "SAY": 1},
    "language": {"WORDS": 1, "SAY": 1},
    "sound": {"HEAR": 1},
    "noise": {"HEAR": 1},
    "voice": {"HEAR": 1, "SAY": 1},
    "speech": {"SAY": 1, "WORDS": 1},
    "color": {"SEE": 1},
    "colour": {"SEE": 1},
    "light": {"SEE": 1},
    "image": {"SEE": 1},
    "picture": {"SEE": 1},
    "shape": {"SEE": 1, "SOMETHING": 1},
    "form": {"BE": 1, "SOMETHING": 1},
    "body": {"BODY": 1},
    "part": {"PART": 1},
    "group": {"PEOPLE": 1, "SOMEONE": 1},
    "collection": {"SOMETHING": 1, "HAVE": 1},
    "set": {"SOMETHING": 1, "HAVE": 1},
    "amount": {"QUANTITY": 1},
    "quantity": {"QUANTITY": 1},
    "number": {"QUANTITY": 1, "ONE": 1},

    # Actions/Verbs
    "move": {"MOVE": 1},
    "motion": {"MOVE": 1},
    "movement": {"MOVE": 1},
    "walk": {"MOVE": 1, "BODY": 1},
    "run": {"MOVE": 1, "BODY": 1},
    "go": {"MOVE": 1},
    "come": {"MOVE": 1},
    "travel": {"MOVE": 1},
    "say": {"SAY": 1},
    "speak": {"SAY": 1, "WORDS": 1},
    "tell": {"SAY": 1, "WORDS": 1},
    "talk": {"SAY": 1, "WORDS": 1},
    "communicate": {"SAY": 1},
    "express": {"SAY": 1},
    "write": {"SAY": 1, "WORDS": 1},
    "read": {"KNOW": 1, "WORDS": 1, "SEE": 1},
    "think": {"THINK": 1},
    "know": {"KNOW": 1},
    "understand": {"KNOW": 1, "THINK": 1},
    "learn": {"KNOW": 1, "START": 1},
    "remember": {"KNOW": 1, "BEFORE": 1},
    "forget": {"KNOW": -1, "BEFORE": 1},
    "believe": {"THINK": 1, "MAYBE": 1},
    "feel": {"FEEL": 1},
    "sense": {"FEEL": 1},
    "experience": {"FEEL": 1},
    "see": {"SEE": 1},
    "look": {"SEE": 1},
    "watch": {"SEE": 1},
    "observe": {"SEE": 1},
    "hear": {"HEAR": 1},
    "listen": {"HEAR": 1},
    "touch": {"TOUCH": 1},
    "want": {"WANT": 1},
    "desire": {"WANT": 1},
    "wish": {"WANT": 1},
    "need": {"WANT": 1, "MUST": 1},
    "like": {"WANT": 1, "GOOD": 1},
    "love": {"WANT": 1, "GOOD": 1, "FEEL": 1},
    "hate": {"WANT": -1, "GOOD": -1, "FEEL": 1},
    "prefer": {"WANT": 1},
    "do": {"DO": 1},
    "make": {"DO": 1, "CAUSE": 1},
    "create": {"DO": 1, "CAUSE": 1, "START": 1},
    "build": {"DO": 1, "CAUSE": 1},
    "produce": {"DO": 1, "CAUSE": 1},
    "use": {"DO": 1, "WITH": 1},
    "work": {"DO": 1},
    "happen": {"HAPPEN": 1},
    "occur": {"HAPPEN": 1},
    "become": {"HAPPEN": 1, "START": 1},
    "change": {"HAPPEN": 1},
    "cause": {"CAUSE": 1},
    "result": {"CAUSE": 1},
    "effect": {"CAUSE": 1},
    "have": {"HAVE": 1},
    "possess": {"HAVE": 1},
    "own": {"HAVE": 1},
    "contain": {"HAVE": 1, "INSIDE": 1},
    "include": {"HAVE": 1},
    "get": {"HAVE": 1, "START": 1},
    "receive": {"HAVE": 1},
    "give": {"HAVE": -1},
    "lose": {"HAVE": -1},
    "be": {"BE": 1},
    "exist": {"EXIST": 1},
    "live": {"ALIVE": 1, "EXIST": 1},
    "die": {"ALIVE": -1, "END": 1},
    "kill": {"ALIVE": -1, "CAUSE": 1},
    "start": {"START": 1},
    "begin": {"START": 1},
    "end": {"END": 1},
    "stop": {"END": 1},
    "finish": {"END": 1},
    "continue": {"START": 1, "END": -1},

    # Evaluative - Positive
    "good": {"GOOD": 1},
    "better": {"GOOD": 1},
    "best": {"GOOD": 1, "INTENSITY": 1},
    "positive": {"GOOD": 1},
    "excellent": {"GOOD": 1, "INTENSITY": 1},
    "wonderful": {"GOOD": 1, "INTENSITY": 1},
    "great": {"GOOD": 1, "BIG": 1},
    "fine": {"GOOD": 1},
    "nice": {"GOOD": 1},
    "lovely": {"GOOD": 1, "FEEL": 1},
    "beautiful": {"GOOD": 1, "SEE": 1},
    "pleasant": {"GOOD": 1, "FEEL": 1},
    "delightful": {"GOOD": 1, "FEEL": 1},
    "joyful": {"GOOD": 1, "FEEL": 1},
    "cheerful": {"GOOD": 1, "FEEL": 1},
    "happy": {"GOOD": 1, "FEEL": 1},
    "glad": {"GOOD": 1, "FEEL": 1},
    "pleased": {"GOOD": 1, "FEEL": 1},
    "content": {"GOOD": 1, "FEEL": 1},
    "satisfied": {"GOOD": 1, "FEEL": 1},
    "fortunate": {"GOOD": 1},
    "lucky": {"GOOD": 1},
    "successful": {"GOOD": 1, "DO": 1},
    "beneficial": {"GOOD": 1, "CAUSE": 1},
    "favorable": {"GOOD": 1},
    "advantageous": {"GOOD": 1},

    # Evaluative - Negative
    "bad": {"GOOD": -1},
    "worse": {"GOOD": -1},
    "worst": {"GOOD": -1, "INTENSITY": 1},
    "negative": {"GOOD": -1},
    "terrible": {"GOOD": -1, "INTENSITY": 1},
    "horrible": {"GOOD": -1, "INTENSITY": 1},
    "awful": {"GOOD": -1, "INTENSITY": 1},
    "dreadful": {"GOOD": -1, "INTENSITY": 1},
    "wretched": {"GOOD": -1, "FEEL": 1},
    "woeful": {"GOOD": -1, "FEEL": 1},
    "miserable": {"GOOD": -1, "FEEL": 1},
    "pathetic": {"GOOD": -1},
    "pitiful": {"GOOD": -1, "FEEL": 1},
    "lamentable": {"GOOD": -1},
    "deplorable": {"GOOD": -1},
    "dismal": {"GOOD": -1, "FEEL": 1},
    "dreary": {"GOOD": -1, "FEEL": 1},
    "gloomy": {"GOOD": -1, "FEEL": 1, "SEE": 1},
    "bleak": {"GOOD": -1, "FEEL": 1},
    "desolate": {"GOOD": -1, "FEEL": 1},
    "forlorn": {"GOOD": -1, "FEEL": 1},
    "cheerless": {"GOOD": -1, "FEEL": 1},
    "joyless": {"GOOD": -1, "FEEL": 1},
    "mirthless": {"GOOD": -1, "FEEL": 1},
    "spiritless": {"GOOD": -1, "FEEL": 1, "THINK": -1},  # Mental sluggishness
    "doleful": {"GOOD": -1, "FEEL": 1},
    "sorrowful": {"GOOD": -1, "FEEL": 1},
    "mournful": {"GOOD": -1, "FEEL": 1},
    "melancholy": {"GOOD": -1, "FEEL": 1},
    "depressing": {"GOOD": -1, "FEEL": 1, "CAUSE": 1},
    "depressed": {"GOOD": -1, "FEEL": 1},
    "despondent": {"GOOD": -1, "FEEL": 1},
    "hopeless": {"GOOD": -1, "FEEL": 1},
    "desperate": {"GOOD": -1, "FEEL": 1, "WANT": 1},
    "unhappy": {"GOOD": -1, "FEEL": 1},
    "unfortunate": {"GOOD": -1},
    "unlucky": {"GOOD": -1},
    "unsuccessful": {"GOOD": -1, "DO": 1},
    "harmful": {"GOOD": -1, "CAUSE": 1},
    "detrimental": {"GOOD": -1, "CAUSE": 1},
    "ugly": {"GOOD": -1, "SEE": 1},
    "unpleasant": {"GOOD": -1, "FEEL": 1},
    "sad": {"GOOD": -1, "FEEL": 1},
    "angry": {"GOOD": -1, "FEEL": 1},
    "afraid": {"GOOD": -1, "FEEL": 1},
    "fearful": {"GOOD": -1, "FEEL": 1},
    "anxious": {"GOOD": -1, "FEEL": 1},
    "worried": {"GOOD": -1, "FEEL": 1, "THINK": 1},
    "distressed": {"GOOD": -1, "FEEL": 1},
    "anguished": {"GOOD": -1, "FEEL": 1},
    "suffering": {"GOOD": -1, "FEEL": 1},
    "painful": {"GOOD": -1, "FEEL": 1, "BODY": 1},
    "dull": {"GOOD": -1, "INTENSITY": -1, "THINK": -1},  # Mental sluggishness
    "boring": {"GOOD": -1, "FEEL": 1},
    "tedious": {"GOOD": -1},
    "monotonous": {"GOOD": -1},

    # Mental sluggishness - THINK=-1 (USAS pattern)
    "languid": {"GOOD": -1, "THINK": -1, "MOVE": -1},
    "sluggish": {"GOOD": -1, "THINK": -1, "MOVE": -1},
    "lethargic": {"GOOD": -1, "THINK": -1, "MOVE": -1},
    "torpid": {"GOOD": -1, "THINK": -1, "MOVE": -1},
    "listless": {"GOOD": -1, "THINK": -1, "FEEL": 1},
    "apathetic": {"GOOD": -1, "THINK": -1, "FEEL": -1},
    "inert": {"MOVE": -1, "DO": -1},
    "passive": {"DO": -1},
    "indolent": {"DO": -1, "WANT": -1},
    "lazy": {"DO": -1, "WANT": -1},

    # Insult words for people - CAN=-1 (USAS pattern: inability/incompetence)
    "idiot": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "fool": {"SOMEONE": 1, "CAN": -1, "THINK": -1},
    "moron": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "imbecile": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "dunce": {"SOMEONE": 1, "CAN": -1, "THINK": -1},
    "dimwit": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "nitwit": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "halfwit": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "simpleton": {"SOMEONE": 1, "CAN": -1, "THINK": -1},
    "blockhead": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "numbskull": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "dolt": {"SOMEONE": 1, "CAN": -1, "THINK": -1},
    "dullard": {"SOMEONE": 1, "CAN": -1, "THINK": -1},
    "ignoramus": {"SOMEONE": 1, "CAN": -1, "KNOW": -1},
    "nincompoop": {"SOMEONE": 1, "CAN": -1, "THINK": -1, "GOOD": -1},
    "buffoon": {"SOMEONE": 1, "CAN": -1, "GOOD": -1},
    "clod": {"SOMEONE": 1, "CAN": -1, "THINK": -1},
    "oaf": {"SOMEONE": 1, "CAN": -1},
    "lout": {"SOMEONE": 1, "CAN": -1, "GOOD": -1},
    "boor": {"SOMEONE": 1, "CAN": -1, "GOOD": -1},
    "asshole": {"SOMEONE": 1, "CAN": -1, "GOOD": -1},
    "arsehole": {"SOMEONE": 1, "CAN": -1, "GOOD": -1},
    "jackass": {"SOMEONE": 1, "CAN": -1, "GOOD": -1},
    "jerk": {"SOMEONE": 1, "GOOD": -1},
    "creep": {"SOMEONE": 1, "GOOD": -1},
    "loser": {"SOMEONE": 1, "CAN": -1, "GOOD": -1},
    "failure": {"DO": 1, "GOOD": -1, "END": 1},
    "incompetent": {"CAN": -1, "DO": -1},
    "incapable": {"CAN": -1},
    "unable": {"CAN": -1},
    "useless": {"CAN": -1, "GOOD": -1},
    "worthless": {"GOOD": -1},
    "hopeless": {"CAN": -1, "GOOD": -1, "MAYBE": -1},
    "bozo": {"SOMEONE": 1, "CAN": -1, "GOOD": -1},
    "dumbo": {"SOMEONE": 1, "CAN": -1, "THINK": -1},

    # Evaluative adjectives - MAYBE=1 (judgment/evaluation implies uncertainty)
    "outstanding": {"GOOD": 1, "MAYBE": 1, "INTENSITY": 1},
    "excellent": {"GOOD": 1, "MAYBE": 1, "INTENSITY": 1},
    "phenomenal": {"GOOD": 1, "MAYBE": 1, "INTENSITY": 1},
    "exceptional": {"GOOD": 1, "MAYBE": 1},
    "remarkable": {"GOOD": 1, "MAYBE": 1},
    "extraordinary": {"MAYBE": 1, "INTENSITY": 1},
    "incredible": {"MAYBE": 1, "INTENSITY": 1},
    "amazing": {"GOOD": 1, "MAYBE": 1, "FEEL": 1},
    "astonishing": {"MAYBE": 1, "FEEL": 1},
    "surprising": {"MAYBE": 1, "FEEL": 1},
    "unusual": {"MAYBE": 1, "OTHER": 1},
    "peculiar": {"MAYBE": 1, "OTHER": 1},
    "strange": {"MAYBE": 1, "OTHER": 1},
    "odd": {"MAYBE": 1, "OTHER": 1},
    "weird": {"MAYBE": 1, "OTHER": 1, "GOOD": -1},

    "big": {"BIG": 1},
    "large": {"BIG": 1},
    "huge": {"BIG": 1, "INTENSITY": 1},
    "great": {"BIG": 1},
    "small": {"BIG": -1},
    "little": {"BIG": -1},
    "tiny": {"BIG": -1, "INTENSITY": 1},
    "long": {"BIG": 1},
    "short": {"BIG": -1},
    "tall": {"BIG": 1},
    "wide": {"BIG": 1},
    "narrow": {"BIG": -1},
    "thick": {"BIG": 1},
    "thin": {"BIG": -1},
    "heavy": {"BIG": 1},
    "light": {"BIG": -1},
    "fast": {"MOVE": 1, "INTENSITY": 1},
    "quick": {"MOVE": 1, "INTENSITY": 1},
    "slow": {"MOVE": 1, "INTENSITY": -1},
    "strong": {"INTENSITY": 1, "CAN": 1},
    "weak": {"INTENSITY": -1, "CAN": -1},
    "hard": {"INTENSITY": 1},
    "soft": {"INTENSITY": -1},
    "loud": {"HEAR": 1, "INTENSITY": 1},
    "quiet": {"HEAR": 1, "INTENSITY": -1},
    "bright": {"SEE": 1, "INTENSITY": 1},
    "dark": {"SEE": 1, "INTENSITY": -1},
    "hot": {"FEEL": 1, "BODY": 1},
    "cold": {"FEEL": 1, "BODY": 1},
    "warm": {"FEEL": 1, "BODY": 1},
    "cool": {"FEEL": 1, "BODY": 1},
    "wet": {"TOUCH": 1},
    "dry": {"TOUCH": 1},
    "new": {"START": 1},
    "old": {"BEFORE": 1},
    "young": {"START": 1, "ALIVE": 1},
    "ancient": {"BEFORE": 1, "LONG_TIME": 1},
    "modern": {"NOW": 1},
    "recent": {"NOW": 1, "BEFORE": 1},
    "future": {"AFTER": 1},
    "past": {"BEFORE": 1},
    "present": {"NOW": 1},
    "true": {"TRUE": 1},
    "false": {"FALSE": 1},
    "real": {"TRUE": 1, "EXIST": 1},
    "fake": {"FALSE": 1},
    "certain": {"CERTAINTY": 1, "TRUE": 1},
    "uncertain": {"CERTAINTY": -1, "MAYBE": 1},
    "possible": {"MAYBE": 1, "CAN": 1},
    "impossible": {"CAN": -1},
    "necessary": {"MUST": 1},
    "important": {"MUST": 1, "GOOD": 1},
    "able": {"CAN": 1},
    "unable": {"CAN": -1},

    # Spatial
    "above": {"ABOVE": 1},
    "below": {"BELOW": 1},
    "over": {"ABOVE": 1},
    "under": {"BELOW": 1},
    "up": {"ABOVE": 1},
    "down": {"BELOW": 1},
    "high": {"ABOVE": 1},
    "low": {"BELOW": 1},
    "top": {"ABOVE": 1},
    "bottom": {"BELOW": 1},
    "upper": {"ABOVE": 1},
    "lower": {"BELOW": 1},
    "inside": {"INSIDE": 1},
    "outside": {"OUTSIDE": 1},
    "within": {"INSIDE": 1},
    "internal": {"INSIDE": 1},
    "external": {"OUTSIDE": 1},
    "inner": {"INSIDE": 1},
    "outer": {"OUTSIDE": 1},
    "near": {"NEAR": 1},
    "close": {"NEAR": 1},
    "far": {"FAR": 1},
    "distant": {"FAR": 1},
    "remote": {"FAR": 1},
    "adjacent": {"NEAR": 1},
    "next": {"NEAR": 1},
    "side": {"SIDE": 1},
    "left": {"SIDE": 1},
    "right": {"SIDE": 1},
    "front": {"SIDE": 1},
    "back": {"SIDE": 1},
    "here": {"HERE": 1},
    "there": {"WHERE": 1},
    "toward": {"TOWARD": 1},
    "towards": {"TOWARD": 1},
    "away": {"AWAY": 1},
    "from": {"AWAY": 1},

    # Temporal
    "before": {"BEFORE": 1},
    "after": {"AFTER": 1},
    "during": {"WHEN": 1},
    "while": {"WHEN": 1},
    "now": {"NOW": 1},
    "then": {"THEN": 1},
    "always": {"WHEN": 1, "ALL": 1},
    "never": {"WHEN": 1, "NOT": 1},
    "sometimes": {"WHEN": 1, "SOME": 1},
    "often": {"WHEN": 1, "MUCH": 1},
    "rarely": {"WHEN": 1, "LITTLE": 1},
    "early": {"BEFORE": 1},
    "late": {"AFTER": 1},
    "soon": {"AFTER": 1, "NEAR": 1},
    "sudden": {"SHORT_TIME": 1},
    "gradual": {"LONG_TIME": 1},
    "permanent": {"LONG_TIME": 1, "END": -1},
    "temporary": {"SHORT_TIME": 1},
    "instant": {"MOMENT": 1},
    "brief": {"SHORT_TIME": 1},

    # Quantifiers
    "one": {"ONE": 1},
    "single": {"ONE": 1},
    "two": {"TWO": 1},
    "both": {"TWO": 1},
    "pair": {"TWO": 1},
    "double": {"TWO": 1},
    "many": {"MUCH": 1, "QUANTITY": 1},
    "much": {"MUCH": 1},
    "few": {"LITTLE": 1, "QUANTITY": 1},
    "little": {"LITTLE": 1},
    "some": {"SOME": 1},
    "any": {"SOME": 1},
    "all": {"ALL": 1},
    "every": {"ALL": 1},
    "each": {"ALL": 1, "ONE": 1},
    "none": {"ZERO": 1, "NOT": 1},
    "no": {"ZERO": 1, "NOT": 1},
    "zero": {"ZERO": 1},
    "whole": {"ALL": 1},
    "entire": {"ALL": 1},
    "complete": {"ALL": 1, "END": 1},
    "partial": {"SOME": 1, "PART": 1},
    "half": {"SOME": 1, "TWO": 1},

    # Logical/Modal
    "not": {"NOT": 1},
    "without": {"WITHOUT": 1, "NOT": 1},
    "with": {"WITH": 1},
    "if": {"IF": 1, "MAYBE": 1},
    "because": {"BECAUSE": 1, "CAUSE": 1},
    "therefore": {"BECAUSE": 1},
    "can": {"CAN": 1},
    "could": {"CAN": 1, "MAYBE": 1},
    "may": {"MAYBE": 1, "CAN": 1},
    "might": {"MAYBE": 1},
    "must": {"MUST": 1},
    "should": {"MUST": 1, "GOOD": 1},
    "would": {"MAYBE": 1},
    "will": {"AFTER": 1},
    "same": {"SAME": 1},
    "different": {"OTHER": 1},
    "other": {"OTHER": 1},
    "another": {"OTHER": 1},
    "similar": {"SAME": 1, "LIKE": 1},
    "like": {"LIKE": 1},
    "kind": {"KIND": 1},
    "type": {"KIND": 1},
    "sort": {"KIND": 1},
}

# POS-based default primitives (enhanced)
POS_PRIMITIVES = {
    "noun": {"SOMETHING": 1},
    "verb": {"DO": 1, "HAPPEN": 1},
    "adj": {"BE": 1},
    "adv": {"BE": 1},
    "pron": {"SOMEONE": 1},
    "det": {"SOME": 1},
    "prep": {"WHERE": 1},
    "conj": {},
    "intj": {"FEEL": 1, "SAY": 1},
    "num": {"QUANTITY": 1, "ONE": 1},
    "particle": {},
    "name": {"SOMEONE": 1, "SOMETHING": 1},
    "phrase": {"WORDS": 1},
    "suffix": {"PART": 1},
    "prefix": {"PART": 1},
    "affix": {"PART": 1},
}

# Grammatical tag to primitive mappings
TAG_PRIMITIVES = {
    # Number/quantity tags
    "plural": {"SOME": 1, "MUCH": 1},
    "singular": {"ONE": 1},
    "countable": {"ONE": 1, "QUANTITY": 1},
    "uncountable": {"SOMETHING": 1},
    "collective": {"PEOPLE": 1, "SOME": 1},

    # Comparison tags (NOTE: comparative/superlative do NOT imply positive valence)
    "comparative": {"INTENSITY": 1},
    "superlative": {"INTENSITY": 1, "ALL": 1},

    # Tense/aspect tags
    "past": {"BEFORE": 1},
    "present": {"NOW": 1},
    "future": {"AFTER": 1},
    "perfect": {"END": 1, "BEFORE": 1},
    "progressive": {"NOW": 1, "DO": 1},
    "imperfective": {"DO": 1},
    "perfective": {"END": 1},

    # Voice/transitivity
    "transitive": {"DO": 1, "CAUSE": 1},
    "intransitive": {"DO": 1, "HAPPEN": 1},
    "reflexive": {"SAME": 1},
    "causative": {"CAUSE": 1},
    "passive": {"HAPPEN": 1},

    # Semantic tags
    "animate": {"ALIVE": 1},
    "inanimate": {"SOMETHING": 1},
    "human": {"SOMEONE": 1, "ALIVE": 1},
    "animal": {"ALIVE": 1, "BODY": 1},
    "abstract": {"THINK": 1},
    "concrete": {"SOMETHING": 1, "BODY": 1},
    "mass": {"SOMETHING": 1, "MUCH": 1},
    "stative": {"BE": 1},
    "dynamic": {"DO": 1, "MOVE": 1},

    # Modality/evidentiality
    "imperative": {"MUST": 1},
    "optative": {"WANT": 1},
    "conditional": {"IF": 1, "MAYBE": 1},
    "potential": {"CAN": 1, "MAYBE": 1},
    "negative": {"NOT": 1},

    # Register/style (less reliable for primitives)
    "formal": {},
    "informal": {},
    "colloquial": {},
    "dated": {"BEFORE": 1},
    "archaic": {"BEFORE": 1},
}

# Register/Stylistic Tags (present in 23-34% of entries)
REGISTER_PRIMITIVES = {
    "archaic": {"BEFORE": 1, "LONG_TIME": 1},
    "dated": {"BEFORE": 1},
    "obsolete": {"BEFORE": 1, "END": 1},
    "historical": {"BEFORE": 1, "WHEN": 1},
    "formal": {"WORDS": 1},
    "informal": {},
    "colloquial": {},
    "slang": {},
    "vulgar": {"GOOD": -1},
    "offensive": {"GOOD": -1},
    "derogatory": {"GOOD": -1},
    "pejorative": {"GOOD": -1},
    "literary": {"WORDS": 1, "THINK": 1},
    "poetic": {"WORDS": 1, "FEEL": 1},
    "rare": {"SOME": -1},
    "nonstandard": {"OTHER": 1},
    "technical": {"THINK": 1, "KNOW": 1},
    "scientific": {"THINK": 1, "KNOW": 1},
    "legal": {"MUST": 1, "WORDS": 1},
    "medical": {"BODY": 1, "ALIVE": 1},
    "religious": {"THINK": 1, "FEEL": 1},
    "humorous": {"FEEL": 1, "GOOD": 1},
    "euphemistic": {"GOOD": 1},
    "dysphemistic": {"GOOD": -1},
}

# Topic/Domain Mapping (720+ Wiktionary domains → primitives)
TOPIC_PRIMITIVES = {
    # Sciences → THINK + domain markers
    "biology": {"ALIVE": 1, "BODY": 1, "THINK": 1},
    "medicine": {"ALIVE": 1, "BODY": 1, "FEEL": 1},
    "physics": {"SOMETHING": 1, "THINK": 1, "CAUSE": 1},
    "chemistry": {"SOMETHING": 1, "THINK": 1},
    "mathematics": {"QUANTITY": 1, "THINK": 1},
    "computer science": {"SOMETHING": 1, "DO": 1, "THINK": 1},
    "computing": {"SOMETHING": 1, "DO": 1},
    "astronomy": {"SEE": 1, "FAR": 1, "BIG": 1},
    "geology": {"SOMETHING": 1, "WHERE": 1},
    "ecology": {"ALIVE": 1, "WHERE": 1},
    "genetics": {"ALIVE": 1, "BODY": 1, "CAUSE": 1},
    "botany": {"ALIVE": 1},
    "zoology": {"ALIVE": 1, "BODY": 1},
    "microbiology": {"ALIVE": 1, "BIG": -1},
    "biochemistry": {"ALIVE": 1, "SOMETHING": 1},
    "neuroscience": {"BODY": 1, "THINK": 1},
    "psychology": {"THINK": 1, "FEEL": 1},
    "psychiatry": {"THINK": 1, "FEEL": 1, "BODY": 1},

    # Body/Health
    "anatomy": {"BODY": 1, "PART": 1},
    "physiology": {"BODY": 1, "DO": 1},
    "pathology": {"BODY": 1, "GOOD": -1},
    "surgery": {"BODY": 1, "DO": 1},
    "pharmacology": {"BODY": 1, "CAUSE": 1},
    "dentistry": {"BODY": 1, "PART": 1},
    "ophthalmology": {"SEE": 1, "BODY": 1},

    # Communication
    "linguistics": {"WORDS": 1, "SAY": 1},
    "phonetics": {"SAY": 1, "HEAR": 1},
    "grammar": {"WORDS": 1},
    "semantics": {"WORDS": 1, "THINK": 1},
    "rhetoric": {"SAY": 1, "WORDS": 1},
    "music": {"HEAR": 1, "FEEL": 1},
    "art": {"SEE": 1, "FEEL": 1},
    "literature": {"WORDS": 1, "THINK": 1},
    "poetry": {"WORDS": 1, "FEEL": 1},
    "drama": {"DO": 1, "SAY": 1, "FEEL": 1},
    "film": {"SEE": 1, "HEAR": 1},
    "photography": {"SEE": 1},
    "journalism": {"SAY": 1, "KNOW": 1},
    "publishing": {"WORDS": 1, "SAY": 1},

    # Actions/Activities
    "sports": {"BODY": 1, "MOVE": 1, "DO": 1},
    "athletics": {"BODY": 1, "MOVE": 1},
    "gymnastics": {"BODY": 1, "MOVE": 1},
    "swimming": {"BODY": 1, "MOVE": 1},
    "boxing": {"BODY": 1, "DO": 1},
    "wrestling": {"BODY": 1, "DO": 1},
    "football": {"BODY": 1, "MOVE": 1, "DO": 1},
    "baseball": {"BODY": 1, "DO": 1},
    "basketball": {"BODY": 1, "MOVE": 1},
    "tennis": {"BODY": 1, "DO": 1},
    "golf": {"DO": 1},
    "hunting": {"DO": 1, "ALIVE": 1},
    "fishing": {"DO": 1, "ALIVE": 1},
    "cooking": {"DO": 1, "BODY": 1},
    "cuisine": {"DO": 1, "FEEL": 1},
    "military": {"DO": 1, "CAUSE": 1},
    "warfare": {"DO": 1, "CAUSE": 1, "GOOD": -1},
    "weaponry": {"SOMETHING": 1, "CAUSE": 1},
    "gardening": {"DO": 1, "ALIVE": 1},
    "agriculture": {"DO": 1, "ALIVE": 1},
    "farming": {"DO": 1, "ALIVE": 1},
    "manufacturing": {"DO": 1, "SOMETHING": 1},
    "construction": {"DO": 1, "SOMETHING": 1},
    "engineering": {"DO": 1, "THINK": 1},
    "aviation": {"MOVE": 1, "ABOVE": 1},
    "nautical": {"MOVE": 1},
    "maritime": {"MOVE": 1, "WHERE": 1},
    "rail": {"MOVE": 1},

    # Places/Geography
    "geography": {"WHERE": 1},
    "architecture": {"WHERE": 1, "SOMETHING": 1},
    "urban planning": {"WHERE": 1},
    "cartography": {"WHERE": 1, "SEE": 1},
    "oceanography": {"WHERE": 1},
    "meteorology": {"WHERE": 1, "HAPPEN": 1},
    "climatology": {"WHERE": 1, "WHEN": 1},

    # Time
    "history": {"BEFORE": 1, "WHEN": 1},
    "archaeology": {"BEFORE": 1, "SOMETHING": 1},
    "paleontology": {"BEFORE": 1, "ALIVE": 1},
    "chronology": {"WHEN": 1},
    "horology": {"WHEN": 1, "SOMETHING": 1},

    # Social
    "law": {"MUST": 1, "WORDS": 1},
    "legal": {"MUST": 1, "WORDS": 1},
    "politics": {"PEOPLE": 1, "MUST": 1},
    "government": {"PEOPLE": 1, "MUST": 1},
    "economics": {"HAVE": 1, "QUANTITY": 1},
    "finance": {"HAVE": 1, "QUANTITY": 1},
    "business": {"DO": 1, "HAVE": 1},
    "commerce": {"HAVE": 1, "DO": 1},
    "trade": {"HAVE": 1},
    "marketing": {"SAY": 1, "WANT": 1},
    "advertising": {"SAY": 1, "WANT": 1},
    "sociology": {"PEOPLE": 1, "THINK": 1},
    "anthropology": {"PEOPLE": 1, "THINK": 1},
    "education": {"KNOW": 1, "THINK": 1},
    "pedagogy": {"KNOW": 1, "SAY": 1},
    "religion": {"THINK": 1, "FEEL": 1, "MAYBE": 1},
    "theology": {"THINK": 1, "FEEL": 1},
    "philosophy": {"THINK": 1, "KNOW": 1},
    "ethics": {"GOOD": 1, "THINK": 1, "MUST": 1},
    "mythology": {"THINK": 1, "BEFORE": 1},
    "folklore": {"PEOPLE": 1, "BEFORE": 1},

    # Materials/Substances
    "textiles": {"SOMETHING": 1},
    "metallurgy": {"SOMETHING": 1, "DO": 1},
    "mineralogy": {"SOMETHING": 1},
    "ceramics": {"SOMETHING": 1, "DO": 1},
    "woodworking": {"SOMETHING": 1, "DO": 1},
    "fashion": {"BODY": 1, "SEE": 1},
    "clothing": {"BODY": 1},
    "jewelry": {"SOMETHING": 1, "SEE": 1},
    "furniture": {"SOMETHING": 1, "WHERE": 1},

    # Games/Entertainment
    "games": {"DO": 1, "FEEL": 1},
    "card games": {"DO": 1},
    "board games": {"DO": 1},
    "video games": {"DO": 1, "SEE": 1},
    "gambling": {"DO": 1, "MAYBE": 1},
    "chess": {"DO": 1, "THINK": 1},
    "poker": {"DO": 1, "THINK": 1},
}

# Etymology patterns for language family → primitives
ETYMOLOGY_PATTERNS = {
    # Language family indicators
    r'\bLatin\b': {"WORDS": 1},  # Latinate = formal/learned
    r'\bGreek\b': {"WORDS": 1, "THINK": 1},  # Greek = technical/scientific
    r'\bOld English\b': {},  # Native = common/core
    r'\bMiddle English\b': {},
    r'\bFrench\b': {"WORDS": 1},  # French = formal/cultural
    r'\bNorman\b': {"WORDS": 1},
    r'\bGerman\b': {},
    r'\bOld Norse\b': {},
    r'\bDutch\b': {},
    r'\bItalian\b': {},
    r'\bSpanish\b': {},
    r'\bPortuguese\b': {},
    r'\bArabic\b': {},
    r'\bHebrew\b': {},
    r'\bSanskrit\b': {"WORDS": 1, "BEFORE": 1},
    r'\bJapanese\b': {},
    r'\bChinese\b': {},

    # Semantic shift indicators
    r'\boriginally\b.*\b(meant|meaning)\b': {"BEFORE": 1},
    r'\bliterally\b': {"TRUE": 1},
    r'\bfigurative\b': {"LIKE": 1},
    r'\bmetaphor\b': {"LIKE": 1},

    # Borrowing patterns
    r'\bborrowed from\b': {"OTHER": 1},
    r'\bloaned from\b': {"OTHER": 1},
    r'\bcognate\b': {"SAME": 1},
    r'\bderived from\b': {"CAUSE": 1, "BEFORE": 1},

    # Compound patterns
    r'\bcompound of\b': {"PART": 1, "WITH": 1},
    r'\bblend of\b': {"PART": 1, "WITH": 1},
}

# Relation-specific decay rates for primitive spreading (user suggestion)
RELATION_DECAY = {
    "synonym": 0.85,      # High trust - synonyms share meaning
    "hypernym": 0.80,     # Genus inheritance - IS-A relation
    "hyponym": 0.70,      # Reverse inheritance - less certain
    "meronym": 0.60,      # Part-of - different semantic type
    "holonym": 0.60,      # Whole-of - different semantic type
    "antonym": 0.50,      # Opposite - need polarity flip
    "related": 0.50,      # Weak association
    "derived": 0.75,      # Morphological derivation
    "coordinate": 0.65,   # Sister terms (same hypernym)
}

# Genus words that indicate entity types
GENUS_PRIMITIVES = {
    # Living things
    "person": {"SOMEONE": 1, "ALIVE": 1},
    "man": {"SOMEONE": 1, "ALIVE": 1},
    "woman": {"SOMEONE": 1, "ALIVE": 1},
    "child": {"SOMEONE": 1, "ALIVE": 1},
    "animal": {"ALIVE": 1, "BODY": 1},
    "plant": {"ALIVE": 1},
    "organism": {"ALIVE": 1},

    # Objects
    "thing": {"SOMETHING": 1},
    "object": {"SOMETHING": 1},
    "device": {"SOMETHING": 1, "DO": 1},
    "tool": {"SOMETHING": 1, "DO": 1},
    "container": {"SOMETHING": 1, "INSIDE": 1},
    "vehicle": {"SOMETHING": 1, "MOVE": 1},

    # Places
    "place": {"WHERE": 1},
    "area": {"WHERE": 1},
    "building": {"WHERE": 1, "SOMETHING": 1},

    # Actions/Events
    "act": {"DO": 1},
    "action": {"DO": 1},
    "process": {"DO": 1, "HAPPEN": 1},
    "event": {"HAPPEN": 1, "WHEN": 1},

    # Mental
    "feeling": {"FEEL": 1},
    "emotion": {"FEEL": 1},
    "thought": {"THINK": 1},
    "belief": {"THINK": 1, "MAYBE": 1},

    # Abstract
    "quality": {"BE": 1},
    "state": {"BE": 1},
    "condition": {"BE": 1},
}


# =============================================================================
# GENUS EXTRACTION
# =============================================================================

GENUS_PATTERNS = [
    # Noun patterns: "A/An/The <adj>* <genus> ..."
    re.compile(r'^(?:A|An|The)\s+(?:\w+\s+)*?(\w+)(?:\s+(?:that|which|who|of|used|from|for|in|on|with|to)\b)', re.IGNORECASE),
    re.compile(r'^(?:A|An|The)\s+(\w+)\s*[,;.]', re.IGNORECASE),
    re.compile(r'^(?:A|An|The)\s+(\w+)$', re.IGNORECASE),

    # Verb patterns: "To <verb> ..."
    re.compile(r'^To\s+(\w+)\b', re.IGNORECASE),

    # Adjective patterns
    re.compile(r'^(?:Having|Being|Of|Relating to|Pertaining to)\s+(?:a\s+)?(\w+)', re.IGNORECASE),
    re.compile(r'^(\w+)\s+in\s+(?:nature|character|quality|manner)', re.IGNORECASE),
]


def extract_genus(definition: str) -> Optional[str]:
    """Extract the genus (hypernym) from a definition."""
    if not definition:
        return None

    definition = definition.strip()

    for pattern in GENUS_PATTERNS:
        match = pattern.match(definition)
        if match:
            genus = match.group(1).lower()
            # Filter out common non-genus words
            if genus not in {'a', 'an', 'the', 'any', 'some', 'one', 'this', 'that'}:
                return genus

    return None


def extract_etymology_primitives(etymology_text: str) -> Dict[str, Tuple[int, float]]:
    """Extract primitives from etymology text based on language patterns."""
    if not etymology_text:
        return {}

    primitives = {}
    for pattern, prims in ETYMOLOGY_PATTERNS.items():
        if re.search(pattern, etymology_text, re.IGNORECASE):
            for prim, val in prims.items():
                if prim not in primitives:
                    primitives[prim] = (val, 0.55)  # Lower confidence for etymology-based
    return primitives


def extract_categories(entry: dict) -> Set[str]:
    """Extract topic/domain categories from a Wiktionary entry."""
    categories = set()

    # Check senses for category info
    for sense in entry.get('senses', []):
        # Topics field
        for topic in sense.get('topics', []):
            categories.add(topic.lower())

        # Categories field
        for cat in sense.get('categories', []):
            if isinstance(cat, dict):
                cat_name = cat.get('name', '').lower()
            else:
                cat_name = str(cat).lower()
            categories.add(cat_name)

        # Tags can also contain domain info
        for tag in sense.get('tags', []):
            categories.add(tag.lower())

    # Check root-level categories
    for cat in entry.get('categories', []):
        if isinstance(cat, dict):
            cat_name = cat.get('name', '').lower()
        else:
            cat_name = str(cat).lower()
        categories.add(cat_name)

    return categories


def extract_register_tags(entry: dict) -> Set[str]:
    """Extract register/stylistic tags from entry."""
    registers = set()

    for sense in entry.get('senses', []):
        for tag in sense.get('tags', []):
            tag_lower = tag.lower()
            if tag_lower in REGISTER_PRIMITIVES:
                registers.add(tag_lower)

        # Also check raw_glosses for register markers
        for gloss in sense.get('raw_glosses', []):
            gloss_lower = gloss.lower()
            for register in REGISTER_PRIMITIVES:
                if f'({register})' in gloss_lower or f'[{register}]' in gloss_lower:
                    registers.add(register)

    return registers


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def create_database(db_path: Path):
    """Create the dictionary-encoded database schema."""
    conn = sqlite3.connect(str(db_path))

    conn.executescript("""
        -- Feature dictionary (patterns stored once)
        CREATE TABLE IF NOT EXISTS feature_dictionary (
            feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern TEXT NOT NULL,
            UNIQUE(pattern_type, pattern)
        );

        -- Feature to primitive mappings
        CREATE TABLE IF NOT EXISTS feature_primitives (
            feature_id INTEGER NOT NULL,
            primitive TEXT NOT NULL,
            value INTEGER NOT NULL,
            confidence REAL DEFAULT 0.8,
            PRIMARY KEY (feature_id, primitive),
            FOREIGN KEY (feature_id) REFERENCES feature_dictionary(feature_id)
        );

        -- Pre-computed word primitives (main lookup table)
        CREATE TABLE IF NOT EXISTS word_primitives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            pos TEXT,
            primitive TEXT NOT NULL,
            value INTEGER NOT NULL,
            confidence REAL NOT NULL,
            source TEXT NOT NULL,
            UNIQUE(word, pos, primitive)
        );

        -- Genus hierarchy
        CREATE TABLE IF NOT EXISTS genus_hierarchy (
            word TEXT NOT NULL,
            pos TEXT,
            genus TEXT NOT NULL,
            depth INTEGER DEFAULT 1,
            confidence REAL DEFAULT 0.8,
            PRIMARY KEY (word, pos, genus)
        );

        -- Semantic relations
        CREATE TABLE IF NOT EXISTS semantic_relations (
            source_word TEXT NOT NULL,
            target_word TEXT NOT NULL,
            relation TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            PRIMARY KEY (source_word, target_word, relation)
        );

        -- Word statistics
        CREATE TABLE IF NOT EXISTS word_stats (
            word TEXT PRIMARY KEY,
            pos TEXT,
            definition TEXT,
            primitive_count INTEGER,
            avg_confidence REAL,
            sources TEXT,
            genus TEXT
        );

        -- Indexes for fast lookup
        CREATE INDEX IF NOT EXISTS idx_word_primitives_word ON word_primitives(word);
        CREATE INDEX IF NOT EXISTS idx_word_primitives_prim ON word_primitives(primitive);
        CREATE INDEX IF NOT EXISTS idx_genus_word ON genus_hierarchy(word);
        CREATE INDEX IF NOT EXISTS idx_genus_genus ON genus_hierarchy(genus);
        CREATE INDEX IF NOT EXISTS idx_relations_source ON semantic_relations(source_word);
        CREATE INDEX IF NOT EXISTS idx_relations_target ON semantic_relations(target_word);
        CREATE INDEX IF NOT EXISTS idx_feature_dict_pattern ON feature_dictionary(pattern);
    """)

    conn.commit()
    return conn


# =============================================================================
# PHASE 2: DICTIONARY ENCODING MIGRATION
# =============================================================================

# All 73 GSE primitives for dictionary encoding
ALL_PRIMITIVES = [
    # SUBSTANTIVES (10)
    "I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART", "SAME", "OTHER",
    # QUANTITY (4)
    "ONE", "TWO", "QUANTITY", "NUMBER",
    # Additional quantity-related
    "SOME", "ALL", "MUCH", "LITTLE", "ZERO",
    # EVALUATORS (4)
    "GOOD", "BAD", "BIG", "SMALL",
    # Additional evaluative
    "INTENSITY",
    # MENTAL (7)
    "THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR", "INFER",
    # ACTION (10)
    "SAY", "WORDS", "DO", "HAPPEN", "MOVE", "BE", "HAVE", "EXIST", "ALIVE", "DEAD",
    # Additional action
    "CAUSE",
    # TEMPORAL (10)
    "MOMENT", "WHEN", "BEFORE", "AFTER", "THEN", "NOW", "LONG_TIME", "SHORT_TIME", "START", "END",
    # SPATIAL (14)
    "WHERE", "HERE", "SIDE", "TOUCH", "ABOVE", "BELOW", "FAR", "NEAR", "OUTSIDE", "INSIDE", "TOWARD", "AWAY", "WITH", "WITHOUT",
    # LOGICAL (14)
    "NOT", "MAYBE", "CAN", "MUST", "BECAUSE", "IF", "LIKE", "TRUE", "FALSE", "CERTAINTY",
]

# All source types for dictionary encoding
ALL_SOURCES = [
    "pos", "tag", "genus", "hypernym", "definition", "keyword",
    "meronym", "holonym", "etymology", "topic", "register",
    "head", "synonym", "antonym", "derived"
]


def create_dictionary_encoded_database(db_path: Path):
    """Create optimized dictionary-encoded schema (Phase 2)."""
    conn = sqlite3.connect(str(db_path))

    conn.executescript("""
        -- Primitive dictionary (stored once, referenced by ID)
        CREATE TABLE IF NOT EXISTS primitive_dictionary (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            bank TEXT,
            is_bipolar BOOLEAN DEFAULT FALSE,
            bipolar_partner_id INTEGER
        );

        -- Source dictionary (stored once, referenced by ID)
        CREATE TABLE IF NOT EXISTS source_dictionary (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            reliability REAL DEFAULT 0.7
        );

        -- Optimized word-primitive storage with integer IDs
        CREATE TABLE IF NOT EXISTS word_primitives_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            pos TEXT,
            primitive_id INTEGER NOT NULL,
            value INTEGER NOT NULL,
            confidence REAL NOT NULL,
            source_id INTEGER NOT NULL,
            FOREIGN KEY (primitive_id) REFERENCES primitive_dictionary(id),
            FOREIGN KEY (source_id) REFERENCES source_dictionary(id)
        );

        -- Genus hierarchy (copied from original)
        CREATE TABLE IF NOT EXISTS genus_hierarchy (
            word TEXT NOT NULL,
            pos TEXT,
            genus TEXT NOT NULL,
            depth INTEGER DEFAULT 1,
            confidence REAL DEFAULT 0.8,
            PRIMARY KEY (word, pos, genus)
        );

        -- Semantic relations (copied from original)
        CREATE TABLE IF NOT EXISTS semantic_relations (
            source_word TEXT NOT NULL,
            target_word TEXT NOT NULL,
            relation TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            PRIMARY KEY (source_word, target_word, relation)
        );

        -- Indexes for fast lookup
        CREATE INDEX IF NOT EXISTS idx_wp2_word ON word_primitives_v2(word);
        CREATE INDEX IF NOT EXISTS idx_wp2_primitive ON word_primitives_v2(primitive_id);
        CREATE INDEX IF NOT EXISTS idx_wp2_word_pos ON word_primitives_v2(word, pos);
        CREATE INDEX IF NOT EXISTS idx_genus_word ON genus_hierarchy(word);
        CREATE INDEX IF NOT EXISTS idx_genus_genus ON genus_hierarchy(genus);
        CREATE INDEX IF NOT EXISTS idx_relations_source ON semantic_relations(source_word);
        CREATE INDEX IF NOT EXISTS idx_relations_target ON semantic_relations(target_word);
    """)

    conn.commit()
    return conn


def populate_dictionaries(conn: sqlite3.Connection):
    """Populate primitive and source dictionaries."""
    logger.info("Populating primitive and source dictionaries...")

    # Bank assignments for primitives
    BANK_ASSIGNMENTS = {
        "SUBSTANTIVES": ["I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART", "SAME", "OTHER"],
        "QUANTITY": ["ONE", "TWO", "QUANTITY", "NUMBER", "SOME", "ALL", "MUCH", "LITTLE", "ZERO"],
        "EVALUATORS": ["GOOD", "BAD", "BIG", "SMALL", "INTENSITY"],
        "MENTAL": ["THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR", "INFER"],
        "ACTION": ["SAY", "WORDS", "DO", "HAPPEN", "MOVE", "BE", "HAVE", "EXIST", "ALIVE", "DEAD", "CAUSE"],
        "TEMPORAL": ["MOMENT", "WHEN", "BEFORE", "AFTER", "THEN", "NOW", "LONG_TIME", "SHORT_TIME", "START", "END"],
        "SPATIAL": ["WHERE", "HERE", "SIDE", "TOUCH", "ABOVE", "BELOW", "FAR", "NEAR", "OUTSIDE", "INSIDE", "TOWARD", "AWAY", "WITH", "WITHOUT"],
        "LOGICAL": ["NOT", "MAYBE", "CAN", "MUST", "BECAUSE", "IF", "LIKE", "TRUE", "FALSE", "CERTAINTY"],
    }

    # Bipolar pairs
    BIPOLAR_PAIRS = [
        ("GOOD", "BAD"), ("BIG", "SMALL"), ("ALIVE", "DEAD"),
        ("BEFORE", "AFTER"), ("THEN", "NOW"), ("LONG_TIME", "SHORT_TIME"),
        ("START", "END"), ("ABOVE", "BELOW"), ("FAR", "NEAR"),
        ("OUTSIDE", "INSIDE"), ("TOWARD", "AWAY"), ("WITH", "WITHOUT"),
        ("TRUE", "FALSE"), ("SAME", "OTHER"),
    ]

    # Build primitive to bank mapping
    prim_to_bank = {}
    for bank, prims in BANK_ASSIGNMENTS.items():
        for prim in prims:
            prim_to_bank[prim] = bank

    # Insert primitives
    for i, prim in enumerate(ALL_PRIMITIVES):
        bank = prim_to_bank.get(prim, "OTHER")
        conn.execute(
            "INSERT OR IGNORE INTO primitive_dictionary (id, name, bank) VALUES (?, ?, ?)",
            (i, prim, bank)
        )

    # Mark bipolar pairs
    for pos_prim, neg_prim in BIPOLAR_PAIRS:
        # Get IDs
        pos_cursor = conn.execute("SELECT id FROM primitive_dictionary WHERE name = ?", (pos_prim,))
        neg_cursor = conn.execute("SELECT id FROM primitive_dictionary WHERE name = ?", (neg_prim,))
        pos_row = pos_cursor.fetchone()
        neg_row = neg_cursor.fetchone()
        if pos_row and neg_row:
            conn.execute(
                "UPDATE primitive_dictionary SET is_bipolar = TRUE, bipolar_partner_id = ? WHERE id = ?",
                (neg_row[0], pos_row[0])
            )
            conn.execute(
                "UPDATE primitive_dictionary SET is_bipolar = TRUE, bipolar_partner_id = ? WHERE id = ?",
                (pos_row[0], neg_row[0])
            )

    # Source reliability weights
    SOURCE_RELIABILITY = {
        "pos": 0.60,
        "tag": 0.65,
        "genus": 0.75,
        "hypernym": 0.80,
        "definition": 0.70,
        "keyword": 0.70,
        "meronym": 0.70,
        "holonym": 0.70,
        "etymology": 0.55,
        "topic": 0.60,
        "register": 0.60,
        "head": 0.70,
        "synonym": 0.85,
        "antonym": 0.50,
        "derived": 0.75,
    }

    # Insert sources
    for i, source in enumerate(ALL_SOURCES):
        reliability = SOURCE_RELIABILITY.get(source, 0.7)
        conn.execute(
            "INSERT OR IGNORE INTO source_dictionary (id, name, reliability) VALUES (?, ?, ?)",
            (i, source, reliability)
        )

    conn.commit()
    logger.info(f"Added {len(ALL_PRIMITIVES)} primitives and {len(ALL_SOURCES)} sources to dictionaries")


def migrate_to_dictionary_encoding(old_db_path: Path, new_db_path: Path):
    """Migrate from string-based to dictionary-encoded storage."""
    logger.info(f"Migrating {old_db_path} to dictionary-encoded format...")

    if not old_db_path.exists():
        logger.error(f"Source database not found: {old_db_path}")
        return False

    # Create new database with dictionary encoding
    if new_db_path.exists():
        new_db_path.unlink()

    new_conn = create_dictionary_encoded_database(new_db_path)
    populate_dictionaries(new_conn)

    # Build lookup maps
    prim_cursor = new_conn.execute("SELECT id, name FROM primitive_dictionary")
    primitive_map = {name: id for id, name in prim_cursor}

    src_cursor = new_conn.execute("SELECT id, name FROM source_dictionary")
    source_map = {name: id for id, name in src_cursor}

    # Open old database
    old_conn = sqlite3.connect(str(old_db_path))
    old_conn.row_factory = sqlite3.Row

    # Migrate word_primitives
    logger.info("Migrating word primitives...")
    cursor = old_conn.execute("SELECT word, pos, primitive, value, confidence, source FROM word_primitives")

    batch = []
    count = 0
    for row in cursor:
        prim = row['primitive']
        source = row['source'].split(':')[0] if ':' in row['source'] else row['source']

        # Skip unknown primitives/sources
        if prim not in primitive_map:
            continue
        if source not in source_map:
            source = "definition"  # Default fallback

        batch.append((
            row['word'],
            row['pos'],
            primitive_map[prim],
            row['value'],
            row['confidence'],
            source_map[source]
        ))

        if len(batch) >= 10000:
            new_conn.executemany("""
                INSERT OR IGNORE INTO word_primitives_v2
                (word, pos, primitive_id, value, confidence, source_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, batch)
            new_conn.commit()
            count += len(batch)
            logger.info(f"Migrated {count:,} rows...")
            batch = []

    # Final batch
    if batch:
        new_conn.executemany("""
            INSERT OR IGNORE INTO word_primitives_v2
            (word, pos, primitive_id, value, confidence, source_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, batch)
        new_conn.commit()
        count += len(batch)

    # Copy other tables
    logger.info("Copying semantic relations...")
    old_conn.execute("ATTACH ? AS new_db", (str(new_db_path),))
    old_conn.execute("""
        INSERT OR IGNORE INTO new_db.semantic_relations
        SELECT * FROM semantic_relations
    """)

    logger.info("Copying genus hierarchy...")
    old_conn.execute("""
        INSERT OR IGNORE INTO new_db.genus_hierarchy
        SELECT * FROM genus_hierarchy
    """)

    old_conn.commit()
    old_conn.close()
    new_conn.close()

    # Report size savings
    old_size = old_db_path.stat().st_size / (1024 * 1024)
    new_size = new_db_path.stat().st_size / (1024 * 1024)
    savings = (1 - new_size / old_size) * 100 if old_size > 0 else 0

    logger.info("\nMigration complete:")
    logger.info(f"  Rows migrated: {count:,}")
    logger.info(f"  Old size: {old_size:.1f} MB")
    logger.info(f"  New size: {new_size:.1f} MB")
    logger.info(f"  Savings: {savings:.1f}%")

    return True


def populate_feature_dictionary(conn: sqlite3.Connection):
    """Populate the feature dictionary with keyword patterns."""
    logger.info("Populating feature dictionary...")

    # Insert keyword features
    for keyword, primitives in KEYWORD_PRIMITIVES.items():
        cursor = conn.execute(
            "INSERT OR IGNORE INTO feature_dictionary (pattern_type, pattern) VALUES (?, ?)",
            ("keyword", keyword)
        )
        if cursor.lastrowid:
            feature_id = cursor.lastrowid
        else:
            cursor = conn.execute(
                "SELECT feature_id FROM feature_dictionary WHERE pattern_type = ? AND pattern = ?",
                ("keyword", keyword)
            )
            feature_id = cursor.fetchone()[0]

        for prim, val in primitives.items():
            conn.execute(
                "INSERT OR IGNORE INTO feature_primitives (feature_id, primitive, value) VALUES (?, ?, ?)",
                (feature_id, prim, val)
            )

    # Insert genus features
    for genus, primitives in GENUS_PRIMITIVES.items():
        cursor = conn.execute(
            "INSERT OR IGNORE INTO feature_dictionary (pattern_type, pattern) VALUES (?, ?)",
            ("genus", genus)
        )
        if cursor.lastrowid:
            feature_id = cursor.lastrowid
        else:
            cursor = conn.execute(
                "SELECT feature_id FROM feature_dictionary WHERE pattern_type = ? AND pattern = ?",
                ("genus", genus)
            )
            feature_id = cursor.fetchone()[0]

        for prim, val in primitives.items():
            conn.execute(
                "INSERT OR IGNORE INTO feature_primitives (feature_id, primitive, value) VALUES (?, ?, ?)",
                (feature_id, prim, val)
            )

    conn.commit()

    cursor = conn.execute("SELECT COUNT(*) FROM feature_dictionary")
    count = cursor.fetchone()[0]
    logger.info(f"Feature dictionary populated with {count} patterns")


def process_entry(entry: dict, conn: sqlite3.Connection, feature_cache: dict) -> dict:
    """Process a single Wiktionary entry and extract primitives."""
    word = entry.get('word', '').lower()
    pos = entry.get('pos', '')

    if not word:
        return {}

    # Get first definition
    senses = entry.get('senses', [])
    definition = ''
    if senses and 'glosses' in senses[0]:
        definition = senses[0]['glosses'][0] if senses[0]['glosses'] else ''

    # Extract primitives
    primitives: Dict[str, Tuple[int, float, str]] = {}  # prim -> (value, confidence, source)

    # 0. If the WORD ITSELF is a known keyword, apply those primitives with HIGH confidence
    # This ensures sentiment words like "wretched", "cheerless" get correct GOOD values
    if word in KEYWORD_PRIMITIVES:
        for prim, val in KEYWORD_PRIMITIVES[word].items():
            primitives[prim] = (val, 0.9, "keyword:self")  # High confidence for self-match

    # 1. POS-based primitives (lower confidence, don't override keyword:self)
    if pos in POS_PRIMITIVES:
        for prim, val in POS_PRIMITIVES[pos].items():
            if prim not in primitives or primitives[prim][1] < 0.6:
                primitives[prim] = (val, 0.6, "pos")

    # 2. Grammatical tag-based primitives from forms (don't override higher confidence)
    forms = entry.get('forms', [])
    for form in forms:
        tags = form.get('tags', [])
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in TAG_PRIMITIVES:
                for prim, val in TAG_PRIMITIVES[tag_lower].items():
                    if prim not in primitives or primitives[prim][1] < 0.65:
                        primitives[prim] = (val, 0.65, f"tag:{tag_lower}")

    # 3. Head template info (e.g., transitive/intransitive markers)
    head_templates = entry.get('head_templates', [])
    for ht in head_templates:
        expansion = ht.get('expansion', '').lower()
        # Check for transitivity markers
        if 'transitive' in expansion:
            if 'intransitive' in expansion:
                primitives.setdefault('DO', (1, 0.7, "head:both"))
            else:
                primitives.setdefault('CAUSE', (1, 0.7, "head:transitive"))
        elif 'intransitive' in expansion:
            primitives.setdefault('HAPPEN', (1, 0.7, "head:intransitive"))
        # Check for countability
        if 'countable' in expansion:
            primitives.setdefault('ONE', (1, 0.65, "head:countable"))
        if 'uncountable' in expansion:
            primitives.setdefault('SOMETHING', (1, 0.65, "head:uncountable"))

    # 4. Hypernym-based primitives (IS-A inheritance)
    hypernyms = entry.get('hypernyms', [])
    for hyp in hypernyms:
        hyp_word = hyp.get('word', '').lower()
        if hyp_word:
            # Store hypernym relationship
            conn.execute(
                "INSERT OR IGNORE INTO genus_hierarchy (word, pos, genus, depth, confidence) VALUES (?, ?, ?, ?, ?)",
                (word, pos, hyp_word, 1, 0.85)
            )
            # Inherit primitives from known hypernyms
            if hyp_word in GENUS_PRIMITIVES:
                for prim, val in GENUS_PRIMITIVES[hyp_word].items():
                    if prim not in primitives:
                        primitives[prim] = (val, 0.8, f"hypernym:{hyp_word}")
            # Check keyword mappings too
            if hyp_word in KEYWORD_PRIMITIVES:
                for prim, val in KEYWORD_PRIMITIVES[hyp_word].items():
                    if prim not in primitives:
                        primitives[prim] = (val, 0.75, f"hypernym:{hyp_word}")

    # 5. Genus extraction from definition
    genus = extract_genus(definition)
    if genus:
        # Store genus relationship
        conn.execute(
            "INSERT OR IGNORE INTO genus_hierarchy (word, pos, genus, depth, confidence) VALUES (?, ?, ?, ?, ?)",
            (word, pos, genus, 1, 0.8)
        )

        # Get primitives from genus
        if genus in GENUS_PRIMITIVES:
            for prim, val in GENUS_PRIMITIVES[genus].items():
                if prim not in primitives:
                    primitives[prim] = (val, 0.75, "genus")

    # 6. Definition keyword matching
    if definition:
        def_lower = definition.lower()
        for keyword, kw_prims in KEYWORD_PRIMITIVES.items():
            # Check for word boundary match
            if re.search(r'\b' + re.escape(keyword) + r'\b', def_lower):
                for prim, val in kw_prims.items():
                    if prim not in primitives:
                        primitives[prim] = (val, 0.7, "definition")

    # 7. Register/stylistic tags (NEW Phase 1)
    registers = extract_register_tags(entry)
    for register in registers:
        if register in REGISTER_PRIMITIVES:
            for prim, val in REGISTER_PRIMITIVES[register].items():
                if prim not in primitives:
                    primitives[prim] = (val, 0.6, f"register:{register}")

    # 8. Topic/domain categories (NEW Phase 1)
    categories = extract_categories(entry)
    for category in categories:
        # Direct match
        if category in TOPIC_PRIMITIVES:
            for prim, val in TOPIC_PRIMITIVES[category].items():
                if prim not in primitives:
                    primitives[prim] = (val, 0.6, f"topic:{category}")
        # Partial match (e.g., "biology" in "cell biology")
        else:
            for topic, topic_prims in TOPIC_PRIMITIVES.items():
                if topic in category:
                    for prim, val in topic_prims.items():
                        if prim not in primitives:
                            primitives[prim] = (val, 0.5, f"topic:{topic}")
                    break

    # 9. Etymology-based primitives (NEW Phase 1)
    etymology_templates = entry.get('etymology_templates', [])
    etymology_text = entry.get('etymology_text', '')
    if etymology_templates:
        # Combine etymology template expansions
        for et in etymology_templates:
            expansion = et.get('expansion', '')
            if expansion:
                etymology_text = f"{etymology_text} {expansion}"

    if etymology_text:
        etym_primitives = extract_etymology_primitives(etymology_text)
        for prim, (val, conf) in etym_primitives.items():
            if prim not in primitives:
                primitives[prim] = (val, conf, "etymology")

    # 10. Semantic relations (synonyms/antonyms/hyponyms/meronyms)
    for sense in senses:
        # Synonyms
        for syn in sense.get('synonyms', []):
            syn_word = syn.get('word', '').lower()
            if syn_word:
                conn.execute(
                    "INSERT OR IGNORE INTO semantic_relations (source_word, target_word, relation, weight) VALUES (?, ?, ?, ?)",
                    (word, syn_word, "synonym", 1.0)
                )

        # Antonyms
        for ant in sense.get('antonyms', []):
            ant_word = ant.get('word', '').lower()
            if ant_word:
                conn.execute(
                    "INSERT OR IGNORE INTO semantic_relations (source_word, target_word, relation, weight) VALUES (?, ?, ?, ?)",
                    (word, ant_word, "antonym", 1.0)
                )

        # Hyponyms (more specific terms)
        for hypo in sense.get('hyponyms', []):
            hypo_word = hypo.get('word', '').lower()
            if hypo_word:
                conn.execute(
                    "INSERT OR IGNORE INTO semantic_relations (source_word, target_word, relation, weight) VALUES (?, ?, ?, ?)",
                    (word, hypo_word, "hyponym", 0.9)
                )

        # Meronyms (parts)
        for mero in sense.get('meronyms', []):
            mero_word = mero.get('word', '').lower()
            if mero_word:
                conn.execute(
                    "INSERT OR IGNORE INTO semantic_relations (source_word, target_word, relation, weight) VALUES (?, ?, ?, ?)",
                    (word, mero_word, "meronym", 0.9)
                )
                # The word has parts, so mark HAVE primitive
                if 'HAVE' not in primitives:
                    primitives['HAVE'] = (1, 0.7, "meronym")

        # Holonyms (wholes this is part of)
        for holo in sense.get('holonyms', []):
            holo_word = holo.get('word', '').lower()
            if holo_word:
                conn.execute(
                    "INSERT OR IGNORE INTO semantic_relations (source_word, target_word, relation, weight) VALUES (?, ?, ?, ?)",
                    (word, holo_word, "holonym", 0.9)
                )
                # The word is a part, so mark PART primitive
                if 'PART' not in primitives:
                    primitives['PART'] = (1, 0.7, "holonym")

    # Store word primitives
    for prim, (val, conf, source) in primitives.items():
        conn.execute(
            "INSERT OR REPLACE INTO word_primitives (word, pos, primitive, value, confidence, source) VALUES (?, ?, ?, ?, ?, ?)",
            (word, pos, prim, val, conf, source)
        )

    # Store word stats
    if primitives:
        sources = list(set(src for _, _, src in primitives.values()))
        avg_conf = sum(conf for _, conf, _ in primitives.values()) / len(primitives)
        conn.execute(
            "INSERT OR REPLACE INTO word_stats (word, pos, definition, primitive_count, avg_confidence, sources, genus) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (word, pos, definition[:500] if definition else None, len(primitives), avg_conf, json.dumps(sources), genus)
        )

    return primitives


# =============================================================================
# DOWNLOAD
# =============================================================================

def download_wiktionary():
    """Download Wiktionary data from kaikki.org."""
    try:
        import requests
    except ImportError:
        logger.error("requests library required - pip install requests")
        return False

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Use the English-only JSONL file (still available, though marked deprecated)
    url = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl"
    logger.info(f"Downloading Wiktionary from {url}")
    logger.info("This file is ~2.6GB and may take 15-30 minutes...")

    try:
        # Stream download with progress
        response = requests.get(url, stream=True, timeout=3600)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(RAW_JSON_PATH, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        pct = (downloaded / total_size) * 100
                        if downloaded % (50 * 1024 * 1024) < 8192:  # Every ~50MB
                            logger.info(f"Downloaded {downloaded / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB ({pct:.1f}%)")

        logger.info(f"Download complete: {RAW_JSON_PATH}")
        return True

    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False


# =============================================================================
# BUILD
# =============================================================================

def build_database():
    """Build the primitive resolver database from Wiktionary JSON."""
    if not RAW_JSON_PATH.exists():
        logger.error(f"Wiktionary data not found at {RAW_JSON_PATH}")
        logger.error("Run with --download first")
        return False

    logger.info(f"Building database from {RAW_JSON_PATH}")

    # Create database
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = create_database(DB_PATH)

    # Populate feature dictionary
    populate_feature_dictionary(conn)

    # Load feature cache for fast lookup
    feature_cache = {}
    cursor = conn.execute("SELECT pattern, feature_id FROM feature_dictionary WHERE pattern_type = 'keyword'")
    for pattern, feature_id in cursor:
        feature_cache[pattern] = feature_id

    # Process entries
    logger.info("Processing Wiktionary entries...")

    count = 0
    batch_size = 10000
    start_time = time.time()

    with open(RAW_JSON_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
                process_entry(entry, conn, feature_cache)
                count += 1

                if count % batch_size == 0:
                    conn.commit()
                    elapsed = time.time() - start_time
                    rate = count / elapsed
                    logger.info(f"Processed {count:,} entries ({rate:.0f}/sec)")

            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.debug(f"Error processing entry: {e}")
                continue

    conn.commit()

    # Final stats
    elapsed = time.time() - start_time
    logger.info(f"Processed {count:,} entries in {elapsed:.1f}s")

    # Get database stats
    cursor = conn.execute("SELECT COUNT(DISTINCT word) FROM word_primitives")
    unique_words = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM word_primitives")
    total_primitives = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM semantic_relations")
    relations = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM genus_hierarchy")
    genus_count = cursor.fetchone()[0]

    logger.info("\nDatabase built:")
    logger.info(f"  Unique words: {unique_words:,}")
    logger.info(f"  Primitive assignments: {total_primitives:,}")
    logger.info(f"  Semantic relations: {relations:,}")
    logger.info(f"  Genus relationships: {genus_count:,}")
    logger.info(f"  Database size: {DB_PATH.stat().st_size / (1024*1024):.1f}MB")

    conn.close()
    return True


# =============================================================================
# TEST
# =============================================================================

def test_resolver():
    """Test the primitive resolver."""
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    test_words = [
        'run', 'happy', 'person', 'dog', 'think', 'love', 'building',
        'above', 'below', 'near', 'far', 'time', 'good', 'bad',
        'water', 'fire', 'earth', 'air', 'tree', 'flower',
        'mother', 'father', 'child', 'friend', 'enemy',
        'speak', 'listen', 'see', 'hear', 'touch',
        'big', 'small', 'fast', 'slow', 'hot', 'cold'
    ]

    print("\n" + "=" * 70)
    print("Wiktionary Primitive Resolver Test")
    print("=" * 70)

    for word in test_words:
        cursor = conn.execute("""
            SELECT primitive, value, confidence, source
            FROM word_primitives
            WHERE word = ?
            ORDER BY confidence DESC
        """, (word,))

        rows = cursor.fetchall()
        if rows:
            prims = {row['primitive']: row['value'] for row in rows}
            sources = list(set(row['source'] for row in rows))
            print(f"\n{word}: {len(prims)} primitives from {sources}")
            print(f"  {prims}")
        else:
            print(f"\n{word}: NOT FOUND")

    # Get stats
    cursor = conn.execute("SELECT COUNT(DISTINCT word) FROM word_primitives")
    total_words = cursor.fetchone()[0]

    cursor = conn.execute("SELECT AVG(primitive_count) FROM word_stats")
    avg_prims = cursor.fetchone()[0]

    print("\n" + "=" * 70)
    print(f"Total words with primitives: {total_words:,}")
    print(f"Average primitives per word: {avg_prims:.1f}")
    print("=" * 70)

    conn.close()
    return True


# =============================================================================
# MAIN
# =============================================================================

# =============================================================================
# PHASE 3: SEMANTIC RELATION SPREADING
# =============================================================================

def spread_primitives_through_relations(db_path: Path, max_depth: int = 2):
    """
    Spread primitives through semantic relations with relation-specific decay.
    Uses the RELATION_DECAY weights for different relation types.
    """
    logger.info("Phase 3: Spreading primitives through semantic relations...")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get all words with primitives
    words_cursor = conn.execute("SELECT DISTINCT word FROM word_primitives")
    words_with_primitives = {row[0] for row in words_cursor}

    # Get all semantic relations
    relations_cursor = conn.execute("""
        SELECT source_word, target_word, relation, weight
        FROM semantic_relations
        ORDER BY source_word
    """)

    relations = defaultdict(list)
    for row in relations_cursor:
        relations[row['source_word']].append({
            'target': row['target_word'],
            'relation': row['relation'],
            'weight': row['weight']
        })

    logger.info(f"Found {len(relations)} words with relations")

    # Process spreading
    new_assignments = []
    processed = set()

    for source_word, related in relations.items():
        if source_word in processed:
            continue

        # Get source word's primitives
        prim_cursor = conn.execute("""
            SELECT primitive, value, confidence
            FROM word_primitives
            WHERE word = ?
        """, (source_word,))
        source_primitives = {row['primitive']: (row['value'], row['confidence']) for row in prim_cursor}

        if not source_primitives:
            continue

        for rel in related:
            target = rel['target']
            relation_type = rel['relation']
            base_weight = rel['weight']

            # Get relation-specific decay
            decay = RELATION_DECAY.get(relation_type, 0.5)
            confidence_modifier = decay * base_weight

            # Check if target already has primitives
            target_cursor = conn.execute("""
                SELECT primitive FROM word_primitives WHERE word = ?
            """, (target,))
            existing_prims = {row[0] for row in target_cursor}

            # Handle antonyms specially - flip polarity for bipolar primitives
            if relation_type == 'antonym':
                for prim, (val, conf) in source_primitives.items():
                    if prim not in existing_prims:
                        # For bipolar primitives, flip the sign
                        # For non-bipolar, still spread but with lower confidence
                        new_val = -val if prim in {'GOOD', 'BAD', 'BIG', 'SMALL', 'ALIVE', 'DEAD',
                                                    'BEFORE', 'AFTER', 'ABOVE', 'BELOW', 'FAR', 'NEAR',
                                                    'TRUE', 'FALSE', 'SAME', 'OTHER'} else val
                        new_conf = conf * confidence_modifier
                        if new_conf > 0.3:  # Minimum confidence threshold
                            new_assignments.append((
                                target, None, prim, new_val, new_conf, f"spread:{relation_type}"
                            ))
            else:
                # For synonyms, hypernyms, etc. - spread primitives with decay
                for prim, (val, conf) in source_primitives.items():
                    if prim not in existing_prims:
                        new_conf = conf * confidence_modifier
                        if new_conf > 0.3:  # Minimum confidence threshold
                            new_assignments.append((
                                target, None, prim, val, new_conf, f"spread:{relation_type}"
                            ))

        processed.add(source_word)

        if len(processed) % 10000 == 0:
            logger.info(f"Processed {len(processed):,} source words, {len(new_assignments):,} new assignments")

    # Insert new assignments
    logger.info(f"Inserting {len(new_assignments):,} new primitive assignments from spreading...")

    batch_size = 10000
    for i in range(0, len(new_assignments), batch_size):
        batch = new_assignments[i:i + batch_size]
        conn.executemany("""
            INSERT OR IGNORE INTO word_primitives
            (word, pos, primitive, value, confidence, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, batch)
        conn.commit()

    # Update statistics
    cursor = conn.execute("SELECT COUNT(DISTINCT word) FROM word_primitives")
    new_word_count = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM word_primitives")
    new_prim_count = cursor.fetchone()[0]

    logger.info("\nAfter spreading:")
    logger.info(f"  Total words: {new_word_count:,}")
    logger.info(f"  Total assignments: {new_prim_count:,}")
    logger.info(f"  New assignments added: {len(new_assignments):,}")

    conn.close()
    return True


# =============================================================================
# PHASE 4: EXTERNAL SOURCE CORRECTIONS
# =============================================================================

def apply_external_corrections(db_path: Path, external_dir: Path):
    """
    Apply corrections from trusted external NLP sources.
    This fixes known issues like GOOD polarity based on NRC, USAS, etc.
    """
    logger.info("Phase 4: Applying external source corrections...")

    conn = sqlite3.connect(str(db_path))

    corrections_applied = 0

    # 1. Load NRC Emotion data for GOOD corrections
    nrc_emotion_path = external_dir / "nrc_emotion.txt"
    if nrc_emotion_path.exists():
        logger.info("Loading NRC Emotion corrections...")
        with open(nrc_emotion_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) != 3:
                    continue
                word, emotion, value = parts
                word = word.lower()

                # Only apply GOOD corrections for clear cases
                if value == '1':
                    if emotion in ('joy', 'trust', 'positive'):
                        # Positive - set GOOD=+1
                        conn.execute("""
                            UPDATE word_primitives
                            SET value = 1, confidence = 0.85, source = 'correction:nrc_emotion'
                            WHERE word = ? AND primitive = 'GOOD'
                        """, (word,))
                        corrections_applied += conn.total_changes
                    elif emotion in ('anger', 'disgust', 'fear', 'sadness', 'negative'):
                        # Negative - set GOOD=-1
                        conn.execute("""
                            UPDATE word_primitives
                            SET value = -1, confidence = 0.85, source = 'correction:nrc_emotion'
                            WHERE word = ? AND primitive = 'GOOD'
                        """, (word,))
                        corrections_applied += conn.total_changes

    # 2. Load NRC VAD data for GOOD corrections (valence)
    nrc_vad_path = external_dir / "nrc_vad.txt"
    if nrc_vad_path.exists():
        logger.info("Loading NRC VAD corrections...")
        with open(nrc_vad_path, 'r', encoding='utf-8') as f:
            next(f)  # Skip header
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) != 4:
                    continue
                word, valence, arousal, dominance = parts
                word = word.lower()

                try:
                    v = float(valence)
                    # Strong positive valence
                    if v >= 0.5:
                        conn.execute("""
                            UPDATE word_primitives
                            SET value = 1, confidence = 0.85, source = 'correction:nrc_vad'
                            WHERE word = ? AND primitive = 'GOOD' AND value != 1
                        """, (word,))
                        corrections_applied += conn.total_changes
                    # Strong negative valence
                    elif v <= -0.3:
                        conn.execute("""
                            UPDATE word_primitives
                            SET value = -1, confidence = 0.85, source = 'correction:nrc_vad'
                            WHERE word = ? AND primitive = 'GOOD' AND value != -1
                        """, (word,))
                        corrections_applied += conn.total_changes
                except ValueError:
                    pass

    # 3. Add missing primitives from ConceptNet
    conceptnet_path = external_dir / "conceptnet-en.sqlite"
    if conceptnet_path.exists():
        logger.info("Adding missing primitives from ConceptNet...")
        cn_conn = sqlite3.connect(str(conceptnet_path))

        # Get high-confidence IsA relations for KIND primitive
        cursor = cn_conn.execute("""
            SELECT DISTINCT start_word
            FROM edges
            WHERE relation = 'IsA' AND weight >= 2.0
        """)

        batch = []
        for (word,) in cursor:
            word = word.lower().replace('/c/en/', '').replace('_', ' ')
            batch.append((word, None, 'KIND', 1, 0.75, 'external:conceptnet'))

            if len(batch) >= 5000:
                conn.executemany("""
                    INSERT OR IGNORE INTO word_primitives
                    (word, pos, primitive, value, confidence, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, batch)
                corrections_applied += len(batch)
                batch = []

        if batch:
            conn.executemany("""
                INSERT OR IGNORE INTO word_primitives
                (word, pos, primitive, value, confidence, source)
                VALUES (?, ?, ?, ?, ?, ?)
            """, batch)
            corrections_applied += len(batch)

        cn_conn.close()

    # 4. Add missing primitives from Lancaster Sensorimotor
    sensorimotor_path = external_dir / "lancaster_sensorimotor.csv"
    if sensorimotor_path.exists():
        logger.info("Adding missing primitives from Lancaster Sensorimotor...")
        import csv

        MODALITY_PRIMS = {
            "Auditory": [("HEAR", 1)],
            "Visual": [("SEE", 1)],
            "Haptic": [("TOUCH", 1)],
            "Interoceptive": [("FEEL", 1), ("BODY", 1)],
            "Foot_leg": [("BODY", 1), ("MOVE", 1)],
            "Hand_arm": [("BODY", 1), ("DO", 1)],
            "Mouth": [("BODY", 1)],
        }

        with open(sensorimotor_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            batch = []
            for row in reader:
                word = row['Word'].lower()
                for modality, prims in MODALITY_PRIMS.items():
                    col = f"{modality}.mean"
                    if col in row:
                        try:
                            score = float(row[col])
                            if score >= 2.5:  # Match audit threshold for consistency
                                for prim, val in prims:
                                    batch.append((word, None, prim, val, 0.7, 'external:sensorimotor'))
                        except ValueError:
                            pass

                if len(batch) >= 5000:
                    conn.executemany("""
                        INSERT OR IGNORE INTO word_primitives
                        (word, pos, primitive, value, confidence, source)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, batch)
                    corrections_applied += len(batch)
                    batch = []

            if batch:
                conn.executemany("""
                    INSERT OR IGNORE INTO word_primitives
                    (word, pos, primitive, value, confidence, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, batch)
                corrections_applied += len(batch)

    conn.commit()

    # Get stats
    cursor = conn.execute("SELECT COUNT(DISTINCT word) FROM word_primitives")
    word_count = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM word_primitives")
    prim_count = cursor.fetchone()[0]

    logger.info("\nAfter external corrections:")
    logger.info(f"  Total words: {word_count:,}")
    logger.info(f"  Total assignments: {prim_count:,}")
    logger.info(f"  Corrections/additions applied: {corrections_applied:,}")

    conn.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Build Wiktionary Primitive Resolver")
    parser.add_argument('--download', action='store_true', help='Download Wiktionary data')
    parser.add_argument('--build', action='store_true', help='Build database')
    parser.add_argument('--all', action='store_true', help='Download and build')
    parser.add_argument('--test', action='store_true', help='Test the resolver')
    parser.add_argument('--migrate', action='store_true', help='Migrate to dictionary encoding (Phase 2)')
    parser.add_argument('--spread', action='store_true', help='Spread primitives through relations (Phase 3)')
    parser.add_argument('--correct', action='store_true', help='Apply external source corrections (Phase 4)')
    parser.add_argument('--full-pipeline', action='store_true', help='Run full pipeline: build, spread, correct, migrate')

    args = parser.parse_args()

    if args.full_pipeline:
        logger.info("=" * 60)
        logger.info("FULL PIPELINE: Build → Spread → Correct → Migrate")
        logger.info("=" * 60)

        # Phase 1: Build with enhanced extraction
        logger.info("\n[Phase 1] Building database with enhanced extraction...")
        if not build_database():
            sys.exit(1)

        # Phase 3: Spread primitives through relations
        logger.info("\n[Phase 3] Spreading primitives through semantic relations...")
        if not spread_primitives_through_relations(DB_PATH):
            sys.exit(1)

        # Phase 4: Apply external source corrections
        logger.info("\n[Phase 4] Applying external source corrections...")
        external_dir = BASE_DIR / "data" / "external"
        if not apply_external_corrections(DB_PATH, external_dir):
            sys.exit(1)

        # Phase 2: Migrate to dictionary encoding
        logger.info("\n[Phase 2] Migrating to dictionary-encoded format...")
        new_db_path = DATA_DIR / "wiktionary_primitives_v2.db"
        if not migrate_to_dictionary_encoding(DB_PATH, new_db_path):
            sys.exit(1)

        logger.info("\n" + "=" * 60)
        logger.info("FULL PIPELINE COMPLETE")
        logger.info("=" * 60)
        return

    if args.all or args.download:
        if not download_wiktionary():
            sys.exit(1)

    if args.all or args.build:
        if not build_database():
            sys.exit(1)

    if args.spread:
        if not spread_primitives_through_relations(DB_PATH):
            sys.exit(1)

    if args.correct:
        external_dir = BASE_DIR / "data" / "external"
        if not apply_external_corrections(DB_PATH, external_dir):
            sys.exit(1)

    if args.migrate:
        new_db_path = DATA_DIR / "wiktionary_primitives_v2.db"
        if not migrate_to_dictionary_encoding(DB_PATH, new_db_path):
            sys.exit(1)

    if args.test:
        if not test_resolver():
            sys.exit(1)

    if not any([args.download, args.build, args.all, args.test, args.migrate, args.spread, args.correct, args.full_pipeline]):
        parser.print_help()


if __name__ == "__main__":
    main()
