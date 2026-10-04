#!/usr/bin/env python3
"""
Fix Top 200 Word Decompositions
-------------------------------
Manually corrected decompositions for high-frequency words.
"""
import sqlite3
import json
import sys

sys.path.insert(0, '/Users/rohanvinaik/gse')
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import PrimitiveBasis
from gse.lexicon_generator import LexiconGenerator

DB_PATH = '/Users/rohanvinaik/gse/data/lexicon.db'

# Manual corrections for top 200 words
# Format: (lemma, pos): [(primitive, role), ...]
CORRECTIONS = {
    # Size/Quantity words - fix semantic inversions
    ("big", "ADJ"): [("BIG", "attribute"), ("MUCH", "quantity"), ("SOMETHING", "theme")],
    ("big", "NOUN"): [("BIG", "attribute"), ("MUCH", "quantity"), ("SOMETHING", "theme")],
    ("high", "ADJ"): [("MUCH", "quantity"), ("ABOVE", "location"), ("BE", "state")],
    ("high", "NOUN"): [("MUCH", "quantity"), ("ABOVE", "location"), ("SOMETHING", "theme")],
    ("great", "ADJ"): [("BIG", "attribute"), ("GOOD", "evaluation"), ("MUCH", "quantity")],
    ("great", "NOUN"): [("BIG", "attribute"), ("GOOD", "evaluation"), ("MUCH", "quantity")],
    ("full", "ADJ"): [("ALL", "quantity"), ("HAVE", "state"), ("SOMETHING", "theme")],
    ("full", "VERB"): [("ALL", "quantity"), ("HAVE", "result"), ("SOMETHING", "theme")],
    ("full", "NOUN"): [("ALL", "quantity"), ("HAVE", "state"), ("SOMETHING", "theme")],
    ("large", "ADJ"): [("BIG", "attribute"), ("MUCH", "quantity"), ("SOMETHING", "theme")],
    ("large", "NOUN"): [("BIG", "attribute"), ("MUCH", "quantity"), ("SOMETHING", "theme")],
    ("small", "ADJ"): [("SMALL", "attribute"), ("LITTLE", "quantity"), ("SOMETHING", "theme")],
    ("small", "NOUN"): [("SMALL", "attribute"), ("LITTLE", "quantity"), ("SOMETHING", "theme")],
    ("little", "ADJ"): [("SMALL", "attribute"), ("LITTLE", "quantity"), ("SOMETHING", "theme")],
    ("little", "ADV"): [("LITTLE", "quantity"), ("SMALL", "degree"), ("NOT", "evaluation")],
    ("little", "NOUN"): [("SMALL", "attribute"), ("LITTLE", "quantity"), ("SOMETHING", "theme")],
    ("low", "ADJ"): [("LITTLE", "quantity"), ("BELOW", "location"), ("BE", "state")],
    ("low", "NOUN"): [("LITTLE", "quantity"), ("BELOW", "location"), ("SOMETHING", "theme")],

    # Time words - fix insufficient decompositions
    ("often", "ADV"): [("MUCH", "frequency"), ("HAPPEN", "action"), ("LONG_TIME", "duration")],
    ("hour", "NOUN"): [("MOMENT", "duration"), ("PART", "attribute"), ("LONG_TIME", "theme")],
    ("early", "ADJ"): [("BEFORE", "time"), ("SHORT_TIME", "duration"), ("BE", "state")],
    ("early", "ADV"): [("BEFORE", "time"), ("SHORT_TIME", "duration"), ("NOW", "relation")],
    ("later", "ADV"): [("AFTER", "time"), ("LONG_TIME", "duration"), ("HAPPEN", "result")],
    ("recent", "ADJ"): [("BEFORE", "time"), ("SHORT_TIME", "duration"), ("NOW", "relation")],
    ("next", "ADJ"): [("AFTER", "time"), ("NEAR", "relation"), ("BE", "state")],

    # Quality/State words - fix single-primitive entries
    ("clear", "ADJ"): [("SEE", "evaluation"), ("GOOD", "attribute"), ("TRUE", "state")],
    ("clear", "VERB"): [("NOT", "result"), ("MOVE", "action"), ("SOMETHING", "theme")],
    ("first", "ADJ"): [("ONE", "quantity"), ("BEFORE", "time"), ("BE", "state")],
    ("first", "ADV"): [("ONE", "quantity"), ("BEFORE", "time"), ("NOW", "relation")],
    ("last", "ADJ"): [("ONE", "quantity"), ("AFTER", "time"), ("BE", "state")],
    ("back", "ADJ"): [("SIDE", "location"), ("OTHER", "attribute"), ("BE", "state")],
    ("whole", "ADJ"): [("ALL", "quantity"), ("ONE", "attribute"), ("BE", "state")],
    ("public", "ADJ"): [("PEOPLE", "theme"), ("ALL", "relation"), ("SEE", "evaluation")],
    ("local", "ADJ"): [("NEAR", "location"), ("HERE", "attribute"), ("BE", "state")],
    ("few", "ADJ"): [("LITTLE", "quantity"), ("SOME", "attribute"), ("BE", "state")],
    ("out", "ADJ"): [("SIDE", "location"), ("NOT", "attribute"), ("BE", "state")],
    ("kind", "ADJ"): [("GOOD", "evaluation"), ("FEEL", "manner"), ("SOMEONE", "attribute")],
    ("mean", "ADJ"): [("BAD", "evaluation"), ("FEEL", "manner"), ("SOMEONE", "attribute")],
    ("only", "ADJ"): [("ONE", "quantity"), ("NOT", "relation"), ("BE", "state")],

    # Verb fixes - add proper semantic content
    ("offer", "VERB"): [("DO", "action"), ("HAVE", "result"), ("SOMEONE", "recipient"), ("SOMETHING", "theme")],
    ("allow", "VERB"): [("DO", "action"), ("CAN", "result"), ("SOMEONE", "agent"), ("SOMEONE", "beneficiary")],
    ("let", "VERB"): [("DO", "action"), ("CAN", "result"), ("SOMEONE", "agent"), ("SOMEONE", "beneficiary")],
    ("better", "VERB"): [("DO", "action"), ("GOOD", "result"), ("MORE", "evaluation")],
    ("best", "VERB"): [("DO", "action"), ("GOOD", "result"), ("ALL", "evaluation")],
    ("stay", "VERB"): [("BE", "state"), ("SAME", "location"), ("LONG_TIME", "duration")],
    ("question", "VERB"): [("SAY", "action"), ("WANT", "intention"), ("KNOW", "goal"), ("SOMEONE", "agent")],
    ("eye", "VERB"): [("SEE", "action"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("own", "VERB"): [("HAVE", "state"), ("SOMEONE", "possessor"), ("SOMETHING", "theme")],
    ("wait", "VERB"): [("BE", "state"), ("LONG_TIME", "duration"), ("WANT", "intention"), ("SOMEONE", "agent")],
    ("expect", "VERB"): [("THINK", "action"), ("WANT", "intention"), ("SOMEONE", "experiencer"), ("HAPPEN", "content")],
    ("spend", "VERB"): [("DO", "action"), ("HAVE", "source"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("pay", "VERB"): [("DO", "action"), ("HAVE", "source"), ("SOMEONE", "agent"), ("SOMEONE", "recipient")],
    ("show", "VERB"): [("DO", "action"), ("SEE", "result"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("add", "VERB"): [("DO", "action"), ("MORE", "result"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("study", "VERB"): [("THINK", "action"), ("KNOW", "goal"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("school", "VERB"): [("KNOW", "goal"), ("SOMEONE", "patient"), ("DO", "action")],
    ("issue", "VERB"): [("DO", "action"), ("SAY", "manner"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("number", "VERB"): [("DO", "action"), ("ONE", "manner"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("room", "VERB"): [("BE", "location"), ("HAVE", "state"), ("SOMETHING", "theme")],

    # Noun fixes - add proper semantic content
    ("side", "NOUN"): [("PART", "theme"), ("WHERE", "location"), ("NEAR", "attribute")],
    ("friend", "NOUN"): [("SOMEONE", "theme"), ("GOOD", "evaluation"), ("FEEL", "relation"), ("KNOW", "state")],
    ("issue", "NOUN"): [("SOMETHING", "theme"), ("THINK", "content"), ("BAD", "evaluation")],
    ("service", "NOUN"): [("DO", "action"), ("GOOD", "goal"), ("SOMEONE", "beneficiary")],
    ("reach", "NOUN"): [("MOVE", "action"), ("FAR", "attribute"), ("CAN", "evaluation")],
    ("why", "NOUN"): [("BECAUSE", "theme"), ("WANT", "intention"), ("KNOW", "goal")],
    ("want", "NOUN"): [("WANT", "state"), ("HAVE", "goal"), ("SOMEONE", "experiencer")],
    ("need", "NOUN"): [("WANT", "state"), ("HAVE", "goal"), ("VERY", "evaluation")],
    ("point", "NOUN"): [("HERE", "location"), ("SMALL", "attribute"), ("SOMETHING", "theme")],

    # Person/Family words - enhance decompositions
    ("mother", "NOUN"): [("SOMEONE", "theme"), ("LIVE", "cause"), ("SOMEONE", "relation"), ("GOOD", "evaluation")],
    ("mother", "VERB"): [("DO", "action"), ("GOOD", "manner"), ("SOMEONE", "agent"), ("SOMEONE", "beneficiary")],
    ("father", "NOUN"): [("SOMEONE", "theme"), ("LIVE", "cause"), ("SOMEONE", "relation"), ("GOOD", "evaluation")],
    ("father", "VERB"): [("DO", "action"), ("LIVE", "cause"), ("SOMEONE", "agent")],
    ("human", "ADJ"): [("SOMEONE", "theme"), ("KIND", "attribute"), ("PEOPLE", "relation")],
    ("team", "NOUN"): [("PEOPLE", "theme"), ("SAME", "attribute"), ("DO", "goal")],

    # Time nouns
    ("night", "NOUN"): [("MOMENT", "theme"), ("NOT", "attribute"), ("SEE", "evaluation"), ("LONG_TIME", "duration")],

    # Spatial/Direction words
    ("down", "ADJ"): [("BELOW", "location"), ("SIDE", "aspect"), ("BE", "state")],
    ("home", "ADV"): [("WHERE", "location"), ("LIVE", "state"), ("GOOD", "evaluation")],

    # Very - fix semantics
    ("very", "ADV"): [("MORE", "quantity"), ("MUCH", "degree"), ("BE", "manner")],

    # Additional fixes for remaining words
    ("part", "VERB"): [("DO", "action"), ("MOVE", "result"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("side", "VERB"): [("DO", "action"), ("SAME", "manner"), ("SOMEONE", "agent")],
    ("later", "ADJ"): [("AFTER", "time"), ("BE", "state"), ("LONG_TIME", "duration")],
    ("then", "ADJ"): [("WHEN", "time"), ("AFTER", "relation"), ("BE", "state")],
    ("man", "VERB"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("happy", "ADJ"): [("FEEL", "state"), ("GOOD", "evaluation"), ("SOMEONE", "experiencer")],
    ("live", "VERB"): [("LIVE", "state"), ("EXIST", "result"), ("SOMEONE", "experiencer"), ("WHERE", "location")],
    ("up", "ADV"): [("ABOVE", "location"), ("MOVE", "manner"), ("BE", "state")],
    ("down", "ADV"): [("BELOW", "location"), ("MOVE", "manner"), ("BE", "state")],
    ("some", "DET"): [("SOME", "quantity"), ("PART", "attribute"), ("SOMETHING", "theme")],
    ("other", "ADJ"): [("OTHER", "attribute"), ("NOT", "relation"), ("SAME", "evaluation")],
    ("before", "ADV"): [("BEFORE", "time"), ("BE", "state"), ("NOT", "relation")],
    ("after", "ADV"): [("AFTER", "time"), ("BE", "state"), ("HAPPEN", "result")],
    ("book", "NOUN"): [("SOMETHING", "theme"), ("WORDS", "content"), ("KNOW", "goal")],
    ("old", "ADJ"): [("LONG_TIME", "duration"), ("BEFORE", "time"), ("BE", "state")],
    ("old", "NOUN"): [("LONG_TIME", "duration"), ("BEFORE", "time"), ("SOMEONE", "theme")],
    ("many", "DET"): [("MUCH", "quantity"), ("MORE", "attribute"), ("SOMETHING", "theme")],
    ("much", "ADV"): [("MUCH", "quantity"), ("MORE", "degree"), ("BE", "manner")],
    ("right", "ADJ"): [("GOOD", "evaluation"), ("TRUE", "attribute"), ("BE", "state")],
    ("game", "NOUN"): [("DO", "action"), ("GOOD", "goal"), ("FEEL", "manner")],
    ("wait", "NOUN"): [("BE", "state"), ("LONG_TIME", "duration"), ("WANT", "intention")],
    ("young", "ADJ"): [("SHORT_TIME", "duration"), ("NOW", "time"), ("LIVE", "state")],
    ("young", "NOUN"): [("SHORT_TIME", "duration"), ("NOW", "time"), ("SOMEONE", "theme")],
    ("offer", "NOUN"): [("SAY", "action"), ("HAVE", "result"), ("SOMETHING", "theme")],
    ("here", "NOUN"): [("HERE", "location"), ("NOW", "time"), ("BE", "state")],
    ("there", "NOUN"): [("FAR", "location"), ("OTHER", "attribute"), ("BE", "state")],
    ("possible", "ADJ"): [("CAN", "evaluation"), ("MAYBE", "manner"), ("BE", "state")],
    ("possible", "NOUN"): [("CAN", "evaluation"), ("MAYBE", "manner"), ("SOMETHING", "theme")],
    ("have", "NOUN"): [("HAVE", "state"), ("SOMETHING", "theme"), ("SOMEONE", "possessor")],
    ("ready", "NOUN"): [("BE", "state"), ("NOW", "time"), ("CAN", "evaluation")],
    ("now", "NOUN"): [("NOW", "time"), ("HERE", "location"), ("BE", "state")],

    # Function words - prepositions, conjunctions, determiners
    ("to", "ADP"): [("BE", "location"), ("MOVE", "goal"), ("WHERE", "path")],
    ("for", "ADP"): [("BE", "location"), ("SOMEONE", "beneficiary"), ("BECAUSE", "cause")],
    ("from", "ADP"): [("BE", "location"), ("MOVE", "source"), ("WHERE", "location")],
    ("in", "ADP"): [("INSIDE", "location"), ("BE", "state"), ("WHERE", "location")],
    ("on", "ADP"): [("ABOVE", "location"), ("TOUCH", "relation"), ("BE", "state")],
    ("at", "ADP"): [("HERE", "location"), ("BE", "state"), ("WHERE", "location")],
    ("with", "ADP"): [("SAME", "location"), ("HAVE", "manner"), ("BE", "relation")],
    ("by", "ADP"): [("NEAR", "location"), ("BECAUSE", "cause"), ("SOMEONE", "agent")],
    ("they", "PRON"): [("SOMEONE", "patient"), ("PEOPLE", "theme"), ("OTHER", "attribute")],
    ("how", "ADV"): [("SEE", "evaluation"), ("SOMEONE", "experiencer"), ("DO", "manner")],
    ("when", "CONJ"): [("BE", "time"), ("HAPPEN", "result"), ("MOMENT", "duration")],
    ("where", "CONJ"): [("WHERE", "location"), ("BE", "state"), ("HERE", "theme")],
    ("my", "DET"): [("I", "possessor"), ("HAVE", "state"), ("THIS", "theme")],
    ("so", "ADV"): [("BECAUSE", "cause"), ("MUCH", "degree"), ("BE", "manner")],
    ("because", "CONJ"): [("BECAUSE", "cause"), ("HAPPEN", "result"), ("TRUE", "relation")],
    ("any", "DET"): [("SOME", "quantity"), ("ALL", "relation"), ("SOMETHING", "theme")],
    ("then", "ADV"): [("AFTER", "time"), ("HAPPEN", "result"), ("NOW", "relation")],
    ("most", "ADV"): [("MUCH", "quantity"), ("ALL", "relation"), ("MORE", "evaluation")],

    # Common nouns that need fixing
    ("example", "NOUN"): [("SOMETHING", "theme"), ("SEE", "goal"), ("KNOW", "manner")],
    ("state", "NOUN"): [("BE", "state"), ("SOMETHING", "theme"), ("WHERE", "location")],
    ("people", "NOUN"): [("SOMEONE", "theme"), ("PEOPLE", "attribute"), ("LIVE", "state")],
    ("network", "NOUN"): [("BE", "location"), ("HAVE", "attribute"), ("PART", "theme")],
    ("networks", "NOUN"): [("BE", "location"), ("HAVE", "attribute"), ("PART", "theme")],
    ("framework", "NOUN"): [("SOMETHING", "theme"), ("BE", "state"), ("PART", "attribute")],
    ("constraint", "NOUN"): [("NOT", "evaluation"), ("DO", "theme"), ("BE", "state")],
    ("use", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("know", "NOUN"): [("THINK", "content"), ("KNOW", "state"), ("SOMEONE", "experiencer")],
    ("feel", "NOUN"): [("FEEL", "state"), ("SOMETHING", "theme"), ("SOMEONE", "experiencer")],
    ("way", "NOUN"): [("MOVE", "path"), ("DO", "manner"), ("SOMETHING", "theme")],
    ("see", "NOUN"): [("SEE", "action"), ("SOMETHING", "theme"), ("SOMEONE", "experiencer")],
    ("core", "NOUN"): [("INSIDE", "location"), ("PART", "attribute"), ("BE", "theme")],
    ("rules", "NOUN"): [("BE", "state"), ("SOMEONE", "agent"), ("DO", "theme")],
    ("form", "NOUN"): [("BE", "attribute"), ("SOMETHING", "theme"), ("SEE", "manner")],
    ("good", "NOUN"): [("GOOD", "evaluation"), ("SOMETHING", "theme"), ("WANT", "goal")],
    ("make", "NOUN"): [("DO", "action"), ("EXIST", "result"), ("SOMETHING", "theme")],
    ("things", "NOUN"): [("SOMETHING", "theme"), ("EXIST", "state"), ("BE", "attribute")],
    ("control", "NOUN"): [("DO", "action"), ("HAVE", "result"), ("SOMEONE", "agent")],
    ("zero", "NOUN"): [("NOT", "quantity"), ("EXIST", "state"), ("SOMETHING", "theme")],
    ("set", "NOUN"): [("SOMETHING", "theme"), ("SAME", "attribute"), ("HAVE", "state")],
    ("others", "NOUN"): [("SOMEONE", "theme"), ("OTHER", "attribute"), ("NOT", "relation")],
    ("intelligence", "NOUN"): [("THINK", "content"), ("KNOW", "state"), ("GOOD", "evaluation")],
    ("verification", "NOUN"): [("SEE", "action"), ("TRUE", "goal"), ("KNOW", "result")],
    ("first", "NOUN"): [("ONE", "quantity"), ("BEFORE", "time"), ("BE", "theme")],
    ("entropy", "NOUN"): [("BE", "state"), ("MOVE", "action"), ("NOT", "evaluation")],
    ("digital", "NOUN"): [("SOMETHING", "theme"), ("ONE", "attribute"), ("BE", "state")],

    # Common verbs
    ("could", "VERB"): [("CAN", "evaluation"), ("MAYBE", "manner"), ("DO", "action")],
    ("based", "VERB"): [("BE", "attribute"), ("HAVE", "source"), ("SOMETHING", "theme")],
    ("using", "VERB"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "instrument")],

    # More content words
    ("information", "NOUN"): [("KNOW", "content"), ("SOMETHING", "theme"), ("WORDS", "manner")],
    ("system", "NOUN"): [("SOMETHING", "theme"), ("PART", "attribute"), ("DO", "goal")],
    ("data", "NOUN"): [("SOMETHING", "theme"), ("KNOW", "content"), ("HAVE", "state")],
    ("model", "NOUN"): [("SOMETHING", "theme"), ("LIKE", "attribute"), ("SEE", "goal")],
    ("time", "NOUN"): [("MOMENT", "theme"), ("LONG_TIME", "duration"), ("BE", "state")],
    ("space", "NOUN"): [("WHERE", "theme"), ("BE", "location"), ("EXIST", "state")],
    ("problem", "NOUN"): [("SOMETHING", "theme"), ("BAD", "evaluation"), ("THINK", "goal")],
    ("process", "NOUN"): [("DO", "action"), ("MOVE", "manner"), ("SOMETHING", "theme")],
    ("structure", "NOUN"): [("SOMETHING", "theme"), ("PART", "attribute"), ("BE", "state")],
    ("value", "NOUN"): [("SOMETHING", "theme"), ("GOOD", "evaluation"), ("HAVE", "state")],
    ("level", "NOUN"): [("PART", "theme"), ("ABOVE", "attribute"), ("BE", "location")],
    ("result", "NOUN"): [("SOMETHING", "theme"), ("HAPPEN", "cause"), ("BE", "result")],
    ("case", "NOUN"): [("SOMETHING", "theme"), ("HAPPEN", "manner"), ("BE", "state")],
    ("number", "NOUN"): [("SOMETHING", "theme"), ("ONE", "attribute"), ("MUCH", "quantity")],
    ("world", "NOUN"): [("WHERE", "theme"), ("ALL", "attribute"), ("EXIST", "location")],
    ("question", "NOUN"): [("SAY", "theme"), ("WANT", "intention"), ("KNOW", "goal")],
    ("life", "NOUN"): [("LIVE", "state"), ("EXIST", "result"), ("SOMEONE", "experiencer")],
    ("work", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "goal")],
    ("fact", "NOUN"): [("SOMETHING", "theme"), ("TRUE", "evaluation"), ("EXIST", "state")],
    ("idea", "NOUN"): [("THINK", "content"), ("SOMETHING", "theme"), ("KNOW", "state")],
    ("experience", "NOUN"): [("FEEL", "state"), ("SOMETHING", "content"), ("SOMEONE", "experiencer")],
    ("knowledge", "NOUN"): [("KNOW", "state"), ("SOMETHING", "content"), ("THINK", "action")],
    ("meaning", "NOUN"): [("BE", "theme"), ("THINK", "content"), ("KNOW", "goal")],
    ("truth", "NOUN"): [("TRUE", "evaluation"), ("SOMETHING", "theme"), ("KNOW", "goal")],
    ("reason", "NOUN"): [("BECAUSE", "theme"), ("THINK", "content"), ("KNOW", "goal")],
    ("power", "NOUN"): [("DO", "action"), ("CAN", "attribute"), ("HAVE", "state")],
    ("change", "NOUN"): [("MOVE", "action"), ("OTHER", "result"), ("BE", "state")],
    ("order", "NOUN"): [("BE", "state"), ("PART", "attribute"), ("SAME", "manner")],
    ("nature", "NOUN"): [("BE", "state"), ("EXIST", "attribute"), ("SOMETHING", "theme")],
    ("action", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("end", "NOUN"): [("AFTER", "time"), ("NOT", "result"), ("BE", "location")],
    ("mind", "NOUN"): [("THINK", "location"), ("SOMEONE", "possessor"), ("KNOW", "state")],
    ("place", "NOUN"): [("WHERE", "location"), ("BE", "state"), ("SOMETHING", "theme")],
    ("history", "NOUN"): [("BEFORE", "time"), ("HAPPEN", "content"), ("KNOW", "theme")],
    ("future", "NOUN"): [("AFTER", "time"), ("HAPPEN", "content"), ("MAYBE", "evaluation")],
    ("present", "NOUN"): [("NOW", "time"), ("HERE", "location"), ("BE", "state")],

    # More words 500-1000 range needing fixes
    ("after", "NOUN"): [("AFTER", "time"), ("HAPPEN", "result"), ("BE", "state")],
    ("agents", "NOUN"): [("SOMEONE", "theme"), ("DO", "action"), ("THINK", "manner")],
    ("context", "NOUN"): [("BE", "state"), ("WHERE", "location"), ("SOMETHING", "theme")],
    ("itself", "NOUN"): [("SAME", "attribute"), ("THIS", "theme"), ("BE", "state")],
    ("decision", "NOUN"): [("THINK", "action"), ("DO", "result"), ("SOMEONE", "agent")],
    ("long", "NOUN"): [("LONG_TIME", "duration"), ("MUCH", "quantity"), ("BE", "attribute")],
    ("node", "NOUN"): [("PART", "theme"), ("BE", "location"), ("SOMETHING", "attribute")],
    ("cognitive", "ADJ"): [("THINK", "content"), ("KNOW", "state"), ("SOMEONE", "experiencer")],
    ("nodes", "NOUN"): [("PART", "theme"), ("BE", "location"), ("SOMETHING", "attribute")],
    ("someone", "NOUN"): [("SOMEONE", "theme"), ("EXIST", "state"), ("BE", "attribute")],
    ("approaches", "NOUN"): [("DO", "action"), ("MOVE", "manner"), ("SOMETHING", "theme")],
    ("include", "NOUN"): [("HAVE", "state"), ("PART", "attribute"), ("SOMETHING", "theme")],
    ("makes", "NOUN"): [("DO", "action"), ("EXIST", "result"), ("SOMEONE", "agent")],
    ("instance", "NOUN"): [("SOMETHING", "theme"), ("ONE", "attribute"), ("BE", "state")],
    ("weights", "NOUN"): [("SOMETHING", "theme"), ("MUCH", "attribute"), ("HAVE", "state")],
    ("agent", "NOUN"): [("SOMEONE", "theme"), ("DO", "action"), ("THINK", "manner")],
    ("bit", "NOUN"): [("PART", "theme"), ("SMALL", "attribute"), ("ONE", "quantity")],
    ("maybe", "NOUN"): [("MAYBE", "evaluation"), ("BE", "state"), ("IF", "relation")],
    ("signal", "NOUN"): [("SOMETHING", "theme"), ("MOVE", "action"), ("KNOW", "goal")],
    ("feedback", "NOUN"): [("SOMETHING", "theme"), ("MOVE", "source"), ("BECAUSE", "cause")],
    ("symbols", "NOUN"): [("SOMETHING", "theme"), ("WORDS", "attribute"), ("SEE", "manner")],
    ("evolution", "NOUN"): [("MOVE", "action"), ("LONG_TIME", "duration"), ("LIVE", "state")],
    ("before", "NOUN"): [("BEFORE", "time"), ("BE", "state"), ("OTHER", "location")],
    ("given", "NOUN"): [("HAVE", "result"), ("SOMEONE", "recipient"), ("SOMETHING", "theme")],
    ("computer", "NOUN"): [("SOMETHING", "theme"), ("THINK", "action"), ("DO", "manner")],
    ("emerges", "NOUN"): [("EXIST", "result"), ("MOVE", "manner"), ("BE", "state")],
    ("implementation", "NOUN"): [("DO", "action"), ("EXIST", "result"), ("SOMETHING", "theme")],
    ("goal", "NOUN"): [("WANT", "content"), ("DO", "goal"), ("SOMEONE", "experiencer")],
    ("task", "NOUN"): [("DO", "action"), ("SOMETHING", "theme"), ("WANT", "goal")],
    ("toward", "NOUN"): [("MOVE", "goal"), ("NEAR", "location"), ("BE", "state")],
    ("goals", "NOUN"): [("WANT", "content"), ("DO", "goal"), ("SOMEONE", "experiencer")],
    ("formal", "NOUN"): [("BE", "attribute"), ("SAME", "manner"), ("TRUE", "evaluation")],
    ("important", "NOUN"): [("GOOD", "evaluation"), ("MUCH", "degree"), ("BE", "attribute")],
    ("operations", "NOUN"): [("DO", "action"), ("SOMETHING", "theme"), ("SOMEONE", "agent")],
    ("uses", "NOUN"): [("DO", "action"), ("SOMETHING", "instrument"), ("SOMEONE", "agent")],
    ("output", "NOUN"): [("SOMETHING", "theme"), ("MOVE", "result"), ("EXIST", "state")],
    ("emergent", "NOUN"): [("EXIST", "result"), ("MOVE", "manner"), ("BE", "attribute")],
    ("neurons", "NOUN"): [("PART", "theme"), ("THINK", "location"), ("BODY", "attribute")],
    ("act", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("during", "VERB"): [("BE", "time"), ("LONG_TIME", "duration"), ("SAME", "relation")],
    ("becomes", "NOUN"): [("BE", "result"), ("MOVE", "manner"), ("OTHER", "state")],
    ("years", "NOUN"): [("LONG_TIME", "duration"), ("MOMENT", "attribute"), ("MUCH", "quantity")],
    ("doing", "VERB"): [("DO", "action"), ("SOMEONE", "agent"), ("NOW", "time")],
    ("zeros", "NOUN"): [("NOT", "quantity"), ("SOMETHING", "theme"), ("BE", "state")],
    ("explicit", "NOUN"): [("SEE", "evaluation"), ("WORDS", "manner"), ("TRUE", "attribute")],
    ("together", "NOUN"): [("SAME", "location"), ("BE", "state"), ("PEOPLE", "relation")],
    ("humans", "NOUN"): [("SOMEONE", "theme"), ("PEOPLE", "attribute"), ("LIVE", "state")],
    ("achieve", "NOUN"): [("DO", "action"), ("GOOD", "result"), ("WANT", "goal")],
    ("examples", "NOUN"): [("SOMETHING", "theme"), ("SEE", "goal"), ("KNOW", "manner")],
    ("flow", "NOUN"): [("MOVE", "action"), ("SOMETHING", "theme"), ("WHERE", "path")],
    ("architectures", "NOUN"): [("SOMETHING", "theme"), ("PART", "attribute"), ("BE", "state")],
    ("adaptation", "NOUN"): [("MOVE", "action"), ("OTHER", "result"), ("BE", "manner")],
    ("she", "PRON"): [("SOMEONE", "theme"), ("OTHER", "attribute"), ("BE", "state")],
    ("terms", "NOUN"): [("WORDS", "theme"), ("SAY", "manner"), ("KNOW", "content")],
    ("points", "NOUN"): [("SOMETHING", "theme"), ("HERE", "location"), ("SMALL", "attribute")],
    ("mental", "NOUN"): [("THINK", "attribute"), ("FEEL", "content"), ("SOMEONE", "experiencer")],
    ("run", "NOUN"): [("MOVE", "action"), ("SOMEONE", "agent"), ("DO", "manner")],
    ("preserving", "VERB"): [("HAVE", "state"), ("SAME", "attribute"), ("LONG_TIME", "duration")],
    ("testing", "VERB"): [("DO", "action"), ("SEE", "goal"), ("TRUE", "evaluation")],
    ("back", "NOUN"): [("SIDE", "location"), ("OTHER", "attribute"), ("BE", "state")],
    ("stage", "NOUN"): [("PART", "theme"), ("WHERE", "location"), ("DO", "goal")],
    ("vectors", "NOUN"): [("SOMETHING", "theme"), ("MOVE", "attribute"), ("PART", "manner")],
    ("parameters", "NOUN"): [("SOMETHING", "theme"), ("PART", "attribute"), ("HAVE", "state")],
    ("safety", "NOUN"): [("GOOD", "evaluation"), ("NOT", "relation"), ("BAD", "goal")],
    ("minimal", "NOUN"): [("LITTLE", "quantity"), ("SMALL", "attribute"), ("BE", "state")],
    ("governance", "NOUN"): [("DO", "action"), ("PEOPLE", "theme"), ("SOMEONE", "agent")],
    ("made", "NOUN"): [("DO", "action"), ("EXIST", "result"), ("SOMEONE", "agent")],
    ("works", "NOUN"): [("DO", "action"), ("GOOD", "result"), ("SOMETHING", "theme")],
    ("mode", "NOUN"): [("BE", "state"), ("KIND", "attribute"), ("DO", "manner")],
    ("complete", "NOUN"): [("ALL", "quantity"), ("BE", "state"), ("EXIST", "result")],
    ("themselves", "NOUN"): [("SAME", "theme"), ("SOMEONE", "relation"), ("BE", "state")],
    ("remains", "NOUN"): [("BE", "state"), ("SAME", "attribute"), ("LONG_TIME", "duration")],
    ("encode", "NOUN"): [("DO", "action"), ("WORDS", "result"), ("SOMETHING", "theme")],
    ("robot", "NOUN"): [("SOMETHING", "theme"), ("DO", "action"), ("MOVE", "manner")],
    ("term", "NOUN"): [("WORDS", "theme"), ("SAY", "manner"), ("MOMENT", "duration")],
    ("artificial", "NOUN"): [("SOMETHING", "theme"), ("NOT", "attribute"), ("LIVE", "evaluation")],
    ("scales", "NOUN"): [("PART", "theme"), ("MUCH", "attribute"), ("BE", "state")],
    ("completely", "ADV"): [("ALL", "quantity"), ("BE", "manner"), ("SAME", "degree")],
    ("general", "NOUN"): [("ALL", "attribute"), ("SAME", "relation"), ("BE", "state")],
    ("ways", "NOUN"): [("DO", "manner"), ("MOVE", "path"), ("SOMETHING", "theme")],
    ("base", "NOUN"): [("PART", "theme"), ("BELOW", "location"), ("BE", "attribute")],
    ("feature", "NOUN"): [("PART", "theme"), ("SEE", "attribute"), ("HAVE", "state")],
    ("three", "NOUN"): [("ONE", "quantity"), ("TWO", "relation"), ("MORE", "attribute")],
    ("impact", "NOUN"): [("DO", "action"), ("TOUCH", "manner"), ("BE", "result")],
    ("actions", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("remain", "NOUN"): [("BE", "state"), ("SAME", "attribute"), ("LONG_TIME", "duration")],
    ("matrix", "NOUN"): [("SOMETHING", "theme"), ("PART", "attribute"), ("HAVE", "state")],

    # Words 1000-1500 range
    ("protocol", "NOUN"): [("DO", "action"), ("SAME", "manner"), ("SOMEONE", "agent")],
    ("higher", "NOUN"): [("ABOVE", "location"), ("MORE", "quantity"), ("BE", "attribute")],
    ("thus", "NOUN"): [("BECAUSE", "cause"), ("BE", "state"), ("SAME", "result")],
    ("expected", "VERB"): [("THINK", "action"), ("WANT", "intention"), ("HAPPEN", "content")],
    ("validation", "NOUN"): [("SEE", "action"), ("TRUE", "goal"), ("KNOW", "result")],
    ("engineering", "VERB"): [("DO", "action"), ("SOMETHING", "theme"), ("THINK", "manner")],
    ("explicitly", "ADV"): [("SEE", "evaluation"), ("WORDS", "manner"), ("TRUE", "attribute")],
    ("whether", "NOUN"): [("IF", "relation"), ("BE", "state"), ("MAYBE", "evaluation")],
    ("reference", "NOUN"): [("SOMETHING", "theme"), ("SEE", "goal"), ("KNOW", "manner")],
    ("metrics", "NOUN"): [("SOMETHING", "theme"), ("MUCH", "attribute"), ("SEE", "manner")],
    ("frame", "NOUN"): [("PART", "theme"), ("SIDE", "location"), ("BE", "attribute")],
    ("show", "NOUN"): [("DO", "action"), ("SEE", "result"), ("SOMEONE", "agent")],
    ("reduce", "NOUN"): [("DO", "action"), ("LITTLE", "result"), ("SOMETHING", "theme")],
    ("linear", "NOUN"): [("MOVE", "path"), ("SAME", "attribute"), ("BE", "manner")],
    ("api", "NOUN"): [("SOMETHING", "theme"), ("DO", "manner"), ("WORDS", "attribute")],
    ("security", "NOUN"): [("BE", "state"), ("GOOD", "evaluation"), ("NOT", "relation")],
    ("property", "NOUN"): [("HAVE", "state"), ("SOMETHING", "theme"), ("BE", "attribute")],
    ("emerge", "NOUN"): [("EXIST", "result"), ("MOVE", "manner"), ("BE", "state")],
    ("universal", "NOUN"): [("ALL", "attribute"), ("SAME", "relation"), ("BE", "state")],
    ("technical", "NOUN"): [("KNOW", "attribute"), ("DO", "manner"), ("SOMETHING", "theme")],
    ("ever", "NOUN"): [("LONG_TIME", "duration"), ("ALL", "time"), ("BE", "state")],
    ("source", "NOUN"): [("WHERE", "location"), ("MOVE", "source"), ("HAVE", "state")],
    ("role", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("BE", "attribute")],
    ("requiring", "VERB"): [("WANT", "state"), ("HAVE", "goal"), ("VERY", "evaluation")],
    ("spaces", "NOUN"): [("WHERE", "location"), ("BE", "state"), ("EXIST", "attribute")],
    ("write", "NOUN"): [("DO", "action"), ("WORDS", "result"), ("SOMEONE", "agent")],
    ("constrained", "VERB"): [("NOT", "evaluation"), ("DO", "action"), ("CAN", "manner")],
    ("style", "NOUN"): [("DO", "manner"), ("SEE", "attribute"), ("BE", "state")],
    ("times", "NOUN"): [("MOMENT", "theme"), ("HAPPEN", "result"), ("MUCH", "quantity")],
    ("domains", "NOUN"): [("WHERE", "location"), ("PART", "attribute"), ("BE", "state")],
    ("demonstrates", "NOUN"): [("DO", "action"), ("SEE", "result"), ("SOMETHING", "theme")],
    ("adapt", "NOUN"): [("MOVE", "action"), ("OTHER", "result"), ("BE", "manner")],
    ("initial", "NOUN"): [("BEFORE", "time"), ("ONE", "quantity"), ("BE", "state")],
    ("temporal", "NOUN"): [("MOMENT", "attribute"), ("WHEN", "time"), ("BE", "state")],
    ("done", "NOUN"): [("DO", "action"), ("AFTER", "time"), ("BE", "result")],
    ("classification", "NOUN"): [("THINK", "action"), ("KIND", "result"), ("SOMETHING", "theme")],
    ("potentially", "ADV"): [("CAN", "evaluation"), ("MAYBE", "manner"), ("BE", "state")],
    ("residual", "NOUN"): [("PART", "theme"), ("AFTER", "time"), ("BE", "attribute")],
    ("yourself", "NOUN"): [("YOU", "theme"), ("SAME", "attribute"), ("BE", "state")],
    ("highly", "ADV"): [("MUCH", "degree"), ("GOOD", "evaluation"), ("BE", "manner")],
    ("sufficient", "NOUN"): [("MUCH", "quantity"), ("GOOD", "evaluation"), ("BE", "state")],
    ("reveals", "NOUN"): [("SEE", "result"), ("SOMETHING", "theme"), ("KNOW", "goal")],
    ("threshold", "NOUN"): [("PART", "location"), ("SIDE", "attribute"), ("BE", "state")],
    ("persistent", "NOUN"): [("LONG_TIME", "duration"), ("SAME", "attribute"), ("BE", "state")],
    ("built", "NOUN"): [("DO", "action"), ("EXIST", "result"), ("SOMETHING", "theme")],
    ("short", "NOUN"): [("SHORT_TIME", "duration"), ("LITTLE", "quantity"), ("BE", "attribute")],
    ("codes", "NOUN"): [("WORDS", "theme"), ("SOMETHING", "attribute"), ("DO", "manner")],
    ("sequence", "NOUN"): [("PART", "theme"), ("AFTER", "relation"), ("BE", "state")],
    ("typically", "ADV"): [("SAME", "manner"), ("MUCH", "frequency"), ("BE", "state")],
    ("routine", "NOUN"): [("DO", "action"), ("SAME", "manner"), ("LONG_TIME", "duration")],
    ("speed", "VERB"): [("MOVE", "action"), ("MUCH", "manner"), ("DO", "result")],
    ("ones", "NOUN"): [("SOMETHING", "theme"), ("ONE", "quantity"), ("BE", "state")],
    ("facts", "NOUN"): [("SOMETHING", "theme"), ("TRUE", "evaluation"), ("EXIST", "state")],
    ("operation", "NOUN"): [("DO", "action"), ("SOMETHING", "theme"), ("SOMEONE", "agent")],
    ("formation", "NOUN"): [("EXIST", "result"), ("DO", "action"), ("SOMETHING", "theme")],
    ("fit", "NOUN"): [("SAME", "attribute"), ("BE", "state"), ("GOOD", "evaluation")],
    ("offers", "NOUN"): [("DO", "action"), ("HAVE", "result"), ("SOMEONE", "recipient")],
    ("simulation", "NOUN"): [("DO", "action"), ("LIKE", "manner"), ("SOMETHING", "theme")],
    ("chemical", "NOUN"): [("SOMETHING", "theme"), ("PART", "attribute"), ("MOVE", "action")],
    ("due", "NOUN"): [("BECAUSE", "cause"), ("BE", "state"), ("HAPPEN", "result")],
    ("interpretability", "NOUN"): [("KNOW", "goal"), ("SEE", "manner"), ("THINK", "content")],
    ("effect", "NOUN"): [("HAPPEN", "result"), ("BECAUSE", "cause"), ("BE", "state")],
    ("generation", "NOUN"): [("DO", "action"), ("EXIST", "result"), ("SOMETHING", "theme")],
    ("including", "VERB"): [("HAVE", "state"), ("PART", "attribute"), ("SOMETHING", "theme")],
    ("operates", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "instrument")],
    ("developmental", "NOUN"): [("MOVE", "action"), ("LONG_TIME", "duration"), ("LIVE", "state")],
    ("minimization", "NOUN"): [("DO", "action"), ("LITTLE", "result"), ("SOMETHING", "theme")],
    ("filter", "NOUN"): [("DO", "action"), ("PART", "result"), ("SOMETHING", "theme")],
    ("put", "NOUN"): [("DO", "action"), ("WHERE", "goal"), ("SOMETHING", "theme")],
    ("choice", "NOUN"): [("THINK", "action"), ("DO", "result"), ("SOMEONE", "agent")],
    ("match", "NOUN"): [("SAME", "attribute"), ("BE", "state"), ("SOMETHING", "theme")],
    ("essential", "NOUN"): [("WANT", "evaluation"), ("MUCH", "degree"), ("BE", "attribute")],
    ("evolving", "VERB"): [("MOVE", "action"), ("LONG_TIME", "duration"), ("OTHER", "result")],
    ("operate", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "instrument")],
    ("checks", "NOUN"): [("SEE", "action"), ("TRUE", "goal"), ("DO", "manner")],
    ("exact", "NOUN"): [("SAME", "attribute"), ("TRUE", "evaluation"), ("BE", "state")],
    ("alphabet", "NOUN"): [("WORDS", "theme"), ("PART", "attribute"), ("SOMETHING", "content")],
    ("study", "NOUN"): [("THINK", "action"), ("KNOW", "goal"), ("SOMETHING", "theme")],
    ("call", "NOUN"): [("SAY", "action"), ("SOMEONE", "agent"), ("WORDS", "instrument")],
    ("layer", "NOUN"): [("PART", "theme"), ("ABOVE", "location"), ("BE", "attribute")],
    ("static", "NOUN"): [("SAME", "attribute"), ("NOT", "action"), ("BE", "state")],
    ("individuals", "NOUN"): [("SOMEONE", "theme"), ("ONE", "attribute"), ("BE", "state")],
    ("face", "NOUN"): [("PART", "theme"), ("BODY", "attribute"), ("SEE", "location")],
    ("worth", "NOUN"): [("GOOD", "evaluation"), ("HAVE", "state"), ("SOMETHING", "theme")],
    ("coding", "VERB"): [("DO", "action"), ("WORDS", "result"), ("SOMEONE", "agent")],
    ("writing", "VERB"): [("DO", "action"), ("WORDS", "result"), ("SOMEONE", "agent")],
    ("neuron", "NOUN"): [("PART", "theme"), ("THINK", "location"), ("BODY", "attribute")],
    ("matters", "NOUN"): [("SOMETHING", "theme"), ("GOOD", "evaluation"), ("BE", "state")],
    ("bad", "NOUN"): [("BAD", "evaluation"), ("SOMETHING", "theme"), ("FEEL", "state")],
    ("forms", "NOUN"): [("SOMETHING", "theme"), ("SEE", "attribute"), ("BE", "state")],
    ("configuration", "NOUN"): [("PART", "theme"), ("SAME", "attribute"), ("BE", "state")],
    ("factors", "NOUN"): [("SOMETHING", "theme"), ("BECAUSE", "cause"), ("BE", "state")],

    # Words 1500-2000 range
    ("exhibit", "NOUN"): [("SEE", "action"), ("SOMETHING", "theme"), ("DO", "manner")],
    ("bound", "NOUN"): [("PART", "location"), ("SIDE", "attribute"), ("BE", "state")],
    ("associative", "ADJ"): [("SAME", "relation"), ("THINK", "manner"), ("BE", "attribute")],
    ("allowing", "VERB"): [("DO", "action"), ("CAN", "result"), ("SOMEONE", "beneficiary")],
    ("terminator", "NOUN"): [("DO", "action"), ("NOT", "result"), ("SOMETHING", "theme")],
    ("cognition", "NOUN"): [("THINK", "action"), ("KNOW", "state"), ("SOMEONE", "experiencer")],
    ("detection", "NOUN"): [("SEE", "action"), ("KNOW", "result"), ("SOMETHING", "theme")],
    ("modern", "NOUN"): [("NOW", "time"), ("BE", "state"), ("OTHER", "attribute")],
    ("enable", "ADJ"): [("DO", "action"), ("CAN", "result"), ("SOMEONE", "agent")],
    ("profound", "NOUN"): [("MUCH", "degree"), ("FEEL", "state"), ("GOOD", "evaluation")],
    ("platform", "NOUN"): [("WHERE", "location"), ("DO", "goal"), ("BE", "state")],
    ("won", "NOUN"): [("DO", "action"), ("GOOD", "result"), ("SOMEONE", "agent")],
    ("conclusion", "NOUN"): [("AFTER", "time"), ("THINK", "result"), ("BE", "state")],
    ("perform", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("SOMETHING", "theme")],
    ("differential", "NOUN"): [("OTHER", "attribute"), ("PART", "relation"), ("BE", "state")],
    ("program", "NOUN"): [("DO", "action"), ("WORDS", "content"), ("SOMETHING", "theme")],
    ("capture", "NOUN"): [("DO", "action"), ("HAVE", "result"), ("SOMETHING", "theme")],
    ("demonstrate", "NOUN"): [("DO", "action"), ("SEE", "result"), ("SOMETHING", "theme")],
    ("experimental", "NOUN"): [("DO", "action"), ("SEE", "goal"), ("KNOW", "result")],
    ("solvers", "NOUN"): [("SOMEONE", "theme"), ("THINK", "action"), ("DO", "manner")],
    ("routines", "NOUN"): [("DO", "action"), ("SAME", "manner"), ("LONG_TIME", "duration")],
    ("culture", "NOUN"): [("PEOPLE", "theme"), ("SAME", "attribute"), ("LIVE", "state")],
    ("trajectory", "NOUN"): [("MOVE", "path"), ("WHERE", "location"), ("BE", "state")],
    ("minimize", "NOUN"): [("DO", "action"), ("LITTLE", "result"), ("SOMETHING", "theme")],
    ("larger", "NOUN"): [("BIG", "attribute"), ("MORE", "quantity"), ("BE", "state")],
    ("captures", "NOUN"): [("DO", "action"), ("HAVE", "result"), ("SOMETHING", "theme")],
    ("events", "NOUN"): [("HAPPEN", "result"), ("SOMETHING", "theme"), ("MOMENT", "time")],
    ("stop", "NOUN"): [("DO", "action"), ("NOT", "result"), ("MOVE", "theme")],
    ("signature", "NOUN"): [("WORDS", "theme"), ("SOMEONE", "possessor"), ("SEE", "manner")],
    ("activity", "NOUN"): [("DO", "action"), ("SOMEONE", "agent"), ("BE", "state")],
    ("piece", "NOUN"): [("PART", "theme"), ("SOMETHING", "attribute"), ("ONE", "quantity")],
    ("pre", "NOUN"): [("BEFORE", "time"), ("BE", "state"), ("PART", "attribute")],
    ("assessment", "NOUN"): [("THINK", "action"), ("SEE", "goal"), ("KNOW", "result")],
    ("track", "NOUN"): [("MOVE", "path"), ("SEE", "action"), ("WHERE", "location")],
    ("useful", "ADJ"): [("GOOD", "evaluation"), ("DO", "goal"), ("HAVE", "state")],
    ("specialized", "VERB"): [("KIND", "attribute"), ("ONE", "quantity"), ("BE", "state")],
    ("implementing", "VERB"): [("DO", "action"), ("EXIST", "result"), ("SOMETHING", "theme")],
    ("criteria", "NOUN"): [("SOMETHING", "theme"), ("SEE", "goal"), ("THINK", "manner")],
    ("software", "NOUN"): [("SOMETHING", "theme"), ("DO", "action"), ("WORDS", "content")],
    ("verify", "NOUN"): [("SEE", "action"), ("TRUE", "goal"), ("KNOW", "result")],
    ("avoid", "NOUN"): [("DO", "action"), ("NOT", "goal"), ("MOVE", "manner")],
    ("prevent", "NOUN"): [("DO", "action"), ("NOT", "result"), ("SOMEONE", "agent")],
    ("total", "NOUN"): [("ALL", "quantity"), ("SOMETHING", "theme"), ("BE", "state")],
    ("define", "NOUN"): [("SAY", "action"), ("BE", "result"), ("SOMETHING", "theme")],
    ("emerging", "VERB"): [("EXIST", "result"), ("MOVE", "manner"), ("NOW", "time")],
    ("designing", "VERB"): [("THINK", "action"), ("DO", "goal"), ("SOMETHING", "theme")],
    ("extremely", "ADV"): [("MUCH", "degree"), ("VERY", "intensity"), ("BE", "manner")],
    ("knows", "NOUN"): [("KNOW", "state"), ("SOMEONE", "experiencer"), ("SOMETHING", "content")],
    ("faster", "NOUN"): [("MOVE", "action"), ("MORE", "quantity"), ("SHORT_TIME", "duration")],
    ("seeing", "VERB"): [("SEE", "action"), ("SOMEONE", "experiencer"), ("SOMETHING", "theme")],
    ("trigger", "NOUN"): [("DO", "action"), ("HAPPEN", "result"), ("BECAUSE", "cause")],
    ("stem", "NOUN"): [("PART", "theme"), ("LIVE", "state"), ("BE", "attribute")],
    ("evolve", "NOUN"): [("MOVE", "action"), ("LONG_TIME", "duration"), ("OTHER", "result")],
    ("preserve", "NOUN"): [("HAVE", "state"), ("SAME", "attribute"), ("LONG_TIME", "duration")],
    ("devices", "NOUN"): [("SOMETHING", "theme"), ("DO", "action"), ("HAVE", "state")],
    ("bounded", "VERB"): [("PART", "location"), ("SIDE", "attribute"), ("BE", "state")],
    ("reduces", "NOUN"): [("DO", "action"), ("LITTLE", "result"), ("SOMETHING", "theme")],
    ("llm", "NOUN"): [("SOMETHING", "theme"), ("WORDS", "content"), ("THINK", "action")],
    ("gets", "NOUN"): [("DO", "action"), ("HAVE", "result"), ("SOMEONE", "agent")],
    ("traits", "NOUN"): [("SOMETHING", "theme"), ("BE", "attribute"), ("SOMEONE", "possessor")],
    ("habit", "NOUN"): [("DO", "action"), ("SAME", "manner"), ("LONG_TIME", "duration")],
    ("monitor", "NOUN"): [("SEE", "action"), ("LONG_TIME", "duration"), ("SOMETHING", "theme")],
    ("break", "NOUN"): [("DO", "action"), ("PART", "result"), ("SOMETHING", "theme")],
    ("maps", "NOUN"): [("SOMETHING", "theme"), ("SEE", "goal"), ("WHERE", "location")],
    ("produces", "NOUN"): [("DO", "action"), ("EXIST", "result"), ("SOMETHING", "theme")],
    ("recognize", "NOUN"): [("SEE", "action"), ("KNOW", "result"), ("SOMETHING", "theme")],
    ("unlike", "NOUN"): [("NOT", "relation"), ("SAME", "evaluation"), ("OTHER", "attribute")],
    ("sounds", "NOUN"): [("HEAR", "theme"), ("SOMETHING", "attribute"), ("BE", "state")],
    ("seems", "NOUN"): [("SEE", "evaluation"), ("MAYBE", "manner"), ("BE", "state")],
    ("effort", "NOUN"): [("DO", "action"), ("MUCH", "quantity"), ("WANT", "intention")],
    ("synthetic", "NOUN"): [("DO", "action"), ("NOT", "attribute"), ("LIVE", "evaluation")],
    ("becoming", "VERB"): [("BE", "result"), ("MOVE", "manner"), ("OTHER", "state")],
    ("matrices", "NOUN"): [("SOMETHING", "theme"), ("PART", "attribute"), ("HAVE", "state")],
    ("revealing", "VERB"): [("SEE", "result"), ("SOMETHING", "theme"), ("KNOW", "goal")],
    ("aspects", "NOUN"): [("PART", "theme"), ("SEE", "attribute"), ("BE", "state")],
    ("scenario", "NOUN"): [("HAPPEN", "content"), ("IF", "relation"), ("BE", "state")],
    ("category", "NOUN"): [("KIND", "theme"), ("SAME", "attribute"), ("BE", "state")],
    ("constant", "NOUN"): [("SAME", "attribute"), ("LONG_TIME", "duration"), ("BE", "state")],
    ("primary", "NOUN"): [("ONE", "quantity"), ("GOOD", "evaluation"), ("BE", "attribute")],
    ("derived", "VERB"): [("MOVE", "source"), ("EXIST", "result"), ("BE", "state")],
    ("additional", "NOUN"): [("MORE", "quantity"), ("OTHER", "attribute"), ("BE", "state")],
    ("nucleotide", "NOUN"): [("PART", "theme"), ("BODY", "attribute"), ("LIVE", "state")],
    ("keeping", "VERB"): [("HAVE", "state"), ("SAME", "attribute"), ("LONG_TIME", "duration")],
    ("written", "NOUN"): [("WORDS", "theme"), ("DO", "action"), ("BE", "result")],
    ("main", "NOUN"): [("ONE", "quantity"), ("GOOD", "evaluation"), ("BE", "attribute")],
    ("guidelines", "NOUN"): [("SAY", "theme"), ("DO", "goal"), ("GOOD", "evaluation")],
    ("immediately", "ADV"): [("NOW", "time"), ("SHORT_TIME", "duration"), ("BE", "manner")],
    ("rest", "NOUN"): [("OTHER", "theme"), ("PART", "attribute"), ("BE", "state")],
    ("immune", "NOUN"): [("NOT", "evaluation"), ("FEEL", "state"), ("BODY", "attribute")],
    ("rigorous", "ADJ"): [("GOOD", "evaluation"), ("TRUE", "manner"), ("MUCH", "degree")],
    ("leveraging", "VERB"): [("DO", "action"), ("HAVE", "instrument"), ("GOOD", "goal")],
    ("brains", "NOUN"): [("PART", "theme"), ("THINK", "location"), ("BODY", "attribute")],
    ("audience", "NOUN"): [("PEOPLE", "theme"), ("SEE", "action"), ("HEAR", "action")],
    ("controlled", "VERB"): [("DO", "action"), ("HAVE", "result"), ("SOMEONE", "agent")],
    ("simulate", "NOUN"): [("DO", "action"), ("LIKE", "manner"), ("SOMETHING", "theme")],
    ("paths", "NOUN"): [("MOVE", "path"), ("WHERE", "location"), ("BE", "state")],
    ("lottery", "NOUN"): [("DO", "action"), ("MAYBE", "manner"), ("HAVE", "result")],
    ("minutes", "NOUN"): [("MOMENT", "theme"), ("SHORT_TIME", "duration"), ("PART", "attribute")],
    ("felt", "NOUN"): [("FEEL", "state"), ("SOMEONE", "experiencer"), ("BEFORE", "time")],
    ("knowing", "VERB"): [("KNOW", "state"), ("SOMEONE", "experiencer"), ("SOMETHING", "content")],
    ("basis", "NOUN"): [("PART", "theme"), ("BELOW", "location"), ("BE", "attribute")],
    ("longer", "NOUN"): [("LONG_TIME", "duration"), ("MORE", "quantity"), ("BE", "attribute")],
    ("sets", "NOUN"): [("SOMETHING", "theme"), ("SAME", "attribute"), ("HAVE", "state")],
    ("analyzing", "VERB"): [("THINK", "action"), ("SEE", "manner"), ("SOMETHING", "theme")],
    ("evolves", "NOUN"): [("MOVE", "action"), ("LONG_TIME", "duration"), ("OTHER", "result")],
    ("sequential", "NOUN"): [("AFTER", "relation"), ("PART", "attribute"), ("BE", "state")],
    ("statistics", "NOUN"): [("SOMETHING", "theme"), ("MUCH", "attribute"), ("KNOW", "content")],
    ("imagine", "NOUN"): [("THINK", "action"), ("SEE", "manner"), ("SOMETHING", "content")],
    ("perception", "NOUN"): [("SEE", "action"), ("FEEL", "state"), ("SOMEONE", "experiencer")],
    ("ground", "NOUN"): [("BELOW", "location"), ("WHERE", "theme"), ("BE", "state")],
    ("status", "NOUN"): [("BE", "state"), ("WHERE", "attribute"), ("SOMEONE", "possessor")],
    ("financial", "NOUN"): [("HAVE", "state"), ("SOMETHING", "theme"), ("MUCH", "attribute")],
    ("simpler", "NOUN"): [("SMALL", "attribute"), ("LITTLE", "quantity"), ("GOOD", "evaluation")],
    ("preserves", "NOUN"): [("HAVE", "state"), ("SAME", "attribute"), ("LONG_TIME", "duration")],
    ("variants", "NOUN"): [("SOMETHING", "theme"), ("OTHER", "attribute"), ("SAME", "relation")],
    ("secure", "NOUN"): [("GOOD", "evaluation"), ("HAVE", "state"), ("NOT", "relation")],
    ("anyone", "NOUN"): [("SOMEONE", "theme"), ("ALL", "attribute"), ("BE", "state")],
    ("ultimately", "ADV"): [("AFTER", "time"), ("BE", "manner"), ("TRUE", "evaluation")],
    ("protection", "NOUN"): [("DO", "action"), ("GOOD", "goal"), ("NOT", "relation")],
    ("maintains", "NOUN"): [("HAVE", "state"), ("SAME", "attribute"), ("LONG_TIME", "duration")],
    ("audit", "NOUN"): [("SEE", "action"), ("TRUE", "goal"), ("DO", "manner")],
    ("fewer", "NOUN"): [("LITTLE", "quantity"), ("NOT", "evaluation"), ("MUCH", "degree")],
    ("categories", "NOUN"): [("KIND", "theme"), ("SAME", "attribute"), ("BE", "state")],
    ("stay", "NOUN"): [("BE", "state"), ("SAME", "location"), ("LONG_TIME", "duration")],
    ("dead", "NOUN"): [("NOT", "state"), ("LIVE", "evaluation"), ("DIE", "result")],
    ("article", "NOUN"): [("WORDS", "theme"), ("SOMETHING", "content"), ("SEE", "goal")],
    ("applied", "VERB"): [("DO", "action"), ("SOMETHING", "instrument"), ("BE", "result")],
    ("variable", "ADJ"): [("OTHER", "attribute"), ("MOVE", "manner"), ("BE", "state")],
    ("choices", "NOUN"): [("THINK", "action"), ("DO", "result"), ("SOMEONE", "agent")],
    ("additionally", "ADV"): [("MORE", "quantity"), ("OTHER", "attribute"), ("BE", "manner")],
    ("move", "NOUN"): [("MOVE", "action"), ("DO", "manner"), ("WHERE", "goal")],
    ("factor", "NOUN"): [("SOMETHING", "theme"), ("BECAUSE", "cause"), ("BE", "attribute")],
    ("depth", "NOUN"): [("INSIDE", "location"), ("MUCH", "quantity"), ("BE", "attribute")],
    ("object", "NOUN"): [("SOMETHING", "theme"), ("SEE", "evaluation"), ("BE", "state")],
    ("event", "NOUN"): [("HAPPEN", "result"), ("SOMETHING", "theme"), ("MOMENT", "time")],
    ("limit", "NOUN"): [("PART", "location"), ("SIDE", "attribute"), ("NOT", "evaluation")],
    ("notion", "NOUN"): [("THINK", "content"), ("SOMETHING", "theme"), ("KNOW", "state")],

    # Critical high-frequency words with insufficient decompositions
    # Life/Death
    ("die", "VERB"): [("DIE", "action"), ("LIVE", "source"), ("NOT", "result"), ("SOMEONE", "patient")],

    # Time expressions
    ("moment", "NOUN"): [("MOMENT", "theme"), ("SHORT_TIME", "duration"), ("NOW", "time")],

    # Distance/Location - prepositions and adjectives
    ("far", "ADJ"): [("FAR", "attribute"), ("MUCH", "quantity"), ("WHERE", "location")],
    ("near", "ADJ"): [("NEAR", "attribute"), ("LITTLE", "quantity"), ("WHERE", "location")],
    ("above", "ADP"): [("ABOVE", "location"), ("SIDE", "attribute"), ("BE", "state")],
    ("below", "ADP"): [("BELOW", "location"), ("SIDE", "attribute"), ("BE", "state")],
    ("inside", "ADP"): [("INSIDE", "location"), ("PART", "attribute"), ("BE", "state")],
    ("outside", "ADP"): [("INSIDE", "location"), ("NOT", "evaluation"), ("SIDE", "attribute")],

    # Modality/Possibility
    ("maybe", "ADV"): [("MAYBE", "evaluation"), ("HAPPEN", "content"), ("KNOW", "manner")],

    # Emotions
    ("sad", "ADJ"): [("FEEL", "state"), ("BAD", "evaluation"), ("SOMEONE", "experiencer")],
    ("angry", "ADJ"): [("FEEL", "state"), ("BAD", "evaluation"), ("VERY", "intensity")],
    ("unhappy", "ADJ"): [("FEEL", "state"), ("BAD", "evaluation"), ("NOT", "manner")],

    # Time/Duration
    ("long", "ADJ"): [("LONG_TIME", "attribute"), ("MUCH", "quantity"), ("BE", "state")],
    ("short", "ADJ"): [("SHORT_TIME", "attribute"), ("LITTLE", "quantity"), ("BE", "state")],

    # Truth/Correctness
    ("true", "ADJ"): [("TRUE", "evaluation"), ("BE", "state"), ("GOOD", "attribute")],
    ("false", "ADJ"): [("TRUE", "evaluation"), ("NOT", "manner"), ("BE", "state")],
    ("wrong", "ADJ"): [("TRUE", "evaluation"), ("NOT", "manner"), ("BAD", "attribute")],

    # Similarity/Difference
    ("same", "ADJ"): [("SAME", "attribute"), ("ONE", "relation"), ("BE", "state")],
    ("different", "ADJ"): [("SAME", "attribute"), ("NOT", "evaluation"), ("OTHER", "relation")],

    # Speed
    ("fast", "ADJ"): [("MUCH", "intensity"), ("SHORT_TIME", "duration"), ("MOVE", "manner")],
    ("quick", "ADJ"): [("MUCH", "intensity"), ("SHORT_TIME", "duration"), ("DO", "manner")],
    ("slow", "ADJ"): [("LITTLE", "intensity"), ("LONG_TIME", "duration"), ("MOVE", "manner")],

    # Temperature
    ("hot", "ADJ"): [("MUCH", "intensity"), ("FEEL", "state"), ("SOMETHING", "theme")],
    ("cold", "ADJ"): [("LITTLE", "intensity"), ("FEEL", "state"), ("SOMETHING", "theme")],

    # Proximity
    ("close", "ADJ"): [("NEAR", "attribute"), ("LITTLE", "quantity"), ("WHERE", "location")],
    ("tiny", "ADJ"): [("SMALL", "attribute"), ("VERY", "degree"), ("LITTLE", "quantity")],

    # Quantity determiners
    ("few", "DET"): [("LITTLE", "quantity"), ("SOME", "attribute"), ("NOT", "evaluation")],

    # Comparison
    ("less", "ADV"): [("LITTLE", "quantity"), ("MORE", "relation"), ("NOT", "evaluation")],

    # Complexity
    ("simple", "ADJ"): [("PART", "attribute"), ("LITTLE", "quantity"), ("KNOW", "evaluation")],
    ("complex", "ADJ"): [("PART", "attribute"), ("MUCH", "quantity"), ("KNOW", "evaluation")],

    # Verb variants for common words (when used as verbs)
    ("up", "VERB"): [("ABOVE", "goal"), ("MOVE", "action"), ("DO", "manner")],
    ("right", "VERB"): [("TRUE", "result"), ("DO", "action"), ("GOOD", "evaluation")],
    ("water", "VERB"): [("HAVE", "action"), ("SOMETHING", "theme"), ("DO", "manner")],
    ("time", "VERB"): [("KNOW", "action"), ("WHEN", "content"), ("DO", "manner")],
    ("even", "VERB"): [("SAME", "result"), ("DO", "action"), ("PART", "manner")],
    ("still", "VERB"): [("NOT", "result"), ("MOVE", "action"), ("DO", "manner")],
    ("group", "VERB"): [("PEOPLE", "theme"), ("SAME", "result"), ("DO", "action")],
    ("team", "VERB"): [("PEOPLE", "theme"), ("DO", "action"), ("SAME", "goal")],

    # Misc high-frequency gaps
    ("john", "NOUN"): [("SOMEONE", "theme"), ("PEOPLE", "attribute"), ("BE", "state")],
    ("then", "NOUN"): [("WHEN", "attribute"), ("AFTER", "time"), ("MOMENT", "theme")],
}


def validate_decomposition(decomp):
    """Validate that all primitives and roles are valid."""
    for prim, role in decomp:
        if prim not in PRIMITIVES:
            print(f"  WARNING: Invalid primitive '{prim}'")
            return False
        if role not in ROLES:
            print(f"  WARNING: Invalid role '{role}'")
            return False
    return True


def fix_decompositions():
    """Apply all corrections to the database."""
    print("=" * 70)
    print("FIXING TOP 200 WORD DECOMPOSITIONS")
    print("=" * 70)

    # Initialize encoder
    basis = PrimitiveBasis.generate(PRIMITIVES, ROLES)
    generator = LexiconGenerator(basis)
    conn = sqlite3.connect(DB_PATH)

    fixed = 0
    failed = 0

    for (lemma, pos), decomp in CORRECTIONS.items():
        # Validate decomposition
        if not validate_decomposition(decomp):
            print(f"  ✗ Skipping {lemma} ({pos}) - invalid decomposition")
            failed += 1
            continue

        # Encode to vector
        vector = generator.encode_decomposition(decomp)

        # Check if entry exists
        existing = conn.execute(
            "SELECT id, decomposition FROM lexicon WHERE lemma = ? AND pos = ?",
            (lemma, pos)
        ).fetchone()

        if existing:
            old_decomp = existing[1]
            conn.execute("""
                UPDATE lexicon
                SET decomposition = ?, vector = ?, source = ?, confidence = ?
                WHERE id = ?
            """, (json.dumps(decomp), vector.serialize(), "manual-fix", 0.95, existing[0]))

            decomp_str = ", ".join([f"{p}-{r}" for p, r in decomp[:3]])
            print(f"  ✓ {lemma:15} ({pos:4}) -> [{decomp_str}...]")
            fixed += 1
        else:
            print(f"  ? {lemma} ({pos}) - not found in database, inserting...")
            conn.execute("""
                INSERT INTO lexicon (lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (lemma, pos, f"{lemma}.{pos}.01", "", json.dumps(decomp), vector.serialize(), 0.9, "manual-fix", 0.95))
            fixed += 1

    conn.commit()
    conn.close()

    print("-" * 70)
    print(f"Fixed: {fixed}")
    print(f"Failed: {failed}")
    print("=" * 70)


if __name__ == "__main__":
    fix_decompositions()
