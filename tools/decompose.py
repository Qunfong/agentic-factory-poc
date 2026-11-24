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


def create_issue(repo, title, body, dry_run):
    if dry_run:
        print(f"::notice::would create feature issue: {title}")
        return
    subprocess.run(["gh", "issue", "create", "-R", repo, "--title", title, "--body", body, "--label", "feature"],
                   check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--design-md", required=True)
    p.add_argument("--issue", required=True)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    if not re.fullmatch(r"[1-9][0-9]*", a.issue):
        sys.exit("decompose: --issue must be a decimal number without leading zeros")
    text = pathlib.Path(a.design_md).read_text(encoding="utf-8")
    features = parse_features(text)
    if not features:
        print('decompose: no "Proposed features" with acceptance criteria found; nothing to do')
        return
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not a.dry_run and not repo:
        sys.exit("decompose: GITHUB_REPOSITORY is required unless --dry-run")
    for title, acs in features:
        create_issue(repo, title, issue_body(a.issue, acs), a.dry_run)
    print(f"decompose: {len(features)} feature issue(s) from design idea #{a.issue}")


if __name__ == "__main__":
    main()
