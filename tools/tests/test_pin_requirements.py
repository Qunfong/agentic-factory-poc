"""tools/pin_requirements.py's closure, its 14-day age cutoff and the committed hash-pinned files (brief 011, Q21, Q53)."""
import datetime, pathlib, re, sys, unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from pin_requirements import PinError, closure, parse_young_pins, select  # noqa: E402

RESOLVED = {
    "app": {"version": "1.0", "requires_dist": ['lib>=2', 'colorama; platform_system == "Windows"',
                                                'tomli; python_version < "3.11"', 'uvloop; sys_platform == "linux"',
                                                'extra-dep; extra == "fast"']},
    "lib": {"version": "2.1", "requires_dist": []},
    "uvloop": {"version": "0.21", "requires_dist": []},
    "extra-dep": {"version": "3.0", "requires_dist": None},
    "colorama": {"version": "0.4", "requires_dist": []},
}


class ClosureTest(unittest.TestCase):
    def test_runner_markers_decide_not_the_host(self):
        self.assertEqual(sorted(closure(["app==1.0"], RESOLVED)), ["app", "lib", "uvloop"])

    def test_extras_pull_their_dependencies(self):
        self.assertIn("extra-dep", closure(["app[fast]==1.0"], RESOLVED))

    def test_a_dependency_the_resolution_lacks_fails(self):
        resolved = {k: v for k, v in RESOLVED.items() if k != "uvloop"}
        with self.assertRaisesRegex(PinError, "no uvloop"):
            closure(["app==1.0"], resolved)

    def test_a_version_outside_the_specifier_fails(self):
        with self.assertRaisesRegex(PinError, "lib 1.5 does not satisfy"):
            closure(["app==1.0"], {**RESOLVED, "lib": {"version": "1.5", "requires_dist": []}})


NOW = datetime.datetime(2026, 11, 11, 12, tzinfo=datetime.timezone.utc)
CUTOFF = NOW - datetime.timedelta(days=14)


def file(days_old, sha):
    t = NOW - datetime.timedelta(days=days_old)
    return {"upload_time_iso_8601": t.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "digests": {"sha256": sha * 64}}


INDEX = {
    "app": {"1.0": [file(30, "a")], "1.1": [file(20, "b")], "1.2": [file(3, "c")]},
    "lib": {"2.0": [file(400, "d")], "2.1": [file(40, "e"), file(2, "f")], "2.2": [file(13, "1")]},
}
REQUIRES = {"app": ["lib>=2"], "lib": []}


def fake_resolve(constraints_text):
    """The newest version of each project that the constraints file does not exclude, as pip would pick."""
    excluded = {}
    for line in constraints_text.splitlines():
        name, _, rest = line.partition("!=")
        excluded[name] = {v.strip() for v in rest.split(",!=")}
    out = {}
    for name in ("app", "lib"):
        version = max((v for v in INDEX[name] if v not in excluded.get(name, ())),
                      key=lambda v: tuple(map(int, v.split("."))))
        out[name] = {"version": version, "requires_dist": REQUIRES[name],
                     "picked": {"hash": "sha256=" + INDEX[name][version][0]["digests"]["sha256"]}}
    return out


def pinned(roots, allowed=None):
    return {n: v for n, v, _ in select(roots, fake_resolve, INDEX.__getitem__, allowed or {}, CUTOFF)}


class AgeCutoffTest(unittest.TestCase):
    def test_versions_younger_than_14_days_are_skipped_for_the_newest_older_one(self):
        self.assertEqual(pinned(["app"]), {"app": "1.1", "lib": "2.0"})

    def test_a_wheel_added_late_to_an_old_release_makes_it_young(self):
        self.assertNotEqual(pinned(["app"])["lib"], "2.1")

    def test_every_file_of_the_pinned_version_is_hashed(self):
        pins = select(["app"], fake_resolve, INDEX.__getitem__, {}, CUTOFF)
        self.assertEqual(pins[0], ("app", "1.1", ["b" * 64]))

    def test_an_exact_root_pin_younger_than_14_days_fails(self):
        with self.assertRaisesRegex(PinError, "app==1.2 was uploaded after 2026-10-28"):
            pinned(["app==1.2"])

    def test_young_pins_allows_exactly_the_listed_version(self):
        self.assertEqual(pinned(["app==1.2"], {"app": "1.2"}), {"app": "1.2", "lib": "2.0"})
        self.assertEqual(pinned(["app"], {"lib": "2.2"}), {"app": "1.1", "lib": "2.2"})
        with self.assertRaises(PinError):
            pinned(["app==1.2"], {"app": "1.1"})

    def test_a_resolver_that_ignores_the_constraints_fails_instead_of_pinning_young(self):
        with self.assertRaisesRegex(PinError, "app 1.2 was uploaded .*, after 2026-10-28"):
            select(["app"], lambda _: fake_resolve(""), INDEX.__getitem__, {}, CUTOFF)


class YoungPinsFileTest(unittest.TestCase):
    def test_entries_need_a_reason_and_a_date(self):
        text = "# header\n\nLitellm==1.2.3  # CVE-2026-1 fix, 2026-11-10\n"
        self.assertEqual(parse_young_pins(text), {"litellm": "1.2.3"})
        for bad in ("litellm==1.2.3", "litellm==1.2.3  # urgent", "litellm>=1.2  # fix, 2026-11-10",
                    "litellm==1.2.3  # , 2026-11-10"):
            with self.subTest(bad=bad), self.assertRaises(PinError):
                parse_young_pins(bad)

    def test_the_committed_file_parses(self):
        parse_young_pins((TOOLS / "young-pins.txt").read_text(encoding="utf-8"))


def pins(path):
    """{name: (version, [sha256...])} from a hash-pinned requirements file."""
    text = path.read_text(encoding="utf-8").replace("\\\n", " ")
    out = {}
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            m = re.fullmatch(r"([a-z0-9-]+)==(\S+)((?:\s+--hash=sha256:[0-9a-f]{64})+)\s*", line)
            assert m, line[:80]
            out[m.group(1)] = (m.group(2), re.findall(r"[0-9a-f]{64}", m.group(3)))
    return out


class CommittedFilesTest(unittest.TestCase):
    def test_every_line_is_pinned_and_hashed_and_covers_its_in_file(self):
        for name in ("requirements", "requirements-review"):
            got = pins(TOOLS / f"{name}.txt")
            self.assertTrue(got, name)
            for root in (TOOLS / f"{name}.in").read_text(encoding="utf-8").split():
                pkg, version = root.split("==")
                self.assertEqual(got[pkg][0], version, (name, root))

    def test_both_files_pin_pyyaml_alike(self):
        self.assertEqual(pins(TOOLS / "requirements.txt")["pyyaml"], pins(TOOLS / "requirements-review.txt")["pyyaml"])


if __name__ == "__main__":
    unittest.main()
