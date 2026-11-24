"""unblock_work_items.unblock() against a scripted `gh` (own incident: WI-2/WI-3 sat `blocked` for
days after WI-1 merged, since nothing ever re-checked depends_on)."""
import json, pathlib, subprocess, sys, unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import unblock_work_items as uw  # noqa: E402


def item(number, feature, wi, state, labels, depends_on):
    title = f"{feature} {wi}: title"
    body = f"Spec: docs/specs/{feature}/spec.md\nAC IDs: AC-{feature}-1\nPaths: a\n" \
           f"Depends on: {', '.join(depends_on) if depends_on else '-'}"
    return {"number": number, "title": title, "state": state, "body": body,
            "labels": [{"name": l} for l in labels]}


class FakeGh:
    def __init__(self, items, open_agent_prs=0):
        self.items = items
        self.open_agent_prs = open_agent_prs
        self.calls = []

    def __call__(self, cmd, **kwargs):
        args = cmd[1:]
        self.calls.append(args)
        out = ""
        if args[:2] == ["issue", "list"]:
            out = json.dumps(self.items)
        elif args[:2] == ["pr", "list"]:
            out = json.dumps([{"number": n} for n in range(self.open_agent_prs)])
        return subprocess.CompletedProcess(cmd, 0, out, "")


def run_unblock(items, open_agent_prs=0, wip_limit="3"):
    gh = FakeGh(items, open_agent_prs)
    with mock.patch.object(subprocess, "run", gh), \
         mock.patch.dict("os.environ", {"WIP_LIMIT": wip_limit}):
        done = uw.unblock()
    return done, gh.calls


class UnblockTest(unittest.TestCase):
    def test_dependency_merged_unblocks_and_dispatches(self):
        items = [
            item(17, "F7", "WI-1", "CLOSED", ["work-item"], []),
            item(11, "F7", "WI-2", "OPEN", ["work-item", "blocked"], ["WI-1"]),
        ]
        done, calls = run_unblock(items)
        self.assertEqual(done, [11])
        self.assertIn(["issue", "edit", "11", "--remove-label", "blocked"], calls)
        self.assertIn(["workflow", "run", "30 build", "-f", "issue=11", "-f", "round=0"], calls)

    def test_dependency_still_open_stays_blocked(self):
        items = [
            item(17, "F7", "WI-1", "OPEN", ["work-item"], []),
            item(11, "F7", "WI-2", "OPEN", ["work-item", "blocked"], ["WI-1"]),
        ]
        done, calls = run_unblock(items)
        self.assertEqual(done, [])
        self.assertFalse(any(c[:2] == ["issue", "edit"] for c in calls))

    def test_unrelated_feature_with_same_wi_id_is_not_mixed_up(self):
        items = [
            item(1, "F9", "WI-1", "OPEN", ["work-item"], []),
            item(17, "F7", "WI-1", "CLOSED", ["work-item"], []),
            item(11, "F7", "WI-2", "OPEN", ["work-item", "blocked"], ["WI-1"]),
        ]
        done, _ = run_unblock(items)
        self.assertEqual(done, [11])

    def test_multiple_dependencies_all_must_be_closed(self):
        items = [
            item(1, "F7", "WI-1", "CLOSED", ["work-item"], []),
            item(2, "F7", "WI-2", "OPEN", ["work-item"], []),
            item(3, "F7", "WI-3", "OPEN", ["work-item", "blocked"], ["WI-1", "WI-2"]),
        ]
        done, _ = run_unblock(items)
        self.assertEqual(done, [])

    def test_over_wip_limit_queues_instead_of_building(self):
        items = [
            item(17, "F7", "WI-1", "CLOSED", ["work-item"], []),
            item(11, "F7", "WI-2", "OPEN", ["work-item", "blocked"], ["WI-1"]),
        ]
        done, calls = run_unblock(items, open_agent_prs=3, wip_limit="3")
        self.assertEqual(done, [11])
        self.assertIn(["issue", "edit", "11", "--add-label", "queued"], calls)
        self.assertFalse(any(c[:2] == ["workflow", "run"] for c in calls))


if __name__ == "__main__":
    unittest.main()
