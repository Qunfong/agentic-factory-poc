"""25-dispatch's `--dispatch-queued` against a scripted `gh`: only trusted ready labels start a build (brief 011, Q27)."""
import contextlib, io, json, os, pathlib, runpy, subprocess, sys, unittest
from unittest import mock

TOOL = pathlib.Path(__file__).resolve().parents[1] / "create_work_items.py"
BOT = "agentic-factory-bot-qunfong[bot]"
ROLES = {"qun": "admin", "dev": "write"}


def labeled(login):
    return {"event": "labeled", "actor": {"login": login}, "label": {"name": "queued"}}


class FakeGh:
    def __init__(self, events_by_issue):
        self.events = events_by_issue
        self.calls = []

    def __call__(self, cmd, **kwargs):
        assert cmd[0] == "gh", cmd
        args = cmd[1:]
        self.calls.append(args)
        out, code = "", 0
        if args[:2] == ["issue", "list"]:
            out = json.dumps([{"number": n} for n in self.events])
        elif args[:2] == ["pr", "list"]:
            out = "[]"
        elif args[0] == "api" and "/collaborators/" in args[-3]:
            login = args[-3].split("/collaborators/")[1].split("/")[0]
            out, code = (ROLES[login] + "\n", 0) if login in ROLES else ("", 1)
        elif args[0] == "api":
            issue = int(args[2].split("/")[-2])
            out = "".join(json.dumps(e) + "\n" for e in self.events[issue])
        if kwargs.get("check") and code:
            raise subprocess.CalledProcessError(code, cmd)
        return subprocess.CompletedProcess(cmd, code, out, "")


def dispatch_queued(events_by_issue):
    gh = FakeGh(events_by_issue)
    env = {"GITHUB_REPOSITORY": "o/r", "FACTORY_BOT_LOGIN": BOT, "WIP_LIMIT": "3"}
    out, code = io.StringIO(), None
    with mock.patch.object(subprocess, "run", gh), mock.patch.dict(os.environ, env), \
            mock.patch.object(sys, "argv", [str(TOOL), "--dispatch-queued"]), contextlib.redirect_stdout(out):
        try:
            runpy.run_path(str(TOOL), run_name="__main__")
        except SystemExit as e:
            code = e.code
    return code, gh.calls, out.getvalue()


def builds(calls):
    return [c[c.index("-f") + 1] for c in calls if c[:2] == ["workflow", "run"]]


class DispatchQueuedTest(unittest.TestCase):
    def test_trusted_labels_dispatch_and_a_write_collaborator_label_does_not(self):
        code, calls, out = dispatch_queued({5: [labeled(BOT)], 6: [labeled("dev")], 7: [labeled("qun")],
                                            8: [labeled("github-actions[bot]")]})
        self.assertEqual(builds(calls), ["issue=5", "issue=7", "issue=8"])
        self.assertIn("#6 not dispatched: 'queued' label: dev has role 'write'", out)
        self.assertEqual(code, 1)

    def test_all_trusted_exits_clean(self):
        code, calls, _ = dispatch_queued({5: [labeled(BOT)]})
        self.assertEqual((code, builds(calls)), (0, ["issue=5"]))

    def test_events_are_read_paginated_one_json_object_per_line(self):
        _, calls, _ = dispatch_queued({5: [labeled(BOT)]})
        self.assertIn(["api", "--paginate", "repos/o/r/issues/5/events", "--jq", ".[] | @json"], calls)


if __name__ == "__main__":
    unittest.main()
