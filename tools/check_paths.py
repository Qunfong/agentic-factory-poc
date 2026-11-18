"""Path guard: fail if the change from an explicit base commit touches anything a role may not.

publish.yml runs this from the workflow's own commit, never from the tree it checks.
Usage: check_paths.py --base SHA [--expect-head SHA] --allow GLOB... [--protect-existing GLOB...] [--new-files-only]

Globs are case-sensitive. `**` as a whole segment crosses `/`; `*` and `?` do not.
"""
import argparse, dataclasses, pathlib, re, subprocess, sys

PUBLISHABLE = {"A", "M"}
LINK_MODES = {"120000": "symlink", "160000": "submodule"}


@dataclasses.dataclass(frozen=True)
class Glob:
    pattern: str
    regex: re.Pattern

    def matches(self, path):
        return self.regex.fullmatch(path) is not None


@dataclasses.dataclass(frozen=True)
class Change:
    status: str
    paths: tuple
    mode: str = ""


@dataclasses.dataclass(frozen=True)
class Policy:
    allow: tuple
    protect_existing: tuple = ()
    new_files_only: bool = False


def unsafe(path):
    """Why a repo path or pattern is not a plain relative path, or "" when it is."""
    if "\\" in path:
        return "backslash in path"
    if path.startswith("/") or re.match(r"[A-Za-z]:", path):
        return "absolute path"
    if any(seg in ("", ".", "..") for seg in path.split("/")):
        return "empty, '.' or '..' path segment"
    return ""


def compile_glob(pattern):
    reason = unsafe(pattern)
    if reason:
        raise ValueError(f"bad glob {pattern!r}: {reason}")
    segs = pattern.split("/")
    out = []
    for i, seg in enumerate(segs):
        last = i == len(segs) - 1
        if seg == "**":
            out.append(r"[^/]+(?:/[^/]+)*" if last else r"(?:[^/]+/)*")
            continue
        if "**" in seg:
            raise ValueError(f"bad glob {pattern!r}: '**' must be a whole segment")
        out.append("".join(r"[^/]*" if c == "*" else r"[^/]" if c == "?" else re.escape(c) for c in seg))
        if not last:
            out.append("/")
    return Glob(pattern, re.compile("".join(out)))


def violations(changes, policy, base_paths=frozenset()):
    """Every reason the changes break the policy. base_paths are the paths tracked at the base commit."""
    folded_base = {p.casefold(): p for p in base_paths}
    bad = []
    for c in changes:
        shown = " -> ".join(c.paths)
        for path in c.paths:
            reason = unsafe(path)
            if reason:
                bad.append(f"{path}: {reason}")
            elif not any(g.matches(path) for g in policy.allow):
                bad.append(f"{path}: outside allowed paths {[g.pattern for g in policy.allow]}")
        if c.status not in PUBLISHABLE:
            bad.append(f"{shown}: status {c.status} is not publishable (only A and M)")
        if c.mode in LINK_MODES:
            bad.append(f"{shown}: {LINK_MODES[c.mode]} is not publishable")
        if c.status == "M" and (policy.new_files_only or any(g.matches(c.paths[0]) for g in policy.protect_existing)):
            bad.append(f"{shown}: existing file changed; needs a protected-change request")
        twin = folded_base.get(c.paths[0].casefold(), c.paths[0])
        if c.status == "A" and twin != c.paths[0]:
            bad.append(f"{shown}: case variant of existing {twin}")
    return bad


def parse_raw(out, status=None):
    """Parse `git diff --raw -z` output into Changes, overriding each status when one is given."""
    tokens = out.split("\0")
    changes, i = [], 0
    while i < len(tokens) and tokens[i]:
        _, mode, _, _, st = tokens[i].lstrip(":").split()
        n = 2 if st[0] in "RC" else 1
        changes.append(Change(status or st, tuple(tokens[i + 1:i + 1 + n]), mode))
        i += 1 + n
    return changes


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def collect(base):
    """What a commit of the index would change from base, plus anything such a commit would not see."""
    changes = parse_raw(git("diff", "--cached", "--raw", "-z", "--no-renames", "--no-ext-diff", base))
    changes += parse_raw(git("diff", "--raw", "-z", "--no-renames", "--no-ext-diff"), status="unstaged")
    changes += [Change("untracked", (p,)) for p in git("ls-files", "--others", "--full-name", "-z").split("\0") if p]
    return changes


def filesystem_link_violations(changes):
    """A second, independent check on the working tree itself: a changed path that is actually a
    symlink, or whose resolved real path escapes the repository, regardless of what the raw-diff
    mode said. Defence in depth (Audit round 2, A2's own test turned out to be the bug, not the
    guard - see test_publish.py - but this check costs little and catches a case the mode field
    can't: a path reached through a symlinked parent directory). Fails closed: anything that can't
    be resolved (broken link, loop, permission error) is a violation, never silently skipped.
    Containment is against the repo's real root (own review, finding #6), not `Path.cwd()`: this
    function doesn't require the caller's cwd to be the repo root, only that it's inside one."""
    root = pathlib.Path(git("rev-parse", "--show-toplevel").strip()).resolve()
    bad = []
    for path in {p for c in changes for p in c.paths}:
        fp = root / path
        if fp.is_symlink():
            bad.append(f"{path}: symlink on disk is not publishable (filesystem check)")
        elif fp.exists():
            # Not just is_file() (own review, finding #3): a path reached only through a symlinked
            # ancestor directory is neither a symlink itself nor skippable just for being some
            # other type, so resolve and check containment regardless of what kind of entry it is.
            try:
                fp.resolve(strict=True).relative_to(root)
            except ValueError:
                bad.append(f"{path}: resolves outside the repository (filesystem check)")
            except OSError as e:
                bad.append(f"{path}: cannot resolve ({e.strerror or e}) (filesystem check)")
    return bad


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="commit the change is measured from")
    p.add_argument("--expect-head", help="fail unless HEAD is still this commit")
    p.add_argument("--allow", action="append", default=[])
    p.add_argument("--protect-existing", action="append", default=[])
    p.add_argument("--new-files-only", action="store_true")
    a = p.parse_args(argv)
    try:
        policy = Policy(tuple(map(compile_glob, a.allow)), tuple(map(compile_glob, a.protect_existing)),
                        a.new_files_only)
        base = git("rev-parse", "--verify", "--end-of-options", f"{a.base}^{{commit}}").strip()
        head = git("rev-parse", "--verify", "HEAD").strip()
        changes = collect(base)
        base_paths = frozenset(git("ls-tree", "-r", "-z", "--full-tree", "--name-only", base).split("\0")) - {""}
    except (ValueError, subprocess.CalledProcessError) as e:
        print(f"Path guard failed: {e}")
        return 1
    bad = violations(changes, policy, base_paths) + filesystem_link_violations(changes)
    if a.expect_head and head != a.expect_head:
        bad.append(f"HEAD moved from {a.expect_head} to {head}")
    if bad:
        print("Path guard failed:\n  " + "\n  ".join(bad))
        return 1
    print(f"Path guard ok ({len(changes)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
