"""Print the risk tier (green|amber|red) of the branch diff from --base, using factory/risk-map.yaml.

A path scores the highest tier of every rule it matches, or the map's default when none does.
The diff scores its highest path. FLOOR rules apply whatever the map says, and the map is read
from --base, so a branch can't lower its own tier.
"""
import argparse, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from check_paths import compile_glob, unsafe  # noqa: E402

ORDER = ("green", "amber", "red")
# Lowercase, so the case-folded score in path_tier also catches `Agents.md` or `.Claude/`. Nested
# AGENTS.md, CLAUDE.md and .claude/ steer agents as much as the root ones do.
FLOOR = tuple((compile_glob(p), "red") for p in (
    "tools/**", ".github/**", "factory/**", "**/.claude/**", "**/agents.md", "**/claude.md"))


def parse_risk_map(data):
    """(rules, default) from the parsed risk-map.yaml, with FLOOR rules added."""
    tiers = [r["tier"] for r in data["rules"]] + [data["default"]]
    unknown = sorted(set(tiers) - set(ORDER))
    if unknown:
        raise ValueError(f"unknown tier {unknown}; known: {ORDER}")
    rules = tuple((compile_glob(r["pattern"]), r["tier"]) for r in data["rules"]) + FLOOR
    return rules, data["default"]


def path_tier(path, rules, default):
    if unsafe(path):
        return "red"

    def score(p):
        hits = [t for g, t in rules if g.matches(p)]
        return max(hits, key=ORDER.index) if hits else default

    # Score the case-folded path too, so `Factory/x` or `.../Billing/...` can't dodge a lowercase rule.
    return max(score(path), score(path.casefold()), key=ORDER.index)


def diff_tier(paths, rules, default):
    if not paths:
        return default
    return max((path_tier(p, rules, default) for p in paths), key=ORDER.index)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="origin/master")
    a = p.parse_args(argv)
    import yaml
    rules, default = parse_risk_map(yaml.safe_load(git("show", f"{a.base}:factory/risk-map.yaml")))
    paths = [f for f in git("diff", "--name-only", "-z", "--no-renames", f"{a.base}...HEAD").split("\0") if f]
    print(diff_tier(paths, rules, default))


if __name__ == "__main__":
    main()
