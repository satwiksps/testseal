"""Exercise the committed Action bundle with real Git, Python, and pip."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "packages/action/dist/index.js"
STRONG_TEST = "def test_value():\n    assert value == 42\n"
WEAK_TEST = "def test_value():\n    assert value\n"


def run(
    command: list[str], cwd: Path, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
        **kwargs,
    )


def outputs(path: Path) -> dict[str, str]:
    result = {}
    lines = iter(path.read_text(encoding="utf-8").splitlines())
    for line in lines:
        name, delimiter = line.split("<<", 1)
        value = []
        for item in lines:
            if item == delimiter:
                break
            value.append(item)
        else:
            raise AssertionError(f"Unterminated Action output: {name}")
        result[name] = "\n".join(value)
    return result


def verify(workspace: Path) -> None:
    repository = workspace / "consumer"
    repository.mkdir()
    environment = workspace / "python environment"
    run([sys.executable, "-I", "-m", "venv", str(environment)], workspace, check=True)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if os.name == "nt":
        node = shutil.which("node")
        if node is None:
            raise OSError("Node.js 24 or newer is required on PATH")
        shutil.copyfile(node, repository / "python.exe")
    test = repository / "tests/test_value.py"
    test.parent.mkdir()
    test.write_text(STRONG_TEST, encoding="utf-8")

    def git(*arguments: str) -> str:
        return run(["git", *arguments], repository, check=True).stdout.strip()

    git("init", "--quiet")
    git("add", "tests/test_value.py")
    git(
        "-c",
        "user.name=TestSeal",
        "-c",
        "user.email=testseal@example.invalid",
        "commit",
        "--no-gpg-sign",
        "--no-verify",
        "-qm",
        "base",
    )
    base = git("rev-parse", "HEAD")

    markers = []
    overlay = workspace / "pythonpath"
    overlay.mkdir()
    for directory, name in [
        (repository, "pip"),
        (repository, "testseal"),
        (repository, "sitecustomize"),
        (overlay, "sitecustomize"),
    ]:
        marker = workspace / f"{directory.name}-{name}-executed"
        markers.append(marker)
        (directory / f"{name}.py").write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
            "raise RuntimeError('The Action imported untrusted checkout content')\n",
            encoding="utf-8",
        )

    def scan(
        label: str,
        outcome: str,
        exit_code: int = 0,
        event_name: str = "workflow_dispatch",
        event: dict[str, object] | None = None,
        **inputs: str,
    ) -> dict[str, object]:
        output = workspace / f"{label}.output"
        output.touch()
        event_path = workspace / f"{label}.event.json"
        event_path.write_text(json.dumps(event or {}), encoding="utf-8")
        env = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith(("INPUT_", "GITHUB_"))
        }
        env.update(
            {
                "GITHUB_OUTPUT": str(output),
                "GITHUB_EVENT_NAME": event_name,
                "GITHUB_EVENT_PATH": str(event_path),
                "INPUT_PYTHON-COMMAND": "python",
                "INPUT_INSTALL": "false",
                "PATH": str(python.parent) + os.pathsep + os.environ.get("PATH", ""),
                "PYTHONPATH": str(overlay),
                **{f"INPUT_{name.upper()}": value for name, value in inputs.items()},
            }
        )
        result = run(["node", str(BUNDLE)], repository, env=env)
        executed = [marker.name for marker in markers if marker.exists()]
        assert not executed, f"{label}: untrusted Python modules executed: {executed}"
        assert result.returncode == exit_code, (
            f"{label}: exit {result.returncode}, expected {exit_code}\n"
            f"{result.stdout}\n{result.stderr}"
        )
        values = outputs(output)
        assert values.get("outcome") == outcome, f"{label}: {values}\n{result.stdout}"
        if outcome == "error":
            assert "result" not in values, values
            print(f"Action {label}: {outcome}")
            return {}
        report = json.loads(values["result"])
        assert values["finding-count"] == str(report["summary"]["finding_count"])
        assert values["files-scanned"] == str(report["summary"]["files_scanned"])
        if outcome in {"findings", "threshold-failed"}:
            assert report["summary"]["finding_count"] == 1, report
            assert report["findings"][0]["rule_id"] == "TS003", report
            assert "::error" in result.stdout and "TS003" in result.stdout, (
                result.stdout
            )
        elif outcome == "clean":
            assert report["summary"]["finding_count"] == 0, report
        elif outcome == "incomplete":
            assert report["warnings"], report
        print(f"Action {label}: {outcome}")
        return report

    test.write_text(WEAK_TEST, encoding="utf-8")
    scan("install-and-scan", "findings", install="true")
    scan("absolute-interpreter", "findings", **{"python-command": str(python)})
    scan("threshold", "threshold-failed", 1, **{"fail-on": "high"})
    git("add", "tests/test_value.py")
    scan("staged", "findings", staged="true")
    git(
        "-c",
        "user.name=TestSeal",
        "-c",
        "user.email=testseal@example.invalid",
        "commit",
        "--no-gpg-sign",
        "--no-verify",
        "-qm",
        "head",
    )
    head = git("rev-parse", "HEAD")
    scan("clean", "clean")
    scan(
        "pull-request",
        "findings",
        event_name="pull_request",
        event={"pull_request": {"base": {"sha": base}, "head": {"sha": head}}},
    )
    scan(
        "merge-group",
        "findings",
        event_name="merge_group",
        event={"merge_group": {"base_sha": base, "head_sha": head}},
    )
    scan("missing-config", "error", 1, config="missing.toml")
    test.write_text("def test_value(:\n    pass\n", encoding="utf-8")
    scan("advisory-incomplete", "incomplete")
    scan("blocking-incomplete", "incomplete", 1, **{"fail-on": "high"})


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="testseal-action-") as directory:
            verify(Path(directory))
    except subprocess.CalledProcessError as error:
        print(
            f"Action verification failed: {error}\n{error.stdout}\n{error.stderr}",
            file=sys.stderr,
        )
        return 1
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f"Action verification failed: {error}", file=sys.stderr)
        return 1
    print(
        "Committed Action bundle passed real installation, scan, and import-isolation checks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
