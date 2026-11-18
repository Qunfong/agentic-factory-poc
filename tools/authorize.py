"""Fail an agent workflow before any model call unless every actor behind the run may start agents (brief 009).

An actor passes when it is the factory-bot App (FACTORY_BOT_LOGIN), GitHub's own Actions bot on a
workflow_dispatch (a workflow in this repo dispatched the run with its GITHUB_TOKEN; fork runs hold a
read-only token and can't dispatch), or a collaborator whose role is maintain or admin.
The role comes from `role_name`: the legacy `permission` field reports maintain as write and triage as read.

Usage: python3 tools/authorize.py --event EVENT ACTOR [ACTOR...]
Needs GH_TOKEN and GITHUB_REPOSITORY; reads FACTORY_BOT_LOGIN.
"""
import argparse, os, subprocess, sys, urllib.parse

AGENT_ROLES = frozenset({"maintain", "admin"})
ACTIONS_BOT = "github-actions[bot]"


def decide(login, role, bot_login, event):
    """None when `login` may start an agent, else the reason it may not."""
    who = login.casefold()
    if not who:
        return "no actor"
    if bot_login and who == bot_login.casefold():
        return None
    if who == ACTIONS_BOT and event == "workflow_dispatch":
        return None
    if role in AGENT_ROLES:
        return None
    return f"{login} has role '{role or 'none'}'; agents start only for the factory bot, maintain or admin"


def last_labeler(events, label):
    """Login that last applied `label`, from an issue's events in API order (oldest first); "" if none did."""
    applied = [e for e in events if e.get("event") == "labeled" and (e.get("label") or {}).get("name") == label]
    return str(((applied[-1].get("actor") or {}).get("login")) or "") if applied else ""


def label_refusal(events, label, role_lookup, bot_login):
    """None when whoever last applied `label` may start an agent, else the reason (brief 011, Q27).

    A label from github-actions[bot] was applied by a workflow of this repo with its GITHUB_TOKEN,
    so it is judged like that workflow dispatching a build.
    """
    who = last_labeler(events, label)
    if not who:
        return f"no one applied the '{label}' label"
    reason = decide(who, role_lookup(who), bot_login, "workflow_dispatch")
    return reason and f"'{label}' label: {reason}"


def role_of(login, repo):
    path = f"repos/{repo}/collaborators/{urllib.parse.quote(login, safe='')}/permission"
    r = subprocess.run(["gh", "api", path, "--jq", ".role_name"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--event", required=True)
    p.add_argument("actors", nargs="+")
    a = p.parse_args()
    repo = os.environ["GITHUB_REPOSITORY"]
    bot = os.environ.get("FACTORY_BOT_LOGIN", "").strip()
    denied = [reason for login in dict.fromkeys(a.actors)
              if (reason := decide(login, role_of(login, repo), bot, a.event))]
    for reason in denied:
        print(f"::error::{reason}")
    if denied:
        sys.exit(1)
    print(f"authorized: {', '.join(dict.fromkeys(a.actors))}")


if __name__ == "__main__":
    main()
