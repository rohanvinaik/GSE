import sys

sys.dont_write_bytecode = True
import json
from pathlib import Path

OUT = Path("/tmp/gse-subagents/noun-facts")
d = json.loads((OUT / "usas_framenet.json").read_text())
for w, pw in d["per_word"].items():
    for e in pw["framenet_noun_records"]:
        lu = e["this_lexUnit_as_listed_in_frame_file__not_retained_by_adapter"]
        a = lu["attributes"]
        print(
            f"{w:9} {e['record_id']} frame={e['frame']} luIndex_attrs={json.dumps(e['luIndex_xml_attributes_for_this_lu'])}"
        )
        print(f"          frame-file lexUnit attrs={json.dumps(a)} sentenceCount={lu['sentenceCount']} semTypes={lu['semTypes']}")
        print(f"          lexemes={lu['lexemes']}")
        print(f"          definition_raw={lu['definition_raw']!r}")

print("\nFE-level semTypes in noun frames:")
for name, fr in d["framenet"]["noun_frames"].items():
    for fe in fr["frame_elements"]:
        if fe["semTypes"]:
            print(f"  {name}.{fe['name']} ({fe['coreType']}): {fe['semTypes']}")
