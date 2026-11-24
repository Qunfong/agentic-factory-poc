import pathlib, sys, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import unblock  # noqa: E402


def issue(n, title, state="OPEN", labels=(), body=""):
    return {"number": n, "title": title, "state": state, "body": body, "labels": [{"name": l} for l in labels]}


BODY = "Spec: docs/specs/F7/spec.md\nAC IDs: AC-F7-2\nPaths: app/\nDepends on: WI-1"


class UnblockTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unblock.parse_dependencies(BODY), ("F7", ["WI-1"]))
        self.assertEqual(unblock.parse_dependencies(BODY.replace("WI-1", "WI-1, WI-2"))[1], ["WI-1", "WI-2"])
        self.assertEqual(unblock.parse_dependencies("Depends on: -")[1], [])

    def issues(self, wi1_state="CLOSED"):
        return [issue(10, "F7 WI-1: a", wi1_state, ["work-item"]),
                issue(11, "F7 WI-2: b", "OPEN", ["work-item", "blocked"], BODY)]

    def test_starts_when_dependency_closed_by_merged_pr(self):
        self.assertEqual(unblock.ready_to_start(self.issues(), {"wi-10"}), [(11, ["WI-1"])])

    def test_hand_closed_dependency_without_merged_pr_does_not_unblock(self):
        self.assertEqual(unblock.ready_to_start(self.issues(), set()), [])

    def test_open_dependency_does_not_unblock(self):
        self.assertEqual(unblock.ready_to_start(self.issues("OPEN"), {"wi-10"}), [])

    def test_unknown_dependency_does_not_unblock(self):
        issues = [issue(11, "F7 WI-2: b", "OPEN", ["blocked"], BODY)]
        self.assertEqual(unblock.ready_to_start(issues, {"wi-10"}), [])

    def test_unparsable_blocked_item_is_reported(self):
        self.assertEqual(unblock.ready_to_start([issue(5, "x", "OPEN", ["blocked"], "no lines")], set()), [(5, None)])

    def test_not_blocked_items_are_ignored(self):
        self.assertEqual(unblock.ready_to_start([issue(11, "F7 WI-2: b", "OPEN", ["work-item"], BODY)], {"wi-10"}), [])


if __name__ == "__main__":
    unittest.main()
