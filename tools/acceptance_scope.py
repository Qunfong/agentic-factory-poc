"""Decide which hidden acceptance scenarios a PR must pass, and check a spec PR's AC IDs.

Scope by head branch (brief 007, ANSWERS Q4):
  wi-<issue>  that work item's ACs plus the ACs of every work item already merged into the base
  spec/F<n>   no scenarios; docs/specs/F<n>/ on the head must declare unique, well-formed AC IDs
  other       the ACs of every merged work item (regression)

Inputs are read only from places the PR cannot change:
  --base-specs   docs/specs at the PR's base commit (approved specs)
  --issues       `gh issue list --label work-item --state all --json number,title`
  --merged       `gh pr list --state merged --base <base> --json number,headRefName,isCrossRepository`
Output (stdout, for $GITHUB_OUTPUT): kind=<wi|spec|other> and scope=<space-separated AC IDs>.
Any error exits 1, so an unreadable input never turns into an empty scope.
"""
import argparse, dataclasses, json, pathlib, re, sys

AC_RE = re.compile(r"AC-F([1-9][0-9]*)-([1-9][0-9]*)")
AC_TOKEN = re.compile(r"\bAC-[A-Za-z0-9-]*[A-Za-z0-9]")
FEATURE_RE = re.compile(r"F([1-9][0-9]*)")
WI_BRANCH = re.compile(r"wi-([1-9][0-9]*)")
SPEC_BRANCH = re.compile(r"spec/(F[1-9][0-9]*)")
ISSUE_TITLE = re.compile(r"(F[1-9][0-9]*) ([^\s:]+): ")


class ScopeError(Exception):
    pass


@dataclasses.dataclass(frozen=True, order=True)
class AcId:
    feature: int
    n: int

    @classmethod
    def parse(cls, text):
        m = AC_RE.fullmatch(text) if isinstance(text, str) else None
        if not m:
            raise ScopeError(f"malformed AC ID {text!r}: expected AC-F<feature>-<n>, e.g. AC-F1-3")
        return cls(int(m.group(1)), int(m.group(2)))

    def __str__(self):
        return f"AC-F{self.feature}-{self.n}"


@dataclasses.dataclass(frozen=True)
class WorkItemPR:
    issue: int


@dataclasses.dataclass(frozen=True)
class SpecPR:
    feature: str


@dataclasses.dataclass(frozen=True)
class OtherPR:
    pass


def parse_branch(branch):
    if m := WI_BRANCH.fullmatch(branch):
        return WorkItemPR(int(m.group(1)))
    if branch.startswith("wi-"):
        raise ScopeError(f"branch {branch!r} looks like a work item but is not wi-<issue> without leading zeros")
    if m := SPEC_BRANCH.fullmatch(branch):
        return SpecPR(m.group(1))
    return OtherPR()


def work_item_errors(feature, items):
    """Why <feature>/work-items.json does not declare unique, well-formed AC IDs; [] when it does."""
    if not isinstance(items, list) or not items:
        return [f"{feature}/work-items.json must be a non-empty JSON array"]
    errors, seen = [], {}
    prefix = f"AC-{feature}-"
    ids = [item.get("id") if isinstance(item, dict) else None for item in items]
    for i, wid in enumerate(ids):
        if not isinstance(wid, str) or not re.fullmatch(r"[^\s:]+", wid) or ids.index(wid) != i:
            errors.append(f"{feature} work item {i + 1} needs a unique id without spaces or colons, got {wid!r}")
    for i, item in enumerate(items):
        ac_ids = item.get("ac_ids") if isinstance(item, dict) else None
        if not isinstance(ac_ids, list) or not ac_ids:
            errors.append(f"{feature} work item {i + 1} has no ac_ids")
            continue
        for raw in ac_ids:
            try:
                ac = AcId.parse(raw)
            except ScopeError as e:
                errors.append(f"{feature}: {e}")
                continue
            if not str(raw).startswith(prefix):
                errors.append(f"{feature}: {raw} belongs to another feature; IDs here start with {prefix}")
            elif ac in seen:
                errors.append(f"{feature}: duplicate AC ID {raw} (work items {seen[ac]} and {i + 1})")
            else:
                seen[ac] = i + 1
    return errors


def spec_errors(feature, items, spec_text):
    """work_item_errors, plus spec.md must describe exactly the declared AC IDs."""
    errors = work_item_errors(feature, items)
    if errors:
        return errors
    declared = {a for it in items for a in it["ac_ids"]}
    mentioned = set(AC_TOKEN.findall(spec_text))
    return [f"{feature}/spec.md: {t} is malformed or not declared in work-items.json"
           for t in sorted(mentioned - declared)] + [
        f"{feature}/spec.md: {a} has no behaviour described" for a in sorted(declared - mentioned)]


def load_work_items(specs_dir):
    """{(feature, work item id): (AcId, ...)} from every docs/specs/F<n>/work-items.json."""
    out = {}
    for path in sorted(pathlib.Path(specs_dir).glob("F*/work-items.json")):
        feature = path.parent.name
        if not FEATURE_RE.fullmatch(feature):
            continue
        items = json.loads(path.read_text(encoding="utf-8"))
        errors = work_item_errors(feature, items)
        if errors:
            raise ScopeError(f"base spec {feature} is invalid: " + "; ".join(errors))
        for item in items:
            out[(feature, item["id"])] = tuple(AcId.parse(a) for a in item["ac_ids"])
    return out


def work_item_key(issue, titles):
    title = titles.get(issue)
    if title is None:
        raise ScopeError(f"work-item issue #{issue} not found")
    m = ISSUE_TITLE.match(title)
    if not m:
        raise ScopeError(f"issue #{issue} title does not start with 'F<n> <work item id>: '")
    return m.group(1), m.group(2)


def merged_issues(merged_prs):
    return sorted({int(m.group(1)) for pr in merged_prs
                   if not pr["isCrossRepository"] and (m := WI_BRANCH.fullmatch(pr["headRefName"]))})


def acs_of(issue, titles, work_items):
    key = work_item_key(issue, titles)
    if key not in work_items:
        raise ScopeError(f"issue #{issue} is {key[0]} {key[1]}, which the base specs do not define")
    return work_items[key]


def scope(target, work_items, titles, merged):
    """The AC IDs the target PR must pass, sorted. `merged` holds merged work-item issue numbers."""
    if isinstance(target, SpecPR):
        return []
    acs = {a for issue in merged for a in acs_of(issue, titles, work_items)}
    if isinstance(target, WorkItemPR):
        acs |= set(acs_of(target.issue, titles, work_items))
    return sorted(acs)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--branch", required=True, help="the PR's head branch")
    p.add_argument("--base-specs", required=True)
    p.add_argument("--head-specs", required=True)
    p.add_argument("--issues", required=True)
    p.add_argument("--merged", required=True)
    a = p.parse_args(argv)
    try:
        target = parse_branch(a.branch)
        if isinstance(target, SpecPR):
            folder = pathlib.Path(a.head_specs) / target.feature
            items = json.loads((folder / "work-items.json").read_text(encoding="utf-8"))
            errors = spec_errors(target.feature, items, (folder / "spec.md").read_text(encoding="utf-8"))
            if errors:
                raise ScopeError("\n".join(errors))
        titles = {i["number"]: i["title"] for i in json.loads(pathlib.Path(a.issues).read_text(encoding="utf-8"))}
        merged = merged_issues(json.loads(pathlib.Path(a.merged).read_text(encoding="utf-8")))
        acs = scope(target, load_work_items(a.base_specs), titles, merged)
    except (ScopeError, OSError, ValueError, KeyError, TypeError) as e:
        print(f"::error::acceptance scope: {e}", file=sys.stderr)
        return 1
    kind = {WorkItemPR: "wi", SpecPR: "spec", OtherPR: "other"}[type(target)]
    print(f"kind={kind}")
    print(f"scope={' '.join(str(a) for a in acs)}")
    print(f"acceptance scope ({kind}, {len(merged)} merged work items): {' '.join(map(str, acs)) or 'no ACs in scope'}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
