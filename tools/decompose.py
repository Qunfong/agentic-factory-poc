"""Turn a signed-off design idea's "Proposed features" list into feature issues (ADR-0018).

Reads design.md's "## Proposed features" section: each top-level "- " bullet is one feature title,
each indented "AC-n: ..." line below it one acceptance criterion. Creates one feature issue per
bullet that has at least one AC line, labelled `feature` with no intent gate - a person still
applies gate:intent-approved (ADR-016); decomposition only drafts the issue, it never starts an agent.

Usage: python tools/decompose.py --design-md PATH --issue N [--dry-run]
Needs GH_TOKEN and GITHUB_REPOSITORY to create issues, unless --dry-run.
"""
import argparse, os, pathlib, re, subprocess, sys

HEADING_RE = re.compile(r"^##\s+Proposed features\s*$", re.IGNORECASE)
NEXT_HEADING_RE = re.compile(r"^##\s+\S")
BULLET_RE = re.compile(r"^- (.+)$")
AC_RE = re.compile(r"^\s+(AC-\d+:.*)$")


def parse_features(text):
    """[(title, [ac_line, ...])] from the "## Proposed features" section; [] if there is none or
    every bullet there has no AC lines under it."""
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if HEADING_RE.match(l))
    except StopIteration:
        return []
    features = []
    for line in lines[start + 1:]:
        if NEXT_HEADING_RE.match(line):
            break
        m = BULLET_RE.match(line)
        if m:
            features.append((m.group(1).strip(), []))
            continue
        m = AC_RE.match(line)
        if m and features:
            features[-1][1].append(m.group(1).strip())
    return [(title, acs) for title, acs in features if acs]


def issue_body(design_issue, acs):
    return "\n".join([f"Decomposed from design idea #{design_issue} once it was signed off.",
                      "", "## Acceptance criteria", *acs]) + "\n"


def existing_titles(repo):
    out = subprocess.run(["gh", "issue", "list", "-R", repo, "--state", "all", "--limit", "500",
                          "--json", "title", "--jq", ".[].title"], capture_output=True, text=True, check=True).stdout
    return {t.strip() for t in out.splitlines()}


def design_docs_changed(since):
    """(issue number, path) for docs/design/D<n>/design.md files changed between `since` and HEAD."""
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AM", since, "HEAD", "--", "docs/design"],
                         capture_output=True, text=True, check=True).stdout
    found = []
    for path in out.splitlines():
        m = re.fullmatch(r"docs/design/D([1-9][0-9]*)/design\.md", path)
        if m:
            found.append((m.group(1), path))
    return found


def create_issue(repo, title, body, dry_run):
    if dry_run:
        print(f"::notice::would create feature issue: {title}")
        return
    subprocess.run(["gh", "issue", "create", "-R", repo, "--title", title, "--body", body, "--label", "feature"],
                   check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--design-md")
    p.add_argument("--issue")
    p.add_argument("--changed-since", help="git revision; process every design.md added or changed since it")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not a.dry_run and not repo:
        sys.exit("decompose: GITHUB_REPOSITORY is required unless --dry-run")
    if a.changed_since:
        docs = design_docs_changed(a.changed_since)
    elif a.design_md and a.issue and re.fullmatch(r"[1-9][0-9]*", a.issue):
        docs = [(a.issue, a.design_md)]
    else:
        sys.exit("decompose: give --changed-since REV, or --design-md PATH with --issue N (no leading zeros)")
    have = set() if a.dry_run else existing_titles(repo)
    made = 0
    for issue, path in docs:
        for title, acs in parse_features(pathlib.Path(path).read_text(encoding="utf-8")):
            if title in have:
                print(f"decompose: skip, an issue titled {title!r} already exists")
                continue
            create_issue(repo, title, issue_body(issue, acs), a.dry_run)
            have.add(title)
            made += 1
    print(f"decompose: {made} feature issue(s) created from {len(docs)} design doc(s)")


if __name__ == "__main__":
    main()
