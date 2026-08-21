#!/usr/bin/env python3
"""Resolve local official, overdraft, and Nova inputs for a fusion build."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


class DetectionError(RuntimeError):
    pass


def run_git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise DetectionError(
            f"git command failed in {repository}: {' '.join(args)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def untracked_snapshot(repository: Path) -> list[dict[str, str]]:
    paths = run_git(repository, "ls-files", "--others", "--exclude-standard").splitlines()
    result: list[dict[str, str]] = []
    for relative in paths:
        path = repository / relative
        if path.is_file():
            result.append({"path": relative, "sha256": sha256_file(path)})
    return result


def repository_snapshot(
    repository: Path,
    branch: str,
    version_file: str,
    fork_version_file: str | None = None,
) -> dict[str, Any]:
    if not (repository / ".git").exists():
        raise DetectionError(f"repository is not available: {repository}")
    version_path = repository / version_file
    if not version_path.is_file():
        raise DetectionError(f"version file is missing: {version_path}")
    fork_version = None
    if fork_version_file:
        fork_path = repository / fork_version_file
        if not fork_path.is_file():
            raise DetectionError(f"fork version file is missing: {fork_path}")
        fork_version = fork_path.read_text(encoding="utf-8").strip()
    status = run_git(repository, "status", "--porcelain=v1")
    snapshot: dict[str, Any] = {
        "path": str(repository),
        "branch": run_git(repository, "branch", "--show-current") or "detached",
        "requested_branch": branch,
        "commit": run_git(repository, "rev-parse", "HEAD"),
        "version": version_path.read_text(encoding="utf-8").strip(),
        "dirty": bool(status),
        "dirty_paths": [line[3:] for line in status.splitlines() if len(line) >= 4],
    }
    if fork_version is not None:
        snapshot["fork_version"] = fork_version
    return snapshot


def nova_snapshot(repository: Path, branch: str, version_file: str) -> dict[str, Any]:
    snapshot = repository_snapshot(repository, branch, version_file)
    combined_diff = run_git(repository, "diff", "--binary")
    staged_diff = run_git(repository, "diff", "--cached", "--binary")
    untracked = untracked_snapshot(repository)
    snapshot["untracked_files"] = untracked
    snapshot["overlay_diff_sha256"] = sha256_bytes(
        (
            staged_diff
            + "\n"
            + combined_diff
            + "\n"
            + json.dumps(untracked, sort_keys=True, separators=(",", ":"))
        ).encode("utf-8")
    )
    return snapshot


def resolve_repository(root: Path, config: dict[str, Any], override: Path | None) -> Path:
    if override is not None:
        return override.resolve()
    return (root / str(config["local_path"])).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--official-root", type=Path)
    parser.add_argument("--overdraft-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    config_path = root / "fusion.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    official_config = config["official"]
    overdraft_config = config["overdraft"]
    nova_config = config["nova"]

    official = repository_snapshot(
        resolve_repository(root, official_config, args.official_root),
        str(official_config["branch"]),
        str(official_config["version_file"]),
    )
    overdraft = repository_snapshot(
        resolve_repository(root, overdraft_config, args.overdraft_root),
        str(overdraft_config["branch"]),
        str(overdraft_config["version_file"]),
        str(overdraft_config["fork_version_file"]),
    )
    nova = nova_snapshot(
        root,
        str(nova_config["branch"]),
        str(nova_config["version_file"]),
    )

    inputs = {
        "schema": config["schema"],
        "official": {
            "repository": official_config["repository"],
            "branch": official["requested_branch"],
            "commit": official["commit"],
            "version": official["version"],
        },
        "overdraft": {
            "repository": overdraft_config["repository"],
            "branch": overdraft["requested_branch"],
            "commit": overdraft["commit"],
            "version": overdraft["version"],
            "fork_version": overdraft["fork_version"],
        },
        "nova": {
            "repository": nova_config["repository"],
            "branch": nova["requested_branch"],
            "commit": nova["commit"],
            "version": nova["version"],
            "overlay_diff_sha256": nova["overlay_diff_sha256"],
        },
        "merge_policy": overdraft_config["merge_policy"],
    }
    canonical = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result = {
        "schema": 1,
        "fingerprint": sha256_bytes(canonical.encode("utf-8")),
        "inputs": inputs,
        "repositories": {"official": official, "overdraft": overdraft, "nova": nova},
    }

    output = args.output.resolve() if args.output else None
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
