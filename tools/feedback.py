"""PR feedback for a builder fix round (brief 033): maintainers' review comments, as data.

A person leaves review comments on a `wi-<n>` PR and sets the label `factory:fix`; 46-feedback starts the
next 30-build round, and the builder prompt gets the comments from here. Only comments written by
maintain/admin collaborators count (a write-only collaborator or a bot must not steer the agent), they are
size-capped, and they are wrapped in tags the prompt marks as untrusted data, never instructions.

Usage: python3 tools/feedback.py --branch wi-<n>      (needs GH_TOKEN, GITHUB_REPOSITORY)
"""
import argparse, json, os, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from authorize import AGENT_ROLES, role_of  # noqa: E402

BRANCH_RE = re.compile(r"^wi-[1-9][0-9]*$")
MAX_ITEMS = 50
MAX_CHARS = 2000


def pick(items, may_steer):
    """Newest MAX_ITEMS comments (dicts with login/body/where) from authors who may steer, oldest first."""
    kept = [i for i in items if (i.get("body") or "").strip() and may_steer(i.get("login") or "")]
    return kept[-MAX_ITEMS:]


def render(items):
    if not items:
        return ""
    out = ["", "## Review feedback from maintainers on this PR (answer each point in your run summary: "
               "addressed, or declined with a reason)",
           "<untrusted-review-feedback>"]
    for n, i in enumerate(items, 1):
        out.append(f"[{n}] {i.get('where') or 'general'}: {i['body'].strip()[:MAX_CHARS]}")
    out.append("</untrusted-review-feedback>")
    return "\n".join(out) + "\n"


def gh_json(*args):
    return json.loads(subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout or "[]")


def collect(repo, branch):
    prs = gh_json("pr", "list", "-R", repo, "--head", branch, "--state", "open", "--json", "number")
    if not prs:
        return []
    n = prs[0]["number"]
    items = []
    for c in gh_json("api", "--paginate", f"repos/{repo}/pulls/{n}/comments"):
        items.append({"login": c["user"]["login"], "body": c["body"], "when": c["created_at"],
                      "where": f"{c.get('path')}:{c.get('line') or c.get('original_line') or ''}"})
    for c in gh_json("api", "--paginate", f"repos/{repo}/issues/{n}/comments"):
        items.append({"login": c["user"]["login"], "body": c["body"], "when": c["created_at"], "where": "PR comment"})
    for r in gh_json("api", "--paginate", f"repos/{repo}/pulls/{n}/reviews"):
        items.append({"login": (r.get("user") or {}).get("login", ""), "body": r.get("body") or "",
                      "when": r.get("submitted_at") or "", "where": f"review ({r.get('state')})"})
    return sorted(items, key=lambda i: i["when"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--branch", required=True)
    a = p.parse_args()
    if not BRANCH_RE.fullmatch(a.branch):
        sys.exit("feedback: branch must be wi-<n>")
    repo = os.environ["GITHUB_REPOSITORY"]
    roles = {}

    def may_steer(login):
        if login not in roles:
            roles[login] = role_of(login, repo) if login and not login.endswith("[bot]") else ""
        return roles[login] in AGENT_ROLES

    print(render(pick(collect(repo, a.branch), may_steer)), end="")


if __name__ == "__main__":
    main()
