"""Guard check: report the changes in a pull request that need the owner."""

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath

DIFF_LINE_LIMIT = 400
PROTECTED_DIRS = ("factory", "deploy", ".github")
PROTECTED_ROOT_FILES = ("Makefile",)
PROTECTED_NAMES = (
    "ruff.toml",
    ".ruff.toml",
    ".trivyignore",
    ".gitleaksignore",
    ".gitleaks.toml",
)
UNCOUNTED_NAMES = ("uv.lock",)
TESTS_DIR = "tests"
ADDED = "A"
BINARY_COUNT = "-"


@dataclass(frozen=True)
class Change:
    """One changed file: its git status letter, its path and its changed lines."""

    status: str
    path: str
    lines: int


def is_protected(path: PurePosixPath) -> bool:
    """Tell whether only the owner may change the path."""
    return (
        path.parts[0] in PROTECTED_DIRS
        or str(path) in PROTECTED_ROOT_FILES
        or path.name in PROTECTED_NAMES
    )


def find_violations(changes: list[Change]) -> list[str]:
    """List each reason why the changes need the owner."""
    paths = [(change, PurePosixPath(change.path)) for change in changes]
    protected = [
        f"protected path: {change.path}" for change, path in paths if is_protected(path)
    ]
    tests = [
        f"existing test changed or removed: {change.path}"
        for change, path in paths
        if TESTS_DIR in path.parts[:-1] and change.status != ADDED
    ]
    size = sum(
        change.lines for change, path in paths if path.name not in UNCOUNTED_NAMES
    )
    oversize = (
        [f"diff size {size} lines is over the limit of {DIFF_LINE_LIMIT}"]
        if size > DIFF_LINE_LIMIT
        else []
    )
    return protected + tests + oversize


def git_diff(option: str, base: str, head: str) -> list[str]:
    """Run one NUL-separated git diff from the merge base and return its fields."""
    output = subprocess.run(
        ["git", "diff", "--no-renames", "-z", option, f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return output.split("\0")[:-1]


def read_changes(base: str, head: str) -> list[Change]:
    """Read the changed files between the merge base and the head."""
    fields = git_diff("--name-status", base, head)
    statuses = dict(zip(fields[1::2], fields[0::2], strict=True))
    counts = (
        record.split("\t", maxsplit=2) for record in git_diff("--numstat", base, head)
    )
    return [
        Change(
            status=statuses[path],
            path=path,
            lines=sum(
                int(count) for count in (added, deleted) if count != BINARY_COUNT
            ),
        )
        for added, deleted, path in counts
    ]


def main() -> int:
    """Print the violations and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--advisory", action="store_true")
    arguments = parser.parse_args()

    violations = find_violations(read_changes(arguments.base, arguments.head))
    for violation in violations:
        print(violation)
    if not violations:
        print("no violation")
    return 1 if violations and not arguments.advisory else 0


if __name__ == "__main__":
    sys.exit(main())
