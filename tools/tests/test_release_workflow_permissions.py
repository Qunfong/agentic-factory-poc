"""Audit R2 evidence: 60-release.yml scopes packages: write to the build job only.

Reads the real workflow file. A job that declares its own `permissions` block replaces the
workflow-level block entirely (GitHub Actions semantics); a job with no block inherits it.
"""
import pathlib, unittest

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/60-release.yml"


class TestReleaseWorkflowPermissions(unittest.TestCase):
    def setUp(self):
        self.doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def test_workflow_level_has_no_write_scope(self):
        self.assertEqual(self.doc["permissions"], {"contents": "read"})

    def test_each_job_has_exactly_the_scope_it_needs(self):
        expected = {"build": {"contents": "read", "packages": "write"},
                    "release-record": {"contents": "read", "pull-requests": "read"}}
        jobs = self.doc["jobs"]
        for name, job in jobs.items():
            perms = job.get("permissions")
            if name in expected:
                self.assertEqual(perms, expected[name])
            else:
                self.assertIsNone(perms, f"{name} must not declare its own permissions (would stop inheriting contents: read only)")

    def test_staging_and_production_resolve_to_read_only(self):
        jobs = self.doc["jobs"]
        for name in ("staging", "production"):
            resolved = jobs[name].get("permissions") or self.doc["permissions"]
            self.assertEqual(resolved, {"contents": "read"}, f"{name} must resolve to contents: read only")


if __name__ == "__main__":
    unittest.main()
