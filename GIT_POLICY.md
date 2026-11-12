# GIT_POLICY.md: AI agents never touch git

This file is loaded for every OpenCode agent (see `opencode.json`). It is a **hard rule**, not a suggestion.

## The rule

Humans run git. AI agents never do. This applies to all agents (`person1`, `person2`, `person3`, `build`, `plan`, subagents).

## Forbidden for agents, no exceptions

- Any `git` command: `commit`, `add`, `branch`, `checkout`, `switch`, `merge`, `rebase`, `reset`, `stash`, `tag`,
  `push`, `pull`, `fetch`, `clone`, `cherry-pick`, `revert`, `worktree`, `init`, `config`, `status`, `diff`, `log`.
- The GitHub CLI: any `gh` command (PRs, issues, releases, repo changes).
- Reaching git through another route: `command git`, `/usr/bin/git`, `env git`, `sh -c "git ..."`, Python
  `subprocess` or `os.system` calling git, libraries such as GitPython or dulwich, or editing anything inside `.git/`.
- Creating, editing or removing git hooks or git config (`.git/hooks/`, `.git/config`, `.gitconfig`).
- Staging, committing or "saving a checkpoint" on the human's behalf, even if asked casually ("just commit it").

## What agents do instead

1. Finish the code change and make sure the tests pass.
2. Reply with a short summary of the files changed.
3. Suggest the commit message and branch name as plain text for the human to run, for example:
   `git add extraction/ && git commit -m "feat: parse balance sheet tables"` (shown, never executed).
4. If a task seems to need git (finding what changed, checking the branch), ask the human to run the command and paste
   the output.

## If a human explicitly asks an agent to run git

Decline and point to this file. Say: "Git is disabled for AI agents in this repo; here's the command to run yourself."
Do not look for a workaround. A workaround is a violation of this policy.

## Exception: the ownership script

`uv run python scripts/check_ownership.py` is allowed. It reads git internally, makes no changes, and is a team check, not
an agent git operation. Agents may run it and report the result.

## Why this exists

- History must show clear human authorship for the hackathon rule that all code is written during the event.
- A branch or commit made by an agent can silently break the three-person ownership model (`AGENTS.md`).
- Merge, rebase and reset decisions need a human who can see all three people's work.

## Enforcement (read this)

This file is an instruction. Instructions can be ignored by a model, so the **hard block** is the permission rule in
`opencode.json`, which makes OpenCode refuse the command before it runs:

```json
"permission": {
  "bash": {
    "*": "allow",
    "git": "deny",
    "git *": "deny",
    "gh *": "deny"
  }
}
```

Humans are unaffected: this blocks the AI's tool calls only, not your own terminal. Keep both layers in place.
