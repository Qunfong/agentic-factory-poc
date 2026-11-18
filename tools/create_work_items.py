"""Create work-item issues from work-items.json (idempotent) and dispatch builds within the WIP limit."""
import json, os, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from authorize import label_refusal, role_of  # noqa: E402

READY_LABEL = "queued"

def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout

def open_agent_prs():
    return len(json.loads(gh("pr", "list", "--label", "agent", "--state", "open", "--json", "number")))

def dispatch(issue):
    if open_agent_prs() >= int(os.environ.get("WIP_LIMIT", "3")):
        gh("issue", "edit", str(issue), "--add-label", READY_LABEL)
        return
    gh("issue", "edit", str(issue), "--remove-label", READY_LABEL)
    gh("workflow", "run", "30 build", "-f", f"issue={issue}", "-f", "round=0")

def ready_label_refusal(issue):
    """A write collaborator can add the ready label; only the bot, a workflow or maintain/admin may start a build."""
    repo = os.environ["GITHUB_REPOSITORY"]
    lines = gh("api", "--paginate", f"repos/{repo}/issues/{issue}/events", "--jq", ".[] | @json").splitlines()
    return label_refusal([json.loads(l) for l in lines if l.strip()], READY_LABEL,
                         lambda login: role_of(login, repo), os.environ.get("FACTORY_BOT_LOGIN", "").strip())

if sys.argv[1] == "--dispatch-queued":
    refused = 0
    for it in json.loads(gh("issue", "list", "--label", READY_LABEL, "--state", "open", "--json", "number")):
        reason = ready_label_refusal(it["number"])
        if reason:
            print(f"::error::#{it['number']} not dispatched: {reason}")
            refused += 1
            continue
        dispatch(it["number"])
    sys.exit(1 if refused else 0)

path = sys.argv[1]
feature = path.split("/")[2]                       # docs/specs/F<n>/work-items.json
items = json.load(open(path))
existing = {i["title"] for i in json.loads(gh("issue", "list", "--label", "work-item", "--state", "all",
                                              "--limit", "500", "--json", "title"))}
created = {}
for it in items:
    title = f"{feature} {it['id']}: {it['title']}"
    if title in existing:
        continue
    body = (f"Spec: docs/specs/{feature}/spec.md\nAC IDs: {', '.join(it['ac_ids'])}\n"
            f"Paths: {', '.join(it.get('paths', []))}\nDepends on: {', '.join(it.get('depends_on', [])) or '-'}")
    url = gh("issue", "create", "--title", title, "--body", body, "--label", "work-item").strip()
    created[it["id"]] = (int(url.rsplit("/", 1)[1]), it.get("depends_on", []))
for wid, (num, deps) in created.items():
    if not deps:
        dispatch(num)
    else:
        gh("issue", "edit", str(num), "--add-label", "blocked")
print(f"created {len(created)} work items")
