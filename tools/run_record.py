"""Write run-record.json for one agent run (POC: uploaded as artifact; production: append-only store)."""
import argparse, hashlib, json, os, pathlib, subprocess, time

p = argparse.ArgumentParser()
for f in ("role", "issue", "pr", "model", "status", "round"):
    p.add_argument(f"--{f}", default="")
a = p.parse_args()

def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:16] if pathlib.Path(path).exists() else ""

rec = {
    "run_id": os.environ.get("GITHUB_RUN_ID"), "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    "role": a.role, "charter_hash": sha(f"factory/charters/{a.role}.yaml"),
    "prompt_hash": sha(f"factory/prompts/{a.role}.md"), "skills_lock_hash": sha("factory/skills.lock.yaml"),
    "model": a.model, "issue": a.issue, "pr": a.pr, "fix_round": a.round,
    "commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
    "actor": os.environ.get("GITHUB_ACTOR"), "reason": "success" if a.status == "success" else a.status or "unknown",
    "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
pathlib.Path("run-record.json").write_text(json.dumps(rec, indent=2))
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as s:
        s.write("### Run record\n```json\n" + json.dumps(rec, indent=2) + "\n```\n")
