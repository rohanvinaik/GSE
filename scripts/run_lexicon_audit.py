import csv
import os
import sqlite3


def load_csv(path, sep=',', names=None, skiprows=0):
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=sep)
        for _ in range(skiprows):
            next(reader, None)

        headers = names if names else next(reader, None)

        for row in reader:
            if not row: continue
            item = {}
            for i, h in enumerate(headers):
                if i < len(row):
                    item[h] = row[i]
            data.append(item)
    return data

def run_audit():
    print("Starting Lexicon Audit (Standard Lib Mode)...")

    # 1. Connect and Load Data
    db_path = 'data/lexicon.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Get top 5000 words
    print("Loading top 5000 words...")
    cur.execute('''
        SELECT l.id, l.lemma, l.pos, l.frequency_rank
        FROM lexemes l
        WHERE l.frequency_rank <= 5000
        ORDER BY l.frequency_rank
    ''')
    top_words = []
    # Determine columns? sqlite3.Row could work but manual dict is fine
    # id, lemma, pos, frequency_rank
    lexeme_map = {} # id -> dict of word info

    for row in cur.fetchall():
        w = {
            'id': row[0],
            'lemma': row[1],
            'pos': row[2],
            'frequency_rank': row[3],
            'primitives': {} # Will populate next
        }
        top_words.append(w)
        lexeme_map[row[0]] = w

    # Get primitives for these words
    print("Loading primitives...")
    ids = [str(w['id']) for w in top_words]
    if not ids:
        print("No words found.")
        return

    cur.execute(f'''
        SELECT pv.lexeme_id, pv.primitive, pv.value
        FROM primitive_values pv
        WHERE pv.lexeme_id IN ({','.join(ids)})
    ''')

    for row in cur.fetchall():
        lid, prim, val = row
        if lid in lexeme_map:
            lexeme_map[lid]['primitives'][prim] = val

    # 2. Load External Data
    print("Loading external datasets...")
    try:
        # nrc_vad: term    valence arousal dominance (tab sep)
        # skiprows=1 because header in file? prompt says "names=['word'...], skiprows=1".
        # Let's verify file content from previous `head` output: "term\tvalence..." -> yes headers exist.
        nrc_vad = load_csv('data/external/nrc_vad.txt', sep='\t', names=['word','valence','arousal','dominance'], skiprows=1)
        # Index by word for fast lookup
        nrc_vad_map = {row['word'].lower(): row for row in nrc_vad}

        lancaster = load_csv('data/external/lancaster_sensorimotor.csv')
        # Header: "Word","Auditory.mean",...
        lancaster_map = {row['Word'].lower(): row for row in lancaster}

        concreteness = load_csv('data/external/concreteness.csv')
        conc_map = {row['Word'].lower(): row for row in concreteness}

        # nrc_emotion: aback   anger   0 (no header)
        nrc_emotion_list = load_csv('data/external/nrc_emotion.txt', sep='\t', names=['word', 'emotion', 'association'])
        # Maybe index? List of dicts checks is fine for simple stuff, but prompt use?
        # Actually prompt script didn't use emotion. I will skip complex indexing unless needed.

    except Exception as e:
        print(f"Error loading external data: {e}")
        conn.close()
        # Continue or return? Return safer
        import traceback
        traceback.print_exc()
        return

    # Helper to get prim value safely
    def get_prim(word_obj, prim_name, default=0):
        return word_obj['primitives'].get(prim_name, default)

    # Check 1: Bipolar Constraint Violations
    print("Running Check 1: Bipolar Violations...")
    bipolar_pairs = [
        ('GOOD', 'BAD'), ('BIG', 'SMALL'), ('ALIVE', 'DEAD'), ('SAME', 'OTHER'),
        ('BEFORE', 'AFTER'), ('THEN', 'NOW'), ('START', 'END'), ('ABOVE', 'BELOW'),
        ('FAR', 'NEAR'), ('INSIDE', 'OUTSIDE'), ('TOWARD', 'AWAY'), ('WITH', 'WITHOUT'),
        ('TRUE', 'FALSE'), ('LONG_TIME', 'SHORT_TIME')
    ]

    bipolar_issues = []
    for w in top_words:
        for p1, p2 in bipolar_pairs:
            v1 = get_prim(w, p1)
            v2 = get_prim(w, p2)
            if v1 != 0 and v2 != 0:
                bipolar_issues.append({
                    'Word': w['lemma'],
                    'Pair': f"{p1}/{p2}",
                    'Values': f"{p1}={int(v1)}, {p2}={int(v2)}",
                    'Severity': 'CRITICAL'
                })

    # Check 2: INTENSITY Bug
    print("Running Check 2: INTENSITY Bug...")
    intensity_candidates = []

    for w in top_words:
        lemma = w['lemma'].lower()
        if lemma in nrc_vad_map:
            vad_entry = nrc_vad_map[lemma]
            arousal = float(vad_entry['arousal'])
            intensity = get_prim(w, 'INTENSITY')

            # Case 1: INTENSITY=-1 but Arousal > 0.4
            if intensity == -1 and arousal > 0.4:
                intensity_candidates.append({
                    'Word': w['lemma'],
                    'Current Value': -1,
                    'NRC Arousal': arousal,
                    'Suggested': '0 or 1',
                    'Reason': 'Arousal > 0.4'
                })

            # Case 2: INTENSITY=-1, Arousal < 0.3 but is Verb
            # pos check: w['pos']
            is_verb = str(w['pos']).lower().startswith('v')
            if intensity == -1 and arousal < 0.3 and is_verb:
                # Avoid dups
                if not any(d['Word'] == w['lemma'] for d in intensity_candidates):
                    intensity_candidates.append({
                        'Word': w['lemma'],
                        'Current Value': -1,
                        'NRC Arousal': arousal,
                        'Suggested': '0',
                        'Reason': 'Low arousal verb (should be 0)'
                    })

    # Check 3: Semantic Sanity
    print("Running Check 3: Semantic Sanity Checks...")
    semantic_issues = []
    func_words = ['the', 'a', 'of', 'and', 'to', 'is', 'that', 'for', 'it', 'with']

    for w in top_words:
        lemma = w['lemma']

        # Function words > 5 primitives
        if lemma in func_words:
            active_count = len([v for v in w['primitives'].values() if v != 0])
            if active_count > 5:
                semantic_issues.append({
                    'Word': lemma, 'Issue': 'Function word > 5 primitives',
                    'Current': active_count, 'Expected': '<=5', 'Source': 'Rule'
                })

        # Verbs missing DO=1 and HAPPEN=1
        if str(w['pos']).lower().startswith('v'):
            has_do = get_prim(w, 'DO') == 1
            has_happen = get_prim(w, 'HAPPEN') == 1
            if not has_do and not has_happen:
                semantic_issues.append({
                    'Word': lemma, 'Issue': 'Verb missing DO/HAPPEN',
                    'Current': 'Neither', 'Expected': 'One of them=1', 'Source': 'Rule'
                })

        # Nouns with MOVE=1 but no BODY/SOMETHING
        if str(w['pos']).lower().startswith('n'):
            if get_prim(w, 'MOVE') == 1:
                has_body = get_prim(w, 'BODY') != 0
                has_something = get_prim(w, 'SOMETHING') != 0
                if not has_body and not has_something:
                    semantic_issues.append({
                        'Word': lemma, 'Issue': 'MOVE=1 without BODY/SOMETHING',
                        'Current': 'Missing entity', 'Expected': 'BODY or SOMETHING', 'Source': 'Rule'
                    })

        # Words with FEEL=1 but no SOMEONE/I/YOU
        if get_prim(w, 'FEEL') == 1:
            has_siy = (get_prim(w, 'SOMEONE') != 0 or get_prim(w, 'I') != 0 or get_prim(w, 'YOU') != 0)
            if not has_siy:
                semantic_issues.append({
                    'Word': lemma, 'Issue': 'FEEL=1 without Experiencer',
                    'Current': 'Missing', 'Expected': 'SOMEONE/I/YOU', 'Source': 'Rule'
                })

        # Words with SAY=1 but no WORDS=1
        if get_prim(w, 'SAY') == 1:
            if get_prim(w, 'WORDS') != 1:
                semantic_issues.append({
                    'Word': lemma, 'Issue': 'SAY=1 without WORDS=1',
                    'Current': f"WORDS={get_prim(w, 'WORDS')}", 'Expected': 'WORDS=1', 'Source': 'Rule'
                })

        # ALIVE=1 but inanimate
        if get_prim(w, 'ALIVE') == 1:
            if lemma.lower() in conc_map:
                try:
                    conc = float(conc_map[lemma.lower()]['Conc.M'])
                    if conc < 2.0:
                        semantic_issues.append({
                            'Word': lemma, 'Issue': 'ALIVE=1 but low concreteness',
                            'Current': f"Conc={conc}", 'Expected': '>2.0', 'Source': 'Concreteness'
                        })
                except:
                    pass

    # Check 4: Source Disagreement
    print("Running Check 4: Source Disagreements...")
    source_issues = []

    for w in top_words:
        lemma = w['lemma'].lower()

        # NRC VAD
        if lemma in nrc_vad_map:
            val = float(nrc_vad_map[lemma]['valence'])
            good = get_prim(w, 'GOOD')

            if val > 0.7 and good != 1:
                source_issues.append({
                    'Word': w['lemma'], 'Primitive': 'GOOD', 'Lexicon': good,
                    'External': f"Valence={val}", 'Source': 'NRC-VAD'
                })

            if val < 0.3 and good != -1:
                source_issues.append({
                    'Word': w['lemma'], 'Primitive': 'GOOD', 'Lexicon': good,
                    'External': f"Valence={val}", 'Source': 'NRC-VAD'
                })

        # Lancaster
        if lemma in lancaster_map:
            l_row = lancaster_map[lemma]
            try:
                # Need to handle potential empty strings if csv is messy, but assume floats
                ha = float(l_row.get('Hand_arm.mean', 0))
                fl = float(l_row.get('Foot_leg.mean', 0))
                threshold = 3.5
                if (ha > threshold or fl > threshold) and get_prim(w, 'BODY') == 0:
                    max_val = max(ha, fl)
                    source_issues.append({
                        'Word': w['lemma'], 'Primitive': 'BODY', 'Lexicon': 0,
                        'External': f"Sensorimotor={max_val}", 'Source': 'Lancaster'
                    })
            except ValueError:
                pass

    # Check 5: Extreme Activation
    print("Running Check 5: Extreme Activations...")
    extreme_issues = []

    for w in top_words:
        active_count = len([v for v in w['primitives'].values() if v != 0])

        if active_count > 25:
             extreme_issues.append({
                'Word': w['lemma'], 'Active Count': active_count, 'Issue': '> 25 primitives'
            })
        elif active_count == 0:
            if w['lemma'] not in func_words:
                 extreme_issues.append({
                    'Word': w['lemma'], 'Active Count': 0, 'Issue': '0 primitives'
                })

    # Generate Report
    print("Generating Report...")
    with open('data/audit_report.md', 'w') as f:
        f.write("# Lexicon Audit Report\n\n")

        total_issues = len(bipolar_issues) + len(intensity_candidates) + len(semantic_issues) + len(source_issues) + len(extreme_issues)

        f.write("## Summary\n")
        f.write(f"- Words audited: {len(top_words)}\n")
        f.write(f"- Total issues found: {total_issues}\n")
        f.write(f"- Critical (bipolar violations): {len(bipolar_issues)}\n")
        f.write(f"- High (semantic inconsistencies): {len(semantic_issues)}\n")
        f.write(f"- Medium (source disagreements): {len(source_issues)}\n")

        f.write("\n## Bipolar Violations\n")
        f.write("| Word | Pair | Values | Severity |\n")
        f.write("|------|------|--------|----------|\n")
        for i in bipolar_issues:
            f.write(f"| {i['Word']} | {i['Pair']} | {i['Values']} | {i['Severity']} |\n")

        f.write("\n## INTENSITY Bug Candidates\n")
        f.write("| Word | Current Value | NRC Arousal | Suggested | Reason |\n")
        f.write("|------|---------------|-------------|-----------|--------|\n")
        for i in intensity_candidates:
            f.write(f"| {i['Word']} | {i['Current Value']} | {i['NRC Arousal']:.3f} | {i['Suggested']} | {i['Reason']} |\n")

        f.write("\n## Semantic Issues\n")
        f.write("| Word | Issue | Current | Expected | Source |\n")
        f.write("|------|-------|---------|----------|--------|\n")
        for i in semantic_issues:
            f.write(f"| {i['Word']} | {i['Issue']} | {i['Current']} | {i['Expected']} | {i['Source']} |\n")

        f.write("\n## Source Disagreements\n")
        f.write("| Word | Primitive | Lexicon | External | Source |\n")
        f.write("|------|-----------|---------|----------|--------|\n")
        for i in source_issues:
            f.write(f"| {i['Word']} | {i['Primitive']} | {i['Lexicon']} | {i['External']} | {i['Source']} |\n")

        f.write("\n## Extreme Activations\n")
        f.write("| Word | Active Count | Issue |\n")
        f.write("|------|--------------|-------|\n")
        for i in extreme_issues:
            f.write(f"| {i['Word']} | {i['Active Count']} | {i['Issue']} |\n")

    print("Audit Complete. Report saved to data/audit_report.md")
    conn.close()

if __name__ == '__main__':
    run_audit()
