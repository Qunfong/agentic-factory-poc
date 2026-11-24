"""Three-family PR review with 2-of-3 consensus (brief 018). Advisory only: never approves or blocks (ADR-003).

Each reviewer family gets the same prompt and diff and never sees another's output. A finding raised by
two or more families is strong. A single-source finding goes to a verifier of another family: confirmed
is kept as "1 model + verified"; rejected is listed under low confidence with the reason. One that no
verifier could check stays visible as unverified and needs a person. Nothing is dropped silently, and
the merge model may only group duplicates (Q22, Q35).

A reviewer that stays unavailable after backoff is an `infra-failure` for that reviewer, and every such
error names the model. Fewer than two answering reviewers is an incomplete review: `needs-human-review`,
the job fails, never a pass. Red tier and any family without its key also get `needs-human-review`. When
the merge model is unavailable, duplicates stay grouped mechanically and the comment says so.
"""
import html, json, os, pathlib, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

MARKER = "<!-- factory-ai-review -->"
HUMAN_REVIEW = "needs-human-review"
INFRA_FAILURE = "infra-failure"
TRANSIENT_STATUS = frozenset({408, 429, 500, 502, 503, 504})
TIMEOUT_ERRORS = frozenset({"Timeout", "APITimeoutError", "TimeoutError"})
TRANSIENT_ERRORS = TIMEOUT_ERRORS | {"RateLimitError", "ServiceUnavailableError", "APIConnectionError",
                                     "InternalServerError", "BadGatewayError"}
ATTEMPTS = 4
TIMEOUT_ATTEMPTS = 2           # a model too slow once is likely too slow again; don't spend 4 timeouts on it
DEFAULT_TIMEOUT_S = 180
MAX_TIMEOUT_S = 900
BASE_DELAY_S = 8.0
MAX_DIFF = 120_000
QUORUM = 2
SEVERITIES = ["blocker", "major", "minor"]
SECTIONS = ("strong", "verified", "unverified", "low")
RECORD_TEXT_MAX = 300
ALL_VERIFIERS_FAILED = "every verifier failed"
DEDUPE_PROMPT_FILE = "factory/prompts/dedupe.md"
MECHANICAL = "Duplicates grouped mechanically (same file, lines within 3, same category)"
RECORD_FIELDS = ("id", "file", "line_start", "line_end", "category", "severity", "problem", "fix", "sources",
                 "agreement", "also_raised_by", "verdict", "verifier", "reason")


class InfraFailure(Exception):
    """A model call failed after retries, or returned no usable JSON."""


@dataclass(frozen=True)
class Plan:
    reviewers: tuple       # families that run
    missing: tuple         # families the tier wants that have no key
    human_review: bool

    @property
    def wanted(self):
        return len(self.reviewers) + len(self.missing)


@dataclass(frozen=True)
class Result:
    calls: tuple           # one row per model call: reviewer, verifier or merge
    findings: list         # every finding after grouping, with agreement and, if single-source, a verdict
    note: str = ""

    @property
    def answered(self):
        return [c["family"] for c in self.calls if c["role"] == "reviewer" and c["result"] == "ok"]

    @property
    def raised(self):
        return sum(c["findings"] for c in self.calls if c["role"] == "reviewer")

    @property
    def failures(self):
        return [f"{c['role']} {c['family']}: {c['result']}" for c in self.calls if c["result"] != "ok"]

    @property
    def infra_failed(self):
        """A reviewer failed, or no verifier could check a single-source finding."""
        return (any(c["role"] == "reviewer" and c["result"] != "ok" for c in self.calls)
                or any(f.get("reason") == ALL_VERIFIERS_FAILED for f in self.findings))


def named(exc, names):
    return any(t.__name__ in names for t in type(exc).__mro__)


def is_transient(exc):
    return getattr(exc, "status_code", None) in TRANSIENT_STATUS or named(exc, TRANSIENT_ERRORS)


MAX_RETRY_AFTER_S = 60.0       # a provider's Retry-After is honoured, but one header may not stall the job


def retry_after(exc):
    """Seconds from a Retry-After header on the provider's response, or None when absent or not a number."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or getattr(exc, "headers", None) or {}
    value = next((v for k, v in dict(headers).items() if str(k).lower() == "retry-after"), None)
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def with_backoff(call, model, attempts=ATTEMPTS, base_delay=BASE_DELAY_S, sleep=time.sleep):
    timeouts = 0
    for i in range(1, attempts + 1):
        try:
            return call()
        except Exception as e:  # noqa: BLE001 - provider SDKs raise many types; each is classified here
            name = type(e).__name__
            if not is_transient(e):
                raise InfraFailure(f"{name} from {model} (not retryable)") from e
            timeouts += named(e, TIMEOUT_ERRORS)
            if i == attempts or timeouts == TIMEOUT_ATTEMPTS:
                raise InfraFailure(f"{name} from {model} after {i} attempts") from e
            delay = base_delay * 2 ** (i - 1)
            asked = retry_after(e)
            sleep(min(max(delay, asked), MAX_RETRY_AFTER_S) if asked is not None else delay)


def parse_json_object(text):
    match = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None


def available_families(families, env):
    """Families review.py may call: an API key is set (and the endpoint, for Azure). Claude has no raw API."""
    return {name for name, f in families.items()
            if not f.get("via") and env.get(f["secret"]) and (not f.get("api_base_env") or env.get(f["api_base_env"]))}


def completion_args(family, env):
    model = family["model"]
    if "<pin" in model or "preview" in model:
        raise ValueError(f"models.yaml: {model} is not a pinned stable model")
    timeout = family.get("timeout_s", DEFAULT_TIMEOUT_S)
    if type(timeout) is not int or not 0 < timeout <= MAX_TIMEOUT_S:
        raise ValueError(f"models.yaml: {model} timeout_s must be a whole number of seconds from 1 to {MAX_TIMEOUT_S}")
    args = {"model": model, "api_key": env[family["secret"]], "timeout": timeout}
    if family.get("api_base_env"):
        args["api_base"] = env[family["api_base_env"]]
    if family.get("api_version"):
        args["api_version"] = family["api_version"]
    return args


def plan_review(tier_cfg, available):
    wanted = tuple(tier_cfg.get("reviewers") or ())
    missing = tuple(f for f in wanted if f not in available)
    return Plan(reviewers=tuple(f for f in wanted if f in available), missing=missing,
                human_review=bool(tier_cfg.get("human_review")) or bool(missing))


def is_complete(result):
    return len(result.answered) >= QUORUM


def labels_for(plan, result=None):
    human = plan.human_review or (result is not None and (
        not is_complete(result) or any(section(f) == "unverified" for f in result.findings)))
    return ([HUMAN_REVIEW] if human else []) + ([INFRA_FAILURE] if result and result.infra_failed else [])


def merge_decision(pr_labels, plan, result):
    """(ok, reason): may the factory merge this PR after the AI review? Strict on purpose (brief 034):
    a work-item PR (`agent` label), every wanted family answered, no unresolved blocker/major from either
    consensus (2+ families) or a verifier-confirmed single source, and nothing that needs a person."""
    if "agent" not in pr_labels:
        return False, "not a work-item PR (no agent label)"
    labels = labels_for(plan, result)
    if HUMAN_REVIEW in labels:
        return False, "needs a person (red tier, missing family, incomplete review or unverified finding)"
    if INFRA_FAILURE in labels or len(result.answered) < plan.wanted:
        return False, "not every reviewer family answered"
    blocking = [f for f in result.findings
                if section(f) in ("strong", "verified") and f.get("severity") in ("blocker", "major")]
    if blocking:
        return False, f"{len(blocking)} blocker/major finding(s) agreed or verified: " + ", ".join(f"#{f['id']}" for f in blocking)
    return True, "complete review, no blocker/major finding"


def write_merge_outputs(pr_number, head_sha, ok, reason):
    """Hand the decision to the workflow. Empty merge_pr means: do not merge."""
    out = os.environ.get("GITHUB_OUTPUT")
    print(f"merge decision for PR #{pr_number}: {'MERGE' if ok else 'no merge'} ({reason})")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"merge_pr={pr_number if ok else ''}\nmerge_head={head_sha if ok else ''}\n")


def verifiers_for(source, answered):
    """Other answering families in turn, starting after `source`, so verification spreads over families."""
    i = answered.index(source) if source in answered else 0
    return [f for f in answered[i + 1:] + answered[:i + 1] if f != source]


def merge_overlapping(findings):
    """Same file + lines within 3 + same category -> one finding; agreement = how many families raised it."""
    merged = []
    for f in findings:
        hit = next((g for g in merged if g["file"] == f["file"] and g["category"] == f["category"]
                    and f["line_start"] <= g["line_end"] + 3 and g["line_start"] <= f["line_end"] + 3), None)
        if hit:
            hit["sources"] = sorted(set(hit["sources"]) | set(f["sources"]))
        else:
            merged.append(dict(f, sources=sorted(f["sources"])))
    return [dict(f, id=n, agreement=len(f["sources"])) for n, f in enumerate(merged, 1)]


def well_formed(data, model):
    """A reviewer's findings, each with str file and category and int lines, or InfraFailure for that reviewer."""
    raw = data.get("findings", [])
    if not isinstance(raw, list) or not all(isinstance(f, dict) for f in raw):
        raise InfraFailure(f"{model} returned malformed findings")
    out = []
    for f in raw:
        start, end = f.get("line_start"), f.get("line_end", f.get("line_start"))
        if not (isinstance(f.get("file"), str) and type(start) is int and type(end) is int):
            raise InfraFailure(f"{model} returned a finding without file and integer lines")
        out.append(dict(f, line_end=max(start, end), category=str(f.get("category") or "other")))
    return out


def section(f):
    if f["agreement"] >= QUORUM:
        return "strong"
    return {"confirmed": "verified", "rejected": "low"}.get(f.get("verdict"), "unverified")


def is_partition(groups, n):
    """True when groups puts each of the indices 0..n-1 in exactly one non-empty group."""
    return (isinstance(groups, list) and all(isinstance(g, list) and g for g in groups)
            and all(type(i) is int for g in groups for i in g)
            and sorted(i for g in groups for i in g) == list(range(n)))


def dedupe(findings, groups):
    """Apply the merge model's grouping. It may group, never drop (Q35): anything but a partition of
    every index is an infra-failure. A group spanning files would blur findings, so that grouping is
    ignored and the findings come back unchanged. A group takes its best-supported member's agreement
    and verdict, so grouping never adds a vote the same-finding rule did not count, and its highest
    severity, so grouping never hides a blocker."""
    if not is_partition(groups, len(findings)):
        raise InfraFailure(f"returned groups that are not a partition of {len(findings)} findings")
    if any(len({findings[i]["file"] for i in g}) != 1 for g in groups):
        return findings
    out = []
    for g in groups:
        members = [findings[i] for i in g]
        best = max(members, key=lambda f: (f["agreement"], f.get("verdict") == "confirmed"))
        others = sorted({s for f in members for s in f["sources"]} - set(best["sources"]))
        severity = min((f.get("severity") for f in members), key=severity_rank)
        out.append(dict(best, severity=severity, also_raised_by=others, ids=sorted(f["id"] for f in members)))
    return out


def clip(plan, diff):
    """Reviewers see at most MAX_DIFF chars. A cut diff needs a person and says so (ADR-0003)."""
    if len(diff) <= MAX_DIFF:
        return plan, diff, ""
    return (replace(plan, human_review=True), diff[:MAX_DIFF],
            f"Diff too large ({len(diff)} chars); only the first {MAX_DIFF} were reviewed.")


def severity_rank(severity):
    return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES) - 1


def cell(text):
    """One line of model text that cannot break the table, open an HTML comment or close <details>."""
    return html.escape(" ".join(str("" if text is None else text).split()), quote=False).replace("|", "\\|")


def verdict_line(f):
    if f["agreement"] >= QUORUM:
        return "not needed, raised by more than one family"
    if f.get("verdict") in ("confirmed", "rejected"):
        return f"{f['verifier']} {f['verdict']}: {cell(f.get('reason')) or 'no reason given'}"
    return f"not verified: {cell(f.get('reason')) or 'no other family answered'}"


def render_finding(f, wanted):
    end = f["line_end"]
    where = cell(f"{f['file']}:{f['line_start']}" + (f"-{end}" if end != f["line_start"] else "")).replace("`", "'")
    also = f"; also raised as a duplicate by {', '.join(f['also_raised_by'])}" if f.get("also_raised_by") else ""
    return [f"**{', '.join(f'#{i}' for i in f.get('ids', [f['id']]))} · {cell(f.get('severity') or 'minor')} · "
            f"`{where}` · {cell(f.get('category'))}**",
            f"- Problem: {cell(f.get('problem'))}",
            f"- Fix: {cell(f.get('fix'))}",
            f"- Agreement: {f['agreement']}/{wanted}: {', '.join(f['sources'])}{also}",
            f"- Verifier: {verdict_line(f)}", ""]


def render(tier, plan, result, head_sha, note="", run_url=""):
    ordered = sorted(result.findings, key=lambda f: severity_rank(f.get("severity")))
    parts = {s: [f for f in ordered if section(f) == s] for s in SECTIONS}
    lines = [MARKER, f"### AI review (advisory) · tier: {tier}",
             f"{result.raised} raised · {len(parts['strong'])} strong · {len(parts['verified'])} verified · "
             f"{len(parts['unverified'])} unverified · {len(parts['low'])} rejected or low confidence."]
    if not is_complete(result):
        lines.append(f"**Review incomplete:** {len(result.answered)} of {plan.wanted} reviewers answered and "
                     f"at least {QUORUM} are needed. This is not a pass.")
    if plan.missing:
        lines.append(f"Unavailable (no key): {', '.join(plan.missing)}.")
    if HUMAN_REVIEW in labels_for(plan, result):
        lines.append(f"Label `{HUMAN_REVIEW}`: a person must review this PR.")
    if result.infra_failed:
        lines.append(f"Label `{INFRA_FAILURE}`: {cell('; '.join(result.failures))}.")
    lines += [x for x in (note, result.note) if x]
    lines += ["", "| Call | Family | Model | Result | Findings | Tokens in/out | Seconds |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {c['role']} | {c['family']} | `{c['model']}` | {cell(c['result'])} | {cell(c['findings'])} "
              f"| {c['tokens_in']}/{c['tokens_out']} | {c['seconds']} |" for c in result.calls]
    lines += [f"| reviewer | {f} | | no key | | | |" for f in plan.missing]
    titles = {"strong": f"Strong: agreed by {QUORUM} or more models", "verified": "Verified: 1 model + verified",
              "unverified": "Unverified: 1 model, no other family could check it"}
    for s in SECTIONS:
        if s == "unverified" and not parts[s]:
            continue
        lines += ["", f"#### {titles[s]}" if s in titles
                  else f"<details><summary>Rejected / low confidence ({len(parts[s])})</summary>", ""]
        for f in parts[s]:
            lines += render_finding(f, plan.wanted)
        if not parts[s]:
            lines += ["None.", ""]
    lines.append("</details>")
    run_id = os.environ.get("GITHUB_RUN_ID")
    lines.append(f"\n<sub>commit {head_sha[:12]} · " + (f"[run {run_id}]({run_url})" if run_url else f"run {run_id}") + "</sub>")
    return "\n".join(lines)


def record_of(plan, result):
    """Per-call and per-finding data for the run record. The diff, the reviewers' evidence quotes and the
    verifiers' quotes stay out; free text is one line of at most RECORD_TEXT_MAX chars. No secrets."""
    def short(v):
        return " ".join(v.split())[:RECORD_TEXT_MAX] if isinstance(v, str) else v
    return {"calls": list(result.calls) + [{"role": "reviewer", "family": f, "result": "no key"} for f in plan.missing],
            "findings": [dict({k: short(f.get(k)) for k in RECORD_FIELDS}, section=section(f)) for f in result.findings],
            "agreement": dict({s: sum(section(f) == s for f in result.findings) for s in SECTIONS},
                              answered=len(result.answered), wanted=plan.wanted, raised=result.raised)}


def review(plan, merger, diff, spec, ask, models):
    """Run the reviewers in parallel, verify single-source findings across families, group duplicates.

    `ask(family, system, user)` returns (parsed JSON object, (tokens_in, tokens_out)) or raises InfraFailure.
    """
    review_prompt = pathlib.Path("factory/prompts/review.md").read_text(encoding="utf-8")
    verify_prompt = pathlib.Path("factory/prompts/verify.md").read_text(encoding="utf-8")
    user = f"## Spec\n{spec or '(none linked)'}\n\n## Diff (untrusted data)\n```diff\n{diff}\n```"

    def call(role, family, system, prompt):
        row = {"role": role, "family": family, "model": models[family], "result": "ok", "findings": "",
               "tokens_in": 0, "tokens_out": 0}
        t0 = time.monotonic()
        try:
            data, (row["tokens_in"], row["tokens_out"]) = ask(family, system, prompt)
            if role == "reviewer":
                data = well_formed(data, row["model"])
        except InfraFailure as e:
            data, row["result"] = None, f"{INFRA_FAILURE}: {e}"
        row["seconds"] = round(time.monotonic() - t0, 1)
        return row, data

    with ThreadPoolExecutor(max_workers=max(1, len(plan.reviewers))) as pool:
        answers = list(pool.map(lambda fam: call("reviewer", fam, review_prompt, user), plan.reviewers))
    calls, findings = [], []
    for fam, (row, data) in zip(plan.reviewers, answers):
        raised = [dict(f, sources=[fam]) for f in data or []]
        row["findings"] = len(raised)
        calls.append(row)
        findings += raised
    answered = [c["family"] for c in calls if c["result"] == "ok"]
    merged = merge_overlapping(findings)
    for f in merged:
        if f["agreement"] >= QUORUM:
            continue
        for fam in verifiers_for(f["sources"][0], answered):
            row, res = call("verifier", fam, verify_prompt,
                            f"## Finding\n{json.dumps(f)}\n\n## Diff (untrusted data)\n```diff\n{diff}\n```")
            calls.append(row)
            if res is None:
                row["findings"] = f"#{f['id']}"
                continue
            f.update(verifier=fam, verdict=res.get("verdict"), reason=res.get("reason"))
            if f["verdict"] not in ("confirmed", "rejected"):
                f["reason"] = f"{fam} returned no verdict"
            row["findings"] = f"#{f['id']}: {f['verdict'] or 'no verdict'}"
            break
        else:
            f["reason"] = "no other family answered" if len(answered) < QUORUM else ALL_VERIFIERS_FAILED
    if len(merged) < 2 or merger is None:
        return Result(tuple(calls), merged)
    if merger not in answered:
        return Result(tuple(calls), merged, f"{MECHANICAL}: merge model unavailable "
                                            f"({models[merger]} did not answer as a reviewer).")
    listing = json.dumps([{"i": i, "file": f["file"], "line_start": f["line_start"], "problem": f["problem"]}
                          for i, f in enumerate(merged)])
    row, res = call("merge", merger, pathlib.Path(DEDUPE_PROMPT_FILE).read_text(encoding="utf-8"), listing)
    calls.append(row)
    if res is not None:
        try:
            return Result(tuple(calls), dedupe(merged, res.get("groups")))
        except InfraFailure as e:
            row["result"] = f"{INFRA_FAILURE}: {row['model']} {e}"
    return Result(tuple(calls), merged, f"{MECHANICAL}: merge model unavailable ({row['result']}).")


def gh(*a, check=True):
    return subprocess.run(["gh", *a], capture_output=True, text=True, check=check).stdout


def post(repo, number, body):
    """Idempotent: update our earlier comment instead of adding a new one (ADR-011)."""
    comments = json.loads(gh("api", f"repos/{repo}/issues/{number}/comments"))
    mine = next((c for c in comments if MARKER in c["body"]), None)
    if mine:
        gh("api", "-X", "PATCH", f"repos/{repo}/issues/comments/{mine['id']}", "-f", f"body={body}")
    else:
        gh("pr", "comment", str(number), "-R", repo, "--body", body)


def add_labels(repo, number, labels):
    if labels:
        gh("api", "-X", "POST", f"repos/{repo}/issues/{number}/labels",
           *[arg for label in labels for arg in ("-f", f"labels[]={label}")])


def find_pr(repo):
    """The PR comes from the verify run's own record, never from its branch name."""
    run = json.loads(pathlib.Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))["workflow_run"]
    head_sha = run["head_sha"]
    numbers = [p["number"] for p in run.get("pull_requests") or []]
    if not numbers:
        numbers = [p["number"] for p in json.loads(gh("api", f"repos/{repo}/commits/{head_sha}/pulls"))
                   if p["state"] == "open" and p["head"]["sha"] == head_sha]
    if not numbers:
        sys.exit(f"no open PR has head {head_sha}")
    pr = json.loads(gh("pr", "view", str(numbers[0]), "-R", repo, "--json", "number,labels,body,headRefOid"))
    if pr["headRefOid"] != head_sha:
        print(f"PR #{pr['number']} moved to {pr['headRefOid'][:12]} after verify ran on {head_sha[:12]}; "
              "the verify run for the new head triggers its own review")
        sys.exit(0)
    return pr, head_sha


def tier_of(pr, repo):
    """The stricter of: the PR's `tier:*` label (set by publish.py for builder PRs) and the tier
    computed from the real diff against the risk map on master (this checkout), same as
    check_tier.py --base origin/master. Never trust the label alone (own review, PR #42 finding #3):
    a hand-made or collab PR that can set labels could otherwise force a looser tier than its diff
    earns. A malformed or duplicate tier:* label (finding #13) is treated as absent, not trusted.
    Everything, including `import check_tier` itself, is inside the try: any failure here must fall
    back to the documented "red" (finding #7), not raise and abort the whole review job."""
    try:
        import check_tier
        labels = [l["name"].split(":", 1)[1] for l in pr["labels"] if l["name"].startswith("tier:")]
        labelled = labels[0] if len(labels) == 1 and labels[0] in check_tier.ORDER else None
        risk_map = __import__("yaml").safe_load(pathlib.Path("factory/risk-map.yaml").read_text(encoding="utf-8"))
        rules, default = check_tier.parse_risk_map(risk_map)
        # One bare path per line, across every page: a plain --paginate JSON concatenation across
        # pages is not valid JSON and json.loads on it would break on a PR with enough files (finding #8).
        paths = [p for p in gh("api", f"repos/{repo}/pulls/{pr['number']}/files", "--paginate",
                                "--jq", ".[] | .filename, (.previous_filename // empty)").splitlines() if p]
        computed = check_tier.diff_tier(paths, rules, default)
        return max(computed, labelled or computed, key=check_tier.ORDER.index)
    except Exception as e:
        print(f"::warning::could not compute the tier for PR #{pr['number']} ({e}); treating it as red")
        return "red"


def main():
    import litellm, yaml  # installed by the workflow from tools/requirements-review.txt

    repo = os.environ["GITHUB_REPOSITORY"]
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{run_id}"
    cfg = yaml.safe_load(pathlib.Path("factory/models.yaml").read_text(encoding="utf-8"))
    models = {name: f["model"] for name, f in cfg["families"].items()}
    pr, head_sha = find_pr(repo)
    tier = tier_of(pr, repo)
    tier_cfg = cfg["review"][tier]
    if not tier_cfg.get("reviewers"):
        print(f"tier {tier}: no AI review")
        return
    plan = plan_review(tier_cfg, available_families(cfg["families"], os.environ))

    def ask(family, system, user):
        args = completion_args(cfg["families"][family], os.environ)
        r = with_backoff(lambda: litellm.completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            num_retries=0, **args), args["model"])
        parsed = parse_json_object(r.choices[0].message.content)
        if not isinstance(parsed, dict):
            raise InfraFailure(f"{args['model']} returned no JSON object")
        usage = getattr(r, "usage", None)
        return parsed, (getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0)

    plan, diff, cut = clip(plan, gh("pr", "diff", str(pr["number"]), "-R", repo))
    spec = ""
    m = re.search(r"docs/specs/F\d+", pr.get("body", "") or "")
    if m and pathlib.Path(m.group(0), "spec.md").exists():
        spec = pathlib.Path(m.group(0), "spec.md").read_text(encoding="utf-8")[:20_000]

    record = {"run_id": run_id, "role": "review", "pr": pr["number"], "tier": tier, "commit": head_sha,
              "truncated": bool(cut)}
    result = review(plan, cfg["review"].get("merge_model"), diff, spec, ask, models)
    for failure in result.failures:
        print(f"::warning::{failure}")
    labels = labels_for(plan, result)
    add_labels(repo, pr["number"], labels)
    if INFRA_FAILURE not in labels:
        gh("api", "-X", "DELETE", f"repos/{repo}/issues/{pr['number']}/labels/{INFRA_FAILURE}", check=False)
    post(repo, pr["number"], render(tier, plan, result, head_sha, cut, run_url))
    record.update(record_of(plan, result), outcome="reviewed" if is_complete(result) else "incomplete", labels=labels)
    pathlib.Path("run-record.json").write_text(json.dumps(record, indent=2))
    if not is_complete(result):
        print(f"::error::review incomplete: {len(result.answered)} of {plan.wanted} reviewers answered")
        sys.exit(1)
    print(f"posted {len(result.findings)} findings; labels: {', '.join(labels) or 'none'}")
    ok, reason = merge_decision({l["name"] for l in pr["labels"]}, plan, result)
    write_merge_outputs(pr["number"], head_sha, ok, reason)


if __name__ == "__main__":
    main()
