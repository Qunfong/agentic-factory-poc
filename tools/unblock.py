"""Pure helpers: which blocked work items may start (dependencies merged). No I/O, easy to test."""


def parse_dependencies(body):
    """(feature, [work item ids]) from a work-item issue body written by create_work_items.py."""
    feature, deps = None, []
    for line in (body or "").splitlines():
        if line.startswith("Spec: docs/specs/"):
            parts = line.split("/")
            feature = parts[2] if len(parts) > 3 else None
        elif line.startswith("Depends on:"):
            deps = [d.strip() for d in line.split(":", 1)[1].split(",") if d.strip() and d.strip() != "-"]
    return feature, deps


def dependency_done(feature, wid, issues, merged_heads):
    """Done = the dependency's issue is CLOSED and a PR from branch wi-<n> was merged. Closing by hand
    (e.g. with `escalated`) must not unblock dependents."""
    for it in issues:
        if it["title"].startswith(f"{feature} {wid}:"):
            return it["state"] == "CLOSED" and f"wi-{it['number']}" in merged_heads
    return False


def ready_to_start(issues, merged_heads):
    """[(issue number, deps)] for open `blocked` work items whose dependencies are all done, plus
    [(issue number, None)] for blocked items that cannot be parsed (a person must look)."""
    out = []
    for it in issues:
        names = {l["name"] for l in it["labels"]}
        if it["state"] != "OPEN" or "blocked" not in names:
            continue
        feature, deps = parse_dependencies(it["body"])
        if not feature or not deps:
            out.append((it["number"], None))
        elif all(dependency_done(feature, d, issues, merged_heads) for d in deps):
            out.append((it["number"], deps))
    return out
