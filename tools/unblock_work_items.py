"""After a work-item PR merges, dispatch any other work item whose dependencies are now all closed.

depends_on sequencing (tools/create_work_items.py) labels a dependent work item `blocked` when it is
created, but nothing ever relabelled it once its dependency merged - own incident, found days after
F7 WI-1 (#17) merged while WI-2 (#11) and WI-3 (#12) sat `blocked` with no trigger to act on it.

Usage: python tools/unblock_work_items.py
Needs GH_TOKEN, GITHUB_REPOSITORY and WIP_LIMIT (same as create_work_items.py --dispatch-queued).
"""
import json, re, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from create_work_items import gh, dispatch  # noqa: E402

TITLE_RE = re.compile(r"^(F\d+) (WI-\d+):")
DEPENDS_RE = re.compile(r"^Depends on:\s*(.*)$", re.MULTILINE)


def parse_deps(body):
    """[WI-id, ...] from a work item's "Depends on: WI-1, WI-2" body line; [] for "-" or no match."""
    m = DEPENDS_RE.search(body or "")
    if not m or m.group(1).strip() == "-":
        return []
    return [d.strip() for d in m.group(1).split(",") if d.strip()]


def unblock():
    """Remove `blocked` and dispatch every open, blocked work item whose own feature's dependencies
    (by "F<n> WI-<m>:" title prefix) are all closed. Returns the dispatched issue numbers."""
    items = json.loads(gh("issue", "list", "--label", "work-item", "--state", "all", "--limit", "500",
                          "--json", "number,title,state,body,labels"))
    by_key = {}
    for it in items:
        m = TITLE_RE.match(it["title"])
        if m:
            by_key[(m.group(1), m.group(2))] = it
    dispatched = []
    for it in items:
        if it["state"] != "OPEN" or "blocked" not in [l["name"] for l in it["labels"]]:
            continue
        m = TITLE_RE.match(it["title"])
        if not m:
            continue
        deps = parse_deps(it["body"])
        dep_issues = [by_key.get((m.group(1), d)) for d in deps]
        if not deps or any(d is None or d["state"] != "CLOSED" for d in dep_issues):
            continue
        gh("issue", "edit", str(it["number"]), "--remove-label", "blocked")
        dispatch(it["number"])
        dispatched.append(it["number"])
    return dispatched


if __name__ == "__main__":
    done = unblock()
    print(f"unblock: dispatched {len(done)} work item(s): {done}" if done else "unblock: nothing to unblock")
