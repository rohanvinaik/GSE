#!/usr/bin/env python3
"""
Quick test to verify NLTK resources are accessible and show sample data.
"""


def test_nltk():
    """Test NLTK availability and show sample data."""
    print("Testing NLTK Resource Access")
    print("=" * 60)

    # Test NLTK import
    try:
        import nltk
        print("✓ NLTK imported successfully")
    except ImportError:
        print("✗ NLTK not installed. Run: pip install nltk")
        return False

    # Download required data
    print("\nDownloading required NLTK data...")
    for corpus in ['framenet_v17', 'wordnet', 'omw-1.4']:
        try:
            nltk.data.find(f'corpora/{corpus}')
            print(f"  ✓ {corpus} already downloaded")
        except LookupError:
            print(f"  Downloading {corpus}...")
            nltk.download(corpus, quiet=True)

    # Test FrameNet
    print("\n" + "-" * 60)
    print("FRAMENET SAMPLE")
    print("-" * 60)

    try:
        from nltk.corpus import framenet as fn

        frames = list(fn.frames())
        print(f"Total frames: {len(frames)}")

        # Show sample frame
        sample_frame = fn.frame('Commerce_buy')
        print(f"\nSample Frame: {sample_frame.name}")
        print(f"  Definition: {sample_frame.definition[:100]}...")

        print("\n  Core Frame Elements:")
        for fe_name, fe in sample_frame.FE.items():
            if fe.coreType == 'Core':
                print(f"    - {fe_name}: {fe.definition[:60]}...")

        print("\n  Lexical Units (words in this frame):")
        for lu_name in list(sample_frame.lexUnit.keys())[:10]:
            print(f"    - {lu_name}")

        # Count total lexical units
        total_lus = sum(len(f.lexUnit) for f in frames)
        print(f"\nTotal lexical units across all frames: {total_lus}")

    except Exception as e:
        print(f"✗ FrameNet error: {e}")
        return False

    # Test WordNet
    print("\n" + "-" * 60)
    print("WORDNET SAMPLE")
    print("-" * 60)

    try:
        from nltk.corpus import wordnet as wn

        # Count synsets
        noun_count = len(list(wn.all_synsets('n')))
        verb_count = len(list(wn.all_synsets('v')))
        adj_count = len(list(wn.all_synsets('a')))
        adv_count = len(list(wn.all_synsets('r')))

        print("Synset counts:")
        print(f"  Nouns: {noun_count}")
        print(f"  Verbs: {verb_count}")
        print(f"  Adjectives: {adj_count}")
        print(f"  Adverbs: {adv_count}")
        print(f"  Total: {noun_count + verb_count + adj_count + adv_count}")

        # Show sample
        print("\nSample word: 'run'")
        for synset in wn.synsets('run')[:5]:
            print(f"  {synset.name()}: {synset.definition()[:60]}...")

        # Show semantic relations
        dog = wn.synset('dog.n.01')
        print("\nSemantic relations for 'dog.n.01':")
        print(f"  Hypernyms (is-a): {[h.name() for h in dog.hypernyms()]}")
        print(f"  Hyponyms (types): {[h.name() for h in dog.hyponyms()[:5]]}...")

        # Show antonyms
        good = wn.synset('good.a.01')
        good_lemma = good.lemmas()[0]
        if good_lemma.antonyms():
            print(f"\nAntonym of 'good': {good_lemma.antonyms()[0].name()}")

    except Exception as e:
        print(f"✗ WordNet error: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ All NLTK resources accessible!")
    print("=" * 60)

    return True


def show_mapping_opportunity():
    """Show how FrameNet maps to GSE concepts."""
    print("\n" + "=" * 60)
    print("FRAMENET → GSE MAPPING OPPORTUNITY")
    print("=" * 60)

    from nltk.corpus import framenet as fn

    # Interesting frames for GSE
    interesting_frames = [
        'Causation',
        'Communication',
        'Desiring',
        'Emotion_directed',
        'Experiencer_focus',
        'Intentionally_act',
        'Killing',
        'Motion',
        'Perception_active',
        'Statement',
    ]

    print("\nFrames with direct GSE relevance:")
    print("-" * 60)

    for frame_name in interesting_frames:
        try:
            frame = fn.frame(frame_name)
            print(f"\n{frame.name}:")
            print(f"  LUs: {len(frame.lexUnit)} words")

            # Show some lexical units
            lus = list(frame.lexUnit.keys())[:5]
            print(f"  Sample words: {', '.join(lus)}")

            # Show core frame elements (= semantic roles)
            core_fes = [fe for fe, info in frame.FE.items() if info.coreType == 'Core']
            print(f"  Core roles: {', '.join(core_fes)}")

        except Exception as e:
            print(f"  {frame_name}: not found ({e})")

    print("\n" + "-" * 60)
    print("These frames contain words with pre-annotated semantic roles!")
    print("The build_lexicon_from_nltk.py script maps these to GSE primitives.")


if __name__ == "__main__":
    if test_nltk():
        show_mapping_opportunity()

        print("\n" + "=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print("""
1. Build the expanded lexicon:
   python scripts/build_lexicon_from_nltk.py

2. Rebuild the database with vectors:
   python scripts/rebuild_lexicon.py

3. Run tests:
   python -m pytest tests/ -v

4. Try it out:
   python -c "from gse.pipeline import load_pipeline; p = load_pipeline(); print(p.process('The dog runs.'))"
""")
