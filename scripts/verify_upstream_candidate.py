#!/usr/bin/env python3
"""Verify the immutable evidence attached to an upstream sync candidate."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from sync_upstream import path_matches, sha256_bytes, sha256_file


SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class VerificationError(RuntimeError):
    """Raised when a candidate cannot be trusted for automatic merging."""


def git_bytes(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def git_text(root: Path, *args: str) -> str:
    return git_bytes(root, *args).decode("utf-8", errors="replace")


def require(value: object, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(message)
    return value


def verify_lineage(root: Path, old: str, new: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", old, new],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        return
    if result.returncode == 1:
        raise VerificationError(f"upstream commit is not a descendant: {old} -> {new}")
    detail = result.stderr.decode("utf-8", errors="replace").strip()
    raise VerificationError(f"cannot verify upstream ancestry: {detail}")


def verify_candidate(
    root: Path,
    provenance_path: Path,
    manifest_path: str,
    base_sha: str,
    candidate_branch: str,
) -> dict:
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid provenance file: {exc}") from exc
    if not isinstance(provenance, dict):
        raise VerificationError("provenance root must be an object")

    if provenance.get("schema") != 1:
        raise VerificationError("unsupported provenance schema")
    if provenance.get("generator") != "scripts/sync_upstream.py":
        raise VerificationError("unexpected provenance generator")
    if provenance.get("upstreamRepository") != "Wei-Shaw/sub2api":
        raise VerificationError("unexpected upstream repository")
    if provenance.get("upstreamRef") != "main":
        raise VerificationError("unexpected upstream ref")
    if provenance.get("targetRef") != "main":
        raise VerificationError("unexpected target ref")
    if provenance.get("baseNovaCommit") != base_sha:
        raise VerificationError("candidate base does not match provenance")
    if provenance.get("candidateBranch") != candidate_branch:
        raise VerificationError("candidate branch does not match provenance")
    if provenance.get("applyStatus") != "ready":
        raise VerificationError("candidate was not applied successfully")

    old = require(provenance.get("oldUpstreamCommit"), "missing old upstream commit")
    new = require(provenance.get("newUpstreamCommit"), "missing new upstream commit")
    if not SHA_RE.fullmatch(old) or not SHA_RE.fullmatch(new):
        raise VerificationError("upstream commits must be full lowercase SHA-1 values")
    verify_lineage(root, old, new)

    actual_manifest_path = require(provenance.get("manifestPath"), "missing manifest path")
    if actual_manifest_path != manifest_path:
        raise VerificationError("provenance manifest path does not match policy input")
    manifest_file = root / manifest_path
    if not manifest_file.is_file():
        raise VerificationError(f"manifest does not exist: {manifest_path}")
    if provenance.get("manifestSha256") != sha256_file(manifest_file):
        raise VerificationError("provenance manifest hash does not match candidate")
    try:
        base_manifest = git_bytes(root, "show", f"{base_sha}:{manifest_path}")
    except VerificationError as exc:
        raise VerificationError("trusted base manifest is unavailable") from exc
    if provenance.get("manifestSha256") != sha256_bytes(base_manifest):
        raise VerificationError("candidate customization policy differs from trusted base")

    patch = git_bytes(root, "diff", "--binary", old, new)
    if provenance.get("patchSha256") != sha256_bytes(patch):
        raise VerificationError("provenance patch hash does not match upstream diff")

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        policy = manifest["protectedPathPolicy"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid customization manifest: {exc}") from exc

    paths = sorted(
        path for path in git_text(root, "diff", "--name-only", "--no-renames", old, new).splitlines() if path
    )
    deleted = []
    for line in git_text(root, "diff", "--name-status", "--no-renames", old, new).splitlines():
        fields = line.split("\t", 2)
        if len(fields) >= 2 and fields[0] == "D":
            deleted.append(fields[1])

    critical = sorted(path for path in paths if path_matches(path, policy["criticalPaths"]))
    manual = sorted(path for path in paths if path_matches(path, policy["manualReviewPaths"]))
    stop_deleted = sorted(
        path for path in deleted if path_matches(path, policy["stopOnDeletePaths"])
    )
    return {
        "oldUpstreamCommit": old,
        "newUpstreamCommit": new,
        "criticalPaths": critical,
        "manualReviewPaths": manual,
        "stopOnDeletePaths": stop_deleted,
        "eligible": not (critical or manual or stop_deleted),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--provenance", type=Path, default=Path(".nova-upstream-provenance.json"))
    parser.add_argument("--manifest", default="state/nova-customizations.json")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-branch", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = verify_candidate(
            args.root.resolve(),
            (args.root / args.provenance).resolve(),
            args.manifest,
            args.base_sha,
            args.candidate_branch,
        )
    except VerificationError as exc:
        print(f"candidate verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
