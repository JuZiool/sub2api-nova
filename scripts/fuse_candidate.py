#!/usr/bin/env python3
"""Prepare an isolated official + overdraft + Nova candidate tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class FusionError(RuntimeError):
    pass


CONTROL_PATHS = {
    Path("fusion.json"),
    Path(".gitignore"),
    Path("scripts/README.md"),
    Path("scripts/detect_fusion.py"),
    Path("scripts/fuse_candidate.py"),
    Path("scripts/build_candidate_image.py"),
    Path("scripts/apply_candidate.py"),
    Path("scripts/test_fusion.py"),
}

NOVA_PRIORITY_PATHS = {
    Path("backend/internal/service/openai_codex_quota_overdraft_probe.go"),
    Path("backend/internal/service/update_service.go"),
    Path("backend/internal/service/update_service_test.go"),
    Path("backend/internal/handler/openai_gateway_handler.go"),
    Path("backend/internal/handler/openai_gateway_handler_test.go"),
    Path("frontend/index.html"),
    Path("README.md"),
}


def run(command: list[str], cwd: Path, *, capture: bool = False) -> str:
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
        raise FusionError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{output[-8192:]}"
        )
    return result.stdout or ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value: str) -> Path:
    relative = Path(value)
    if (
        relative.is_absolute()
        or not value
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise FusionError(f"unsafe relative path: {value!r}")
    return relative


def ensure_regular(path: Path, label: str) -> None:
    if path.is_symlink():
        raise FusionError(f"refusing symlink in {label}: {path}")
    if path.exists() and not path.is_file():
        raise FusionError(f"expected regular file in {label}: {path}")


def file_signature(root: Path, relative: Path) -> tuple[str, int] | None:
    path = root / relative
    if not path.exists() and not path.is_symlink():
        return None
    ensure_regular(path, str(root))
    mode = stat.S_IMODE(path.stat().st_mode)
    return sha256_file(path), mode


def changed_tracked_paths(repository: Path, base_ref: str | None = None) -> list[tuple[str, Path]]:
    statuses: dict[Path, str] = {}
    ranges = [f"{base_ref}..HEAD"] if base_ref else []
    ranges.append("HEAD")
    for revision in ranges:
        raw = run(
            ["git", "diff", "--name-status", "--no-renames", "-z", revision, "--"],
            repository,
            capture=True,
        )
        parts = raw.split("\0")
        index = 0
        while index + 1 < len(parts):
            status = parts[index]
            value = parts[index + 1]
            index += 2
            if status and value:
                statuses[safe_relative(value)] = status[0]
    return [(status, relative) for relative, status in sorted(statuses.items())]


def git_file_bytes(repository: Path, revision: str, relative: Path) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative.as_posix()}"],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return result.stdout if result.returncode == 0 else None


def git_file_signature(repository: Path, revision: str, relative: Path) -> tuple[str, int] | None:
    value = git_file_bytes(repository, revision, relative)
    return (hashlib.sha256(value).hexdigest(), 0o644) if value is not None else None


def untracked_paths(repository: Path) -> list[Path]:
    raw = run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        repository,
        capture=True,
    )
    return [safe_relative(value) for value in raw.split("\0") if value]


def validate_composite_base(
    official: Path,
    overdraft: Path,
    official_commit: str,
    overdraft_commit: str,
    base_commit: str,
) -> str:
    for label, repository, descendant in (
        ("official", official, official_commit),
        ("overdraft", overdraft, overdraft_commit),
    ):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", base_commit, descendant],
            cwd=repository,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            details = result.stderr.decode(errors="replace").strip()
            raise FusionError(
                f"Nova composite base is not an ancestor of {label} commit: "
                f"{base_commit} -> {descendant}"
                + (f": {details}" if details else "")
            )
    return base_commit


def clone_official(official: Path, commit: str, destination: Path) -> None:
    run(["git", "clone", "--no-hardlinks", str(official), str(destination)], destination.parent)
    run(["git", "checkout", "--detach", commit], destination)


def apply_patch(patch_path: Path, destination: Path, label: str) -> None:
    result = subprocess.run(
        ["git", "apply", "--3way", "--ignore-whitespace", str(patch_path)],
        cwd=destination,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    unresolved = run(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        destination,
        capture=True,
    ).strip()
    output = (result.stdout or "").strip()
    if result.returncode != 0 or unresolved:
        details = output[-8192:] if output else "no git output"
        if unresolved:
            details += f"\nunresolved files:\n{unresolved}"
        raise FusionError(f"{label} replay failed:\n{details}")


def apply_overdraft_patch(
    official: Path,
    overdraft: Path,
    official_commit: str,
    overdraft_commit: str,
    base_commit: str,
    destination: Path,
) -> dict[str, Any]:
    merge_base = run(
        ["git", "merge-base", base_commit, overdraft_commit],
        overdraft,
        capture=True,
    ).strip()
    if merge_base != base_commit:
        raise FusionError(
            f"overdraft base is not an ancestor of the selected overdraft commit: "
            f"{merge_base} != {base_commit}"
        )

    patch = run(
        ["git", "diff", "--binary", f"{base_commit}..{overdraft_commit}"],
        overdraft,
        capture=True,
    )
    if not patch.strip():
        raise FusionError("overdraft feature diff is empty")
    patch_path = destination.parent / "overdraft-feature.patch"
    patch_path.write_text(patch, encoding="utf-8", newline="\n")

    clone_official(official, official_commit, destination)
    apply_patch(patch_path, destination, "overdraft")
    return {
        "mode": "three-way-replay",
        "base_commit": base_commit,
        "official_commit": official_commit,
        "overdraft_commit": overdraft_commit,
        "patch_sha256": sha256_file(patch_path),
    }


def apply_nova_commit_patch(
    nova: Path,
    base_ref: str | None,
    candidate: Path,
) -> dict[str, Any]:
    if not base_ref:
        return {"mode": "working-tree-only", "base_commit": None}

    nova_commit = run(["git", "rev-parse", "HEAD"], nova, capture=True).strip()
    base_commit = run(["git", "rev-parse", base_ref], nova, capture=True).strip()
    if base_commit == nova_commit:
        return {"mode": "committed-overlay-empty", "base_commit": base_commit}

    remote_name = "nova-source"
    run(["git", "remote", "add", remote_name, str(nova)], candidate)
    run(["git", "fetch", "--no-tags", remote_name, base_commit, nova_commit], candidate)
    patch = run(
        [
            "git",
            "diff",
            "--binary",
            f"{base_commit}..{nova_commit}",
            "--",
            ":!fusion.json",
            ":!scripts",
            ":!.gitignore",
            ":!README.md",
            ":!backend/internal/handler/openai_gateway_handler.go",
            ":!backend/internal/handler/openai_gateway_handler_test.go",
        ],
        nova,
        capture=True,
    )
    if not patch.strip():
        return {"mode": "committed-overlay-empty", "base_commit": base_commit}
    patch_path = candidate.parent / "nova-committed-overlay.patch"
    patch_path.write_text(patch, encoding="utf-8", newline="\n")
    apply_patch(patch_path, candidate, "Nova committed overlay")
    return {
        "mode": "committed-overlay-replay",
        "base_commit": base_commit,
        "nova_commit": nova_commit,
        "patch_sha256": sha256_file(patch_path),
    }


def remove_destination(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def copy_overlay_file(source: Path, destination: Path) -> None:
    ensure_regular(source, "Nova worktree")
    if destination.exists() and destination.is_symlink():
        raise FusionError(f"refusing to replace candidate symlink: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def merge_nova_file(
    relative: Path,
    official: Path,
    overdraft: Path,
    current: Path,
    candidate: Path,
) -> None:
    ensure_regular(current, "Nova worktree")
    official_file = official / relative
    overdraft_file = overdraft / relative
    current_bytes = current.read_bytes()

    # A file introduced by the overdraft branch and then edited in Nova is
    # already a complete Nova-side result. Reusing it preserves the overdraft
    # implementation while retaining the Nova edits.
    if not official_file.exists() and overdraft_file.exists():
        copy_overlay_file(current, candidate / relative)
        return

    # Binary assets cannot be merged line by line; the current Nova asset is the
    # explicit overlay for this path.
    if b"\x00" in current_bytes:
        copy_overlay_file(current, candidate / relative)
        return

    if not official_file.exists() or not overdraft_file.exists():
        copy_overlay_file(current, candidate / relative)
        return

    if b"\x00" in official_file.read_bytes() or b"\x00" in overdraft_file.read_bytes():
        copy_overlay_file(current, candidate / relative)
        return

    result = subprocess.run(
        [
            "git",
            "merge-file",
            "--diff3",
            "--marker-size=7",
            "-p",
            str(overdraft_file),
            str(official_file),
            str(current),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        details = result.stderr.decode(errors="replace").strip()
        raise FusionError(
            f"Nova three-way merge conflict in {relative.as_posix()}"
            + (f": {details}" if details else "")
        )
    destination = candidate / relative
    if destination.exists() and destination.is_symlink():
        raise FusionError(f"refusing to replace candidate symlink: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(result.stdout)
    destination.chmod(stat.S_IMODE(current.stat().st_mode))


def merge_dockerfile(nova: Path, overdraft: Path, candidate: Path) -> None:
    nova_text = nova.read_text(encoding="utf-8")
    overdraft_text = overdraft.read_text(encoding="utf-8")
    text = nova_text

    def insert_after_once(value: str, marker: str, insertion: str) -> str:
        if insertion.strip() in value:
            return value
        index = value.find(marker)
        if index < 0:
            raise FusionError(f"Dockerfile merge marker not found: {marker!r}")
        end = index + len(marker)
        return value[:end] + insertion + value[end:]

    text = insert_after_once(text, "ARG COMMIT=docker\n", "ARG BUILD_TYPE=source\n")
    if "COPY FORK_VERSION /app/FORK_VERSION" not in text:
        marker = "COPY backend/ ./\n"
        text = insert_after_once(text, marker, "COPY FORK_VERSION /app/FORK_VERSION\n")
    version_line = '    if [ -z "${VERSION_VALUE}" ]; then VERSION_VALUE="$(./scripts/resolve-version.sh)"; fi && \\\n'
    if version_line not in text:
        raise FusionError("Dockerfile version resolution marker not found")
    text = text.replace(
        version_line,
        '    if [ -z "${VERSION_VALUE}" ] && [ -s /app/FORK_VERSION ]; then VERSION_VALUE="$(tr -d \'\\r\\n\' < /app/FORK_VERSION)"; fi && \\\n'
        + version_line,
        1,
    )

    text = text.replace(
        '-X main.BuildType=release"',
        '-X main.BuildType=${BUILD_TYPE}"',
        1,
    )
    if "LABEL org.opencontainers.image.version=\"${VERSION}\"" not in text:
        raise FusionError("Nova OCI version label missing after Dockerfile merge")
    if "LABEL org.opencontainers.image.source=\"https://github.com/JuZiool/sub2api-nova\"" not in text:
        raise FusionError("Nova OCI source label missing after Dockerfile merge")
    destination = candidate / "Dockerfile"
    destination.write_text(text, encoding="utf-8", newline="\n")
    destination.chmod(stat.S_IMODE(nova.stat().st_mode))


def materialize_revision(repository: Path, revision: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "archive", revision],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if archive.returncode != 0:
        details = archive.stderr.decode(errors="replace").strip()
        raise FusionError(f"cannot materialize {revision}: {details}")
    import io
    import tarfile

    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
        bundle.extractall(destination)


def git_tracked_paths(repository: Path) -> set[Path]:
    if not (repository / ".git").exists():
        return {
            safe_relative(path.relative_to(repository).as_posix())
            for path in repository.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
    raw = run(["git", "ls-files", "-z"], repository, capture=True)
    return {safe_relative(value) for value in raw.split("\0") if value}


def composite_paths(base: Path, official: Path, nova: Path) -> set[Path]:
    paths = git_tracked_paths(base) | git_tracked_paths(official) | git_tracked_paths(nova)
    paths.update(untracked_paths(nova))
    return {
        relative
        for relative in paths
        if relative not in CONTROL_PATHS
        and not (relative.parts and relative.parts[0] == "build")
    }


def copy_or_remove(source: Path, destination: Path) -> None:
    if source.exists() or source.is_symlink():
        copy_overlay_file(source, destination)
    elif destination.exists() or destination.is_symlink():
        remove_destination(destination)


def merge_composite_file(
    relative: Path,
    base: Path,
    official: Path,
    nova: Path,
    candidate: Path,
    temporary: Path,
) -> str:
    base_file = base / relative
    official_file = official / relative
    nova_file = nova / relative
    destination = candidate / relative
    base_signature = file_signature(base, relative)
    official_signature = file_signature(official, relative)
    nova_signature = file_signature(nova, relative)

    if nova_signature == base_signature:
        return "official"
    if official_signature == base_signature:
        copy_or_remove(nova_file, destination)
        return "nova"
    if nova_signature == official_signature:
        copy_or_remove(nova_file, destination)
        return "same"

    if base_signature is None:
        if official_signature is None and nova_signature is not None:
            copy_or_remove(nova_file, destination)
            return "nova"
        if nova_signature is None and official_signature is not None:
            return "official"
        raise FusionError(f"Nova composite add/add conflict in {relative.as_posix()}")
    if official_signature is None or nova_signature is None:
        raise FusionError(f"Nova composite delete/modify conflict in {relative.as_posix()}")

    base_bytes = base_file.read_bytes()
    official_bytes = official_file.read_bytes()
    nova_bytes = nova_file.read_bytes()
    if b"\x00" in base_bytes + official_bytes + nova_bytes:
        raise FusionError(f"Nova composite binary conflict in {relative.as_posix()}")

    merge_root = temporary / "merge"
    merge_root.mkdir(parents=True, exist_ok=True)
    merge_base = merge_root / "base"
    merge_official = merge_root / "official"
    merge_nova = merge_root / "nova"
    merge_base.write_bytes(base_bytes)
    merge_official.write_bytes(official_bytes)
    merge_nova.write_bytes(nova_bytes)
    result = subprocess.run(
        ["git", "merge-file", "--diff3", "--marker-size=7", "-p", str(merge_nova), str(merge_base), str(merge_official)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        details = result.stderr.decode(errors="replace").strip()
        raise FusionError(
            f"Nova composite merge conflict in {relative.as_posix()}"
            + (f": {details}" if details else "")
        )
    if destination.exists() and destination.is_symlink():
        raise FusionError(f"refusing to replace candidate symlink: {relative}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(result.stdout)
    destination.chmod(stat.S_IMODE(nova_file.stat().st_mode))
    return "merged"


def apply_composite_overlay(
    nova: Path,
    base: Path,
    official: Path,
    candidate: Path,
    temporary: Path,
) -> dict[str, Any]:
    applied: list[str] = []
    merged: list[str] = []
    for relative in sorted(composite_paths(base, official, nova)):
        if relative in NOVA_PRIORITY_PATHS:
            copy_overlay_file(nova / relative, candidate / relative)
            applied.append(relative.as_posix())
            continue
        result = merge_composite_file(relative, base, official, nova, candidate, temporary)
        if result == "nova":
            applied.append(relative.as_posix())
        elif result == "merged":
            applied.append(relative.as_posix())
            merged.append(relative.as_posix())
    return {
        "overlay_files": sorted(applied),
        "overlay_skipped": [],
        "overlay_file_count": len(applied),
        "overlay_merged_files": sorted(merged),
        "overlay_merge_file_count": len(merged),
    }


def apply_nova_priority_overlay(nova: Path, candidate: Path) -> dict[str, Any]:
    applied: list[str] = []
    for relative in sorted(NOVA_PRIORITY_PATHS):
        source = nova / relative
        if not source.exists():
            continue
        copy_overlay_file(source, candidate / relative)
        applied.append(relative.as_posix())
    return {
        "overlay_files": applied,
        "overlay_skipped": [],
        "overlay_file_count": len(applied),
        "overlay_merged_files": [],
        "overlay_merge_file_count": 0,
    }


def apply_nova_overlay(
    nova: Path,
    official: Path,
    overdraft: Path,
    candidate: Path,
    base_ref: str | None = None,
) -> dict[str, Any]:
    tracked = changed_tracked_paths(nova, base_ref)
    untracked = untracked_paths(nova)
    applied: list[str] = []
    skipped: list[str] = []
    merged: list[str] = []

    for status, relative in tracked:
        if relative in CONTROL_PATHS or relative.parts and relative.parts[0] == "build":
            skipped.append(relative.as_posix())
            continue

        current_signature = file_signature(nova, relative)
        official_signature = file_signature(official, relative)
        overdraft_signature = file_signature(overdraft, relative)
        current = nova / relative

        if current_signature is None:
            destination = candidate / relative
            if destination.exists() or destination.is_symlink():
                remove_destination(destination)
            applied.append(f"delete:{relative.as_posix()}")
            continue

        if relative in NOVA_PRIORITY_PATHS:
            copy_overlay_file(current, candidate / relative)
            applied.append(relative.as_posix())
            continue

        # The selected official/overdraft layer already contains this exact file.
        if current_signature == official_signature or current_signature == overdraft_signature:
            skipped.append(relative.as_posix())
            continue

        current = nova / relative
        # Dockerfile has independent build and branding requirements that need
        # both source layers, so merge it with an explicit policy.
        if relative == Path("Dockerfile"):
            merge_dockerfile(nova / relative, overdraft / relative, candidate)
        # Nova owns the generated version marker. Other files use a real
        # three-way merge whenever both source layers already contain them.
        elif relative == Path("FORK_VERSION"):
            copy_overlay_file(current, candidate / relative)
        else:
            merge_nova_file(relative, official, overdraft, current, candidate)
            if official_signature is not None and overdraft_signature is not None:
                merged.append(relative.as_posix())
        applied.append(relative.as_posix())

    for relative in untracked:
        if relative in CONTROL_PATHS or relative.parts and relative.parts[0] == "build":
            skipped.append(relative.as_posix())
            continue
        current = nova / relative
        if not current.is_file() or current.is_symlink():
            raise FusionError(f"unsupported untracked Nova path: {relative.as_posix()}")
        copy_overlay_file(current, candidate / relative)
        applied.append(relative.as_posix())

    return {
        "overlay_files": sorted(applied),
        "overlay_skipped": sorted(skipped),
        "overlay_file_count": len(applied),
        "overlay_merged_files": sorted(merged),
        "overlay_merge_file_count": len(merged),
    }


def nova_version_for(official_version: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", official_version):
        raise FusionError(f"unsupported official version: {official_version}")
    return f"{official_version}-nova"


def apply_candidate_version(candidate: Path, official_version: str) -> str:
    version = nova_version_for(official_version)
    for relative in (Path("FORK_VERSION"), Path("backend/cmd/server/VERSION")):
        path = candidate / relative
        if not path.is_file() or path.is_symlink():
            raise FusionError(f"candidate version file is missing: {relative}")
        path.write_text(version + "\n", encoding="utf-8", newline="\n")
    return version


def load_config(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((root / "fusion.json").read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("configuration is not an object")
        return value
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise FusionError(f"cannot load fusion.json: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--official-root", type=Path)
    parser.add_argument("--overdraft-root", type=Path)
    parser.add_argument("--nova-base", help="Nova commit from which committed overlay changes are replayed")
    parser.add_argument("--output", type=Path, help="copy the candidate to this new directory")
    parser.add_argument("--prepare-only", action="store_true", help="print metadata without copying output")
    args = parser.parse_args()

    root = args.root.resolve()
    config = load_config(root)
    official_config = config["official"]
    overdraft_config = config["overdraft"]

    official = (args.official_root or (root / official_config["local_path"])).resolve()
    overdraft = (args.overdraft_root or (root / overdraft_config["local_path"])).resolve()
    official_commit = run(["git", "rev-parse", "HEAD"], official, capture=True).strip()
    overdraft_commit = run(["git", "rev-parse", "HEAD"], overdraft, capture=True).strip()
    nova_base = args.nova_base or config["nova"].get("overlay_base_commit")
    if config["nova"].get("includes_overdraft", False):
        if not nova_base:
            raise FusionError("Nova composite base is missing")
        base_commit = validate_composite_base(
            official,
            overdraft,
            official_commit,
            overdraft_commit,
            nova_base,
        )
    else:
        base_commit = run(
            ["git", "merge-base", official_commit, overdraft_commit], overdraft, capture=True
        ).strip()
    if config["nova"].get("includes_overdraft", False) and base_commit != nova_base:
        raise FusionError(
            f"overdraft base does not match Nova composite base: {base_commit} != {nova_base}"
        )

    temporary = tempfile.TemporaryDirectory(prefix="sub2api-nova-fusion-")
    work = Path(temporary.name)
    candidate = work / "candidate"
    try:
        if config["nova"].get("includes_overdraft", False):
            clone_official(official, official_commit, candidate)
            base_tree = work / "base-tree"
            materialize_revision(official, nova_base, base_tree)
            nova_commit = run(["git", "rev-parse", "HEAD"], root, capture=True).strip()
            nova_provenance = {
                "mode": "composite-three-way",
                "base_commit": nova_base,
                "nova_commit": nova_commit,
            }
            overlay = apply_composite_overlay(root, base_tree, official, candidate, work)
            provenance = {
                "mode": "official-plus-nova-composite-replay",
                "official_commit": official_commit,
                "overdraft_commit": overdraft_commit,
                "overdraft_base_commit": base_commit,
                "nova_committed": nova_provenance,
            }
        else:
            provenance = apply_overdraft_patch(
                official,
                overdraft,
                official_commit,
                overdraft_commit,
                base_commit,
                candidate,
            )
            nova_provenance = apply_nova_commit_patch(root, nova_base, candidate)
            overlay = apply_nova_priority_overlay(root, candidate)

        candidate_version = apply_candidate_version(
            candidate,
            (official / official_config["version_file"]).read_text(encoding="utf-8").strip(),
        )
        metadata = {
            "schema": 1,
            "official": {
                "repository": official_config["repository"],
                "commit": official_commit,
                "version": (official / official_config["version_file"]).read_text(encoding="utf-8").strip(),
            },
            "overdraft": {
                "repository": overdraft_config["repository"],
                "commit": overdraft_commit,
                "base_commit": base_commit,
                "version": (overdraft / overdraft_config["version_file"]).read_text(encoding="utf-8").strip(),
                "fork_version": (overdraft / overdraft_config["fork_version_file"]).read_text(encoding="utf-8").strip(),
            },
            "nova": {
                "repository": config["nova"]["repository"],
                "commit": run(["git", "rev-parse", "HEAD"], root, capture=True).strip(),
                "version": candidate_version,
                "overlay_base_commit": nova_base,
            },
            "provenance": {**provenance, **overlay},
        }
        if args.output and not args.prepare_only:
            output = args.output.resolve()
            build_root = (root / "build").resolve()
            if output == root or (output != build_root and build_root not in output.parents):
                raise FusionError("candidate output must be inside Nova build/")
            if output.exists() or output.is_symlink():
                raise FusionError(f"output already exists: {output}")
            shutil.copytree(candidate, output, ignore=shutil.ignore_patterns(".git"))
            (output / ".nova-fusion-metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            metadata["output"] = str(output)
        print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    finally:
        temporary.cleanup()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FusionError as exc:
        print(f"error: {exc}", flush=True)
        raise SystemExit(1)
