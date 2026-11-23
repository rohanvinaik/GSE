"""Does FrameNet's luIndex list every lexical unit its frame files contain? Complete counts by status.

The builder's adapter reads luIndex.xml. This compares it with the frame files themselves and lists
every frame-file lexical unit absent from the index for the frames the closeout rules join on.
"""

import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path.home() / "nltk_data/corpora/framenet_v17"
NS = "{http://framenet.icsi.berkeley.edu}"
FRAMES = ("Emotion_directed", "Experiencer_focus", "Fear", "Emotions_by_stimulus", "Desirability", "Size", "Dimension")


def main() -> int:
    index = {n.attrib["ID"]: n.attrib for n in ET.parse(ROOT / "luIndex.xml").getroot() if n.tag == NS + "lu"}
    units = {}
    for path in sorted((ROOT / "frame").glob("*.xml")):
        frame = ET.parse(path).getroot()
        for lu in frame.findall(NS + "lexUnit"):
            units[lu.attrib["ID"]] = {"frame": frame.attrib["name"], "name": lu.attrib["name"], "status": lu.attrib["status"]}
    report = {
        "frame_file_lexical_units": len(units),
        "index_lexical_units": len(index),
        "index_ids_absent_from_frame_files": sorted(set(index) - set(units)),
        "frame_file_units_by_status": dict(sorted(Counter(u["status"] for u in units.values()).items())),
        "indexed_units_by_status": dict(sorted(Counter(u["status"] for k, u in units.items() if k in index).items())),
        "index_status_attribute": dict(sorted(Counter(str(a.get("status")) for a in index.values()).items())),
        "unindexed_units_in_closeout_frames": {
            name: sorted(
                (f"{u['name']} [{u['status']}]" for k, u in units.items() if u["frame"] == name and k not in index)
            )
            for name in FRAMES
        },
        "indexed_unit_count_in_closeout_frames": {
            name: sum(1 for k, u in units.items() if u["frame"] == name and k in index) for name in FRAMES
        },
    }
    Path(sys.argv[1]).write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
