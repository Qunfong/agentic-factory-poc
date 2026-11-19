"""Assert the factory's workflow security policy (briefs 001, 003, 004, 006, 009) over .github/workflows/*.yml.

Each rule is one function in RULES: it takes {filename: parsed workflow} and returns violations.
Add a rule by writing a function and decorating it with @rule.
check_issue_forms() also checks the issue forms in the sibling ISSUE_TEMPLATE directory.
Usage: python tools/check_workflow_policy.py [workflow_dir]
"""
import pathlib, re, sys

AGENT_ACTIONS = ("anthropics/claude-code-action@",)
# Brief 013: the tester is a plain `run:` step (tools/tester_loop.py), not a `uses:` action, so the
# agent-job rules below must recognise it by script name too, not only AGENT_ACTIONS.
AGENT_SCRIPTS = ("tools/tester_loop.py",)
PUBLISH_FILE = "publish.yml"
PUBLISH_REF = "./.github/workflows/publish.yml"
APP_TOKEN_ACTION = re.compile(r"^actions/create-github-app-token@[0-9a-f]{40}$")
PUSH_OR_PR = re.compile(r"\bgit\s+push\b|\bgh\s+pr\s+(create|edit|merge|review)\b")
MAVEN_CACHE_FILES = {"40-verify.yml", "60-release.yml"}
EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)
SAME_REPO_HEAD = "github.event.workflow_run.head_repository.full_name == github.repository"
VERIFY_FILE = "40-verify.yml"
MAX_RETENTION_DAYS = 7
AUTHORIZE_JOB = "authorize"
AUTHORIZE_TOOL = "tools/authorize.py"
AUTHORIZE_PASSED = "needs.authorize.result == 'success'"
STATUS_FUNCTION = re.compile(r"\b(always|cancelled|failure)\(\)")
WORKFLOW_SHA = "${{ github.workflow_sha }}"
TRUSTED_TOOLS = "$WORKFLOW_SHA:tools/"
TOOLS_WORD = re.compile(r"(?<![\w-])tools(?![\w-])")
SWALLOWED = re.compile(r"\|\|\s*(true\b|:(?!\S)|exit\s+0\b)|>\s*/dev/null|\bset\s+\+e\b")
# Deny by default: every secret except these may spend model budget, so a new or retired model key is covered.
NON_MODEL_SECRETS = frozenset({"GITHUB_TOKEN", "ACCEPTANCE_REPO_TOKEN", "FACTORY_APP_PRIVATE_KEY"})
SECRET_NAME = re.compile(r"secrets\.(\w+)")
SECRET_PRESENCE = re.compile(r"secrets\.\w+\s*!=\s*''")
PLUGIN_INPUTS = ("plugins", "plugin_marketplaces")
LOAD_SKILLS = "tools/load_skills.py"
RULES = []


def rule(fn):
    RULES.append(fn)
    return fn


def jobs(workflows):
    for name, wf in workflows.items():
        for job_id, job in (wf.get("jobs") or {}).items():
            yield name, job_id, job


def steps(job):
    return job.get("steps") or []


def uses(step, prefix):
    return str(step.get("uses", "")).startswith(prefix)


def needs(job):
    n = job.get("needs") or []
    return {n} if isinstance(n, str) else set(n)


def is_agent_step(step):
    return any(uses(step, a) for a in AGENT_ACTIONS) or any(sc in str(step.get("run", "")) for sc in AGENT_SCRIPTS)


def is_agent_job(job):
    return any(is_agent_step(s) for s in steps(job))


def agent_jobs(workflows):
    return ((n, j, job) for n, j, job in jobs(workflows) if is_agent_job(job))


def value_reads(x):
    """repr(x) without `secrets.X != ''`, which reads only whether a secret is set."""
    return SECRET_PRESENCE.sub("", repr(x))


def secret_values(x):
    return "secrets." in value_reads(x)


def spends_model_budget(job):
    text = value_reads(job)
    return is_agent_job(job) or any(k not in NON_MODEL_SECRETS for k in SECRET_NAME.findall(text))


def triggers(wf):
    # PyYAML reads YAML 1.1, where the bare key `on` loads as the boolean True.
    on = wf.get("on", wf.get(True))
    if isinstance(on, str):
        return {on}
    return set(on or ())


def env_maps(job):
    yield job.get("env") or {}
    for s in steps(job):
        yield s.get("env") or {}


@rule
def agent_job_has_read_only_permissions(workflows):
    out = []
    for name, job_id, job in agent_jobs(workflows):
        perms = job.get("permissions")
        if perms is None:
            out.append(f"{name}:{job_id}: agent job must set its own permissions (it inherits the workflow's)")
        elif perms == "write-all" or (isinstance(perms, dict) and "write" in perms.values()):
            out.append(f"{name}:{job_id}: agent job has a write permission: {perms}")
    return out


@rule
def agent_job_holds_no_token_env_or_app_token(workflows):
    out = []
    for name, job_id, job in agent_jobs(workflows):
        for env in env_maps(job):
            for key in ("GH_TOKEN", "GITHUB_TOKEN"):
                if key in env:
                    out.append(f"{name}:{job_id}: agent job sets {key} in env")
        text = repr(job)
        for marker in ("create-github-app-token", "FACTORY_APP_PRIVATE_KEY", "steps.app.outputs.token"):
            if marker in text:
                out.append(f"{name}:{job_id}: agent job references {marker}")
    return out


@rule
def agent_checkout_does_not_persist_credentials(workflows):
    return [f"{name}:{job_id}: actions/checkout without persist-credentials: false"
            for name, job_id, job in agent_jobs(workflows)
            for s in steps(job)
            if uses(s, "actions/checkout@") and (s.get("with") or {}).get("persist-credentials") is not False]


@rule
def agent_job_shares_no_cache(workflows):
    out = []
    for name, job_id, job in agent_jobs(workflows):
        for s in steps(job):
            w = s.get("with") or {}
            if uses(s, "actions/setup-java@") and w.get("cache"):
                out.append(f"{name}:{job_id}: setup-java cache in an agent job")
            if uses(s, "actions/cache") and not str(w.get("key", "")).startswith("agent-"):
                out.append(f"{name}:{job_id}: agent cache key must start with agent-")
    return out


@rule
def maven_cache_only_in_verify_and_release(workflows):
    return [f"{name}:{job_id}: cache: maven outside {sorted(MAVEN_CACHE_FILES)}"
            for name, job_id, job in jobs(workflows) if name not in MAVEN_CACHE_FILES
            for s in steps(job) if (s.get("with") or {}).get("cache") == "maven"]


@rule
def push_and_pr_only_in_publish(workflows):
    return [f"{name}:{job_id}: git push or gh pr write outside {PUBLISH_FILE}"
            for name, job_id, job in jobs(workflows) if name != PUBLISH_FILE
            for s in steps(job) if PUSH_OR_PR.search(str(s.get("run", "")))]


@rule
def publish_uses_only_the_pinned_app_token(workflows):
    wf = workflows.get(PUBLISH_FILE)
    if wf is None:
        return [f"{PUBLISH_FILE} is missing"]
    out = []
    for _, job_id, job in jobs({PUBLISH_FILE: wf}):
        st = steps(job)
        mint = [i for i, s in enumerate(st) if uses(s, "actions/create-github-app-token@")]
        if len(mint) != 1:
            out.append(f"{PUBLISH_FILE}:{job_id}: expected exactly one create-github-app-token step")
            continue
        m = st[mint[0]]
        w = m.get("with") or {}
        if not APP_TOKEN_ACTION.match(m["uses"]):
            out.append(f"{PUBLISH_FILE}:{job_id}: create-github-app-token is not pinned by a full commit sha")
        if w.get("private-key") != "${{ secrets.FACTORY_APP_PRIVATE_KEY }}" or "client_id" not in str(w.get("client-id")) or "app-id" in w:
            out.append(f"{PUBLISH_FILE}:{job_id}: app token must use inputs.client_id and secrets.FACTORY_APP_PRIVATE_KEY")
        guard = [s for s in st[:mint[0]] if "FACTORY_APP_PRIVATE_KEY" in repr(s.get("env")) and "exit 1" in str(s.get("run"))]
        if not guard:
            out.append(f"{PUBLISH_FILE}:{job_id}: no step fails clearly before minting when the App secrets are missing")
        for env in env_maps(job):
            for key in ("GH_TOKEN", "GITHUB_TOKEN"):
                if key in env and env[key] != "${{ steps.app.outputs.token }}":
                    out.append(f"{PUBLISH_FILE}:{job_id}: {key} is not the App token")
        for s in st:
            if uses(s, "actions/checkout@") and (s.get("with") or {}).get("token") != "${{ steps.app.outputs.token }}":
                out.append(f"{PUBLISH_FILE}:{job_id}: checkout must use the App token")
        if "github.token" in repr(job):
            out.append(f"{PUBLISH_FILE}:{job_id}: references github.token")
    return out


@rule
def publish_callers_pass_the_app_explicitly(workflows):
    out = []
    for name, job_id, job in jobs(workflows):
        if job.get("uses") != PUBLISH_REF:
            continue
        if (job.get("with") or {}).get("client_id") != "${{ vars.FACTORY_APP_CLIENT_ID }}":
            out.append(f"{name}:{job_id}: must pass client_id: ${{{{ vars.FACTORY_APP_CLIENT_ID }}}}")
        if job.get("secrets") != {"FACTORY_APP_PRIVATE_KEY": "${{ secrets.FACTORY_APP_PRIVATE_KEY }}"}:
            out.append(f"{name}:{job_id}: must pass only FACTORY_APP_PRIVATE_KEY (no secrets: inherit)")
    return out


@rule
def artifacts_expire_within_a_week(workflows):
    # Artifacts of a public repo are downloadable by anyone; run records and patches go stale fast.
    def short(step):
        days = str((step.get("with") or {}).get("retention-days", ""))
        return days.isdigit() and 1 <= int(days) <= MAX_RETENTION_DAYS

    return [f"{name}:{job_id}: upload-artifact must set retention-days of at most {MAX_RETENTION_DAYS}"
            for name, job_id, job in jobs(workflows)
            for s in steps(job) if uses(s, "actions/upload-artifact@") and not short(s)]


@rule
def model_jobs_need_authorize(workflows):
    # Agent jobs and jobs holding a model key (50-review) spend model budget (brief 009, Q30).
    out = []
    for name, job_id, job in jobs(workflows):
        if not spends_model_budget(job):
            continue
        auth = (workflows[name].get("jobs") or {}).get(AUTHORIZE_JOB)
        if auth is None or not any(AUTHORIZE_TOOL in str(s.get("run", "")) for s in steps(auth)):
            out.append(f"{name}:{job_id}: no {AUTHORIZE_JOB} job that runs {AUTHORIZE_TOOL}")
        if AUTHORIZE_JOB not in needs(job):
            out.append(f"{name}:{job_id}: model job must list {AUTHORIZE_JOB} in needs")
        cond = str(job.get("if", ""))
        if STATUS_FUNCTION.search(cond) and AUTHORIZE_PASSED not in cond:
            out.append(f"{name}:{job_id}: if: uses a status function, so it must also check {AUTHORIZE_PASSED}")
    return out


@rule
def agent_secrets_only_on_the_agent_step(workflows):
    # Steps after the agent step run code the agent can reach or wrote; they may learn only
    # whether a secret is set (brief 003). A step before it runs only this job's own trusted
    # checkout, since no agent code has executed yet in this job - for example a step that writes
    # a model key to a short-lived file and exits before the agent step starts, so the key never
    # reaches the agent step's own process env (Cowork A2: /proc/<pid>/environ reflects a
    # process's env at exec() time for its whole life, so the key must never be there at all).
    out = []
    for name, job_id, job in agent_jobs(workflows):
        if secret_values(job.get("env")):
            out.append(f"{name}:{job_id}: job env reads a secret; put it on the agent step")
        st = steps(job)
        agent_at = next((i for i, s in enumerate(st) if is_agent_step(s)), len(st))
        for i, s in enumerate(st):
            if i > agent_at and not is_agent_step(s) and secret_values(s):
                out.append(f"{name}:{job_id}: step {i + 1} reads a secret value outside the agent step")
    return out


def untrusted_tools_refs(run):
    """Each `tools` path word in run other than the `git show "$WORKFLOW_SHA:tools/..."` operand (Q49)."""
    return [m for m in TOOLS_WORD.finditer(run)
            if run[m.start() - len("$WORKFLOW_SHA:"):m.end() + 1] != TRUSTED_TOOLS]


@rule
def tools_after_agent_code_come_from_workflow_sha(workflows):
    # Once agent code ran, the checkout and anything in it may be rewritten (QUESTIONS Q19, Q20).
    # A positive rule (Q49): the only `tools` a post-agent step may name is the git show operand.
    # In the agent's own job even that is out, since the agent could have planted refs/replace in .git.
    out = []
    for name, job_id, job in jobs(workflows):
        st = steps(job)
        agent_at = next((i for i, s in enumerate(st) if is_agent_step(s)), None)
        if agent_at is not None:
            if any(TOOLS_WORD.search(str(s.get("run", ""))) for s in st[agent_at + 1:]):
                out.append(f"{name}:{job_id}: names tools/ after the agent step; run tools in a later job "
                           f"from git show \"$WORKFLOW_SHA:tools/...\"")
            continue
        downstream = name == PUBLISH_FILE or any(is_agent_job(workflows[name]["jobs"].get(n) or {}) for n in needs(job))
        if not downstream:
            continue
        for s in st:
            run = str(s.get("run", ""))
            if untrusted_tools_refs(run):
                out.append(f"{name}:{job_id}: reads tools/ other than via git show \"$WORKFLOW_SHA:tools/...\"")
            if TRUSTED_TOOLS in run and (s.get("env") or {}).get("WORKFLOW_SHA") != WORKFLOW_SHA:
                out.append(f"{name}:{job_id}: WORKFLOW_SHA must be {WORKFLOW_SHA}")
    return out


@rule
def agent_transcripts_stay_off_logs(workflows):
    # Logs of a public repo are public. claude-code-action prints the full transcript when
    # show_full_output is true or ACTIONS_STEP_DEBUG is "true" (base-action/src/parse-sdk-options.ts).
    out = []
    for name, job_id, job in agent_jobs(workflows):
        for s in steps(job):
            w = s.get("with") or {}
            if uses(s, "anthropics/claude-code-action@"):
                for key in ("show_full_output", "display_report"):
                    if str(w.get(key, "false")).lower() != "false":
                        out.append(f"{name}:{job_id}: agent output: {key} must stay false")
                if (s.get("env") or {}).get("ACTIONS_STEP_DEBUG") != "false":
                    out.append(f"{name}:{job_id}: agent output: set env ACTIONS_STEP_DEBUG: \"false\" on the claude step")
    return out


@rule
def tester_does_not_use_codex_action(workflows):
    # Brief 013: codex-action piped the tester's full stderr transcript into the (now public) log
    # with no way to suppress it; the LiteLLM-driven tools/tester_loop.py replaces it entirely.
    return [f"{name}: {job_id}: step {i + 1} still uses openai/codex-action@, which brief 013 removed"
            for name, job_id, job in jobs(workflows)
            for i, s in enumerate(steps(job)) if uses(s, "openai/codex-action@")]


PRINT_TRANSCRIPT = re.compile(r"\bcat\b.*\b(transcript|run-record)\S*\.json\b")
SHELL_TRACE = re.compile(r"\bset\s+-\w*x\w*\b|\bbash\s+-\w*x\w*\b")


@rule
def agent_job_steps_do_not_print_the_transcript(workflows):
    # Brief 013, extending the quiet-transcripts rule to the tester's run-record file: model text,
    # tool arguments and file contents belong only there, never in the (now public) log.
    out = []
    for name, job_id, job in agent_jobs(workflows):
        for i, s in enumerate(steps(job)):
            run = str(s.get("run", ""))
            if PRINT_TRANSCRIPT.search(run):
                out.append(f"{name}:{job_id}: step {i + 1} cats the run-record/transcript file to the log")
            if SHELL_TRACE.search(run):
                out.append(f"{name}:{job_id}: step {i + 1} enables shell tracing, which echoes commands to the log")
    return out


@rule
def run_scripts_hold_no_expressions(workflows):
    # Any ${{ }} in run: is pasted into the script before bash parses it, so event text,
    # inputs and step outputs derived from them become code. They go through env: instead.
    return [f"{name}:{job_id}: run: contains {m.group(0)}; pass it through env: and quote it"
            for name, job_id, job in jobs(workflows)
            for s in steps(job)
            for m in EXPRESSION.finditer(str(s.get("run", "")))]


@rule
def no_pull_request_target(workflows):
    return [f"{name}: pull_request_target runs fork code with the base repo's token and secrets"
            for name, wf in workflows.items() if "pull_request_target" in triggers(wf)]


@rule
def workflow_run_jobs_require_a_same_repo_head(workflows):
    out = []
    for name, wf in workflows.items():
        if "workflow_run" not in triggers(wf):
            continue
        for _, job_id, job in jobs({name: wf}):
            cond = " ".join(str(job.get("if", "")).replace("${{", "").replace("}}", "").split())
            first_conjunct = cond == SAME_REPO_HEAD or cond.startswith(SAME_REPO_HEAD + " &&")
            if not first_conjunct or "||" in cond:
                out.append(f"{name}:{job_id}: if: must start with `{SAME_REPO_HEAD} &&` and hold no ||")
    return out


@rule
def verify_acceptance_fails_closed(workflows):
    # Brief 007: a failure in the hidden scenarios must fail the job, and their output stays on the runner (brief 009).
    if VERIFY_FILE not in workflows:
        return []
    job = (workflows[VERIFY_FILE].get("jobs") or {}).get("acceptance")
    if job is None:
        return [f"{VERIFY_FILE}: no acceptance job"]
    out = [f"{VERIFY_FILE}:acceptance: continue-on-error"
           for x in (job, *steps(job)) if x.get("continue-on-error")]
    for s in steps(job):
        if uses(s, "actions/upload-artifact@"):
            out.append(f"{VERIFY_FILE}:acceptance: uploads an artifact; scenario output must stay on the runner")
        for m in SWALLOWED.finditer(str(s.get("run", ""))):
            out.append(f"{VERIFY_FILE}:acceptance: `{m.group(0)}` swallows a failure or hides its cause")
    return out


@rule
def verify_required_needs_every_job(workflows):
    if VERIFY_FILE not in workflows:
        return []
    all_jobs = workflows[VERIFY_FILE].get("jobs") or {}
    req = all_jobs.get("required")
    if req is None:
        return [f"{VERIFY_FILE}: no required job"]
    req_needs = needs(req)
    out = [f"{VERIFY_FILE}:required: does not need {j}" for j in sorted(set(all_jobs) - {"required"} - req_needs)]
    out += [f"{VERIFY_FILE}:required: does not check needs.{j}.result" for j in sorted(req_needs)
            if f"needs.{j}.result" not in repr(req)]
    if "always()" not in str(req.get("if", "")):
        out.append(f"{VERIFY_FILE}:required: must run with if: always() so a skipped job fails it")
    return out


@rule
def no_plugin_installs(workflows):
    # Brief 001: agents load only pinned skills from the repo, never a live plugin or marketplace.
    out = []
    for name, job_id, job in jobs(workflows):
        for i, x in enumerate((job, *steps(job))):
            for key in PLUGIN_INPUTS:
                if key in (x.get("with") or {}):
                    out.append(f"{name}:{job_id}: {'job' if i == 0 else f'step {i}'} sets `{key}:`; load pinned skills with {LOAD_SKILLS}")
    return out


@rule
def agent_steps_follow_load_skills(workflows):
    # Brief 001: .claude/skills holds exactly the role's pinned skills when the agent starts.
    out = []
    for name, job_id, job in agent_jobs(workflows):
        loaded = False
        for s in steps(job):
            if LOAD_SKILLS in str(s.get("run", "")):
                loaded = True
            if is_agent_step(s) and not loaded:
                out.append(f"{name}:{job_id}: agent step runs before {LOAD_SKILLS}")
    return out


WI_BRANCH_PATTERN = re.compile(r"wi-[(\[]")
WI_BRANCH_CANON = "^wi-([1-9][0-9]*)$"
LOOSE_ISSUE_NUMBER = re.compile(r'"\$ISSUE"\s*=~\s*\^\[0-9\]')


@rule
def work_item_numbers_are_canonical(workflows):
    # One branch per issue: `wi-7` and `wi-007` must not both map to issue 7 (brief 011, Q15).
    out = []
    for name, job_id, job in jobs(workflows):
        for s in steps(job):
            run = str(s.get("run", ""))
            for m in WI_BRANCH_PATTERN.finditer(run):
                if run[m.start() - 1:m.start() - 1 + len(WI_BRANCH_CANON)] != WI_BRANCH_CANON:
                    out.append(f"{name}:{job_id}: a wi branch regex must be {WI_BRANCH_CANON}")
            if LOOSE_ISSUE_NUMBER.search(run):
                out.append(f"{name}:{job_id}: an issue number must match ^[1-9][0-9]*$ (no leading zeros)")
    return out


BUILD_DISPATCH = re.compile(r"\bgh\s+workflow\s+run\s+(\"30 build\"|'30 build'|30-build\.yml)")
DISPATCH_QUEUED = "create_work_items.py --dispatch-queued"
BOT_LOGIN_VAR = "${{ vars.FACTORY_BOT_LOGIN }}"


@rule
def build_dispatchers_are_authorized(workflows):
    # 30-build admits github-actions[bot] on workflow_dispatch, so whoever makes a workflow dispatch it
    # must pass the same check first: a write collaborator must not reach model spend indirectly (Q27).
    out = []
    for name, job_id, job in jobs(workflows):
        for s in steps(job):
            run = str(s.get("run", ""))
            if BUILD_DISPATCH.search(run):
                auth = (workflows[name].get("jobs") or {}).get(AUTHORIZE_JOB)
                checks = auth is not None and any(AUTHORIZE_TOOL in str(a.get("run", "")) for a in steps(auth))
                if not checks or AUTHORIZE_JOB not in needs(job):
                    out.append(f"{name}:{job_id}: dispatches 30 build without needing an {AUTHORIZE_JOB} job that runs {AUTHORIZE_TOOL}")
            if DISPATCH_QUEUED in run and (s.get("env") or {}).get("FACTORY_BOT_LOGIN") != BOT_LOGIN_VAR:
                out.append(f"{name}:{job_id}: {DISPATCH_QUEUED} needs env FACTORY_BOT_LOGIN: {BOT_LOGIN_VAR} to judge labelers")
    return out


EGRESS_BLOCK = ("sudo -n iptables -A OUTPUT -m owner --uid-owner nobody ! -o lo -j REJECT",
                "sudo -n ip6tables -A OUTPUT -m owner --uid-owner nobody ! -o lo -j REJECT",
                'curl -sS --max-time 10 -o /dev/null https://api.github.com || { echo "::error::egress probe inconclusive',
                "if sudo -n -u nobody curl -sS --max-time 5 -o /dev/null https://api.github.com; then")
APP_START = 'sudo -n -u nobody "$JAVA_HOME/bin/java"'


@rule
def verify_blocks_app_egress_before_it_starts(workflows):
    # The app under test runs agent-written code; it gets no network beyond loopback (brief 011, Q26).
    # An app that needs egress gets an allow list through a protected change, never by dropping the block.
    if VERIFY_FILE not in workflows:
        return []
    job = (workflows[VERIFY_FILE].get("jobs") or {}).get("acceptance")
    if job is None:
        return []
    runs = [str(s.get("run", "")) for s in steps(job)]
    start = next((i for i, r in enumerate(runs) if APP_START in r), None)
    if start is None:
        return [f"{VERIFY_FILE}:acceptance: no step starts the app with {APP_START}"]
    if not any(all(part in r for part in EGRESS_BLOCK) for r in runs[:start]):
        return [f"{VERIFY_FILE}:acceptance: no step before the app starts blocks nobody's egress "
                f"with iptables and ip6tables and probes https://api.github.com as the runner (else "
                f"\"probe inconclusive\") and as nobody"]
    return []


GITLEAKS_IMAGE = re.compile(r"zricethezav/gitleaks(:[\w.-]+)?(@sha256:[0-9a-f]{64})?")


@rule
def gitleaks_runs_from_the_pinned_image(workflows):
    # An action by tag runs whatever the tag points at today, with the job's token (brief 011, Q29).
    out = []
    for name, job_id, job in jobs(workflows):
        for s in steps(job):
            if uses(s, "gitleaks/gitleaks-action"):
                out.append(f"{name}:{job_id}: gitleaks action by tag; run the image pinned by digest instead")
            for m in GITLEAKS_IMAGE.finditer(repr(s)):
                if not m.group(2):
                    out.append(f"{name}:{job_id}: gitleaks image {m.group(0)} is not pinned by sha256 digest")
    static = ((workflows.get(VERIFY_FILE) or {}).get("jobs") or {}).get("static")
    if static is not None and not any(GITLEAKS_IMAGE.search(repr(s)) and "docker run" in str(s.get("run", ""))
                                      for s in steps(static)):
        out.append(f"{VERIFY_FILE}:static: no secret scan with the pinned gitleaks image")
    return out


PIP_INSTALL = re.compile(r"\bpip3?\s+install\b")
HASHED_INSTALL = re.compile(r"\bpip3?\s+install\s+(-q\s+)?--require-hashes\s+--only-binary=:all:\s+-r\s+\S+$")


@rule
def pip_installs_are_hash_pinned(workflows):
    # litellm pulls dozens of transitive packages into a job that holds model keys (brief 011, Q21).
    out = []
    for name, job_id, job in jobs(workflows):
        for s in steps(job):
            for cmd in re.split(r"&&|\|\||;|\n", str(s.get("run", "")).replace("\\\n", " ")):
                if PIP_INSTALL.search(cmd) and not HASHED_INSTALL.search(cmd.strip()):
                    out.append(f"{name}:{job_id}: `{cmd.strip()}` must be pip install --require-hashes "
                               f"--only-binary=:all: -r <hash-pinned file>")
    return out


TOOL_RUNNERS = re.compile(r"\b(pipx|uvx|uv\s+tool\s+run)\b")


@rule
def no_unpinned_tool_runners(workflows):
    # pipx run and uvx resolve the newest release and its dependency tree at run time, unhashed (Q51).
    return [f"{name}:{job_id}: `{m.group(0)}` installs an unpinned tool; use a hash-pinned requirements file "
            f"or an image pinned by digest"
            for name, job_id, job in jobs(workflows)
            for s in steps(job)
            for m in TOOL_RUNNERS.finditer(str(s.get("run", "")))]


SEMGREP_IMAGE = re.compile(r"semgrep/semgrep(:[\w.-]+)?(@sha256:[0-9a-f]{64})?")
SEMGREP_SCAN = re.compile(r"\bsemgrep\s+(scan|ci)\b")
SEMGREP_CONFIG = re.compile(r"(?:--config|-c|-f)[\s=]+(\S+)")
SEMGREP_OFFLINE = ("docker run", "--network none", "--metrics off")


@rule
def semgrep_runs_pinned_and_offline(workflows):
    # An unpinned scanner or registry ruleset is not a reproducible gate (Q51). With no network in the
    # container, the scanner can neither send metrics nor fetch rules other than the local file.
    out = []
    for name, job_id, job in jobs(workflows):
        for s in steps(job):
            for m in SEMGREP_IMAGE.finditer(repr(s)):
                if not m.group(2):
                    out.append(f"{name}:{job_id}: semgrep image {m.group(0)} is not pinned by sha256 digest")
            run = str(s.get("run", ""))
            scan = SEMGREP_SCAN.search(run)
            if not scan:
                continue
            missing = [part for part in SEMGREP_OFFLINE if part not in run]
            if missing or not SEMGREP_IMAGE.search(repr(s)):
                out.append(f"{name}:{job_id}: semgrep must run from the pinned image with {', '.join(SEMGREP_OFFLINE)}")
            configs = SEMGREP_CONFIG.findall(run[scan.end():])
            if not configs or any("://" in c or not c.endswith((".yml", ".yaml")) for c in configs):
                out.append(f"{name}:{job_id}: semgrep --config must name local .yml files only, got {configs}")
            if "sha256sum -c" not in run:
                out.append(f"{name}:{job_id}: semgrep rules must be checked against a pinned sha256")
    static = ((workflows.get(VERIFY_FILE) or {}).get("jobs") or {}).get("static")
    if static is not None and not any(SEMGREP_SCAN.search(str(s.get("run", ""))) for s in steps(static)):
        out.append(f"{VERIFY_FILE}:static: no Semgrep scan")
    return out


@rule
def no_workflow_loads_pending_skills(workflows):
    # Q44: a skill whose source is still `reviewed: pending` loads only in the local skill eval, never in CI.
    return [f"{name}: passes --allow-pending; unreviewed skill sources load only in the local tools/skill_eval.py"
            for name, wf in workflows.items() if re.search(r"allow[-_]pending", repr(wf), re.I)]


def check(workflows):
    return [v for r in RULES for v in r(workflows)]


# GitHub drops a form with a key outside its schema and silently shows the blank issue instead, so the
# form's labels are never applied. Keys from docs.github.com, "Syntax for issue forms" and
# "Syntax for GitHub's form schema".
FORM_REQUIRED = ("name", "description", "body")
FORM_ELEMENT_KEYS = {"type", "id", "attributes", "validations"}
FORM_ATTRIBUTES = {
    "markdown": {"value"},
    "textarea": {"label", "description", "placeholder", "value", "render"},
    "input": {"label", "description", "placeholder", "value"},
    "dropdown": {"label", "description", "multiple", "options", "default"},
    "checkboxes": {"label", "description", "options"},
    "upload": {"label", "description"},
}
FORM_CONFIG = "config.yml"


def check_issue_forms(forms):
    out = []
    for name, form in forms.items():
        form = form if isinstance(form, dict) else {}
        out += [f"{name}: missing top-level `{k}`" for k in FORM_REQUIRED if k not in form]
        for i, el in enumerate(form.get("body") or [], 1):
            el = el if isinstance(el, dict) else {}
            where = f"{name}: body[{i}] ({el.get('id', el.get('type'))})"
            allowed = FORM_ATTRIBUTES.get(el.get("type"))
            if allowed is None:
                out.append(f"{where}: unknown type {el.get('type')!r}")
                continue
            extra = sorted(map(repr, set(el) - FORM_ELEMENT_KEYS))
            if extra:
                out.append(f"{where}: unknown element keys {', '.join(extra)}")
            attrs = el.get("attributes")
            extra = sorted(map(repr, set(attrs or {}) - allowed)) if isinstance(attrs, dict) else ["(not a map)"]
            if extra:
                out.append(f"{where}: attributes has keys outside GitHub's form schema: {', '.join(extra)}; "
                           f"quote a value that holds commas")
    return out


def main():
    try:
        import yaml
    except ImportError:
        print("check_workflow_policy needs pyyaml: pip install -r tools/requirements.txt")
        sys.exit(2)
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".github/workflows")
    load = lambda p: yaml.safe_load(p.read_text(encoding="utf-8"))
    workflows = {p.name: load(p) for p in sorted(root.glob("*.yml"))}
    forms = {p.name: load(p) for p in sorted((root.parent / "ISSUE_TEMPLATE").glob("*.y*ml")) if p.name != FORM_CONFIG}
    violations = check(workflows) + check_issue_forms(forms)
    for v in violations:
        print(v)
    print(f"{len(RULES)} rules, {len(workflows)} workflows, {len(forms)} issue forms, {len(violations)} violations")
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
