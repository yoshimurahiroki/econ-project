"""Quality selectors must remain data across Make and shell boundaries."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest
import yaml


FILE_TARGETS = ("quality", "lint", "format", "format-check", "typecheck", "lint-r", "format-r")
SPECIAL_NAMES = (
    "with space.py",
    "single'quote.py",
    'double"quote.py',
    "`touch SHELL_SIDE_EFFECT`.py",
    "$(touch SHELL_SIDE_EFFECT).py",
    "$(shell touch MAKE_SIDE_EFFECT).py",
    "-leading.py",
)


@pytest.fixture
def workspace(tmp_path):
    shutil.copyfile(Path(__file__).parents[1] / "Makefile", tmp_path / "Makefile")
    recorder = tmp_path / "record.py"
    recorder.write_text(
        "import json, os, pathlib, sys\n"
        "pathlib.Path('called.json').write_text(json.dumps({"
        "'args': sys.argv[1:], 'file': os.environ.get('QUALITY_FILE'), "
        "'test': os.environ.get('QUALITY_TEST'), 'base': os.environ.get('QUALITY_BASE')}))\n"
    )
    return tmp_path, shlex.join([sys.executable, str(recorder)])


def invoke(root, target, selector, prefix):
    env = {
        key: value for key, value in os.environ.items() if key not in {"MAKEFLAGS", "MAKEOVERRIDES"}
    }
    return subprocess.run(
        ["make", "-s", target, selector, f"QUALITY_RUN={prefix}", f"PIXI_RUN={prefix}"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("target", FILE_TARGETS)
@pytest.mark.parametrize("name", SPECIAL_NAMES)
def test_file_is_one_argument_or_r_environment_value(workspace, target, name):
    root, prefix = workspace
    (root / name).write_text("value = 1\n")
    result = invoke(root, target, f"FILE={name}", prefix)
    assert result.returncode == 0, result.stdout + result.stderr
    call = json.loads((root / "called.json").read_text())
    assert call["file"] == "./" + name
    if target in {"lint-r", "format-r"}:
        assert 'Sys.getenv("QUALITY_FILE")' in call["args"][-1]
    else:
        assert call["args"][-1] == "./" + name
    assert not (root / "SHELL_SIDE_EFFECT").exists()
    assert not (root / "MAKE_SIDE_EFFECT").exists()


@pytest.mark.parametrize("target", FILE_TARGETS)
@pytest.mark.parametrize("name", ("", "missing.py", "."))
def test_invalid_file_stops_before_running_tool(workspace, target, name):
    root, prefix = workspace
    result = invoke(root, target, f"FILE={name}", prefix)
    assert result.returncode != 0
    assert "Specify FILE=one-existing-file" in result.stderr
    assert not (root / "called.json").exists()


@pytest.mark.parametrize("target,key", (("test", "TEST"), ("quality-changed", "BASE")))
def test_other_selectors_are_not_evaluated(workspace, target, key):
    root, prefix = workspace
    selector = '$(shell touch MAKE_SIDE_EFFECT)`touch SHELL_SIDE_EFFECT` "value"'
    result = invoke(root, target, f"{key}={selector}", prefix)
    assert result.returncode == 0, result.stdout + result.stderr
    call = json.loads((root / "called.json").read_text())
    assert call[key.lower()] == selector
    assert selector in call["args"]
    assert not (root / "SHELL_SIDE_EFFECT").exists()
    assert not (root / "MAKE_SIDE_EFFECT").exists()


@pytest.mark.parametrize("target", ("lint", "format", "format-check", "typecheck"))
@pytest.mark.parametrize("directory", SPECIAL_NAMES)
def test_python_tools_accept_special_path_components(workspace, target, directory):
    root, _ = workspace
    folder = root / directory
    folder.mkdir()
    source = folder / "example.py"
    source.write_text("value: int = 1\n")
    # Use the installed quality tools; no research environment or fake checker.
    bindir = Path(sys.executable).parent
    command = "mypy" if target == "typecheck" else "ruff"
    assert (bindir / command).is_file(), "Run with pixi run -e quality pytest"
    prefix = shlex.join(["env", f"PATH={bindir}:{os.environ['PATH']}"])
    result = invoke(root, target, f"FILE={source.relative_to(root)}", prefix)
    assert result.returncode == 0, result.stdout + result.stderr
    assert source.read_text() == "value: int = 1\n"
    assert not (root / "SHELL_SIDE_EFFECT").exists()
    assert not (root / "MAKE_SIDE_EFFECT").exists()


@pytest.mark.parametrize("command", ("ruff", "mypy", "shellcheck"))
def test_local_hooks_accept_precommit_normalized_dash_paths(workspace, command):
    root, _ = workspace
    config = yaml.safe_load((Path(__file__).parents[1] / ".pre-commit-config.yaml").read_text())
    hook = next(
        hook
        for repo in config["repos"]
        if repo["repo"] == "local"
        for hook in repo["hooks"]
        if command in shlex.split(hook["entry"])
    )
    arguments = shlex.split(hook["entry"])
    arguments = arguments[arguments.index(command) :]
    arguments[0] = str(Path(sys.executable).with_name(command))
    folder = root / "-leading"
    folder.mkdir()
    filename = "-leading/example.sh" if command == "shellcheck" else "-leading/example.py"
    (root / filename).write_text(
        '#!/bin/sh\nprintf "hello\\n"\n' if command == "shellcheck" else "value: int = 1\n"
    )
    result = subprocess.run(arguments + [filename], cwd=root, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_private_key_hook_accepts_precommit_normalized_dash_file(workspace):
    root, _ = workspace
    shutil.copyfile(
        Path(__file__).parents[1] / ".pre-commit-config.yaml", root / ".pre-commit-config.yaml"
    )
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
    (root / "-example.py").write_text("value: int = 1\n")
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("pre-commit")),
            "run",
            "detect-private-key",
            "--files",
            "./-example.py",
        ],
        cwd=root,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Passed" in result.stdout
