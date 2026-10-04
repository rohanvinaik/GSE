#!/usr/bin/env python3
"""Analyze teaching epochs for performance metrics."""

import json
import sys
from pathlib import Path

# Find the session file
session_files = list(Path("data/teaching_sessions").glob("session_default_*.json"))
if not session_files:
    print("No session files found")
    sys.exit(1)

session_file = sorted(session_files)[-1]  # Most recent
with open(session_file) as f:
    data = json.load(f)

epochs = data['epochs']

# Get data at 10% intervals
checkpoints = [7, 14, 21, 28, 35, 42, 49, 56, 63, 72]

print("CHECKPOINT ANALYSIS (every ~10%)")
print("=" * 120)
print(f"{'Epoch':>6} | {'Document':40} | {'Updates':>8} | {'Sents':>8} | {'Words':>10} | {'dText':>9} | {'dPara':>9} | {'dSent':>9}")
print("-" * 120)

for cp in checkpoints:
    e = epochs[cp-1]
    doc_name = e['document'][:40]
    print(f"{e['epoch_number']:>6} | {doc_name:40} | {e['total_updates']:>8} | {e['sentences_processed']:>8} | {e['words_processed']:>10} | {e['deltas']['text']:>+9.5f} | {e['deltas']['paragraph']:>+9.5f} | {e['deltas']['sentence']:>+9.5f}")

print()
print("CUMULATIVE STATISTICS BY CHECKPOINT")
print("=" * 120)

running = {'updates': 0, 'sents': 0, 'words': 0, 'paras': 0, 'duration': 0}
prev_cp = 0
for cp in checkpoints:
    for ep in epochs[prev_cp:cp]:
        running['updates'] += ep['total_updates']
        running['sents'] += ep['sentences_processed']
        running['words'] += ep['words_processed']
        running['paras'] += ep['paragraphs_processed']
        running['duration'] += ep['duration_seconds']

    pct = (cp / 72) * 100
    ups = running['updates'] / max(0.1, running['duration'])
    wps = running['words'] / max(0.1, running['duration'])
    print(f"Epoch {cp:2d} ({pct:5.1f}%): {running['updates']:>7} updates | {running['sents']:>7} sents | {running['words']:>10,} words | {running['duration']:>6.2f}s | {ups:>8,.0f} updates/s | {wps:>10,.0f} words/s")
    prev_cp = cp

print()
print("WEIGHT NORM DELTAS (cumulative from start)")
print("=" * 120)

text_cum = 0
para_cum = 0
sent_cum = 0
orch_cum = 0

prev_cp = 0
for cp in checkpoints:
    for ep in epochs[prev_cp:cp]:
        text_cum += ep['deltas']['text']
        para_cum += ep['deltas']['paragraph']
        sent_cum += ep['deltas']['sentence']
        orch_cum += ep['deltas']['orchestrator']

    pct = (cp / 72) * 100
    print(f"Epoch {cp:2d} ({pct:5.1f}%): text={text_cum:>+9.5f} | para={para_cum:>+9.5f} | sent={sent_cum:>+9.5f} | orch={orch_cum:>+9.5f}")
    prev_cp = cp

print()
print("PROCESSING COMPLEXITY BY SEGMENT")
print("=" * 120)

prev_cp = 0
for cp in checkpoints:
    segment_updates = sum(ep['total_updates'] for ep in epochs[prev_cp:cp])
    segment_sents = sum(ep['sentences_processed'] for ep in epochs[prev_cp:cp])
    segment_words = sum(ep['words_processed'] for ep in epochs[prev_cp:cp])
    segment_paras = sum(ep['paragraphs_processed'] for ep in epochs[prev_cp:cp])
    segment_duration = sum(ep['duration_seconds'] for ep in epochs[prev_cp:cp])

    if segment_sents > 0:
        ups = segment_updates / segment_sents
        wps = segment_words / segment_sents
        tput = segment_words / max(0.01, segment_duration)
        print(f"Epochs {prev_cp+1:2d}-{cp:2d}: {ups:>6.3f} updates/sent | {wps:>6.1f} words/sent | {segment_paras:>6} paras | {tput:>10,.0f} words/s | {segment_duration:>5.2f}s")
    prev_cp = cp

print()
print("STATE SPACE ANALYSIS (theoretical vs actual)")
print("=" * 120)

# Calculate theoretical state space vs actual for sentence processing
total_sents = sum(ep['sentences_processed'] for ep in epochs)
total_words = sum(ep['words_processed'] for ep in epochs)
avg_sent_len = total_words / max(1, total_sents)

# Theoretical: N words * P primitives * P connections * N states
N_PRIMITIVES = 63  # From lexicon
THEORETICAL_PER_WORD = N_PRIMITIVES * N_PRIMITIVES  # Full connection matrix per word

# With grammar constraints: ~3 args * ~3 states
CONSTRAINED_PER_WORD = 3 * 3  # Grammar-constrained

# With dimension instantiation: O(1) per operation
INSTANTIATED_PER_WORD = 1  # Direct lookup

print(f"Average sentence length: {avg_sent_len:.1f} words")
print()
print("Theoretical state space per sentence (full matrix):")
print(f"  {avg_sent_len:.0f} words × {N_PRIMITIVES} primitives × {N_PRIMITIVES} connections = {avg_sent_len * THEORETICAL_PER_WORD:,.0f} operations")
print()
print("Grammar-constrained state space:")
print(f"  {avg_sent_len:.0f} words × 3 arguments × 3 states = {avg_sent_len * CONSTRAINED_PER_WORD:,.0f} operations")
print(f"  Reduction: {(1 - CONSTRAINED_PER_WORD/THEORETICAL_PER_WORD)*100:.1f}%")
print()
print("Dimension-instantiated operations (O(1) lookup):")
print(f"  {avg_sent_len:.0f} words × 1 direct operation = {avg_sent_len * INSTANTIATED_PER_WORD:.0f} operations")
print(f"  Total reduction: {(1 - INSTANTIATED_PER_WORD/THEORETICAL_PER_WORD)*100:.2f}%")
print()

# Actual updates vs theoretical
total_updates = sum(ep['total_updates'] for ep in epochs)
theoretical_ops = total_sents * avg_sent_len * THEORETICAL_PER_WORD
actual_ratio = total_updates / theoretical_ops

print("Empirical complexity:")
print(f"  Total sentences processed: {total_sents:,}")
print(f"  Total network updates: {total_updates:,}")
print(f"  Theoretical full-matrix ops: {theoretical_ops:,.0f}")
print(f"  Actual/Theoretical ratio: {actual_ratio:.6f} ({actual_ratio*100:.4f}%)")
print(f"  Orders of magnitude reduction: {-1 * (len(str(int(theoretical_ops))) - len(str(total_updates)))}")
