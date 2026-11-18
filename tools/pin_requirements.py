"""Write a hash-pinned requirements file for the CI runner (ubuntu-latest, CPython 3.12, x86_64) from a .in file.

pip-compile does this too, but it is not installed here. This resolves with pip's own dry run for the
runner's platform, wheels only, then recomputes the closure under the runner's markers, because pip
evaluates markers on the host. Every file PyPI holds for each pinned version gets its sha256 (like
pip-compile --generate-hashes); pip confirms the hash of what it downloads.

No pin may be younger than MIN_AGE (Q53): most malicious or broken releases are yanked within days.
pip 22 has no upload-time cutoff, so every version of a pinned project uploaded after the cutoff is
excluded through a constraints file and pip resolves again, until the closure holds only old versions.
A security fix that cannot wait goes in tools/young-pins.txt, which is a protected change.

Usage: python -I tools/pin_requirements.py tools/requirements-review.in tools/requirements-review.txt
Needs network access to PyPI and pip >= 22.2. Installs nothing.
"""
import datetime, functools, json, pathlib, re, subprocess, sys, tempfile, urllib.request
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.utils import canonicalize_name

RUNNER = {"implementation_name": "cpython", "implementation_version": "3.12.3", "os_name": "posix",
          "platform_machine": "x86_64", "platform_python_implementation": "CPython", "platform_release": "",
          "platform_system": "Linux", "platform_version": "", "python_full_version": "3.12.3",
          "python_version": "3.12", "sys_platform": "linux"}
PIP_TARGET = ["--platform", "manylinux_2_39_x86_64", "--platform", "manylinux_2_28_x86_64",
              "--platform", "manylinux2014_x86_64", "--platform", "linux_x86_64", "--python-version", "3.12",
              "--implementation", "cp", "--abi", "cp312", "--abi", "abi3", "--abi", "none", "--only-binary=:all:"]
MIN_AGE = datetime.timedelta(days=14)
YOUNG_PINS = pathlib.Path(__file__).resolve().parent / "young-pins.txt"
YOUNG_PIN_LINE = re.compile(r"([A-Za-z0-9._-]+)==(\S+)\s+#\s*(\S.*\S),\s*(\d{4}-\d{2}-\d{2})")
MAX_ROUNDS = 10


class PinError(Exception):
    pass


def applies(req, extras, env=RUNNER):
    return req.marker is None or any(req.marker.evaluate({**env, "extra": e}) for e in {"", *extras})


def closure(roots, resolved, env=RUNNER):
    """{name: extras} the runner installs from roots, given {name: {"version", "requires_dist"}} from pip's report."""
    need, todo = {}, [Requirement(r) for r in roots]
    while todo:
        req = todo.pop()
        name = canonicalize_name(req.name)
        meta = resolved.get(name)
        if meta is None:
            raise PinError(f"the runner needs {req}, but pip's resolution has no {name}")
        if not req.specifier.contains(meta["version"], prereleases=True):
            raise PinError(f"{name} {meta['version']} does not satisfy {req}")
        done = need.get(name)
        if done is not None and set(req.extras) <= done:
            continue
        extras = need[name] = (done or set()) | set(req.extras)
        for d in meta.get("requires_dist") or []:
            dep = Requirement(d)
            if applies(dep, extras, env):
                dep.marker = None
                todo.append(dep)
    return need


def parse_young_pins(text):
    """{name: version} from tools/young-pins.txt; each entry is `pkg==version  # reason, YYYY-MM-DD`."""
    allowed = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = YOUNG_PIN_LINE.fullmatch(line.strip())
        if not m:
            raise PinError(f"young-pins.txt:{n}: expected `pkg==version  # reason, YYYY-MM-DD`, got {line.strip()!r}")
        allowed[canonicalize_name(m.group(1))] = m.group(2)
    return allowed


def uploaded(files):
    """When the newest file of a release reached PyPI: a wheel added later can be installed too."""
    return max(datetime.datetime.fromisoformat(f["upload_time_iso_8601"].replace("Z", "+00:00")) for f in files)


def young_versions(releases, cutoff, allowed=None):
    """Versions in {version: [PyPI file]} uploaded after cutoff, except the one young-pins.txt allows."""
    return sorted(v for v, files in releases.items() if files and v != allowed and uploaded(files) > cutoff)


def constraints(excluded):
    return "".join(f"{n}{','.join('!=' + v for v in vs)}\n" for n, vs in sorted(excluded.items()) if vs)


def select(roots, resolve, releases_of, allowed, cutoff):
    """[(name, version, [sha256...])] for the closure of roots, with no version uploaded after cutoff
    unless allowed. resolve(constraints_text) -> pip's resolution; releases_of(name) -> PyPI's releases."""
    excluded = {}
    for root in map(Requirement, roots):
        name = canonicalize_name(root.name)
        exact = [s.version for s in root.specifier if s.operator == "=="]
        if exact and exact[0] in young_versions(releases_of(name), cutoff, allowed.get(name)):
            raise PinError(f"{root} was uploaded after {cutoff:%Y-%m-%d}; pin an older version, or add a security "
                           f"fix to tools/young-pins.txt as `{name}=={exact[0]}  # reason, YYYY-MM-DD`")
    for _ in range(MAX_ROUNDS):
        resolved = resolve(constraints(excluded))
        need = closure(roots, resolved)
        unseen = [n for n in need if n not in excluded]
        if not unseen:
            break
        for n in unseen:
            excluded[n] = young_versions(releases_of(n), cutoff, allowed.get(n))
        if not any(resolved[n]["version"] in excluded[n] for n in unseen):
            break
    else:
        raise PinError(f"no resolution without versions uploaded after {cutoff:%Y-%m-%d} in {MAX_ROUNDS} rounds")
    pins = []
    for name in sorted(need):
        meta, files = resolved[name], releases_of(name).get(resolved[name]["version"]) or []
        if not files:
            raise PinError(f"{name} {meta['version']}: PyPI lists no files")
        if uploaded(files) > cutoff and allowed.get(name) != meta["version"]:
            raise PinError(f"{name} {meta['version']} was uploaded {uploaded(files):%Y-%m-%d}, after {cutoff:%Y-%m-%d}")
        hashes = sorted({f["digests"]["sha256"] for f in files})
        algo, _, digest = meta["picked"].get("hash", "").partition("=")
        if algo != "sha256" or digest not in hashes:
            raise PinError(f"{name}: the file pip picked is not among PyPI's sha256 digests")
        pins.append((name, meta["version"], hashes))
    skipped = sorted(set(resolved) - set(need))
    if skipped:
        print(f"left out (pip needs them only on this host's markers): {', '.join(skipped)}", file=sys.stderr)
    return pins


def pip_resolve(in_path, constraint_text):
    with tempfile.TemporaryDirectory() as tmp:
        report, cons = pathlib.Path(tmp) / "report.json", pathlib.Path(tmp) / "constraints.txt"
        cons.write_text(constraint_text, encoding="utf-8")
        subprocess.run([sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet",
                        "--disable-pip-version-check", "--target", str(pathlib.Path(tmp) / "target"), *PIP_TARGET,
                        "--report", str(report), "-c", str(cons), "-r", str(in_path)], check=True)
        data = json.loads(report.read_text(encoding="utf-8"))
    return {canonicalize_name(i["metadata"]["name"]): {**i["metadata"], "picked": i["download_info"]["archive_info"]}
            for i in data["install"]}


@functools.cache
def pypi_releases(name):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=60) as r:
        return json.load(r)["releases"]


def render(in_name, pins):
    """pins: [(name, version, [sha256...])] sorted by name."""
    head = (f"# Generated by tools/pin_requirements.py from {in_name} for ubuntu-latest CPython 3.12 x86_64.\n"
            f"# Do not edit; change {in_name} and regenerate. Install with --require-hashes --only-binary=:all: -r.\n")
    return head + "".join(f"{n}=={v} \\\n" + " \\\n".join(f"    --hash=sha256:{h}" for h in hashes) + "\n"
                          for n, v, hashes in pins)


def main(argv=None):
    in_path, out_path = map(pathlib.Path, argv or sys.argv[1:])
    roots = [l.split("#")[0].strip() for l in in_path.read_text(encoding="utf-8").splitlines()]
    roots = [r for r in roots if r]
    allowed = parse_young_pins(YOUNG_PINS.read_text(encoding="utf-8"))
    cutoff = datetime.datetime.now(datetime.timezone.utc) - MIN_AGE
    pins = select(roots, lambda c: pip_resolve(in_path, c), pypi_releases, allowed, cutoff)
    out_path.write_bytes(render(in_path.as_posix(), pins).encode("utf-8"))
    print(f"{out_path.as_posix()}: {len(pins)} packages, none uploaded after {cutoff:%Y-%m-%d %H:%M} UTC "
          f"except tools/young-pins.txt", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except PinError as e:
        sys.exit(f"pin_requirements: {e}")
