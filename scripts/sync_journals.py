"""Report (and optionally add) Pinakes journals missing from data/journals.yaml.

    python scripts/sync_journals.py PATH/TO/Rhet-Comp-Index/journals.py [--write]

Reads the Pinakes file with ast.literal_eval, so nothing in it is executed
and nothing is imported from Pinakes at runtime. New titles are appended as
bare entries (name, ISSN, URL, status) for hand curation; existing entries
are never modified. Titles in yaml but no longer in Pinakes are listed, not
removed: a journal leaving Pinakes is exactly the kind of thing to keep here.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jhc.journals import load_journals  # noqa: E402

LISTS = ["CROSSREF_JOURNALS", "RSS_JOURNALS", "SCRAPE_JOURNALS", "MANUAL_JOURNALS",
         "UNAVAILABLE_JOURNALS"]


def pinakes_entries(path: Path) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in LISTS:
                found[name] = ast.literal_eval(node.value)
    out = []
    for lst in LISTS:
        for j in found.get(lst, []):
            out.append({**j, "_list": lst})
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    src = Path(argv[0])
    write = "--write" in argv
    ours = {j.name for j in load_journals()}
    theirs = pinakes_entries(src)
    names = {j["name"] for j in theirs}

    new = [j for j in theirs if j["name"] not in ours]
    gone = sorted(ours - names)
    for j in new:
        print(f"+ {j['name']}  ({j['_list']})")
    for n in gone:
        print(f"  (not in Pinakes) {n}")
    if not new:
        print("no new Pinakes journals")

    if write and new:
        yaml_path = ROOT / "data" / "journals.yaml"
        lines = ["", "# ── Added by sync_journals.py; curate by hand ──"]
        for j in new:
            lines.append(f'- name: "{j["name"]}"')
            if j.get("issn"):
                lines.append(f"  issn_print: {j['issn']}  # check print/online")
            if j.get("url"):
                lines.append(f"  home_url: {j['url']}")
            if j["_list"] == "UNAVAILABLE_JOURNALS":
                lines.append("  status: unavailable")
        with yaml_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print(f"appended {len(new)} entr{'y' if len(new) == 1 else 'ies'} to {yaml_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
