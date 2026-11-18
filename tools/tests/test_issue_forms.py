"""check_issue_forms over the design field of .github/ISSUE_TEMPLATE/feature.yml, before and after quoting its label.
Each line is mirrored by hand so the test runs without pyyaml; with pyyaml the mirror is checked against the parser."""
import pathlib, sys, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_workflow_policy as policy  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None

BROKEN_LINE = "attributes: {label: Design link (tokens, reference images, mockups)}"
FIXED_LINE = 'attributes: {label: "Design link (tokens, reference images, mockups)"}'
BROKEN = {"label": "Design link (tokens", "reference images": None, "mockups)": None}
FIXED = {"label": "Design link (tokens, reference images, mockups)"}


def form(attributes):
    return {"feature.yml": {"name": "Feature", "description": "d", "labels": ["feature"], "body": [
        {"type": "input", "id": "design", "attributes": attributes}]}}


class IssueFormTest(unittest.TestCase):
    def test_unquoted_label_with_commas_fails_and_quoted_passes(self):
        self.assertEqual(policy.check_issue_forms(form(BROKEN)), [
            "feature.yml: body[1] (design): attributes has keys outside GitHub's form schema: "
            "'mockups)', 'reference images'; quote a value that holds commas"])
        self.assertEqual(policy.check_issue_forms(form(FIXED)), [])

    @unittest.skipUnless(yaml, "pyyaml not installed")
    def test_mirrors_match_the_parser(self):
        self.assertEqual(yaml.safe_load(BROKEN_LINE)["attributes"], BROKEN)
        self.assertEqual(yaml.safe_load(FIXED_LINE)["attributes"], FIXED)

    def test_missing_top_level_keys_and_unknown_types_fail(self):
        found = policy.check_issue_forms({"f.yml": {"name": "F", "body": [{"type": "text", "attributes": {}}]}})
        self.assertEqual(found, ["f.yml: missing top-level `description`", "f.yml: body[1] (text): unknown type 'text'"])

    def test_yaml_1_1_boolean_key_is_reported_not_crashed_on(self):
        found = policy.check_issue_forms(form({"label": "L", True: "x"}))
        self.assertEqual(len(found), 1)
        self.assertIn("True", found[0])


if __name__ == "__main__":
    unittest.main()
