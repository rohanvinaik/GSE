import sys

sys.dont_write_bytecode = True
import json
from pathlib import Path

d = json.loads(Path("/tmp/gse-subagents/noun-facts/wordnet.json").read_text(encoding="utf-8"))
a = d["availability"]
print("directory exists:", a["directory_corpora_wordnet_exists"])
print("wordnet.zip sha256:", a["archives"]["wordnet.zip"]["sha256"], "size", a["archives"]["wordnet.zip"]["size_bytes"])
print("version:", a["wordnet_version_reported_by_reader"], "| nltk:", a["nltk_version"], "| reader root:", a["reader_root"])
for name, text in a["wordnet_zip_small_documentation_members"].items():
    print("\n=====", name, "=====")
    print(text)
