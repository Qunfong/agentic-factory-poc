"""Brief 013: LiteLLM-driven tester tool loop, replacing openai/codex-action.

Runs the tester role as a tool-calling loop on Azure gpt-5 (same family/model as 50-review).
Tools: read_file, list_files (read anywhere in the repo), write_file (new files only, under
app/src/test/**) and run_mvn (a fixed argument allow-list). No shell, no network tool, no git.

Path rules are enforced here (reject .., absolute paths, anything outside app/src/test/** for
writes) and again by the publish guard (tools/check_paths.py) downstream; this loop is not
trusted to replace it (Decision 3).

Quiet by design (Decision 4): stdout gets only step names, tool names, counts, exit codes and
the final result line. Model text, tool arguments and file contents are written to the
run-record transcript file (--out) instead, never printed.

run_mvn's child process has the model's own API key removed from its environment (Decision 6):
the loop holds the key, but nothing it can be told to execute should see it.

Usage: tools/tester_loop.py --prompt-file FILE --charter FILE --out FILE [--repo-root DIR]
"""
import argparse, json, os, pathlib, re, subprocess, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from check_paths import compile_glob, unsafe  # noqa: E402
from review import InfraFailure, completion_args, with_backoff  # noqa: E402

WRITE_GLOB = compile_glob("app/src/test/**")
TEST_COMPILE_ARGS = ("-B", "-q", "-f", "app/pom.xml", "test-compile")
TEST_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.$]*(#[A-Za-z_][A-Za-z0-9_]*)?$")
SCRUBBED_ENV_KEYS = ("AZURE_OPENAI_API_KEY",)
MAX_TURNS = 60          # backstop only; the charter's max_active_minutes is the real limit
MAX_FILE_BYTES = 200_000
MVN_TIMEOUT_S = 600
BEGIN_MESSAGE = "Begin. Use only the tools provided; there is no shell, network or git access."

TOOLS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a UTF-8 text file from the repository.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "list_files", "description": "List files under a repository directory, recursively.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Create a new test file under app/src/test/**. Fails if the file already exists.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run_mvn",
        "description": "Run `mvn -B -q -f app/pom.xml test-compile`, or the same with "
                       "`test -Dtest=<Class>[#<method>]` to run one test.",
        "parameters": {"type": "object", "properties": {"args": {"type": "array", "items": {"type": "string"}}},
                       "required": ["args"]}}},
]


class ToolError(Exception):
    """A tool call the model made was rejected; reported back to the model as an error, not raised."""


def validate_mvn_args(args):
    args = list(args)
    if args == list(TEST_COMPILE_ARGS):
        return None
    if (len(args) == 6 and tuple(args[:4]) == TEST_COMPILE_ARGS[:4] and args[4] == "test"
            and args[5].startswith("-Dtest=") and TEST_NAME_RE.match(args[5][len("-Dtest="):])):
        return None
    return f"disallowed mvn arguments: {args!r}"


def validate_read_path(path):
    reason = unsafe(path)
    return f"bad path {path!r}: {reason}" if reason else None


def resolve_contained(repo_root, path):
    """The real path for a read, refusing a symlink itself or one reached through a symlinked
    ancestor (Cowork A1): the tester checks out a tree it does not control, and a planted symlink
    to /proc/self/environ or similar would otherwise let the model read this process's own
    environment (the model key included) into its context. Fails closed on any resolution error
    (broken link, loop, permission), same as check_paths.py's filesystem_link_violations."""
    root = repo_root.resolve()
    full = root / path
    if full.is_symlink():
        raise ToolError(f"refuses a symlink: {path!r}")
    try:
        real = full.resolve(strict=True)
    except OSError as e:
        raise ToolError(f"cannot resolve {path!r}: {e}") from e
    try:
        real.relative_to(root)
    except ValueError as e:
        raise ToolError(f"{path!r} resolves outside the repository") from e
    return real


def validate_write_path(repo_root, path):
    reason = unsafe(path)
    if reason:
        return f"bad path {path!r}: {reason}"
    if not WRITE_GLOB.matches(path):
        return f"write outside app/src/test/**: {path!r}"
    if (repo_root / path).exists():
        return f"refuses to overwrite an existing file: {path!r}"
    return None


def read_file(repo_root, path):
    err = validate_read_path(path)
    if err:
        raise ToolError(err)
    full = resolve_contained(repo_root, path)
    if not full.is_file():
        raise ToolError(f"no such file: {path!r}")
    return full.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]


def list_files(repo_root, path):
    err = validate_read_path(path)
    if err:
        raise ToolError(err)
    base = resolve_contained(repo_root, path)
    if not base.is_dir():
        raise ToolError(f"no such directory: {path!r}")
    root = repo_root.resolve()
    out = []
    for p in base.rglob("*"):
        if p.is_symlink() or not p.is_file():
            continue
        try:
            real = p.resolve(strict=True)
            real.relative_to(root)
        except (OSError, ValueError):
            continue
        out.append(str(p.relative_to(repo_root)).replace("\\", "/"))
    return sorted(out)


def write_file(repo_root, path, content):
    err = validate_write_path(repo_root, path)
    if err:
        raise ToolError(err)
    full = repo_root / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return f"wrote {path} ({len(content)} bytes)"


def run_mvn(repo_root, args):
    err = validate_mvn_args(args)
    if err:
        raise ToolError(err)
    env = {k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV_KEYS}
    try:
        proc = subprocess.run(["mvn", *args], cwd=repo_root, env=env, capture_output=True, text=True,
                              timeout=MVN_TIMEOUT_S)
    except subprocess.TimeoutExpired as e:
        raise ToolError(f"mvn timed out after {MVN_TIMEOUT_S}s") from e
    tail = lambda s: s[-4000:]
    return {"exit_code": proc.returncode, "stdout": tail(proc.stdout), "stderr": tail(proc.stderr)}


DISPATCH = {"read_file": read_file, "list_files": list_files, "write_file": write_file, "run_mvn": run_mvn}


def call_tool(repo_root, name, args):
    fn = DISPATCH.get(name)
    if fn is None:
        raise ToolError(f"unknown tool: {name!r}")
    return fn(repo_root, **args)


def msg_to_dict(msg):
    if hasattr(msg, "model_dump"):
        return msg.model_dump(exclude_none=True)
    return {"role": msg.get("role"), "content": msg.get("content"), "tool_calls": msg.get("tool_calls")}


def run(system_prompt, model_args, repo_root, deadline, max_turns=MAX_TURNS):
    """Drive the tool loop. Returns (final_text, transcript, counts); raises InfraFailure."""
    import litellm
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": BEGIN_MESSAGE}]
    transcript = list(messages)
    counts = {"turns": 0, "tool_calls": 0, "files_written": 0, "mvn_runs": 0}
    for _ in range(max_turns):
        if time.monotonic() > deadline:
            raise InfraFailure("tester: wall-clock limit reached before the model finished")
        counts["turns"] += 1
        # _skip_mcp_handler: litellm.completion() otherwise always imports its MCP handler when
        # tools is non-empty, even though we only use plain OpenAI-style function tools, no MCP -
        # and the mcp package isn't in tools/requirements-review.txt (proven live, run 44342754745:
        # ModuleNotFoundError: No module named 'mcp'). Confirmed in litellm 1.106.3's main.py.
        resp = with_backoff(lambda: litellm.completion(messages=messages, tools=TOOLS, _skip_mcp_handler=True,
                                                        **model_args),
                            model_args["model"])
        msg = msg_to_dict(resp.choices[0].message)
        messages.append(msg)
        transcript.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content") or "", transcript, counts
        for call in calls:
            counts["tool_calls"] += 1
            name = call["function"]["name"] if isinstance(call, dict) else call.function.name
            raw_args = call["function"]["arguments"] if isinstance(call, dict) else call.function.arguments
            call_id = call["id"] if isinstance(call, dict) else call.id
            try:
                result = call_tool(repo_root, name, json.loads(raw_args or "{}"))
                if name == "write_file":
                    counts["files_written"] += 1
                if name == "run_mvn":
                    counts["mvn_runs"] += 1
                content = result if isinstance(result, str) else json.dumps(result)
            except (ToolError, json.JSONDecodeError, TypeError) as e:
                content = json.dumps({"error": str(e)})
            tool_msg = {"role": "tool", "tool_call_id": call_id, "content": content}
            messages.append(tool_msg)
            transcript.append({**tool_msg, "tool_name": name})
    raise InfraFailure(f"tester: no result after {max_turns} turns")


def main(argv=None):
    import yaml
    p = argparse.ArgumentParser()
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--charter", required=True)
    p.add_argument("--models-file", default="factory/models.yaml")
    p.add_argument("--out", required=True)
    p.add_argument("--repo-root", default=".")
    a = p.parse_args(argv)

    repo_root = pathlib.Path(a.repo_root).resolve()
    charter = yaml.safe_load(pathlib.Path(a.charter).read_text(encoding="utf-8"))
    max_minutes = (charter.get("limits") or {}).get("max_active_minutes", 20)
    models = yaml.safe_load(pathlib.Path(a.models_file).read_text(encoding="utf-8"))
    family = models["families"][models["roles"]["tester"]]
    model_args = completion_args(family, os.environ)
    # Cowork A2: run_mvn already excludes this from the child's own env, but a child running as
    # the same Linux user could still read this process's /proc/<pid>/environ. The key is captured
    # into model_args above; nothing after this line needs it in os.environ.
    os.environ.pop(family["secret"], None)
    system_prompt = pathlib.Path(a.prompt_file).read_text(encoding="utf-8")

    print(f"tester: starting (model {model_args['model']}, limit {max_minutes}m)")
    deadline = time.monotonic() + max_minutes * 60
    status, final_text, transcript, counts = "success", "", [], {}
    try:
        final_text, transcript, counts = run(system_prompt, model_args, repo_root, deadline)
    except InfraFailure as e:
        status, final_text = "infra-failure", str(e)
        print(f"tester: infra-failure: {type(e.__cause__ or e).__name__}")

    pathlib.Path(a.out).write_text(json.dumps({"final_text": final_text, "transcript": transcript}, indent=2))
    print(f"tester: turns={counts.get('turns', 0)} tool_calls={counts.get('tool_calls', 0)} "
          f"files_written={counts.get('files_written', 0)} mvn_runs={counts.get('mvn_runs', 0)}")
    print(f"tester: result={status}")
    return 0 if status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
