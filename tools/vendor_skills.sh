#!/usr/bin/env bash
# Vendor the pinned third-party skills in factory/skills.lock.yaml into their dir (factory/skills/vendor/<name>).
# Each source is fetched at its 40-hex commit only, HEAD is checked, and each skill's hash is compared with the lock.
# Review the diff, then commit through a PR. Rerun any time: an unchanged pin reproduces the same files.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
"${PYTHON:-python}" - <<'PY'
import os, pathlib, re, shutil, stat, subprocess, sys, tempfile
sys.path.insert(0, "tools")
import load_skills

lock = load_skills.read_lock(pathlib.Path("."))
by_source = {}
for name, entry in lock["skills"].items():
    if "source" in entry:
        by_source.setdefault(entry["source"], []).append((name, entry))

def writable(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)

mismatch = []
for source, skills in by_source.items():
    src = lock["sources"][source]
    commit = src["commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        sys.exit(f"{source}: commit must be a 40-hex sha, got {commit!r}")
    tmp = tempfile.mkdtemp(prefix=f"vendor-{source}-")
    try:
        git = lambda *a: subprocess.run(["git", "-c", "core.autocrlf=false", "-C", tmp, *a], check=True, capture_output=True, text=True).stdout.strip()
        git("init", "--quiet")
        git("fetch", "--quiet", "--depth", "1", "--no-tags", src["repo"], commit)
        git("checkout", "--quiet", "--detach", "FETCH_HEAD")
        head = git("rev-parse", "HEAD")
        if head != commit:
            sys.exit(f"{source}: fetched {head}, expected {commit}")
        for name, entry in skills:
            dst = pathlib.Path(entry["dir"])
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(pathlib.Path(tmp, entry["path"]), dst)
            shutil.copy(pathlib.Path(tmp, src["license_file"]), dst / "LICENSE")
            actual = load_skills.tree_hash(dst)
            if actual != entry.get("sha256"):
                mismatch.append(f"{name}: sha256 {actual} (lock has {entry.get('sha256')!r})")
            print(f"vendored {name} from {source}@{commit[:12]} -> {dst} sha256 {actual}")
    finally:
        shutil.rmtree(tmp, onerror=writable)
if mismatch:
    sys.exit("update factory/skills.lock.yaml and every charter that lists these, after review:\n" + "\n".join(mismatch))
PY
