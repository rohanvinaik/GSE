
import sqlite3
import os
import sys
from typing import List, Dict, Tuple, Any

DB_PATH = "data/lexicon.db"
REPORT_PATH = "data/stage1_audit_report.md"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(conn, query: str) -> List[sqlite3.Row]:
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Query failed: {e}")
        return []

def format_markdown_table(rows: List[sqlite3.Row], limit: int = None) -> str:
    if not rows:
        return "None"
    
    # Get column names from the first row keys
    columns = rows[0].keys()
    
    # Header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    
    lines = [header, separator]
    
    count = 0
    for row in rows:
        if limit and count >= limit:
            break
        values = [str(row[col]) for col in columns]
        line = "| " + " | ".join(values) + " |"
        lines.append(line)
        count += 1
        
    return "\n".join(lines)

def column_exists(conn, table_name, column_name):
    # Check if column exists
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]
    return column_name in columns

def check_component_type(conn):
    print("Running Component Type checks...")
    issues = {}
    
    has_component = column_exists(conn, 'lexemes', 'component_type')
    has_operator = column_exists(conn, 'lexemes', 'operator_type')

    issues['schema_error'] = []
    if not has_component:
        issues['schema_error'].append("Missing column: component_type")
    if not has_operator:
        issues['schema_error'].append("Missing column: operator_type")

    if not has_component:
        # Default empty/zero values if column missing
        issues['missing_component_type'] = "N/A (Column Missing)"
        issues['operator_missing_type_count'] = "N/A"
        issues['incorrect_atomic_count'] = "N/A"
        issues['missing_tam_aux_count'] = "N/A"
        issues['operator_missing_type_rows'] = []
        issues['incorrect_atomic_rows'] = []
        issues['missing_tam_aux_rows'] = []
        return issues
        
    # Words missing component_type
    q1 = "SELECT COUNT(*) as count FROM lexemes WHERE component_type IS NULL;"
    r1 = run_query(conn, q1)
    issues['missing_component_type'] = r1[0]['count'] if r1 else 0

    # OPERATORs missing operator_type
    q2 = "SELECT lemma, pos FROM lexemes WHERE component_type = 'OPERATOR' AND operator_type IS NULL;"
    r2 = run_query(conn, q2)
    issues['operator_missing_type_count'] = len(r2)
    issues['operator_missing_type_rows'] = r2

    # Known function words incorrectly marked ATOMIC
    function_words = "('the', 'a', 'not', 'very', 'in', 'on', 'and', 'or', 'is', 'are', 'was', 'were', 'did', 'will', 'have', 'be')"
    q3 = f"SELECT lemma, pos, component_type FROM lexemes WHERE lemma IN {function_words} AND component_type = 'ATOMIC';"
    r3 = run_query(conn, q3)
    issues['incorrect_atomic_count'] = len(r3)
    issues['incorrect_atomic_rows'] = r3

    # Auxiliaries not marked as TAM_AUXILIARY
    aux_words = "('be', 'am', 'is', 'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must')"
    q4 = f"SELECT lemma FROM lexemes WHERE lemma IN {aux_words} AND (component_type != 'OPERATOR' OR operator_type != 'TAM_AUXILIARY');"
    r4 = run_query(conn, q4)
    issues['missing_tam_aux_count'] = len(r4)
    issues['missing_tam_aux_rows'] = r4
    
    return issues

def check_syn_dimensions(conn):
    print("Running SYN dimensions checks...")
    issues = {}
    
    has_component = column_exists(conn, 'lexemes', 'component_type')
    atomic_filter = "AND l.component_type = 'ATOMIC'" if has_component else ""

    # Nouns missing SYN_SUBJ
    q1 = f"""
    SELECT COUNT(*) as count FROM lexemes l
    WHERE l.pos IN ('NOUN', 'NN', 'NNS', 'NNP', 'NNPS')
    AND NOT EXISTS (
        SELECT 1 FROM primitive_values pv
        WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_SUBJ'
    );
    """
    r1 = run_query(conn, q1)
    issues['nouns_missing_syn_subj'] = r1[0]['count'] if r1 else 0

    # Verbs missing SYN_PRED (excluding OPERATORs if possible)
    q2 = f"""
    SELECT COUNT(*) as count FROM lexemes l
    WHERE l.pos IN ('VERB', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ')
    {atomic_filter}
    AND NOT EXISTS (
        SELECT 1 FROM primitive_values pv
        WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_PRED'
    );
    """
    r2 = run_query(conn, q2)
    issues['verbs_missing_syn_pred'] = r2[0]['count'] if r2 else 0

    # Adjectives missing SYN_ADJ_MOD
    q3 = """
    SELECT COUNT(*) as count FROM lexemes l
    WHERE l.pos IN ('ADJ', 'JJ', 'JJR', 'JJS')
    AND NOT EXISTS (
        SELECT 1 FROM primitive_values pv
        WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_ADJ_MOD'
    );
    """
    r3 = run_query(conn, q3)
    issues['adj_missing_syn_adj_mod'] = r3[0]['count'] if r3 else 0

    return issues

def check_semantic_consistency(conn):
    print("Running Semantic Consistency checks...")
    issues = {}
    
    has_component = column_exists(conn, 'lexemes', 'component_type')
    has_operator = column_exists(conn, 'lexemes', 'operator_type')
    atomic_filter = "AND l.component_type = 'ATOMIC'" if has_component else ""

    # Rule 1: FEEL=1 without experiencer
    q1 = """
    SELECT l.lemma, l.pos FROM lexemes l
    JOIN primitive_values feel ON l.id = feel.lexeme_id AND feel.primitive = 'FEEL'
    WHERE feel.value = 1
    AND NOT EXISTS (
        SELECT 1 FROM primitive_values pv
        WHERE pv.lexeme_id = l.id AND pv.primitive IN ('SOMEONE', 'I', 'YOU') AND pv.value = 1
    )
    LIMIT 50;
    """
    r1 = run_query(conn, q1)
    issues['feel_no_experiencer_count'] = len(r1)
    issues['feel_no_experiencer_rows'] = r1

    # Rule 2: SAY=1 without WORDS
    q2 = """
    SELECT l.lemma FROM lexemes l
    JOIN primitive_values say ON l.id = say.lexeme_id AND say.primitive = 'SAY'
    LEFT JOIN primitive_values words ON l.id = words.lexeme_id AND words.primitive = 'WORDS'
    WHERE say.value = 1 AND (words.value IS NULL OR words.value != 1)
    LIMIT 50;
    """
    r2 = run_query(conn, q2)
    issues['say_no_words_count'] = len(r2) 
    issues['say_no_words_rows'] = r2

    # Rule 3: Bipolar violations (GOOD=1 AND BAD=1)
    q3 = """
    SELECT l.lemma, 'GOOD/BAD' as pair FROM lexemes l
    JOIN primitive_values g ON l.id = g.lexeme_id AND g.primitive = 'GOOD'
    JOIN primitive_values b ON l.id = b.lexeme_id AND b.primitive = 'BAD'
    WHERE g.value = 1 AND b.value = 1;
    """
    r3 = run_query(conn, q3)
    issues['bipolar_violations_count'] = len(r3)
    issues['bipolar_violations_rows'] = r3

    # Rule 5: Verbs missing DO/HAPPEN
    q5 = f"""
    SELECT l.lemma FROM lexemes l
    WHERE l.pos IN ('VERB', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ')
    {atomic_filter}
    AND NOT EXISTS (
        SELECT 1 FROM primitive_values pv
        WHERE pv.lexeme_id = l.id AND pv.primitive IN ('DO', 'HAPPEN') AND pv.value = 1
    )
    LIMIT 50;
    """
    r5 = run_query(conn, q5)
    issues['verbs_missing_do_happen_count'] = len(r5)
    issues['verbs_missing_do_happen_rows'] = r5

    # Rule 8: OPERATORs with too many primitives
    if has_component:
        q8 = """
        SELECT l.lemma, l.operator_type, COUNT(*) as prim_count
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id
        WHERE l.component_type = 'OPERATOR' AND pv.value != 0
        GROUP BY l.lemma
        HAVING prim_count > 2
        ORDER BY prim_count DESC
        LIMIT 30;
        """
        r8 = run_query(conn, q8)
        issues['operator_excess_prims_count'] = len(r8)
        issues['operator_excess_prims_rows'] = r8
    else:
        issues['operator_excess_prims_count'] = "N/A (Column Missing)"
        issues['operator_excess_prims_rows'] = []

    # Rule 10: SING/PLUR/ZERO Mutual Transparency Violation
    # If ZERO=1, neither SING nor PLUR should be 1
    q10 = """
    SELECT l.lemma,
           sing.value as SING,
           plur.value as PLUR,
           zero.value as ZERO
    FROM lexemes l
    JOIN primitive_values zero ON l.id = zero.lexeme_id AND zero.primitive = 'ZERO'
    LEFT JOIN primitive_values sing ON l.id = sing.lexeme_id AND sing.primitive = 'SING'
    LEFT JOIN primitive_values plur ON l.id = plur.lexeme_id AND plur.primitive = 'PLUR'
    WHERE zero.value = 1
      AND (COALESCE(sing.value, 0) = 1 OR COALESCE(plur.value, 0) = 1);
    """
    r10 = run_query(conn, q10)
    issues['transparency_violations_count'] = len(r10)
    issues['transparency_violations_rows'] = r10

    return issues

def check_grammatical_features(conn):
    print("Running Grammatical Feature checks...")
    issues = {}
    
    has_gram_features = False
    # Check if table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gram_feature_values';")
    if cursor.fetchone():
        has_gram_features = True
        
    issues['missing_table'] = not has_gram_features
    
    if not has_gram_features:
        issues['pronoun_missing_person_count'] = "N/A (Table Missing)"
        issues['determiner_missing_def_count'] = "N/A (Table Missing)"
        issues['numeral_missing_sing_zero_count'] = "N/A (Table Missing)" # actually this checks primitives but grouping here
        issues['pronoun_missing_person_rows'] = []
        issues['determiner_missing_def_rows'] = []
        issues['numeral_missing_sing_zero_rows'] = []
        # We can still check numerals as that uses primitive_values
    
    # Pronouns with SOMEONE=1 should have person feature
    if has_gram_features:
        q1 = """
        SELECT l.lemma, 'missing person' as issue
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.primitive = 'SOMEONE' AND pv.value = 1
        WHERE l.lemma IN ('i', 'me', 'my', 'mine', 'myself',
                          'you', 'your', 'yours', 'yourself',
                          'he', 'him', 'his', 'she', 'her', 'hers',
                          'it', 'its', 'we', 'us', 'our', 'ours',
                          'they', 'them', 'their', 'theirs')
        AND NOT EXISTS (
            SELECT 1 FROM gram_feature_values gf
            WHERE gf.lexeme_id = l.id AND gf.feature = 'person'
        );
        """
        r1 = run_query(conn, q1)
        issues['pronoun_missing_person_count'] = len(r1)
        issues['pronoun_missing_person_rows'] = r1

        # Determiners should have definiteness feature
        q2 = """
        SELECT l.lemma, 'missing definiteness' as issue
        FROM lexemes l
        WHERE l.operator_type = 'DETERMINER'
        AND NOT EXISTS (
            SELECT 1 FROM gram_feature_values gf
            WHERE gf.lexeme_id = l.id AND gf.feature = 'definiteness'
        );
        """
        r2 = run_query(conn, q2)
        issues['determiner_missing_def_count'] = len(r2)
        issues['determiner_missing_def_rows'] = r2
    
    # Numerals should have SING or ZERO (Primitive check, but categorized under Gram Features in prompts)
    q3 = """
    SELECT l.lemma, 'missing SING/ZERO' as issue
    FROM lexemes l
    WHERE l.lemma IN ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
                      'eight', 'nine', 'ten', 'first', 'second', 'third', 'fourth')
    AND NOT EXISTS (
        SELECT 1 FROM primitive_values pv
        WHERE pv.lexeme_id = l.id AND pv.primitive IN ('SING', 'ZERO') AND pv.value = 1
    );
    """
    r3 = run_query(conn, q3)
    issues['numeral_missing_sing_zero_count'] = len(r3)
    issues['numeral_missing_sing_zero_rows'] = r3

    return issues

def check_modifier_hierarchy(conn):
    print("Running Modifier Hierarchy checks...")
    issues = {}
    
    has_operator = column_exists(conn, 'lexemes', 'operator_type')

    # INTENSITY=-1 is WRONG
    q1 = """
    SELECT l.lemma, i.value as INTENSITY
    FROM lexemes l
    JOIN primitive_values i ON l.id = i.lexeme_id AND i.primitive = 'INTENSITY'
    WHERE i.value < 0;
    """
    r1 = run_query(conn, q1)
    issues['negative_intensity_count'] = len(r1)
    issues['negative_intensity_rows'] = r1

    # Check degree modifiers for correct encoding
    if has_operator:
        q2 = """
        SELECT l.lemma, l.operator_type,
               COALESCE(i.value, 'NULL') as INTENSITY,
               COALESCE(hp.value, 'NULL') as HIER_PLUS,
               COALESCE(hm.value, 'NULL') as HIER_MINUS
        FROM lexemes l
        LEFT JOIN primitive_values i ON l.id = i.lexeme_id AND i.primitive = 'INTENSITY'
        LEFT JOIN primitive_values hp ON l.id = hp.lexeme_id AND hp.primitive = 'HIER_PLUS'
        LEFT JOIN primitive_values hm ON l.id = hm.lexeme_id AND hm.primitive = 'HIER_MINUS'
        WHERE l.operator_type = 'DEGREE';
        """
        r2 = run_query(conn, q2)
        issues['degree_modifier_check_rows'] = r2
    else:
        issues['degree_modifier_check_rows'] = []
    
    return issues

def check_empty_banks(conn):
    print("Running Empty Banks checks...")
    issues = {}
    
    has_component = column_exists(conn, 'lexemes', 'component_type')
    atomic_filter = "AND l.component_type = 'ATOMIC'" if has_component else ""

    # Words with zero active primitives (excluding OPERATORs if possible)
    q1 = f"""
    SELECT l.lemma, l.pos FROM lexemes l
    WHERE l.frequency_rank <= 5000
    {atomic_filter}
    AND NOT EXISTS (
        SELECT 1 FROM primitive_values pv
        WHERE pv.lexeme_id = l.id AND pv.value != 0
    );
    """
    # Note: excluding component_type from select if it might not exist? 
    # Actually the prompt Select included it, but I should probably just select what exists.
    # The WHERE clause handles the filter.
    
    if has_component:
        # Original query if column exists
        q1 = """
        SELECT l.lemma, l.pos, l.component_type FROM lexemes l
        WHERE l.component_type = 'ATOMIC'
        AND l.frequency_rank <= 5000
        AND NOT EXISTS (
            SELECT 1 FROM primitive_values pv
            WHERE pv.lexeme_id = l.id AND pv.value != 0
        );
        """
    
    r1 = run_query(conn, q1)
    issues['atomic_no_prims_count'] = len(r1)
    issues['atomic_no_prims_rows'] = r1
    
    return issues

def generate_report(results):
    print(f"Generating report to {REPORT_PATH} ...")
    
    comp_issues = results['component']
    syn_issues = results['syn']
    sem_issues = results['semantic']
    gram_issues = results['grammatical']
    mod_issues = results['modifier']
    empty_issues = results['empty']
    
    # Calculate total issues (ignoring N/A strings)
    def safe_add(iterable):
        total = 0
        for x in iterable:
            if isinstance(x, int):
                total += x
        return total

    total_issues = safe_add([
        comp_issues.get('missing_component_type'),
        comp_issues.get('operator_missing_type_count'),
        comp_issues.get('incorrect_atomic_count'),
        syn_issues.get('nouns_missing_syn_subj'),
        syn_issues.get('verbs_missing_syn_pred'),
        syn_issues.get('adj_missing_syn_adj_mod'),
        sem_issues.get('feel_no_experiencer_count'),
        sem_issues.get('say_no_words_count'),
        sem_issues.get('bipolar_violations_count'),
        sem_issues.get('verbs_missing_do_happen_count'),
        sem_issues.get('operator_excess_prims_count'),
        sem_issues.get('transparency_violations_count'),
        gram_issues.get('pronoun_missing_person_count'),
        gram_issues.get('determiner_missing_def_count'),
        gram_issues.get('numeral_missing_sing_zero_count'),
        mod_issues.get('negative_intensity_count'),
        empty_issues.get('atomic_no_prims_count')
    ])

    with open(REPORT_PATH, 'w') as f:
        f.write("# Stage 1 Audit Report\n\n")
        f.write("## Summary\n")
        
        if comp_issues.get('schema_error'):
            f.write("> [!WARNING]\n")
            f.write("> **CRITICAL SCHEMA FAILURES DETECTED**\n")
            for err in comp_issues['schema_error']:
                f.write(f"> - {err}\n")
            f.write("\n")
        
        f.write("- Words audited: Top 5000 (roughly)\n")
        f.write(f"- Total issues found: {total_issues}\n\n")
        
        f.write("### Issue Counts by Category\n")
        f.write("| Category | Count |\n")
        f.write("|----------|-------|\n")
        f.write(f"| Missing component_type | {comp_issues['missing_component_type']} |\n")
        f.write(f"| OPERATORs missing operator_type | {comp_issues['operator_missing_type_count']} |\n")
        f.write(f"| Function words incorrectly ATOMIC | {comp_issues['incorrect_atomic_count']} |\n")
        f.write(f"| Missing SYN_* dimensions | {safe_add([syn_issues['nouns_missing_syn_subj'], syn_issues['verbs_missing_syn_pred'], syn_issues['adj_missing_syn_adj_mod']])} |\n")
        f.write(f"| FEEL without experiencer | {sem_issues['feel_no_experiencer_count']} |\n")
        f.write(f"| SAY without WORDS | {sem_issues['say_no_words_count']} |\n")
        f.write(f"| Bipolar violations | {sem_issues['bipolar_violations_count']} |\n")
        f.write(f"| Verbs missing DO/HAPPEN | {sem_issues['verbs_missing_do_happen_count']} |\n")
        f.write(f"| OPERATORs with excessive primitives | {sem_issues.get('operator_excess_prims_count', 0)} |\n")
        f.write(f"| Wrong INTENSITY encoding | {mod_issues['negative_intensity_count']} |\n")
        f.write(f"| ATOMICs with no primitives | {empty_issues['atomic_no_prims_count']} |\n")
        f.write(f"| **SING/PLUR/ZERO violations** | {sem_issues.get('transparency_violations_count', 0)} |\n")
        f.write(f"| **Pronouns missing gram features** | {gram_issues.get('pronoun_missing_person_count', 0)} |\n")
        f.write(f"| **Determiners missing definiteness** | {gram_issues.get('determiner_missing_def_count', 0)} |\n")
        f.write(f"| **Numerals missing SING/ZERO** | {gram_issues.get('numeral_missing_sing_zero_count', 0)} |\n\n")

        f.write("## Component Type Issues\n")
        if comp_issues['operator_missing_type_rows']:
            f.write("### OPERATORs missing operator_type\n")
            f.write(format_markdown_table(comp_issues['operator_missing_type_rows']) + "\n\n")
        
        if comp_issues['incorrect_atomic_rows']:
            f.write("### Known function words incorrectly marked ATOMIC\n")
            f.write(format_markdown_table(comp_issues['incorrect_atomic_rows']) + "\n\n")
            
        if comp_issues['missing_tam_aux_rows']:
            f.write("### Auxiliaries not marked as TAM_AUXILIARY\n")
            f.write(format_markdown_table(comp_issues['missing_tam_aux_rows']) + "\n\n")

        f.write("## SYN_* Dimension Issues\n")
        f.write("| POS Category | Missing Count |\n")
        f.write("|--------------|---------------|\n")
        f.write(f"| Nouns (SYN_SUBJ) | {syn_issues['nouns_missing_syn_subj']} |\n")
        f.write(f"| Verbs (SYN_PRED) | {syn_issues['verbs_missing_syn_pred']} |\n")
        f.write(f"| Adjectives (SYN_ADJ_MOD) | {syn_issues['adj_missing_syn_adj_mod']} |\n\n")

        f.write("## Semantic Consistency Issues\n")
        
        if sem_issues['feel_no_experiencer_rows']:
             f.write("### FEEL=1 without experiencer (First 50)\n")
             f.write(format_markdown_table(sem_issues['feel_no_experiencer_rows']) + "\n\n")
        
        if sem_issues['say_no_words_rows']:
             f.write("### SAY=1 without WORDS (First 50)\n")
             f.write(format_markdown_table(sem_issues['say_no_words_rows']) + "\n\n")

        if sem_issues['bipolar_violations_rows']:
             f.write("### Bipolar violations (GOOD=1 AND BAD=1)\n")
             f.write(format_markdown_table(sem_issues['bipolar_violations_rows']) + "\n\n")
             
        if sem_issues['verbs_missing_do_happen_rows']:
             f.write("### Verbs missing DO/HAPPEN (First 50)\n")
             f.write(format_markdown_table(sem_issues['verbs_missing_do_happen_rows']) + "\n\n")

             f.write("### OPERATORs with too many primitives (>2)\n")
             f.write(format_markdown_table(sem_issues['operator_excess_prims_rows']) + "\n\n")
        
        if sem_issues.get('transparency_violations_rows'):
             f.write("## SING/PLUR/ZERO Mutual Transparency Violations (NEW)\n")
             f.write(format_markdown_table(sem_issues['transparency_violations_rows']) + "\n\n")
             
        f.write("## Grammatical Feature Issues (NEW)\n")
        if gram_issues.get('missing_table'):
             f.write("> [!WARNING]\n")
             f.write("> **MISSING TABLE: gram_feature_values**\n\n")
             
        if gram_issues.get('pronoun_missing_person_rows'):
             f.write("### Pronouns missing gram features\n")
             f.write(format_markdown_table(gram_issues['pronoun_missing_person_rows']) + "\n\n")
             
        if gram_issues.get('determiner_missing_def_rows'):
             f.write("### Determiners missing definiteness\n")
             f.write(format_markdown_table(gram_issues['determiner_missing_def_rows']) + "\n\n")
             
        if gram_issues.get('numeral_missing_sing_zero_rows'):
             f.write("### Numerals missing SING/ZERO\n")
             f.write(format_markdown_table(gram_issues['numeral_missing_sing_zero_rows']) + "\n\n")
        
        f.write("## Modifier Hierarchy Issues\n")
        if mod_issues['negative_intensity_rows']:
            f.write("### INTENSITY = -1 (Should be +1)\n")
            f.write(format_markdown_table(mod_issues['negative_intensity_rows']) + "\n\n")
            
        if mod_issues['degree_modifier_check_rows']:
             f.write("### Degree Modifiers Check\n")
             f.write(format_markdown_table(mod_issues['degree_modifier_check_rows']) + "\n\n")

        f.write("## Empty Bank Issues\n")
        if empty_issues['atomic_no_prims_rows']:
            f.write(f"### ATOMIC words with no primitives (Top 5000) - Count: {empty_issues['atomic_no_prims_count']}\n")
            # Only show top 50
            f.write(format_markdown_table(empty_issues['atomic_no_prims_rows'], limit=50) + "\n\n")

def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = get_db_connection()
    try:
        results = {}
        results['component'] = check_component_type(conn)
        results['syn'] = check_syn_dimensions(conn)
        results['semantic'] = check_semantic_consistency(conn)
        results['grammatical'] = check_grammatical_features(conn)
        results['modifier'] = check_modifier_hierarchy(conn)
        results['empty'] = check_empty_banks(conn)
        
        generate_report(results)
        print("Audit complete.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
