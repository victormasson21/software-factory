import subprocess
from pathlib import Path

import pytest

from guard import DIFF_LINE_LIMIT, Change, find_violations, main, read_changes

CLEAN_CHANGE = Change(status="M", path="services/hello/src/hello/main.py", lines=10)


def test_clean_change_has_no_violation() -> None:
    assert find_violations([CLEAN_CHANGE]) == []


@pytest.mark.parametrize(
    "path",
    [
        "factory/guard/guard.py",
        "deploy/dev/kustomization.yaml",
        ".github/workflows/hello.yml",
        "Makefile",
        "services/hello/ruff.toml",
        "services/hello/.ruff.toml",
        "services/hello/conftest.py",
        "services/hello/src/hello/conftest.py",
        "services/hello/pytest.ini",
        "services/hello/.pytest.ini",
        "services/hello/pytest.toml",
        "services/hello/.pytest.toml",
        "services/hello/.trivyignore",
        ".gitleaksignore",
        ".gitleaks.toml",
    ],
)
def test_protected_path_is_a_violation(path: str) -> None:
    assert find_violations([Change(status="M", path=path, lines=1)]) == [
        f"protected path: {path}"
    ]


def test_makefile_below_the_root_is_not_protected() -> None:
    change = Change(status="A", path="services/hello/Makefile", lines=1)

    assert find_violations([change]) == []


@pytest.mark.parametrize("status", ["M", "D", "T"])
def test_existing_test_touched_is_a_violation(status: str) -> None:
    path = "services/hello/tests/test_main.py"

    assert find_violations([Change(status=status, path=path, lines=1)]) == [
        f"existing test changed or removed: {path}"
    ]


def test_added_test_has_no_violation() -> None:
    change = Change(status="A", path="services/hello/tests/test_new.py", lines=20)

    assert find_violations([change]) == []


def test_diff_over_the_limit_is_a_violation() -> None:
    change = Change(
        status="M", path="services/hello/src/hello/main.py", lines=DIFF_LINE_LIMIT + 1
    )

    assert find_violations([change]) == [
        f"diff size {DIFF_LINE_LIMIT + 1} lines is over the limit of {DIFF_LINE_LIMIT}"
    ]


def test_diff_at_the_limit_has_no_violation() -> None:
    change = Change(
        status="M", path="services/hello/src/hello/main.py", lines=DIFF_LINE_LIMIT
    )

    assert find_violations([change]) == []


def test_lockfile_lines_do_not_count_toward_the_limit() -> None:
    lockfile = Change(
        status="M", path="services/hello/uv.lock", lines=DIFF_LINE_LIMIT * 2
    )

    assert find_violations([CLEAN_CHANGE, lockfile]) == []


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            *arguments,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    tests = tmp_path / "services" / "hello" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_main.py").write_text("def test_one() -> None:\n    assert True\n")
    git(tmp_path, "init", "--initial-branch", "main")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--message", "base")
    git(tmp_path, "switch", "--create", "change")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_renamed_test_reads_as_a_removed_test(repo: Path) -> None:
    git(
        repo,
        "mv",
        "services/hello/tests/test_main.py",
        "services/hello/tests/test_other.py",
    )
    git(repo, "commit", "--message", "rename")

    assert read_changes("main", "change") == [
        Change(status="D", path="services/hello/tests/test_main.py", lines=2),
        Change(status="A", path="services/hello/tests/test_other.py", lines=2),
    ]


def test_changes_on_the_base_branch_are_not_read(repo: Path) -> None:
    (repo / "added.py").write_text("VALUE = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "--message", "change")
    git(repo, "switch", "main")
    (repo / "Makefile").write_text("up:\n")
    git(repo, "add", ".")
    git(repo, "commit", "--message", "base moves on")

    assert read_changes("main", "change") == [
        Change(status="A", path="added.py", lines=1)
    ]


@pytest.mark.parametrize(("flags", "status"), [([], 1), (["--advisory"], 0)])
def test_removed_test_fails_unless_advisory(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flags: list[str],
    status: int,
) -> None:
    git(repo, "rm", "services/hello/tests/test_main.py")
    git(repo, "commit", "--message", "remove")
    monkeypatch.setattr(
        "sys.argv", ["guard", "--base", "main", "--head", "change", *flags]
    )

    assert main() == status
    assert capsys.readouterr().out == (
        "existing test changed or removed: services/hello/tests/test_main.py\n"
    )
