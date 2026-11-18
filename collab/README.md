# Collaboration: Cowork (design) + Claude Code (build)

Two Claude sessions work on this repo through files. Neither can message the other directly; the human (Qun) relays when needed.

| | Cowork (design session) | Claude Code (build session) |
| --- | --- | --- |
| Owns | Thinking and writing: briefs, specs, ADRs, prompts, skill text, review of results | Code, workflows, scripts, tests, running things, git |
| Writes to | `collab/briefs/`, `collab/ANSWERS.md`, `docs/design/`, `docs/adr/` (factory ADRs 0002+), `factory/prompts/*.md`, `factory/skills/**/SKILL.md` | Everything else; `collab/STATUS.md`, `collab/QUESTIONS.md` |
| Never | Runs git write commands, edits code, workflows or tools | Rewrites a brief, a prompt or skill text silently. Propose changes in `collab/QUESTIONS.md` instead |

## The loop

1. Cowork writes a brief: `collab/briefs/NNN-<topic>.md` with goal, decisions, acceptance criteria and open points.
2. Claude Code reads new briefs at the start of each session (and when Qun says "check collab"), implements on a branch `brief-NNN`, and commits Cowork's files together with its own.
3. Claude Code updates `collab/STATUS.md`: brief, branch, state (todo / doing / blocked / review / done), what changed, test evidence.
4. When unsure or when a brief is wrong, Claude Code writes a numbered question in `collab/QUESTIONS.md` and continues with what is unblocked. It never guesses business rules, model names or security trade-offs.
5. Cowork answers in `collab/ANSWERS.md` (same number), or writes a new brief if the answer is bigger.
6. Qun reviews the PR per brief. Cowork can review the diff on request.

## Running without a relay

Qun does not want to relay messages. Both sessions poll the files.
- **Claude Code** re-reads `collab/ANSWERS.md` and `collab/briefs/`:
  - before it starts each brief;
  - after it writes a question;
  - and whenever it is blocked, at least every 30 minutes, for example with `/loop 30m check collab`.

  A new answer counts as instruction. A file change Claude Code did not make itself in `collab/ANSWERS.md` or `collab/briefs/` is Cowork's, and Claude Code commits it with its next commit.
- **Cowork** checks `collab/QUESTIONS.md` and `collab/STATUS.md` on a schedule. It answers what it owns, and lists Qun's decisions under "Waiting for Qun" in ANSWERS.md.
- **Qun-only actions**, such as clicks, money, visibility changes, force pushes or weakening a control, always go to "Waiting for Qun". Neither session may decide them.

## Rules

- One brief = one branch = one PR. Small commits.
- Briefs state *what* and *why*; Claude Code decides *how*, within the architecture doc and the ADRs.
- Never weaken a control (gates, path guards, secret scoping, branch protection) to make something pass. Raise it as a question.
- Files under `factory/skills/` and `factory/prompts/` are drafted by Cowork and reviewed by Qun; Claude Code may fix syntax but proposes content changes as questions.
