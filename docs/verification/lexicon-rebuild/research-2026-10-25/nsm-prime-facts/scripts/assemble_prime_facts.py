"""Assemble prime_facts.json from the agent's own part files.

Reads only the part files under parts/ (the agent's own notes). It never opens any
source text. Run with: python3 -I assemble_prime_facts.py
"""
import json
import os
import sys

BASE = "/tmp/gse-subagents/nsm-prime-facts"
PARTS = os.path.join(BASE, "parts")
OUT = os.path.join(BASE, "prime_facts.json")

# (GSE name, NSM exponent label as given in the task, chart box titles)
PRIMES = [
    ("YOU", "YOU", ["YOU"]),
    ("PEOPLE", "PEOPLE", ["PEOPLE"]),
    ("BODY", "BODY", ["BODY"]),
    ("KIND", "KIND (KINDS)", ["KINDS"]),
    ("PART", "PART ((HAVE) PARTS)", ["(HAVE) PARTS"]),
    ("SAME", "SAME (THE SAME)", ["THE SAME"]),
    ("OTHER", "OTHER (OTHER~ELSE)", ["OTHER~ELSE"]),
    ("ONE", "ONE", ["ONE"]),
    ("TWO", "TWO", ["TWO"]),
    ("THINK", "THINK", ["THINK"]),
    ("KNOW", "KNOW", ["KNOW"]),
    ("SEE", "SEE", ["SEE"]),
    ("HEAR", "HEAR", ["HEAR"]),
    ("SAY", "SAY", ["SAY"]),
    ("WORDS", "WORDS", ["WORDS"]),
    ("TRUE", "TRUE", ["TRUE"]),
    ("DO", "DO", ["DO"]),
    ("HAPPEN", "HAPPEN", ["HAPPEN"]),
    ("MOVE", "MOVE", ["MOVE"]),
    ("BE", "BE (BE (SOMEWHERE) and BE (SOMEONE/SOMETHING))", ["BE (SOMEWHERE)", "BE (SOMEONE/SOMETHING)"]),
    ("HAVE", "HAVE ((IS) MINE and (HAVE) PARTS)", ["(IS) MINE", "(HAVE) PARTS"]),
    ("EXIST", "EXIST (THERE IS)", ["THERE IS"]),
    ("MOMENT", "MOMENT", ["MOMENT"]),
    ("WHEN", "WHEN (TIME~WHEN)", ["TIME~WHEN"]),
    ("LONG_TIME", "LONG_TIME (A LONG TIME)", ["A LONG TIME"]),
    ("SHORT_TIME", "SHORT_TIME (A SHORT TIME)", ["A SHORT TIME"]),
    ("BEFORE", "BEFORE", ["BEFORE"]),
    ("AFTER", "AFTER", ["AFTER"]),
    ("WHERE", "WHERE (PLACE~WHERE~SOMEWHERE)", ["PLACE~WHERE~SOMEWHERE"]),
    ("SIDE", "SIDE (ON (ONE) SIDE)", ["ON (ONE) SIDE"]),
    ("TOUCH", "TOUCH", ["TOUCH"]),
    ("ABOVE", "ABOVE", ["ABOVE"]),
    ("BELOW", "BELOW", ["BELOW"]),
    ("FAR", "FAR", ["FAR"]),
    ("NEAR", "NEAR", ["NEAR"]),
    ("INSIDE", "INSIDE", ["INSIDE"]),
    ("NOT", "NOT (NOT~DON'T)", ["NOT~DON’T"]),
    ("MAYBE", "MAYBE", ["MAYBE"]),
    ("CAN", "CAN", ["CAN"]),
    ("IF", "IF", ["IF"]),
    ("LIKE", "LIKE (LIKE~AS~WAY)", ["LIKE~AS~WAY"]),
]
assert len(PRIMES) == 41, len(PRIMES)
GSE_NAMES = [p[0] for p in PRIMES]
VALID_TAGS = set(GSE_NAMES) | {"GENERAL"}
IGNORED_TAGS = {"VERY"}  # VERY is not one of the 41; facts about it carry a very_more topic

SOURCE_ORDER = ["G12", "LFH22", "GW2014"]
USAGE_ONLY_TOPICS = {"explication_usage", "explication_frame"}


def load(name):
    with open(os.path.join(PARTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def page_of(location):
    """First page number in a location string such as 'printed p.12, ...' (sort key only)."""
    marker = "p."
    idx = location.find(marker)
    if idx < 0:
        return 0
    digits = ""
    for ch in location[idx + len(marker):]:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return int(digits) if digits else 0


def groups_for(topic):
    groups = []
    if "allolex" in topic:
        groups.append("allolexes")
    if "polysem" in topic or "lexicalisation" in topic or "exponent_in_compounds" in topic:
        groups.append("polysemy_and_lexicalisation")
    if "valency" in topic or "combinatoric" in topic or "frame" in topic:
        groups.append("valency_and_combinatorics")
    if "restriction" in topic:
        groups.append("restrictions")
    if "very_more" in topic or "_very" in topic or topic.startswith("very"):
        groups.append("very_more")
    if "separation" in topic:
        groups.append("separation")
    if ("exponent_name" in topic or "category" in topic or "exponent_note" in topic
            or "exponent_form" in topic
            or topic in ("exponents", "inventory_size", "inventory_size_and_exponents", "mention")):
        groups.append("exponent_names_and_lists")
    if "explication" in topic:
        groups.append("explication_usage")
    if not groups:
        groups.append("other")
    return groups


def main():
    chart = load("chart_boxes.json")
    boxes = chart["boxes"]
    evidence_doc = load("very_more_evidence.json")
    evidence = evidence_doc["evidence"]

    # ---- facts from the sources ----------------------------------------------------
    fact_files = [
        "g12_facts.json",
        "g12_allolex_cells.json",
        "lfh22_facts.json",
        "lfh22_allolex_cells.json",
        "gw2014_ch1_ch2.json",
        "gw2014_ch2_extra.json",
        "gw2014_ch3_ch4.json",
        "gw2014_ch6_ch10.json",
        "gw2014_ch8.json",
    ]
    facts = []
    counters = {}
    for fname in fact_files:
        doc = load(fname)
        src = doc["source_key"]
        for original_index, fact in enumerate(doc["facts"]):
            counters[src] = counters.get(src, 0) + 1
            tags = [t for t in fact["primes"] if t not in IGNORED_TAGS]
            unknown = [t for t in tags if t not in VALID_TAGS]
            if unknown:
                raise SystemExit("unknown prime tag %r in %s: %s" % (unknown, fname, fact["location"]))
            if not tags:
                tags = ["GENERAL"]
            record = {
                "id": "%s-%03d" % (src, counters[src]),
                "source": src,
                "location": fact["location"],
                "topic": fact["topic"],
                "groups": groups_for(fact["topic"]),
                "primes_tagged": tags,
                "quote": fact["quote"],
            }
            if fact.get("note"):
                record["note"] = fact["note"]
            record["_sort"] = (SOURCE_ORDER.index(src), page_of(fact["location"]), len(facts))
            facts.append(record)
    facts.sort(key=lambda r: r["_sort"])
    for record in facts:
        del record["_sort"]

    def is_usage_only(record):
        return record["topic"] in USAGE_ONLY_TOPICS

    usage_facts = {r["id"]: r for r in facts if is_usage_only(r)}

    # ---- chart-derived statements ----------------------------------------------------
    fw = chart["function_words_and_portmanteaus"]["entries"]
    fw_lines = {
        "in": "388", "at": "389", "of": "390", "with": "391", "about": "392", "these": "393",
        "it_dummy": "394", "it_thing": "395", "a_lot": "396", "well": "397", "such": "398",
        "they_them": "399", "everywhere": "400", "often_sometimes_always_never": "401-402",
        "singular_they": "403-404",
    }
    fw_primes = {
        "in": ["WHERE", "MOMENT"], "at": ["WHEN", "MOMENT"], "of": ["ONE", "KIND", "PEOPLE"],
        "with": ["DO"], "about": ["THINK", "SAY"], "these": ["GENERAL"], "it_dummy": ["GENERAL"],
        "it_thing": ["GENERAL"], "a_lot": ["GENERAL"], "well": ["SEE"], "such": ["LIKE"],
        "they_them": ["PEOPLE"], "everywhere": ["WHERE"],
        "often_sometimes_always_never": ["WHEN"], "singular_they": ["GENERAL"],
    }
    chart_statements = []
    for key, text in fw.items():
        chart_statements.append({
            "source": "CH",
            "location": "box 'Function words and portmanteaus', txt line %s" % fw_lines[key],
            "topic": "function_word_or_portmanteau",
            "primes_tagged": fw_primes[key],
            "quote": text,
        })
    using = chart["using_nsm_in_explications"]["paragraphs"]
    chart_statements += [
        {"source": "CH", "location": "box 'Using NSM in explications', txt lines 366-368",
         "topic": "restriction", "primes_tagged": ["DO", "GENERAL"], "quote": using[0],
         "note": "The chart names 'make' as an English-specific word to avoid; it does not tie 'make' to DO."},
        {"source": "CH", "location": "box 'Using NSM in explications', txt lines 369-374",
         "topic": "restriction_valency", "primes_tagged": ["DO", "GENERAL"], "quote": using[1]},
        {"source": "CH", "location": "box 'Using NSM in explications', txt lines 375-378",
         "topic": "restriction", "primes_tagged": ["SAY", "GENERAL"], "quote": using[2],
         "note": "'comparative (e.g. better than, more than)' also bears on MORE (not one of the 41); 'indirect speech' bears on SAY."},
        {"source": "CH", "location": "box 'Using NSM in explications', txt lines 379-384",
         "topic": "general", "primes_tagged": ["GENERAL"], "quote": using[3]},
        {"source": "CH", "location": "preamble, txt lines 360-362",
         "topic": "general", "primes_tagged": ["GENERAL"],
         "quote": "The chart displays the English words for the primes and some of their combinatorial possibilities, according to NSM grammar. More complex combinations are also possible."},
        {"source": "CH", "location": "preamble, txt line 362",
         "topic": "polysemy_colexification", "primes_tagged": ["HEAR"],
         "quote": "In some languages, two primes e.g. feel and hear may be expressed by the same word."},
        {"source": "CH", "location": "preamble, txt lines 362-363",
         "topic": "allolexy", "primes_tagged": ["OTHER"],
         "quote": "In some languages, a prime can have two or more exponents (allolexes), e.g. English other and else."},
        {"source": "CH", "location": "preamble, txt line 363",
         "topic": "portmanteau", "primes_tagged": ["LIKE"],
         "quote": "Sometimes a combination of two or more primes, e.g. like this, can be expressed by a single portmanteau word."},
    ]
    for st in chart_statements:
        for tag in st["primes_tagged"]:
            assert tag in VALID_TAGS, tag

    # ---- per-prime records -----------------------------------------------------------
    def box_record(title):
        box = boxes[title]
        return {"title": title, "txt_lines": box["txt_lines"], "entries": box["entries"]}

    primes_out = {}
    for gse, label, titles in PRIMES:
        rec = {
            "gse_name": gse,
            "nsm_exponent_label": label,
            "chart_boxes": [box_record(t) for t in titles],
            "chart_footer_and_preamble_statements": [
                {k: v for k, v in st.items() if k != "primes_tagged"}
                for st in chart_statements if gse in st["primes_tagged"]
            ],
            "statements_from_G12_LFH22_GW2014": [],
            "explication_usage_ids": [],
        }
        for record in facts:
            if gse not in record["primes_tagged"]:
                continue
            if is_usage_only(record):
                item = {"id": record["id"], "source": record["source"], "location": record["location"]}
                if record.get("note"):
                    item["note"] = record["note"]
                rec["explication_usage_ids"].append(item)
            else:
                item = {k: v for k, v in record.items() if k != "primes_tagged"}
                rec["statements_from_G12_LFH22_GW2014"].append(item)
        index = {}
        for item in rec["statements_from_G12_LFH22_GW2014"]:
            for g in item["groups"]:
                index.setdefault(g, []).append(item["id"])
        rec["statement_ids_by_group"] = index

        chart_vm = [e for e in evidence if e["prime"] == gse and e["source"] == "CH"]
        other_vm = [e for e in evidence if e["prime"] == gse and e["source"] != "CH"]
        vm = {
            "chart": [{k: v for k, v in e.items() if k != "prime"} for e in chart_vm],
            "other_sources": [{k: v for k, v in e.items() if k != "prime"} for e in other_vm],
        }
        if not chart_vm:
            vm["chart_note"] = ("No VERY or MORE combined with %s in any chart box (the boxes VERY and MORE~ANYMORE, "
                                "the box of the prime itself, and the rest of the chart were checked)." % gse)
        if not other_vm:
            vm["other_sources_note"] = ("No VERY or MORE combined with %s in G12 (read whole), LFH22 (read whole) or the "
                                        "GW2014 pages listed under coverage (GW2014 was read only in part)." % gse)
        rec["very_more"] = vm
        primes_out[gse] = rec

    general = [{k: v for k, v in r.items() if k != "primes_tagged"} for r in facts if "GENERAL" in r["primes_tagged"] and not is_usage_only(r)]
    general += [{k: v for k, v in st.items() if k != "primes_tagged"} for st in chart_statements if "GENERAL" in st["primes_tagged"]]

    # ---- separation of the primes GSE merges or renames -----------------------------------
    def pick(source, location_prefix):
        found = [r for r in facts if r["source"] == source and r["location"].startswith(location_prefix)]
        if len(found) != 1:
            raise SystemExit("separation pick %r %r matched %d facts" % (source, location_prefix, len(found)))
        return found[0]

    def sep_item(record):
        return {k: v for k, v in record.items() if k not in ("primes_tagged",)}

    def facts_with_topic(fragment, tags):
        return [r for r in facts if fragment in r["topic"] and any(t in r["primes_tagged"] for t in tags)]

    same_other_boxes = ["THIS", "THE SAME", "OTHER~ELSE"]
    cross_box = []
    for title, box in boxes.items():
        if title in same_other_boxes:
            continue
        hits = [e for e in box["entries"] if ("same" in e.lower() or "other" in e.lower() or "else" in e.lower() or "another" in e.lower())]
        if hits:
            cross_box.append({"box": title, "txt_lines": box["txt_lines"], "entries": hits})

    separation = {
        "SAME_OTHER": {
            "gse_primes": ["SAME", "OTHER"],
            "chart_boxes": [box_record(t) for t in same_other_boxes],
            "source_statements": [sep_item(r) for r in (
                pick("G12", "ms p.3, Table 1, txt line 124"),
                pick("LFH22", "journal p.5, Table 1 (English), txt line 249"),
                pick("GW2014", "printed p.12, Table 1.1, txt line 601"),
                pick("GW2014", "printed p.13, txt lines 650-664"),
                pick("GW2014", "printed p.13, txt lines 665-672"),
                pick("GW2014", "printed p.30, txt lines 1377-1387"),
                pick("GW2014", "printed p.159, txt lines 6775-6789"),
            )] + [sep_item(r) for r in facts_with_topic("separation_cross_language", ["SAME", "OTHER"])],
            "chart_preamble_on_allolexes": [
                {k: v for k, v in st.items() if k != "primes_tagged"} for st in chart_statements
                if "OTHER" in st["primes_tagged"]
            ],
            "other_chart_boxes_whose_entries_contain_same_other_else_or_another": cross_box,
        },
        "BE": {
            "gse_primes": ["BE"],
            "chart_boxes": [box_record(t) for t in ("BE (SOMEWHERE)", "BE (SOMEONE/SOMETHING)", "THERE IS", "(IS) MINE")],
            "source_statements": [sep_item(r) for r in (
                pick("G12", "ms p.3, Table 1, txt lines 131-132"),
                pick("LFH22", "journal p.6, Table 1 (English), txt line 273"),
                pick("GW2014", "printed p.12, Table 1.1, txt lines 609-610"),
                pick("G12", "ms p.27-28, note 5"),
            )] + [sep_item(r) for r in facts_with_topic("separation_cross_language", ["BE"])],
        },
        "HAVE": {
            "gse_primes": ["HAVE", "PART"],
            "chart_boxes": [box_record(t) for t in ("(IS) MINE", "(HAVE) PARTS")],
            "source_statements": [sep_item(r) for r in (
                pick("G12", "ms p.3, Table 1, txt lines 131-132"),
                pick("G12", "ms p.3, Table 1, txt line 123"),
                pick("G12", "ms p.27, note 3"),
                pick("LFH22", "journal p.5, Table 1 (English), txt line 247"),
                pick("LFH22", "journal p.6, Table 1 (English), txt line 275"),
                pick("GW2014", "printed p.12, Table 1.1, txt lines 609-610"),
                pick("GW2014", "printed p.12, Table 1.1, txt line 600"),
            )] + [sep_item(r) for r in facts_with_topic("separation_cross_language", ["HAVE"])],
            "usage_of_have_in_the_part_whole_sense_in_explications": [
                {"id": r["id"], "source": r["source"], "location": r["location"], "note": r.get("note", "")}
                for r in facts if r["id"] in usage_facts and "HAVE" in r["primes_tagged"]
            ] + [
                {"id": r["id"], "source": r["source"], "location": r["location"], "note": r.get("note", "")}
                for r in facts if (not is_usage_only(r)) and "explication" in r["topic"] and "HAVE" in r["primes_tagged"]
            ],
        },
        "EXIST": {
            "gse_primes": ["EXIST"],
            "chart_boxes": [box_record(t) for t in ("THERE IS", "BE (SOMEWHERE)")],
            "source_statements": [sep_item(r) for r in (
                pick("G12", "ms p.3, Table 1, txt lines 131-132"),
                pick("LFH22", "journal p.6, Table 1 (English), txt line 273"),
                pick("GW2014", "printed p.12, Table 1.1, txt lines 609-610"),
            )] + [sep_item(r) for r in facts_with_topic("separation_cross_language", ["EXIST"])],
            "usage_of_there_is_frames_in_explications": [
                {"id": r["id"], "source": r["source"], "location": r["location"], "note": r.get("note", "")}
                for r in facts if "EXIST" in r["primes_tagged"] and "explication" in r["topic"]
            ],
        },
    }
    # de-duplicate source_statements inside each group while keeping order
    for group in separation.values():
        seen = set()
        unique = []
        for item in group["source_statements"]:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            unique.append(item)
        group["source_statements"] = unique

    name_table = {
        "description": "How each source names and labels the NSM items that GSE merges or renames. Names are copied as printed (the .txt of GW2014 prints the allolex mark as U+02DC).",
        "rows": {
            "THE SAME": {"CH": "box THE SAME", "G12": "THE SAME (row 'THIS, THE SAME, OTHER~ELSE', label determiners)", "LFH22": "THE SAME (row 'THIS, THE SAME, OTHER~ELSE~ANOTHER')", "GW2014": "the same (row 'this, the same, other˜else', label determiners)"},
            "OTHER~ELSE": {"CH": "box OTHER~ELSE; preamble gives other and else as allolexes", "G12": "OTHER~ELSE (label determiners)", "LFH22": "OTHER~ELSE~ANOTHER", "GW2014": "other˜else (label determiners); p.13: other modifies nouns, else modifies indefinite pronouns"},
            "location use of be": {"CH": "box BE (SOMEWHERE)", "G12": "BE (SOMEWHERE) (label location)", "LFH22": "BE (SOMEWHERE)", "GW2014": "be (somewhere) (label location)"},
            "specification use of be": {"CH": "box BE (SOMEONE/SOMETHING)", "G12": "BE (SOMEONE/SOMETHING) (label specification)", "LFH22": "BE (SOMEONE/SOMETHING)", "GW2014": "be (someone/something) (label specification)"},
            "existence": {"CH": "box THERE IS", "G12": "THERE IS (label existence)", "LFH22": "THERE IS", "GW2014": "there is (label existence)"},
            "possession": {"CH": "box (IS) MINE", "G12": "HAVE (SOMETHING) (label possession)", "LFH22": "(IS) MINE", "GW2014": "be (someone)’s (label possession)"},
            "part-whole": {"CH": "box (HAVE) PARTS", "G12": "PART (row 'KIND, PART', label relational substantives)", "LFH22": "PART (in the first row, after KIND)", "GW2014": "parts (row 'kind, parts', label relational substantives)"},
        },
    }

    meta = {
        "task": "Fact-gathering only: documented combinatorial properties of the 41 GSE primes that correspond to NSM semantic primes. The file records what the sources say and where; it contains no decision about any definition or vector and no advice.",
        "date": "2026-10-25",
        "sources": {
            "CH": {"title": "Chart of NSM Semantic Primes, English, version 20 (10 May 2022)", "publisher": "nsm-approach.net",
                   "files": {"txt": "nsm-primes-chart-v20-2022.txt (10733 bytes, sha256 5847b39219381181f98a2afbfc57b149ad16cd77157ca0d205b341d1466cf732)",
                             "png": "nsm-primes-chart-v20-2022.png (1985x1404, 739800 bytes, sha256 e104a3bb491591687ecb24669216e55b4978181d87cb5aad904f4d2991919355)"},
                   "location_system": "txt line numbers; box membership and the wrapping of entries checked against the PNG",
                   "coverage": "txt read whole (lines 1-404); PNG viewed whole and in enlarged crops of every box and of both footer boxes"},
            "G12": {"title": "Goddard 2012, Semantic primes, semantic molecules, semantic templates: Key concepts in the NSM approach to lexical typology, Linguistics 50(3): 711-743 (author manuscript)",
                    "file": "goddard-2012-primes-molecules-templates.txt (110186 bytes, sha256 42ecd3602a299b795436bb250e03a48d15b0def88fb17b3493d41e045f785b2d)",
                    "location_system": "author-manuscript pages from the '- N -' footer lines (not the journal pages), plus txt line numbers",
                    "coverage": "read whole, txt lines 1-1592 (title page, body, appendix, notes, references)"},
            "LFH22": {"title": "Levisen, Fernandez and Hein 2022, Cognitive cultural semantics: A Nordic guide to Natural Semantic Metalanguage (NSM), Scandinavian Studies in Language 13(1): 1-38",
                      "file": "levisen-fernandez-hein-2022-nordic-guide-to-nsm.txt (97785 bytes, sha256 504bf9f00297669e3ced0c1d0947ea481f79140883efd55b61665850ff7ef527)",
                      "location_system": "journal pages (the page number is printed at the foot of each page), plus txt line numbers",
                      "coverage": "read whole, txt lines 1-1981; PDF pages 5-6 also viewed to confirm the table rows"},
            "GW2014": {"title": "Goddard and Wierzbicka 2014, Words and Meanings: Lexical Semantics across Domains, Languages, and Cultures (Oxford University Press)",
                       "file": "goddard-wierzbicka-2014-words-and-meanings.txt (974496 bytes, sha256 3ce88d4d1bd2c9678d0479f5f1af3ed43fb5a040a5b5118176b03bb2c5329781; 13427 lines)",
                       "location_system": "printed book pages (PDF page = printed page + 9), plus txt line numbers",
                       "coverage_read": [
                           "contents and front matter, txt lines 1-118",
                           "chapter 1 whole, printed pp.1-21 (txt lines 119-1030)",
                           "chapter 2 whole, printed pp.22-54 (txt lines 1031-2418)",
                           "chapter 3 whole, printed pp.55-79 (txt lines 2419-3477)",
                           "chapter 4, printed pp.80-87 (txt lines 3478-3810) and pp.95-101 (txt lines 4130-4387)",
                           "chapter 5, only the opening, printed pp.102-103 (txt lines 4388-4459)",
                           "chapter 6, printed pp.135-142 (txt lines 5800-6060)",
                           "chapter 7, printed pp.156-181 (txt lines 6650-7690)",
                           "chapter 8, from the middle of printed p.186 to the first part of p.192 (txt lines 7900-8159)",
                           "chapter 9, printed pp.229-237 (txt lines 9700-10047)",
                           "chapter 10 whole, printed pp.238-261 (txt lines 10057-11040)",
                           "the end of the reference list (txt lines 12150-12363) and the Index whole, printed pp.291-314 (txt lines 12364-13427), used to choose the pages above"],
                       "coverage_not_read": [
                           "chapter 4 printed pp.88-94; chapter 5 printed pp.104-126; chapter 6 printed pp.127-134 and pp.143-155; chapter 7 printed pp.182-183; chapter 8 printed pp.184-185, the first part of p.186, and the rest of p.192 through p.204; chapter 9 printed pp.205-228 (the book's domain studies of colour, happiness, pain, proverbs and abstract nouns); the reference list"],
                       "page_choice": "Pages were chosen from the book's own index entries (allolexy, combinatorial properties, complement, exponent(s) of a prime, grammar of semantic primes, patient, partitive, polysemy, predicate(s), quantifiers, specifiers, substantives, syntactic frames, valency frame, universal grammar, and the entries for after, before, all, say, words, part(s), kinds, like, near, touch, touching, see, happen, the same, place, think, know) and from the contents list."},
        },
        "quote_conventions": [
            "A quote is the source text with line breaks joined by one space; words split at a line end by a typesetting hyphen are rejoined; running heads and interleaved footnote text at page breaks are left out; explication and table layouts keep one line per row separated by a newline; [...] marks omitted text inside a quoted passage.",
            "Ligature characters in the GW2014 .txt are written as plain letters (fi, fl). Straight and curly quotation marks and apostrophes are kept as in the source, including the modifier-letter apostrophe that the G12 explications print. Footnote reference numbers attached to words in the .txt are left out of the quotes.",
            "Two-column tables are written as the left column, four spaces, then the right column; where the .txt interleaves columns, the note field says how the row was reassembled.",
            "Chart entries are joined as the PNG shows them (an entry that wraps onto a second line, with a hanging indent in the PNG, is one entry); the txt line range of each box is given beside it."],
        "kinds_of_entry": {
            "statements_from_G12_LFH22_GW2014": "statements and tables in the sources about exponent names, valency or combinatorial frames, allolexes, polysemy, restrictions, and VERY or MORE, plus a limited number of passages where an author's own explication shows a prime in a frame; the groups field says which of these a statement bears on (an entry can bear on several).",
            "explication_usage_ids": "passages where an author's explication or scenario simply uses the prime in a frame. These are illustrations, not stated properties, and they are a selected set, not an exhaustive scan of the explications in the sources; the full quotes are in explication_usage_facts."},
        "rules_followed": "No text-search or text-cutting command was run on any source; the sources were read with the Read tool in consecutive chunks. The only programs run were mkdir, ls, sips (to enlarge parts of the chart PNG), and Python (-I) scripts that read and write only this agent's own files under /tmp/gse-subagents/nsm-prime-facts/. Nothing inside /Users/rohanvinaik/Projects/gse was modified."
    }

    out = {
        "meta": meta,
        "count_of_gse_primes": len(PRIMES),
        "primes": primes_out,
        "general_statements": general,
        "separation_of_merged_or_renamed_primes": {"name_table": name_table, **separation},
        "very_more_outside_the_41": {
            "very": evidence_doc["very_with_primes_outside_the_41"],
            "more": evidence_doc["more_with_primes_outside_the_41"],
        },
        "explication_usage_facts": usage_facts,
        "chart": {
            "title": chart["title_line"],
            "location_system": chart["location_system"],
            "boxes": boxes,
            "preamble": chart["preamble"],
            "using_nsm_in_explications": chart["using_nsm_in_explications"],
            "function_words_and_portmanteaus": chart["function_words_and_portmanteaus"],
        },
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    # summary counts
    print("facts", len(facts), "usage-only", len(usage_facts))
    print("primes", len(primes_out))
    for gse in GSE_NAMES:
        rec = primes_out[gse]
        print(gse, "stmts", len(rec["statements_from_G12_LFH22_GW2014"]), "usage", len(rec["explication_usage_ids"]),
              "very_more chart", len(rec["very_more"]["chart"]), "other", len(rec["very_more"]["other_sources"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
