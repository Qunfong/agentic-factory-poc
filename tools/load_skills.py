"""Load exactly the skills a role's charter lists (briefs 001 and 010).

factory/skills.lock.yaml pins every skill a factory agent may load by the sha256 of its directory.
A charter names each skill with that same hash. An unknown, unpinned or changed skill fails the run
before the agent starts, and so does a third-party skill whose source is still `reviewed: pending`.
Always-on skills are inlined into the role's prompt (tools/build_prompt.py), never installed.
On-trigger skills go to the run workspace's .claude/skills/ (delivery: workspace) or are named by path
in the prompt (delivery: prompt, for Codex, which reads no .claude/skills).
Standard library only, so it runs on a bare runner and on Windows.

Usage:
  python tools/load_skills.py <role> [--workspace DIR]   install the role's on-trigger skills
  python tools/load_skills.py --check       charters, lock and files agree (and match PyYAML when installed)
  python tools/load_skills.py --hash DIR    print a directory's content hash
  python tools/load_skills.py --tokens      estimated tokens (chars/4) each role's inlined always-on skills add
`--allow-pending` loads unreviewed sources; only the local tools/skill_eval.py may use it, never a workflow.
"""
import argparse, hashlib, math, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK = "factory/skills.lock.yaml"
CHARTERS = "factory/charters"
INSTALL_DIR = ".claude/skills"
GROUPS = ("always", "on_trigger")
DELIVERIES = ("workspace", "prompt")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
INTERACTIVE = "interactive"  # lock `use:` for a skill kept for people only; no charter may list it
LINK = re.compile(r"\]\(([^)\s]+)\)")
CODE_PATH = re.compile(r"`((?:\.\.?/)[^`\s]*|[^`\s]+\.md(?:#[^`\s]*)?)`")
CODE_NAME = re.compile(r"`([a-z0-9][a-z0-9-]*)`")
# Skill names --check knows besides the lock's (Q48): interactive-only and retired skills a loaded skill must not name.
UNLOADED_NAMES = ("create-verification-skill", "verify-meter", "architect", "blast-radius", "how", "why", "arena", "unslop", "ponytail")


class SkillError(Exception):
    pass


def parse_block(lines):
    """Block-style YAML mappings of plain scalars: the only shape the lock and a charter's skills: block use.
    Anything else (flow collections, lists, multi-line scalars) raises, so the format can't drift unnoticed."""
    root = {}
    stack = [(-1, root)]
    for n, raw in enumerate(lines, 1):
        line = re.sub(r"(^|\s)#.*$", "", raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, sep, value = line.strip().partition(":")
        if not sep or not key or key.startswith(("-", "{", "[")) or value[:1] not in ("", " "):
            raise SkillError(f"line {n}: expected `key: value` or `key:`, got {raw.strip()!r}")
        value = value.strip()
        if value[:1] in ("{", "[", "|", ">", "&", "*", "!"):
            raise SkillError(f"line {n}: use block style and plain scalars, got {value!r}")
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if not isinstance(parent, dict) or key in parent:
            raise SkillError(f"line {n}: bad nesting or duplicate key {key!r}")
        if value:
            parent[key] = value.strip("\"'")
        else:
            parent[key] = {}
            stack.append((indent, parent[key]))
    return root


def top_level_block(text, key):
    """The lines of one top-level key, including the key line, so parse_block can read one charter section."""
    out, inside = [], False
    for raw in text.splitlines():
        if raw[:1] not in ("", " ", "#"):
            inside = raw.split(":", 1)[0] == key
        if inside:
            out.append(raw)
    return out


def read_lock(root=ROOT):
    return parse_block((root / LOCK).read_text(encoding="utf-8").splitlines())


def read_charter_skills(role, root=ROOT):
    path = root / CHARTERS / f"{role}.yaml"
    if not path.is_file():
        raise SkillError(f"{role}: no charter at {CHARTERS}/{role}.yaml")
    skills = parse_block(top_level_block(path.read_text(encoding="utf-8"), "skills")).get("skills", {})
    for key, value in skills.items():
        if key == "delivery":
            if value not in DELIVERIES:
                raise SkillError(f"{role}: skills.delivery must be one of {DELIVERIES}")
        elif key not in GROUPS or not isinstance(value, dict):
            raise SkillError(f"{role}: skills: may hold only delivery and the groups {GROUPS}, got {key!r}")
    return skills


def tree_hash(directory):
    """sha256 over (relative path, file sha256) of every file, in path order. Symlinks are refused."""
    directory = pathlib.Path(directory)
    files = []
    for p in directory.rglob("*"):
        if p.is_symlink():
            raise SkillError(f"{p}: symlinks are not allowed in a skill")
        if p.is_file():
            files.append((p.relative_to(directory).as_posix(), p))
    h = hashlib.sha256()
    for rel, p in sorted(files):
        h.update(f"{rel}\0{hashlib.sha256(p.read_bytes()).hexdigest()}\n".encode())
    return h.hexdigest()


def pinned_dir(who, name, lock, root=ROOT, allow_pending=False):
    """The directory of a skill the lock pins by hash; a third-party one also needs a 40-hex commit and a reviewed source."""
    entry = lock.get("skills", {}).get(name)
    if entry is None:
        raise SkillError(f"{who}: {name}: not in {LOCK}")
    if not SHA256.match(entry.get("sha256", "")):
        raise SkillError(f"{who}: {name}: unpinned in {LOCK} (sha256 must be 64 hex)")
    if "source" in entry:
        src = lock.get("sources", {}).get(entry["source"], {})
        if not COMMIT.match(src.get("commit", "")):
            raise SkillError(f"{who}: {name}: source {entry['source']!r} is not pinned to a 40-hex commit")
        if src.get("reviewed", "pending") in ("", "pending") and not allow_pending:
            raise SkillError(f"{who}: {name}: source {entry['source']!r} is reviewed: pending in {LOCK}; "
                             "a human reviews the pin before any agent loads it")
    return root / entry["dir"]


def resolve(role, skills, lock, root=ROOT, groups=GROUPS, allow_pending=False):
    """[(name, group, source dir)] for the chosen groups of a charter's skills, each checked against the lock."""
    out = []
    for group in groups:
        for name, charter_hash in skills.get(group, {}).items():
            directory = pinned_dir(role, name, lock, root, allow_pending)
            lock_hash = lock["skills"][name]["sha256"]
            if charter_hash != lock_hash:
                raise SkillError(f"{role}: {name}: charter hash {charter_hash[:12]} differs from the lock's {lock_hash[:12]}")
            out.append((name, group, directory))
    return out


def verify(role, entries, lock):
    for name, _, directory in entries:
        if not (directory / "SKILL.md").is_file():
            raise SkillError(f"{role}: {name}: no SKILL.md in {directory}")
        actual = tree_hash(directory)
        if actual != lock["skills"][name]["sha256"]:
            raise SkillError(f"{role}: {name}: content hash {actual[:12]} of {directory} differs from {LOCK}")


def charter_entries(role, root=ROOT, allow_pending=False):
    """The role's whole charter, resolved and verified, so a bad or unreviewed skill fails every use of the role."""
    lock, skills = read_lock(root), read_charter_skills(role, root)
    entries = resolve(role, skills, lock, root, allow_pending=allow_pending)
    verify(role, entries, lock)
    return lock, skills, entries


def install(role, workspace, root=ROOT, allow_pending=False):
    """Empty <workspace>/.claude/skills and copy in the role's on-trigger skills (delivery: workspace),
    then verify the copies. Returns their names."""
    lock, skills, entries = charter_entries(role, root, allow_pending)
    chosen = [e for e in entries if e[1] == "on_trigger"] if delivery(skills) == "workspace" else []
    target = pathlib.Path(workspace) / INSTALL_DIR
    if target.is_symlink() or target.is_file():
        raise SkillError(f"{target} must be a plain directory")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    copies = [(name, group, target / name) for name, group, _ in chosen]
    for (_, _, src), (_, _, dst) in zip(chosen, copies):
        shutil.copytree(src, dst)
    verify(role, copies, lock)
    return [name for name, _, _ in chosen]


def frontmatter(skill_md):
    text = pathlib.Path(skill_md).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        raise SkillError(f"{skill_md}: no frontmatter")
    fields, key = {}, None
    for line in m.group(1).splitlines():
        if line.startswith(" ") and key:
            fields[key] = f"{fields[key]} {line.strip()}".strip()
            continue
        key, sep, value = line.partition(":")
        key = key.strip() if sep else None
        if key:
            fields[key] = value.strip().lstrip(">|-").strip().strip("\"'")
    return fields, m.group(2)


def prompt_section(role, root=ROOT, groups=GROUPS, allow_pending=False):
    """The role's skills for its prompt: always-on bodies inline, hash-checked; on-trigger named by path only
    for delivery: prompt (Codex). Claude Code finds workspace on-trigger skills in .claude/skills itself."""
    _, skills, entries = charter_entries(role, root, allow_pending)
    parts = []
    for name, group, directory in entries:
        if group not in groups:
            continue
        meta, body = frontmatter(directory / "SKILL.md")
        if group == "always":
            parts += [f"\n### Skill: {name}", body.strip()]
        elif delivery(skills) == "prompt":
            rel = directory.relative_to(root).as_posix()
            parts.append(f"\n### On trigger: {name}\n{meta.get('description', '')} When that applies, read `{rel}/SKILL.md` and follow it.")
    return "\n".join([f"\n## Skills (from {CHARTERS}/{role}.yaml)", *parts]) if parts else ""


def delivery(skills):
    return skills.get("delivery", "workspace")


def estimate_tokens(text):
    return math.ceil(len(text) / 4)


def always_on_tokens(role, root=ROOT):
    """Estimated tokens (chars/4) of each always-on body the role's prompt inlines."""
    _, _, entries = charter_entries(role, root, allow_pending=True)
    return {name: estimate_tokens(frontmatter(d / "SKILL.md")[1].strip()) for name, group, d in entries if group == "always"}


def pending_sources(root=ROOT):
    return sorted(n for n, s in read_lock(root).get("sources", {}).items() if s.get("reviewed", "pending") in ("", "pending"))


def outside_references(directory, root=ROOT):
    """References in a skill's markdown that do not resolve inside its own folder: link targets, and backticked
    paths that are .md files or start with ./ or ../. A backticked path that names an existing repo file outside
    factory/ (docs/adr/index.md) is the agent's workspace, not another skill, so it passes."""
    directory = pathlib.Path(directory).resolve()
    out = []
    for md in sorted(directory.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        refs = [(t, True) for t in LINK.findall(text)] + [(t, False) for t in CODE_PATH.findall(text)]
        for target, is_link in refs:
            path = target.split("#", 1)[0]
            if not path or re.match(r"^[a-z]+:", path):
                continue
            inside = [c for c in ((md.parent / path).resolve(), (directory / path).resolve())
                      if c.is_relative_to(directory) and c.exists()]
            workspace = (root / path).resolve()
            if inside or (not is_link and not path.startswith(".") and workspace.exists()
                          and not workspace.is_relative_to((root / "factory").resolve())):
                continue
            out.append(f"{md.relative_to(directory).as_posix()} -> {target}")
    return out


def dangling_names(role, entries, known):
    """A backticked skill name (`how`) in a skill the role loads, naming a known skill the role does not load (Q48)."""
    loaded = {name for name, _, _ in entries}
    return [f"{role}: {name}: {md.relative_to(directory).as_posix()} names `{token}`, which {role} does not load"
            for name, _, directory in entries for md in sorted(directory.rglob("*.md"))
            for token in sorted(set(CODE_NAME.findall(md.read_text(encoding="utf-8"))))
            if token in known and token not in loaded]


def roles(root=ROOT):
    return sorted(p.stem for p in (root / CHARTERS).glob("*.yaml"))


def check(root=ROOT):
    """Every charter resolves and verifies; every skill is pinned; no agent-loadable skill points outside its folder;
    no loaded skill names a known skill its role does not load;
    no charter lists an interactive-only skill; PyYAML (when present) reads the same data."""
    problems = []
    lock = read_lock(root)
    for name, entry in lock.get("skills", {}).items():
        if not SHA256.match(entry.get("sha256", "")):
            problems.append(f"{name}: unpinned in {LOCK}")
        elif tree_hash(root / entry["dir"]) != entry["sha256"]:
            problems.append(f"{name}: {entry['dir']} hash {tree_hash(root / entry['dir'])} differs from {LOCK}")
    for name, entry in lock.get("skills", {}).items():
        if entry.get("use", INTERACTIVE) != INTERACTIVE:
            problems.append(f"{name}: use: may only be {INTERACTIVE}")
        elif "use" not in entry and (root / entry["dir"]).is_dir():
            problems += [f"{name}: {ref} leaves the skill's folder" for ref in outside_references(root / entry["dir"], root)]
    for role in roles(root):
        try:
            skills = read_charter_skills(role, root)
            entries = resolve(role, skills, lock, root, allow_pending=True)
            verify(role, entries, lock)
        except SkillError as e:
            problems.append(str(e))
            continue
        problems += dangling_names(role, entries, {*lock.get("skills", {}), *UNLOADED_NAMES})
        problems += [f"{role}: {name} is use: {INTERACTIVE} in {LOCK}; no charter may list it"
                     for group in GROUPS for name in skills.get(group, {})
                     if lock["skills"][name].get("use") == INTERACTIVE]
    try:
        import yaml
    except ImportError:
        return problems
    def plain(x):
        return {k: plain(v) for k, v in x.items()} if isinstance(x, dict) else ({} if x is None else str(x))
    if plain(yaml.safe_load((root / LOCK).read_text(encoding="utf-8"))) != plain(lock):
        problems.append(f"{LOCK}: PyYAML reads it differently from load_skills")
    for role in roles(root):
        full = yaml.safe_load((root / CHARTERS / f"{role}.yaml").read_text(encoding="utf-8")) or {}
        if plain(full.get("skills") or {}) != plain(read_charter_skills(role, root)):
            problems.append(f"{role}: PyYAML reads skills: differently from load_skills")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("role", nargs="?")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--allow-pending", action="store_true", help="local skill evals only; never in a workflow")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--hash")
    ap.add_argument("--tokens", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.hash:
            print(tree_hash(a.hash))
        elif a.check:
            problems = check()
            for p in problems:
                print(p)
            print(f"{len(roles())} charters, {len(read_lock().get('skills', {}))} pinned skills, {len(problems)} problems")
            if pending_sources():
                print(f"reviewed: pending, so agents refuse their skills: {', '.join(pending_sources())}")
            return 1 if problems else 0
        elif a.tokens:
            for role in roles():
                section_tokens = estimate_tokens(prompt_section(role, groups=("always",), allow_pending=True))
                print(f"{role}: {section_tokens} inlined (estimate, chars/4, with headings) {always_on_tokens(role)}")
        elif a.role:
            names = install(a.role, a.workspace, allow_pending=a.allow_pending)
            print(f"{a.role}: loaded {names or 'no skills'} into {pathlib.Path(a.workspace) / INSTALL_DIR}")
        else:
            ap.error("give a role, --check, --hash or --tokens")
    except (SkillError, OSError) as e:
        print(f"load_skills: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
