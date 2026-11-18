import pathlib, sys, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from authorize import decide, label_refusal  # noqa: E402

BOT = "agentic-factory-bot-qunfong[bot]"


class DecisionTableTest(unittest.TestCase):
    def test_table(self):
        rows = [
            # login, role_name, FACTORY_BOT_LOGIN, event, allowed
            ("qun", "admin", BOT, "issues", True),
            ("lead", "maintain", BOT, "workflow_dispatch", True),
            ("dev", "write", BOT, "workflow_dispatch", False),
            ("helper", "triage", BOT, "issues", False),
            ("reader", "read", BOT, "issues", False),
            ("outsider", "", BOT, "issues", False),
            ("outsider", "none", BOT, "issues", False),
            (BOT, "", BOT, "workflow_dispatch", True),
            ("Agentic-Factory-Bot-Qunfong[bot]", "", BOT, "issues", True),
            ("github-actions[bot]", "", BOT, "workflow_dispatch", True),
            ("github-actions[bot]", "", BOT, "issues", False),
            ("other-app[bot]", "", BOT, "workflow_dispatch", False),
            ("", "admin", BOT, "workflow_dispatch", False),
        ]
        for login, role, bot, event, allowed in rows:
            with self.subTest(login=login, role=role, event=event):
                self.assertEqual(decide(login, role, bot, event) is None, allowed)

    def test_missing_bot_login_admits_no_bot_and_no_one_else(self):
        for bot in ("", None):
            self.assertIsNotNone(decide(BOT, "", bot, "workflow_dispatch"))
            self.assertIsNotNone(decide("", "", bot, "workflow_dispatch"))
            self.assertIsNotNone(decide("dev", "write", bot, "issues"))
            self.assertIsNone(decide("qun", "admin", bot, "issues"))

    def test_reason_names_the_actor_and_role(self):
        self.assertIn("dev has role 'write'", decide("dev", "write", BOT, "issues"))


def labeled(login, name="queued"):
    return {"event": "labeled", "actor": {"login": login}, "label": {"name": name}}


ROLES = {"qun": "admin", "lead": "maintain", "dev": "write", "github-actions[bot]": "", BOT: ""}


class ReadyLabelTest(unittest.TestCase):
    """25-dispatch starts a build only when the bot, a workflow or maintain/admin last applied `queued` (Q27)."""

    def refusal(self, events):
        return label_refusal(events, "queued", lambda login: ROLES.get(login, ""), BOT)

    def test_trusted_labelers_dispatch(self):
        for login in (BOT, "github-actions[bot]", "qun", "lead"):
            self.assertIsNone(self.refusal([labeled(login)]), login)

    def test_write_collaborator_or_outsider_label_is_refused(self):
        for login in ("dev", "stranger", "other-app[bot]"):
            self.assertIn(f"{login} has role", self.refusal([labeled(login)]), login)

    def test_the_last_application_counts(self):
        self.assertIsNotNone(self.refusal([labeled(BOT), {"event": "unlabeled", "actor": {"login": "dev"},
                                                          "label": {"name": "queued"}}, labeled("dev")]))
        self.assertIsNone(self.refusal([labeled("dev"), labeled("qun")]))

    def test_other_labels_and_events_do_not_count(self):
        events = [labeled("qun", "work-item"), {"event": "commented", "actor": {"login": "qun"}}, labeled("dev")]
        self.assertIsNotNone(self.refusal(events))
        self.assertEqual(self.refusal([labeled("qun", "work-item")]), "no one applied the 'queued' label")
        self.assertIsNotNone(self.refusal([{"event": "labeled", "actor": None, "label": {"name": "queued"}}]))


if __name__ == "__main__":
    unittest.main()
