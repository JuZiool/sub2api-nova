#!/usr/bin/env python3
"""Fuse Nova sources, run build gates, and build a local Docker candidate."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BuildError(RuntimeError):
    pass


def run(command: list[str], cwd: Path, *, capture: bool = False) -> str:
    print("+ " + " ".join(command), file=sys.stderr, flush=True)
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if result.returncode != 0:
        output = (result.stdout or "").strip()
        raise BuildError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{output[-8192:]}"
        )
    return result.stdout or ""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"JSON root must be an object: {path}")
    return value


def count_test_functions(candidate: Path) -> int:
    total = 0
    for directory in (candidate / "backend" / "internal" / "service", candidate / "backend" / "internal" / "repository"):
        for path in directory.glob("*_test.go"):
            total += len(re.findall(r"^func Test[A-Za-z0-9_]+", path.read_text(encoding="utf-8"), re.MULTILINE))
    return total


def resolve_input_path(value: Path | None, root: Path) -> Path | None:
    if value is None or value.is_absolute():
        return value
    current_relative = (Path.cwd() / value).resolve()
    if current_relative.exists():
        return current_relative
    return (root / value).resolve()


def optional_arg(flag: str, value: str | Path | None) -> list[str]:
    return [flag, str(value)] if value else []


def pnpm_command() -> list[str]:
    configured = os.environ.get("SUB2API_PNPM")
    if configured:
        return configured.split()
    if shutil.which("pnpm"):
        return ["pnpm"]
    if shutil.which("corepack"):
        return ["corepack.cmd", "pnpm"] if os.name == "nt" else ["corepack", "pnpm"]
    raise BuildError("pnpm is unavailable; install pnpm or enable Corepack")


def run_frontend_gates(candidate: Path) -> None:
    frontend = candidate / "frontend"
    pnpm = pnpm_command()
    run([*pnpm, "install", "--frozen-lockfile"], frontend)
    run([*pnpm, "run", "typecheck"], frontend)
    run([*pnpm, "run", "test:run"], frontend)


def run_backend_gates(candidate: Path, full_tests: bool) -> None:
    backend = candidate / "backend"
    if full_tests:
        run(["go", "test", "./internal/service", "./internal/repository"], backend)
        return
    test_args = [
        "go",
        "test",
        "-tags",
        "unit",
        "./internal/service",
        "./internal/repository",
        "-run",
        "Test(UpdateService|GitHubReleaseClient|CodexQuotaOverdraft|FinalizeCodexQuotaOverdraft|PersistCodexQuotaOverdraft|ClearCodexQuotaOverdraft)",
        "-count=1",
    ]
    test_output = run(test_args, backend, capture=True)
    if "[no tests to run]" in test_output:
        raise BuildError("candidate targeted Go test filter matched no tests")
    print(test_output, end="", file=sys.stderr)
    run(["go", "test", "./internal/service", "./internal/repository", "-run", "^$"], backend)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--official-root", type=Path)
    parser.add_argument("--overdraft-root", type=Path)
    parser.add_argument("--nova-base")
    parser.add_argument("--tag", default="sub2api-nova:candidate")
    parser.add_argument("--output", type=Path, default=Path("build/candidate-image"))
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-image", action="store_true", help="run gates without building a local Docker image")
    parser.add_argument(
        "--full-tests",
        action="store_true",
        help="run the complete Go service and repository test packages",
    )
    parser.add_argument(
        "--validate-existing",
        action="store_true",
        help="validate the checked-out tree without running the fusion step",
    )
    args = parser.parse_args()

    if args.validate_existing and (args.official_root or args.overdraft_root or args.nova_base):
        raise BuildError("--validate-existing cannot be combined with fusion inputs")

    root = args.root.resolve()
    official_root = resolve_input_path(args.official_root, root)
    overdraft_root = resolve_input_path(args.overdraft_root, root)
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    if output == root or root not in output.parents:
        raise BuildError("build output must be inside Nova build/")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    candidate = root / "build" / "candidate"
    if args.validate_existing:
        candidate = Path(tempfile.mkdtemp(prefix="sub2api-nova-existing-")) / "candidate"
    elif candidate.exists():
        shutil.rmtree(candidate)

    if args.validate_existing:
        shutil.copytree(
            root,
            candidate,
            ignore=shutil.ignore_patterns(".git", "build", "node_modules"),
        )
        version_path = candidate / "backend" / "cmd" / "server" / "VERSION"
        metadata = {
            "schema": 1,
            "official": {},
            "overdraft": {},
            "nova": {
                "repository": "JuZiool/sub2api-nova",
                "commit": run(["git", "rev-parse", "HEAD"], root, capture=True).strip(),
                "version": version_path.read_text(encoding="utf-8").strip(),
                "overlay_base_commit": load_json(root / "fusion.json")["nova"]["overlay_base_commit"],
            },
            "provenance": {"mode": "checked-out-tree"},
        }
    else:
        fusion_script = root / "scripts" / "fuse_candidate.py"
        run(
            [
                sys.executable,
                str(fusion_script),
                "--root",
                str(root),
                *optional_arg("--official-root", official_root),
                *optional_arg("--overdraft-root", overdraft_root),
                *optional_arg("--nova-base", args.nova_base),
                "--output",
                str(candidate),
            ],
            root,
        )
        metadata = load_json(candidate / ".nova-fusion-metadata.json")
    version = str(metadata["nova"]["version"])
    commit = str(metadata["nova"]["commit"])

    if not args.skip_tests:
        run_frontend_gates(candidate)
        run_backend_gates(candidate, args.full_tests)

    image = args.tag
    inspect: Any = None
    if not args.skip_image:
        build_args = [
            "docker",
            "build",
            "--progress=plain",
            "-f",
            str(candidate / "Dockerfile"),
            "--build-arg",
            f"VERSION={version}",
            "--build-arg",
            f"COMMIT={commit}",
            "-t",
            image,
            str(candidate),
        ]
        run(build_args, root)
        inspect = load_json_text(run(["docker", "image", "inspect", image], root, capture=True))
    metadata.update(
        {
            "build": {
                "status": "verified",
                "image": image if not args.skip_image else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "docker_inspect": inspect,
                "tests": "skipped" if args.skip_tests else "passed",
            }
        }
    )
    (output / "build-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def load_json_text(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise BuildError(f"docker inspect returned invalid JSON: {exc}") from exc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
