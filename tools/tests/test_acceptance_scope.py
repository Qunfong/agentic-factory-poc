import contextlib, io, json, pathlib, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import acceptance_scope as s  # noqa: E402

F1 = [
    {"id": "WI-1", "title": "validate", "ac_ids": ["AC-F1-1", "AC-F1-2"]},
    {"id": "WI-2", "title": "list", "ac_ids": ["AC-F1-3"]},
    {"id": "WI-3", "title": "delete", "ac_ids": ["AC-F1-4"]},
]
SPEC_F1 = "AC-F1-1 rejects. AC-F1-2 creates. AC-F1-3 lists. AC-F1-4 deletes."
ISSUES = [{"number": 11, "title": "F1 WI-1: validate"}, {"number": 12, "title": "F1 WI-2: list"},
          {"number": 13, "title": "F1 WI-3: delete"}]
MERGED_WI2 = [{"number": 40, "headRefName": "wi-12", "isCrossRepository": False},
              {"number": 41, "headRefName": "brief-007", "isCrossRepository": False},
              {"number": 42, "headRefName": "wi-13", "isCrossRepository": True}]


def write_tree(root, specs):
    for feature, (items, spec) in specs.items():
        d = pathlib.Path(root) / feature
        d.mkdir(parents=True)
        (d / "work-items.json").write_text(json.dumps(items), encoding="utf-8")
        (d / "spec.md").write_text(spec, encoding="utf-8")


def run(branch, base=None, head=None, issues=ISSUES, merged=MERGED_WI2):
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        write_tree(t / "base", base if base is not None else {"F1": (F1, SPEC_F1)})
        write_tree(t / "head", head or {})
        (t / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
        (t / "merged.json").write_text(json.dumps(merged), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = s.main(["--branch", branch, "--base-specs", str(t / "base"), "--head-specs", str(t / "head"),
                           "--issues", str(t / "issues.json"), "--merged", str(t / "merged.json")])
        return code, out.getvalue(), err.getvalue()


class ScopeTest(unittest.TestCase):
    def test_work_item_runs_its_acs_plus_merged_work_items_and_nothing_unbuilt(self):
        code, out, _ = run("wi-11")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["kind=wi", "scope=AC-F1-1 AC-F1-2 AC-F1-3"])

    def test_fork_and_non_work_item_merges_do_not_count_as_merged(self):
        code, out, _ = run("wi-11", merged=MERGED_WI2[1:])
        self.assertEqual(out.splitlines()[1], "scope=AC-F1-1 AC-F1-2")

    def test_other_pr_runs_the_regression_set(self):
        self.assertEqual(run("brief-007")[1].splitlines(), ["kind=other", "scope=AC-F1-3"])

    def test_other_pr_before_any_merge_has_an_empty_scope(self):
        code, out, err = run("brief-007", merged=[])
        self.assertEqual(out.splitlines(), ["kind=other", "scope="])
        self.assertIn("no ACs in scope", err)

    def test_work_item_branch_with_leading_zero_fails_instead_of_running_the_regression_set(self):
        for branch in ("wi-011", "wi-0", "wi-", "wi-11a"):
            code, out, err = run(branch)
            self.assertEqual((code, out), (1, ""), branch)
            self.assertIn("leading zeros", err)

    def test_merged_work_item_with_leading_zero_is_not_counted(self):
        merged = [{"number": 40, "headRefName": "wi-012", "isCrossRepository": False}]
        self.assertEqual(run("wi-11", merged=merged)[1].splitlines()[1], "scope=AC-F1-1 AC-F1-2")

    def test_unknown_issue_or_undefined_work_item_fails_instead_of_shrinking_scope(self):
        self.assertEqual(run("wi-99")[0], 1)
        renamed = [dict(ISSUES[0], title="F1 WI-9: validate")] + ISSUES[1:]
        code, _, err = run("wi-11", issues=renamed)
        self.assertEqual(code, 1)
        self.assertIn("do not define", err)
        self.assertEqual(run("wi-11", issues=[dict(ISSUES[0], title="validate")] + ISSUES[1:])[0], 1)

    def test_malformed_base_spec_fails_every_scope(self):
        code, _, err = run("brief-007", base={"F1": ([{"id": "WI-1", "ac_ids": ["AC-1"]}], "AC-1")})
        self.assertEqual(code, 1)
        self.assertIn("malformed AC ID 'AC-1'", err)

    def test_missing_input_file_fails(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(s.main(["--branch", "wi-1", "--base-specs", ".", "--head-specs", ".",
                                     "--issues", "nope.json", "--merged", "nope.json"]), 1)


class SpecPRTest(unittest.TestCase):
    def test_spec_pr_with_unique_well_formed_ids_passes_with_no_scenarios(self):
        code, out, _ = run("spec/F2", head={"F2": ([{"id": "WI-1", "ac_ids": ["AC-F2-1", "AC-F2-2"]}],
                                                   "AC-F2-1 and AC-F2-2")})
        self.assertEqual((code, out.splitlines()), (0, ["kind=spec", "scope="]))

    def assertSpecFails(self, items, spec, message):
        code, _, err = run("spec/F2", head={"F2": (items, spec)})
        self.assertEqual(code, 1)
        self.assertIn(message, err)

    def test_duplicate_id_fails(self):
        self.assertSpecFails([{"id": "WI-1", "ac_ids": ["AC-F2-1"]}, {"id": "WI-2", "ac_ids": ["AC-F2-1"]}],
                             "AC-F2-1", "duplicate AC ID AC-F2-1")

    def test_malformed_id_fails(self):
        self.assertSpecFails([{"id": "WI-1", "ac_ids": ["AC-1"]}], "AC-1", "malformed AC ID 'AC-1'")
        self.assertSpecFails([{"id": "WI-1", "ac_ids": ["AC-F2-01"]}], "AC-F2-01", "malformed")

    def test_id_of_another_feature_fails(self):
        self.assertSpecFails([{"id": "WI-1", "ac_ids": ["AC-F1-1"]}], "AC-F1-1", "belongs to another feature")

    def test_spec_text_must_describe_exactly_the_declared_ids(self):
        items = [{"id": "WI-1", "ac_ids": ["AC-F2-1"]}]
        self.assertSpecFails(items, "AC-F2-1 and AC-F2-7", "AC-F2-7 is malformed or not declared")
        self.assertSpecFails(items, "AC-2: legacy and AC-F2-1", "AC-2 is malformed")
        self.assertSpecFails(items, "nothing", "AC-F2-1 has no behaviour described")

    def test_work_item_without_acs_or_with_duplicate_id_fails(self):
        self.assertSpecFails([{"id": "WI-1", "ac_ids": []}], "", "has no ac_ids")
        self.assertSpecFails([{"id": "WI-1", "ac_ids": ["AC-F2-1"]}, {"id": "WI-1", "ac_ids": ["AC-F2-2"]}],
                             "AC-F2-1 AC-F2-2", "needs a unique id")

    def test_missing_spec_folder_fails(self):
        self.assertEqual(run("spec/F2")[0], 1)


if __name__ == "__main__":
    unittest.main()
