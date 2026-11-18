"""Preflight: which model credentials are set (yes/no only, never a value) and which roles can run (brief 003).

Usage: python tools/check_secrets_env.py [--role ROLE ...]
Without --role it prints the table and exits 0. With --role it fails when a named role can't run,
so a workflow stops before the agent instead of mid-run. Workflows pass a secret's presence, not its
value: `NAME: ${{ secrets.NAME != '' && 'set' || '' }}`.
"""
import argparse, os, sys

CREDENTIALS = ("CLAUDE_CODE_OAUTH_TOKEN", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_AI_V1_ENDPOINT")
AZURE = ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT")
# role -> (required, optional, what happens without the optional ones); mirrors factory/models.yaml
ROLES = {
    "spec-writer": (("CLAUDE_CODE_OAUTH_TOKEN",), (), ""),
    "builder": (("CLAUDE_CODE_OAUTH_TOKEN",), (), ""),
    "tester": (AZURE, (), ""),
    "review": (AZURE, ("AZURE_AI_V1_ENDPOINT",),
               "the Grok and DeepSeek reviewers are off; amber and red PRs get needs-human-review"),
}


def is_set(env, name):
    return bool(env.get(name, "").strip())


def readiness(env):
    """[(role, runnable, note)] from which credentials are set."""
    rows = []
    for role, (required, optional, degraded) in ROLES.items():
        missing = [n for n in required if not is_set(env, n)]
        absent = [n for n in optional if not is_set(env, n)]
        if missing:
            note = "missing " + ", ".join(missing)
        elif absent:
            note = f"without {', '.join(absent)}: {degraded}"
        else:
            note = ""
        rows.append((role, not missing, note))
    return rows


def report(env):
    lines = [f"{'credential':<26} set"]
    lines += [f"{n:<26} {'yes' if is_set(env, n) else 'no'}" for n in CREDENTIALS]
    lines += ["", f"{'role':<12} {'runnable':<9} note"]
    lines += [f"{role:<12} {'yes' if ok else 'no':<9} {note}".rstrip() for role, ok, note in readiness(env)]
    return "\n".join(lines)


def main(argv=None, env=None):
    env = os.environ if env is None else env
    p = argparse.ArgumentParser()
    p.add_argument("--role", action="append", default=[], choices=sorted(ROLES))
    a = p.parse_args(argv)
    print(report(env))
    blocked = [(role, note) for role, ok, note in readiness(env) if role in a.role and not ok]
    for role, note in blocked:
        print(f"::error::role {role} can't run: {note}. Set it with collab/setup-keys.ps1 -GitHub.")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
