"""Turn one agent's patch into a commit on its branch, inside the trusted publish job.

The patch is the only thing an agent job hands over. Everything else (branch, guard,
commit message, PR title, body and labels) comes from ROLES and the caller's trusted inputs.
Run with the working tree checked out at --base-sha. Pushing and the PR stay in publish.yml.
"""
import argparse, dataclasses, os, pathlib, re, subprocess, sys

MAX_PATCH_BYTES = 2 * 1024 * 1024
BRANCH_RE = re.compile(r"^(spec/F[1-9][0-9]*|wi-[1-9][0-9]*|design/D[1-9][0-9]*)$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
BOT = ("factory-bot", "factory-bot@users.noreply.github.com")
STUB_MARKER = "// factory-test-stub"


@dataclasses.dataclass(frozen=True)
class Role:
    branch: str
    guard: tuple
    subject: str
    assisted_by: str
    pr: bool = False
    pr_title: str = ""
    pr_body: str = ""
    labels: tuple = ()
    tier_label: bool = False


ROLES = {
    "spec-writer": Role(
        branch="spec/F{issue}",
        guard=("--allow", "docs/specs/F{issue}/**", "--allow", "docs/adr/proposed-*.md"),
        subject="spec: F{issue}",
        assisted_by="claude-code:claude-opus-5-5",
        pr=True,
        pr_title="spec: F{issue} {title}",
        pr_body="Spec, plan, work items and ADR proposals for #{issue}. "
                "Merging this PR is the **plan gate** (tech lead, see CODEOWNERS).",
        labels=("spec",),
    ),
    "design-writer": Role(
        branch="design/D{issue}",
        guard=("--allow", "docs/design/D{issue}/**", "--allow", "docs/adr/proposed-*.md"),
        subject="design: D{issue}",
        assisted_by="claude-code:claude-opus-5-5",
        pr=True,
        pr_title="design: D{issue} {title}",
        pr_body="Design idea, open questions and ADR proposals for #{issue}. "
                "Merging this PR is the **idea sign-off** (tech lead, see CODEOWNERS); it is not auto-merged.",
        labels=("design",),
    ),
    "tester": Role(
        branch="wi-{issue}",
        guard=("--allow", "app/src/test/**", "--new-files-only"),
        subject="test: WI #{issue}",
        assisted_by="litellm:{tester_model}",
    ),
    "builder": Role(
        branch="wi-{issue}",
        guard=("--allow", "app/src/main/**"),
        subject="feat: WI #{issue} (round {round})",
        assisted_by="claude-code:claude-opus-5-5",
        pr=True,
        pr_title="{title}",
        pr_body="Closes #{issue}",
        labels=("agent",),
        tier_label=True,
    ),
}


class Rejected(Exception):
    pass


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode:
        raise Rejected(f"git {args[0]} failed: {r.stderr.strip()[:500]}")
    return r


def remove_shadowed_stubs():
    """Trusted side-effect of a builder publish only: a tester-written compile-time stub (round 0,
    before the real class exists) and the builder's real class can end up with the same path under
    app/src/test/** and app/src/main/**. Maven puts test-classes ahead of classes on the test
    classpath, so an empty stub left behind silently shadows the real implementation forever - not
    a build failure, a 404 at runtime (own incident, F7 WI-1).

    Deletes exactly one thing: a file at app/src/test/<rest> whose first line is the literal
    STUB_MARKER, and only when this same guarded patch just added app/src/main/<rest>. Never the
    agent's own doing - the builder's tools never reach outside app/src/main/**, and this never
    touches a file without the exact marker, so a same-named real test is never at risk. Runs after
    the guard, on the already-validated patch; the deletion itself needs no guard of its own
    because it isn't driven by anything the agent wrote beyond the path it added.
    """
    added = git("diff", "--cached", "--name-status", "--no-renames").stdout
    for line in added.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or parts[0] != "A" or not parts[1].startswith("app/src/main/"):
            continue
        stub_path = pathlib.Path("app/src/test/" + parts[1][len("app/src/main/"):])
        if not stub_path.is_file():
            continue
        try:
            first_line = stub_path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        except IndexError:
            continue
        if first_line.strip() == STUB_MARKER:
            git("rm", "-q", "--", str(stub_path).replace(os.sep, "/"))


def publish(role_name, issue, round_, base_sha, patch, trusted, tester_model="", run_id=""):
    if role_name not in ROLES:
        raise Rejected(f"unknown role {role_name!r}; known: {sorted(ROLES)}")
    if not re.fullmatch(r"[1-9][0-9]*", issue) or not re.fullmatch(r"[0-9]+", round_):
        raise Rejected("issue must be a decimal number without leading zeros, round a decimal number")
    if not SHA_RE.fullmatch(base_sha):
        raise Rejected("base sha must be a full 40-hex commit id")
    role = ROLES[role_name]
    fields = {"issue": issue, "round": round_, "tester_model": tester_model}
    branch = role.branch.format(**fields)
    if not BRANCH_RE.fullmatch(branch):
        raise Rejected(f"branch {branch!r} does not match {BRANCH_RE.pattern}")
    if git("rev-parse", "HEAD").stdout.strip() != base_sha:
        raise Rejected("working tree is not checked out at the base sha")
    if git("status", "--porcelain", "--untracked-files=all").stdout.strip():
        raise Rejected("working tree is not clean before applying the patch")

    patch = pathlib.Path(patch)
    if not patch.is_file():
        raise Rejected(f"no patch artifact at {patch}")
    if patch.stat().st_size > MAX_PATCH_BYTES:
        raise Rejected(f"patch is larger than {MAX_PATCH_BYTES} bytes")
    if patch.stat().st_size:
        if git("apply", "--check", "--index", "--binary", str(patch), check=False).returncode:
            raise Rejected("patch does not apply cleanly to the base sha")
        git("apply", "--index", "--binary", str(patch))

    guard = subprocess.run([sys.executable, str(pathlib.Path(trusted) / "check_paths.py"),
                            "--base", base_sha, "--expect-head", base_sha,
                            *(arg.format(**fields) for arg in role.guard)])
    if guard.returncode:
        raise Rejected(f"path guard failed for role {role_name}")

    if role_name == "builder":
        remove_shadowed_stubs()

    if not git("diff", "--cached", "--name-only").stdout.strip():
        raise Rejected(f"role {role_name} produced no changes to publish")
    # A rerun must rebuild the same commit, so its push is a no-op instead of a non-fast-forward.
    date = git("log", "-1", "--format=%cI", base_sha).stdout.strip()
    r = subprocess.run(["git", "-c", f"user.name={BOT[0]}", "-c", f"user.email={BOT[1]}", "commit", "-q",
                        "-m", role.subject.format(**fields),
                        "-m", f"Refs #{issue}\n\nAssisted-by: {role.assisted_by.format(**fields)}\nFactory-Run: {run_id}"],
                       env={**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    if r.returncode:
        raise Rejected("commit failed")
    return role, branch


def proposed_adr_links(base_sha):
    """Every docs/adr/proposed-*.md this commit added since base_sha, as markdown links - so a
    reviewer sees them in the PR description itself, not only by opening the diff."""
    added = git("diff", "--name-status", "--no-renames", base_sha, "HEAD").stdout.splitlines()
    paths = sorted(line.split("\t", 1)[1] for line in added
                   if line.startswith("A\t") and line.split("\t", 1)[1].startswith("docs/adr/proposed-"))
    return [f"- [{pathlib.Path(p).name}]({p})" for p in paths]


def write_pr(role, trusted, out, issue, title, base_sha=""):
    out.mkdir(parents=True, exist_ok=True)
    labels = list(role.labels)
    if role.tier_label:
        tier = subprocess.run([sys.executable, str(pathlib.Path(trusted) / "check_tier.py"), "--base", "origin/master"],
                              capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
        labels.append(f"tier:{tier}")
    body = role.pr_body.format(issue=issue)
    links = proposed_adr_links(base_sha) if base_sha else []
    if links:
        body += "\n\n**Proposed ADRs:**\n" + "\n".join(links)
    (out / "title").write_text(role.pr_title.format(issue=issue, title=" ".join(title.split()))[:256], encoding="utf-8")
    (out / "body.md").write_text(body + "\n", encoding="utf-8")
    (out / "labels").write_text("\n".join(labels) + "\n", encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--role", required=True)
    p.add_argument("--issue", required=True)
    p.add_argument("--round", default="0")
    p.add_argument("--base-sha", required=True)
    p.add_argument("--patch", required=True)
    p.add_argument("--trusted", required=True, help="directory holding the base commit's guard tools")
    p.add_argument("--pr-dir", required=True)
    p.add_argument("--tester-model", default="")
    a = p.parse_args()
    try:
        role, branch = publish(a.role, a.issue, a.round, a.base_sha, a.patch, a.trusted,
                               a.tester_model, os.environ.get("GITHUB_RUN_ID", ""))
        if role.pr:
            write_pr(role, a.trusted, pathlib.Path(a.pr_dir), a.issue, os.environ.get("ISSUE_TITLE", ""), a.base_sha)
    except Rejected as e:
        print(f"::error::publish rejected: {e}")
        sys.exit(1)
    outputs = {"branch": branch, "open_pr": str(role.pr).lower(), "head_sha": git("rev-parse", "HEAD").stdout.strip()}
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as f:
        f.writelines(f"{k}={v}\n" for k, v in outputs.items())
    print(f"publish ok: role={a.role} branch={branch}")


if __name__ == "__main__":
    main()
