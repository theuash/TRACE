"""Fails if a change touches a folder that belongs to someone else.

Run it before a PR. Two ways in:

    python scripts/check_ownership.py                    # staged changes (needs git)
    python scripts/check_ownership.py --files a b c      # explicit list, no git needed

Exit 0 when clean, 1 with a report when something crosses a boundary.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

# Mirrors the ownership table in AGENTS.md. Keep the two in sync.
PERSON: dict[str, list[str]] = {
    "person1": [
        "extraction/",
        "llm/",
        "mcp_server/",
        "tests/extraction/",
        "tests/llm/",
        "tests/fixtures/",
    ],
    "person2": [
        "workflow/",
        "audit/",
        "validation/",
        "tests/workflow/",
        "tests/audit/",
        "tests/validation/",
    ],
    "person3": [
        "verification/",
        "api/",
        "trace-ui/",
        "docs/",
        "tests/verification/",
        "trace-ui/e2e/",
    ],
    "shared": ["shared/", "tests/shared/", ".opencode/", "scripts/", ".env.example"],
}
EXACT_SHARED = {
    "AGENTS.md",
    "VISION.md",
    "GIT_POLICY.md",
    "README.md",
    "HEAD_LOG.md",
    "opencode.json",
}
# Everyone may touch these; nobody owns them.
NEUTRAL = {".env", ".env.example", ".gitignore", "pyproject.toml", "uv.lock"}


def owner_of(path: str) -> str:
    if path in EXACT_SHARED or path in NEUTRAL:
        return "shared"
    for person, prefixes in PERSON.items():
        for prefix in prefixes:
            if path.startswith(prefix):
                return person
    return "shared"


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "--cached"], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        print(f"git failed: {out.stderr.strip() or 'not a git repository'}", file=sys.stderr)
        sys.exit(2)
    return [line for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", nargs="*", help="explicit file list instead of staged changes")
    parser.add_argument("--who", help="only report files owned by this person, e.g. person3")
    args = parser.parse_args()

    files = args.files if args.files is not None else staged_files()
    if not files:
        print("nothing to check")
        return 0

    if args.who is None:
        for path in files:
            print(f"  {path}  ->  {owner_of(path)}")
        print(f"{len(files)} file(s). Pass --who personN to fail on other people's folders.")
        return 0

    offenders = [
        (path, owner_of(path))
        for path in files
        if owner_of(path) not in ("shared", args.who)
    ]
    if not offenders:
        print(f"ok: {len(files)} file(s), no cross-owner changes")
        return 0
    print("cross-owner changes:")
    for path, owner in offenders:
        print(f"  {path}  ->  owned by {owner}")
    print("Each person edits only their own folder.")
    print("Otherwise open docs/requests/p<from>-to-p<to>-<topic>.md and use a fake meanwhile.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
