"""Measure whether a role's skills earn their place: run a golden task headless in each skill setup (brief 001).

Setups (brief 010): A no skills; B the charter's always-on skills inlined into the prompt, as CI runs them;
C is B plus exactly the charter's on-trigger skills in .claude/skills (Q46: the eval measures the CI configuration).
Each run works in a throwaway one-commit repo built from HEAD (never a worktree) without factory/golden,
so neither the files nor git history show the agent the hidden acceptance test. After the agent stops, the task's AcceptanceTest.java is copied in and
`mvn -B -f app/pom.xml verify` decides pass/fail. One CSV row per run goes to factory/golden/results/.

Usage: python tools/skill_eval.py --task G001 --setups A,B [--max-turns 30] [--model claude-opus-5-5] [--allow-pending]
--allow-pending loads skills whose source is still `reviewed: pending`; this local eval is the only place allowed to.
Needs the `claude` CLI (logged in), git, mvn and a JDK 21 (JAVA_HOME or --java-home).
"""
import argparse, csv, datetime, json, os, pathlib, re, shutil, stat, subprocess, sys, tarfile, tempfile, time
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import load_skills  # noqa: E402

ROOT = load_skills.ROOT
GOLDEN = "factory/golden"
RESULTS = "factory/golden/results"
SETUPS = {"A": (), "B": ("always",), "C": ("always", "on_trigger")}
HIDDEN_HEADING = "## Expected outcome"
# Same tools as the builder step in .github/workflows/30-build.yml.
ALLOWED_TOOLS = "Read,Glob,Grep,Skill,Edit(app/src/main/**),Write(app/src/main/**),Bash(mvn:*),Bash(git status),Bash(git diff:*)"
COLUMNS = ["started_utc", "task", "setup", "skills", "model", "max_turns", "repo_commit", "agent_status", "turns",
           "input_tokens", "cache_creation_tokens", "cache_read_tokens", "output_tokens", "cost_usd", "agent_wall_s",
           "diff_lines_main", "diff_lines_total", "verify_pass", "acceptance_tests", "acceptance_failed", "pass",
           "total_wall_s"]


def task_prompt(role_prompt, task_md):
    """The role prompt plus the task, minus the evaluator-only section."""
    visible = task_md.split(HIDDEN_HEADING, 1)[0].rstrip()
    return f"{role_prompt.rstrip()}\n\n## Work item (golden task)\n<untrusted-issue-text>\n{visible}\n</untrusted-issue-text>\n"


def numstat_lines(numstat, prefix=""):
    total = 0
    for line in numstat.splitlines():
        added, deleted, path = line.split("\t", 2)
        if path.startswith(prefix) and added != "-":
            total += int(added) + int(deleted)
    return total


def surefire(reports_dir, test_class):
    """(tests, failed) from the surefire report of one test class; (0, 0) when it never ran."""
    tests = failed = 0
    for xml in pathlib.Path(reports_dir).glob(f"TEST-*{test_class}.xml"):
        suite = ET.parse(xml).getroot()
        tests += int(suite.get("tests", 0))
        failed += int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    return tests, failed


def agent_metrics(stdout):
    """Fields from `claude -p --output-format json`; agent_status says why a run produced none."""
    try:
        out = json.loads(stdout)
    except ValueError:
        return {"agent_status": "no json output"}
    usage = out.get("usage") or {}
    status = out.get("subtype", "unknown")
    if out.get("is_error"):
        status = f"error: {str(out.get('result', status))[:120]}"
    return {"agent_status": status, "turns": out.get("num_turns"),
            "input_tokens": usage.get("input_tokens"), "cache_creation_tokens": usage.get("cache_creation_input_tokens"),
            "cache_read_tokens": usage.get("cache_read_input_tokens"), "output_tokens": usage.get("output_tokens"),
            "cost_usd": out.get("total_cost_usd")}


def run(cmd, cwd, env=None, timeout=None, stdin=None):
    """subprocess.run that kills the whole process tree on timeout (mvn and claude start children)."""
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    try:
        out, err = p.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        else:
            p.kill()
        out, err = p.communicate()
        return subprocess.CompletedProcess(cmd, "timeout", out, err)
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def tool(name):
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"skill_eval: `{name}` is not on PATH")
    return path


def writable(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def git_show(repo, spec):
    return subprocess.run(["git", "-C", str(repo), "show", spec], check=True, capture_output=True).stdout


def workspace_without_golden(commit, repo, tar_path):
    """A fresh one-commit repo of `commit` minus factory/golden, so not even git history holds the hidden test."""
    subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", "-o", str(tar_path), commit], check=True)
    with tarfile.open(tar_path) as tar:
        members = [m for m in tar.getmembers() if not (m.name + "/").startswith(GOLDEN + "/")]
        if any(m.issym() or m.islnk() or m.name.startswith(("/", "..")) or "/../" in m.name for m in members):
            raise SystemExit("skill_eval: refusing an archive with links or paths outside the workspace")
        tar.extractall(repo, members)
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=skill-eval", "-c", "user.email=skill-eval@invalid", "commit", "-q", "-m", "workspace"]):
        git(repo, *args)


def load_setup(role, repo, groups, allow_pending):
    """(skills column, role prompt) for one setup: always-on inlined, on-trigger installed."""
    role_prompt = (repo / f"factory/prompts/{role}.md").read_text(encoding="utf-8")
    installed = repo / load_skills.INSTALL_DIR
    if not groups:
        shutil.rmtree(installed, ignore_errors=True)
        return "-", role_prompt
    role_prompt += load_skills.prompt_section(role, root=repo, groups=groups, allow_pending=allow_pending)
    inlined = [f"inline:{n}" for n in load_skills.read_charter_skills(role, repo).get("always", {})]
    if "on_trigger" in groups:
        names = load_skills.install(role, repo, root=repo, allow_pending=allow_pending)
    else:
        shutil.rmtree(installed, ignore_errors=True)
        names = []
    return " ".join(inlined + names) or "-", role_prompt


def run_setup(task, setup, a, env):
    started = time.monotonic()
    row = {"started_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "task": task, "setup": setup, "model": a.model, "max_turns": a.max_turns}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"skill-eval-{task}-{setup}-"))
    try:
        repo = tmp / "repo"
        row["repo_commit"] = git(ROOT, "rev-parse", "HEAD").strip()
        task_md = (ROOT / GOLDEN / task / "task.md").read_text(encoding="utf-8")
        hidden = tmp / "AcceptanceTest.java"
        hidden.write_bytes(git_show(ROOT, f"HEAD:{GOLDEN}/{task}/AcceptanceTest.java"))
        workspace_without_golden(row["repo_commit"], repo, tmp / "src.tar")
        row["skills"], role_prompt = load_setup(a.role, repo, SETUPS[setup], a.allow_pending)
        prompt = task_prompt(role_prompt, task_md)
        claude = [tool("claude"), "-p", "--model", a.model, "--max-turns", str(a.max_turns), "--output-format", "json",
                  "--setting-sources", "project", "--allowedTools", ALLOWED_TOOLS]
        t0 = time.monotonic()
        res = run(claude, repo, env, a.timeout_min * 60, prompt)
        row["agent_wall_s"] = round(time.monotonic() - t0, 1)
        row.update(agent_metrics(res.stdout))
        if res.returncode == "timeout":
            row["agent_status"] = "timeout"

        git(repo, "add", "-A", "-N", ".")
        numstat = git(repo, "diff", "--numstat", "HEAD", "--", ".", ":!.claude")
        row["diff_lines_main"] = numstat_lines(numstat, "app/src/main/")
        row["diff_lines_total"] = numstat_lines(numstat)

        package = re.search(r"^package\s+([\w.]+);", hidden.read_text(encoding="utf-8"), re.M).group(1)
        dest = repo / "app/src/test/java" / package.replace(".", "/") / "AcceptanceTest.java"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(hidden, dest)
        mvn = run([tool("mvn"), "-B", "-f", "app/pom.xml", "verify"], repo, env, a.timeout_min * 60)
        if a.keep_logs:
            (pathlib.Path(a.out) / f"{task}-{setup}-mvn.log").write_text(mvn.stdout[-20000:], encoding="utf-8")
        row["verify_pass"] = mvn.returncode == 0
        row["acceptance_tests"], row["acceptance_failed"] = surefire(repo / "app/target/surefire-reports", "AcceptanceTest")
        row["pass"] = row["verify_pass"] and row["acceptance_tests"] > 0 and row["acceptance_failed"] == 0
    finally:
        if a.keep:
            print(f"kept {tmp}")
        else:
            shutil.rmtree(tmp, onerror=writable)
    row["total_wall_s"] = round(time.monotonic() - started, 1)
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", required=True)
    ap.add_argument("--setups", default="A,B,C")
    ap.add_argument("--role", default="builder")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--timeout-min", type=int, default=45)
    ap.add_argument("--java-home", default=os.environ.get("JAVA_HOME"))
    ap.add_argument("--out", default=str(ROOT / RESULTS))
    ap.add_argument("--allow-pending", action="store_true", help="load skills whose source is still reviewed: pending")
    ap.add_argument("--keep", action="store_true", help="keep the temp clone for inspection")
    ap.add_argument("--keep-logs", action="store_true", help="write each run's mvn log next to the CSV")
    a = ap.parse_args(argv)
    setups = [s for s in a.setups.split(",") if s]
    if not setups or set(setups) - set(SETUPS):
        ap.error(f"--setups takes a comma list of {sorted(SETUPS)}")
    if not (ROOT / GOLDEN / a.task / "AcceptanceTest.java").is_file():
        ap.error(f"{GOLDEN}/{a.task}/AcceptanceTest.java is missing")
    env = dict(os.environ)
    if a.java_home:
        env["JAVA_HOME"] = a.java_home
        env["PATH"] = str(pathlib.Path(a.java_home, "bin")) + os.pathsep + env["PATH"]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"{a.task}-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for setup in setups:
            row = run_setup(a.task, setup, a, env)
            w.writerow(row)
            f.flush()
            print(json.dumps(row))
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
