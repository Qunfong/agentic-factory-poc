"""Release check: every agent-assisted commit since the last release carries a Factory-Run trailer."""
import argparse, subprocess, sys

p = argparse.ArgumentParser(); p.add_argument("--since", required=True); a = p.parse_args()
rng = "HEAD" if set(a.since) <= {"0"} else f"{a.since}..HEAD"
log = subprocess.run(["git", "log", "--format=%H%x00%B%x01", rng], capture_output=True, text=True, check=True).stdout
bad = [c.split("\x00")[0][:12] for c in log.split("\x01") if "Assisted-by:" in c and "Factory-Run:" not in c]
if bad:
    print("Agent commits without a run record:", ", ".join(bad)); sys.exit(1)
print("run-record check ok")
