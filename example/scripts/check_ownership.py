#!/usr/bin/env python3
"""Fails if your branch touches files that belong to another person.

Branch names decide who you are:
    feat/p1-...  fix/p1-...  test/p1-...   -> Person 1 folders
    feat/p2-...                            -> Person 2 folders
    feat/p3-...                            -> Person 3 folders
    chore/deps-...                         -> pyproject.toml and uv.lock only
    contract/...                           -> shared/ and root config (needs all 3 approvals)

Run it before every PR:   uv run python scripts/check_ownership.py
Install as a pre-push hook:   bash scripts/install_hooks.sh
"""

from __future__ import annotations

import re
import subprocess
import sys

OWNERS: dict[str, list[str]] = {
    "1": ["extraction/", "llm/", "mcp_server/", "tests/extraction/", "tests/llm/", "tests/fixtures/"],
    "2": ["workflow/", "audit/", "validation/", "tests/workflow/", "tests/audit/",
          "tests/validation/"],
    "3": ["verification/", "api/", "ui/", "demo/", "docs/", "README.md", "tests/verification/",
          "tests/api/", "tests/ui/"],
}
ANYONE = ["docs/requests/"]  # create new, uniquely named files only
DEPS = ["pyproject.toml", "uv.lock"]
CONTRACT = ["shared/", "tests/shared/", "AGENTS.md", "VISION.md", "opencode.json", ".opencode/",
            "scripts/", ".env.example", ".gitignore"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def base_ref() -> str:
    for ref in ("dev", "origin/dev", "main", "origin/main"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], capture_output=True).returncode == 0:
            return ref
    sys.exit("No dev/main branch found to compare against.")


def allowed_prefixes(branch: str) -> list[str] | None:
    if branch in ("dev", "main", "HEAD"):
        return None  # integration branches: nothing to check
    if re.match(r"^chore/deps-", branch):
        return DEPS
    if branch.startswith("contract/"):
        return CONTRACT + ANYONE
    m = re.match(r"^(feat|fix|test|docs|chore|refactor)/p([123])-", branch)
    if not m:
        sys.exit(f"Branch '{branch}' must look like feat/p1-topic, feat/p2-topic, feat/p3-topic, "
                 "chore/deps-x or contract/x.")
    return OWNERS[m.group(2)] + ANYONE


def changed_files(base: str) -> set[str]:
    merge_base = git("merge-base", "HEAD", base)
    files = set(git("diff", "--name-only", merge_base).splitlines())  # committed + uncommitted
    files |= set(git("ls-files", "--others", "--exclude-standard").splitlines())  # new files
    return {f for f in files if f}


def main() -> int:
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    allowed = allowed_prefixes(branch)
    if allowed is None:
        print(f"On '{branch}': ownership check skipped.")
        return 0
    bad = sorted(f for f in changed_files(base_ref()) if not any(f == a or f.startswith(a) for a in allowed))
    if not bad:
        print(f"OK: '{branch}' only touches files it owns.")
        return 0
    print(f"BLOCKED: '{branch}' touches files outside its ownership:")
    for f in bad:
        print(f"  - {f}")
    print("\nMove those changes to the right owner, or write a request in docs/requests/.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
