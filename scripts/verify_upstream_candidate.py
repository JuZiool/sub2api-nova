#!/usr/bin/env python3
"""Verify the immutable evidence attached to an upstream sync candidate."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from sync_upstream import (
    nova_version,
    path_matches,
    protected_patterns,
    sha256_bytes,
    sha256_file,
)


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


def verify_candidate_tree(
    root: Path,
    provenance: dict,
    base_sha: str,
    candidate_sha: str,
    patch: bytes,
) -> None:
    """Rebuild the expected candidate tree without executing candidate code."""
    if not SHA_RE.fullmatch(candidate_sha):
        raise VerificationError("candidate commit must be a full lowercase SHA-1 value")

    temp_root = Path(tempfile.mkdtemp(prefix="nova-candidate-tree-"))
    worktree_added = False
    try:
        git_bytes(root, "worktree", "add", "--detach", str(temp_root), base_sha)
        worktree_added = True
        result = subprocess.run(
            ["git", "apply", "--3way", "--binary", "-"],
            cwd=temp_root,
            input=patch,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise VerificationError(f"expected direct upstream patch does not apply: {detail}")

        new_version = require(provenance.get("newVersion"), "missing new upstream version")
        for relative in ("FORK_VERSION", "backend/cmd/server/VERSION"):
            version_path = temp_root / relative
            if version_path.exists():
                version_path.write_text(nova_version(new_version) + "\n", encoding="utf-8")

        git_bytes(root, "-C", str(temp_root), "add", "--all")
        expected_direct_tree = git_text(root, "-C", str(temp_root), "write-tree").strip()
        overlay_scope = [":(exclude).nova-upstream-provenance.json"]
        overlay_patch = git_bytes(
            root,
            "diff",
            "--binary",
            "--no-renames",
            expected_direct_tree,
            candidate_sha,
            "--",
            *overlay_scope,
        )
        overlay_paths = sorted(
            path
            for path in git_text(
                root,
                "diff",
                "--name-only",
                "--no-renames",
                expected_direct_tree,
                candidate_sha,
                "--",
                *overlay_scope,
            ).splitlines()
            if path
        )
        if provenance.get("overlayPaths") != overlay_paths:
            raise VerificationError("provenance overlayPaths does not match candidate overlay")
        if provenance.get("overlayPatchSha256") != sha256_bytes(overlay_patch):
            raise VerificationError("provenance overlay patch hash does not match candidate")
        if overlay_patch:
            result = subprocess.run(
                ["git", "apply", "--3way", "--binary", "-"],
                cwd=temp_root,
                input=overlay_patch,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", errors="replace").strip()
                raise VerificationError(f"expected Nova overlay patch does not apply: {detail}")

        expected_provenance = temp_root / ".nova-upstream-provenance.json"
        expected_provenance_value = dict(provenance)
        # The merge commit hash is self-referential and is recorded by the follow-up
        # baseline metadata commit; it must not alter the merge tree reconstruction.
        expected_provenance_value.pop("novaMergeCommit", None)
        expected_provenance.write_text(
            json.dumps(expected_provenance_value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        git_bytes(root, "-C", str(temp_root), "add", "--all")
        expected_tree = git_text(root, "-C", str(temp_root), "write-tree").strip()
        actual_tree = git_text(root, "rev-parse", f"{candidate_sha}^{{tree}}").strip()
        if expected_tree != actual_tree:
            raise VerificationError(
                "candidate tree does not exactly match the trusted upstream fusion result"
            )
    finally:
        if worktree_added:
            try:
                git_bytes(root, "worktree", "remove", "--force", str(temp_root))
            except VerificationError:
                pass
        shutil.rmtree(temp_root, ignore_errors=True)


def verify_candidate(
    root: Path,
    provenance_path: Path,
    manifest_path: str,
    base_sha: str,
    candidate_branch: str,
    candidate_sha: str | None = None,
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
    protected = protected_patterns(policy)
    preserved_protected = sorted(path for path in paths if path_matches(path, protected))
    applied = sorted(path for path in provenance.get("appliedPaths", []) if path)
    adapted = sorted(path for path in provenance.get("adaptedPaths", []) if path)
    if any(path not in paths for path in applied + adapted):
        raise VerificationError("provenance applied or adapted paths contain a non-upstream path")
    if any(path in preserved_protected for path in applied + adapted):
        raise VerificationError("provenance applied or adapted paths contain a protected path")
    if set(applied).intersection(adapted):
        raise VerificationError("provenance appliedPaths and adaptedPaths overlap")
    excluded = sorted(
        path for path in paths if path not in set(applied).union(adapted, preserved_protected)
    )
    declared_excluded = sorted(path for path in provenance.get("excludedPaths", []) if path)
    if declared_excluded != excluded:
        raise VerificationError("provenance excludedPaths does not match upstream classification")
    version_paths = [
        relative
        for relative in ("FORK_VERSION", "backend/cmd/server/VERSION")
        if (root / relative).exists()
    ]
    patch_args = ["diff", "--binary", "--no-renames", old, new, "--", *applied]
    patch = git_bytes(root, *patch_args)
    if provenance.get("patchSha256") != sha256_bytes(patch):
        raise VerificationError("provenance filtered patch hash does not match upstream diff")
    for field, expected in (
        ("appliedPaths", applied),
        ("preservedProtectedPaths", preserved_protected),
        ("versionPaths", version_paths),
    ):
        if provenance.get(field) != expected:
            raise VerificationError(f"provenance {field} does not match upstream classification")
    if candidate_sha is not None:
        verify_candidate_tree(root, provenance, base_sha, candidate_sha, patch)

    return {
        "oldUpstreamCommit": old,
        "newUpstreamCommit": new,
        "conflicts": [],
        "criticalPaths": critical,
        "manualReviewPaths": manual,
        "stopOnDeletePaths": stop_deleted,
        "appliedPaths": applied,
        "preservedProtectedPaths": preserved_protected,
        "versionPaths": version_paths,
        "eligible": True,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--provenance", type=Path, default=Path(".nova-upstream-provenance.json"))
    parser.add_argument("--manifest", default="state/nova-customizations.json")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-branch", required=True)
    parser.add_argument("--candidate-sha", required=True)
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
            args.candidate_sha,
        )
    except VerificationError as exc:
        print(f"candidate verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
