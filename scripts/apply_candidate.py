#!/usr/bin/env python3
"""Apply a verified fusion candidate to a Nova synchronization checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


class ExportError(RuntimeError):
    pass


PROTECTED_PREFIXES = (
    Path(".github/workflows"),
    Path("scripts"),
    Path("build"),
)
PROTECTED_PATHS = {
    Path("fusion.json"),
    Path(".gitignore"),
    Path("AGENTS.md"),
}
SKIPPED_CANDIDATE_PATHS = {
    Path(".nova-fusion-metadata.json"),
}


def safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not value or any(part in {"", ".", ".."} for part in path.parts):
        raise ExportError(f"unsafe candidate path: {value!r}")
    return path


def is_protected(relative: Path) -> bool:
    return relative in PROTECTED_PATHS or any(
        relative == prefix or prefix in relative.parents for prefix in PROTECTED_PREFIXES
    )


def ensure_regular(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ExportError(f"refusing symlink in {label}: {path}")
    if path.exists() and not path.is_file():
        raise ExportError(f"expected regular file in {label}: {path}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def candidate_files(candidate: Path) -> set[Path]:
    if not candidate.is_dir() or candidate.is_symlink():
        raise ExportError(f"candidate directory is invalid: {candidate}")
    result: set[Path] = set()
    for path in candidate.rglob("*"):
        relative = safe_relative(path.relative_to(candidate).as_posix())
        if path.is_symlink():
            raise ExportError(f"candidate contains symlink: {relative}")
        if path.is_file() and not is_protected(relative) and relative not in SKIPPED_CANDIDATE_PATHS:
            result.add(relative)
    return result


def tracked_files(target: Path) -> set[Path]:
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=target,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise ExportError(f"cannot list target Git files: {result.stderr.decode(errors='replace')}")
    return {
        safe_relative(value)
        for value in result.stdout.decode().split("\0")
        if value and not is_protected(safe_relative(value))
    }


def update_fusion_config(target: Path, official_commit: str) -> None:
    path = target / "fusion.json"
    if not path.is_file() or path.is_symlink():
        raise ExportError("target fusion.json is missing")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportError(f"cannot read fusion.json: {exc}") from exc
    try:
        config["nova"]["overlay_base_commit"] = official_commit
    except (KeyError, TypeError) as exc:
        raise ExportError("fusion.json has no nova.overlay_base_commit") from exc
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_candidate(target: Path, candidate: Path, official_commit: str) -> dict[str, Any]:
    candidate_set = candidate_files(candidate)
    target_set = tracked_files(target)
    changed: list[str] = []
    added: list[str] = []
    deleted: list[str] = []
    protected: list[str] = []

    for relative in sorted(candidate_set):
        source = candidate / relative
        destination = target / relative
        ensure_regular(source, "candidate")
        if destination.exists() and destination.is_symlink():
            raise ExportError(f"refusing to replace target symlink: {relative}")
        if destination.exists() and not destination.is_file():
            raise ExportError(f"target path is not a regular file: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        before = sha256(destination) if destination.exists() else None
        shutil.copy2(source, destination)
        after = sha256(destination)
        if before is None:
            added.append(relative.as_posix())
        elif before != after:
            changed.append(relative.as_posix())

    for relative in sorted(target_set - candidate_set):
        destination = target / relative
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink():
                raise ExportError(f"refusing to delete target symlink: {relative}")
            if destination.is_file():
                destination.unlink()
                deleted.append(relative.as_posix())

    protected: list[str] = sorted(
        path.as_posix()
        for path in PROTECTED_PATHS
        if (target / path).exists()
    )
    update_fusion_config(target, official_commit)
    return {
        "official_commit": official_commit,
        "changed": changed,
        "added": added,
        "deleted": deleted,
        "protected": protected,
        "changed_count": len(changed),
        "added_count": len(added),
        "deleted_count": len(deleted),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--official-commit", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    target = args.target.resolve()
    candidate = args.candidate.resolve()
    if not (target / ".git").exists():
        raise ExportError(f"target is not a Git repository: {target}")
    result = apply_candidate(target, candidate, args.official_commit)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.resolve().write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExportError as exc:
        print(f"error: {exc}")
        raise SystemExit(1)
