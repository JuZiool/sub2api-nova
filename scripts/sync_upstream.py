#!/usr/bin/env python3
"""Create a reviewed Nova branch from an upstream commit range."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


class SyncError(RuntimeError):
    """Raised when a sync candidate cannot be created safely."""


@dataclass(frozen=True)
class Config:
    root: Path
    state_path: Path
    manifest_path: Path
    report_path: Path
    upstream_remote: str
    upstream_repository: str
    upstream_ref: str
    target_ref: str
    requested_commit: str | None
    branch: str | None
    commit: bool
    create_branch: bool
    apply: bool


def run_git(config: Config, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=config.root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SyncError(f"git {' '.join(args)} 失败: {detail}")
    return result.stdout.strip()


def load_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"无法读取 JSON 文件 {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SyncError(f"JSON 根节点必须是对象: {path}")
    return value


def resolve_commit(config: Config, ref: str) -> str:
    return run_git(config, "rev-parse", "--verify", f"{ref}^{{commit}}")


def version_at(config: Config, commit: str) -> str:
    for path in ("backend/cmd/server/VERSION", "FORK_VERSION"):
        result = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=config.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            value = result.stdout.strip()
            if value:
                return value
    return "unknown"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def patch_bytes(config: Config, old: str, new: str) -> bytes:
    return subprocess.run(
        ["git", "diff", "--binary", old, new],
        cwd=config.root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def verify_upstream_remote(config: Config) -> None:
    try:
        remote_url = run_git(config, "remote", "get-url", config.upstream_remote)
    except SyncError:
        raise SyncError(f"缺少上游远程：{config.upstream_remote}")
    normalized = remote_url.removesuffix(".git").rstrip("/").lower()
    expected = f"https://github.com/{config.upstream_repository}".lower()
    if normalized != expected:
        raise SyncError(
            f"上游远程地址与配置不一致：期望 {expected}，实际 {normalized}"
        )


def verify_upstream_object(config: Config, commit: str) -> None:
    resolved = resolve_commit(config, commit)
    if resolved != commit:
        raise SyncError(f"上游提交不是完整且稳定的 SHA: {commit}")


def write_provenance(config: Config, report: dict, patch: bytes) -> str:
    provenance_path = config.root / ".nova-upstream-provenance.json"
    manifest_hash = sha256_file(config.manifest_path)
    provenance = {
        "schema": 1,
        "generator": "scripts/sync_upstream.py",
        "upstreamRepository": config.upstream_repository,
        "upstreamRemote": config.upstream_remote,
        "upstreamRef": config.upstream_ref,
        "oldUpstreamCommit": report["oldUpstreamCommit"],
        "newUpstreamCommit": report["newUpstreamCommit"],
        "oldVersion": report["oldVersion"],
        "newVersion": report["newVersion"],
        "targetRef": report["targetRef"],
        "candidateBranch": report.get("candidateBranch"),
        "baseNovaCommit": resolve_commit(config, config.target_ref),
        "manifestPath": str(config.manifest_path.relative_to(config.root)).replace("\\", "/"),
        "manifestSha256": manifest_hash,
        "patchSha256": sha256_bytes(patch),
        "applyStatus": report["applyStatus"],
    }
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(provenance_path.relative_to(config.root)).replace("\\", "/")


def path_matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.rstrip("/")
    for pattern in patterns:
        candidate = pattern.rstrip("/")
        if normalized == candidate or normalized.startswith(candidate + "/"):
            return True
        if fnmatch.fnmatch(normalized, candidate):
            return True
    return False


def changed_paths(config: Config, old: str, new: str) -> list[str]:
    output = run_git(config, "diff", "--name-only", "--no-renames", old, new)
    return sorted({line for line in output.splitlines() if line})


def diff_stat(config: Config, old: str, new: str) -> list[str]:
    output = run_git(config, "diff", "--stat", "--no-renames", old, new)
    return [line for line in output.splitlines() if line.strip()]


def deleted_paths(config: Config, old: str, new: str) -> list[str]:
    output = run_git(config, "diff", "--name-status", "--no-renames", old, new)
    deleted: list[str] = []
    for line in output.splitlines():
        fields = line.split("\t", 2)
        if len(fields) >= 2 and fields[0] == "D":
            deleted.append(fields[1])
    return sorted(deleted)


def ensure_clean(config: Config) -> None:
    status = run_git(config, "status", "--porcelain")
    if status:
        raise SyncError("工作树不是干净状态，已停止同步：\n" + status)


def ensure_paths_exist(config: Config, manifest: dict) -> None:
    policy = manifest.get("protectedPathPolicy", {})
    for key in ("criticalPaths", "manualReviewPaths", "stopOnDeletePaths"):
        paths = policy.get(key, [])
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            raise SyncError(f"保护清单字段 {key} 必须是字符串数组")
        missing = [item for item in paths if not (config.root / item.rstrip("/")).exists()]
        if missing:
            raise SyncError(f"保护清单包含不存在路径 {key}: {', '.join(missing)}")


def nova_version(version: str) -> str:
    base = re.sub(r"-nova(?:\.[0-9]+)?$", "", version)
    return f"{base}-nova"


def update_nova_versions(config: Config, version: str) -> list[str]:
    value = nova_version(version) + "\n"
    updated: list[str] = []
    for relative in ("FORK_VERSION", "backend/cmd/server/VERSION"):
        path = config.root / relative
        if path.exists():
            path.write_text(value, encoding="utf-8")
            updated.append(relative)
    return updated


def preflight_three_way(config: Config, patch: bytes) -> list[str]:
    temp_root = Path(tempfile.mkdtemp(prefix="nova-sync-preflight-"))
    worktree_added = False
    try:
        run_git(config, "worktree", "add", "--detach", str(temp_root), config.target_ref)
        worktree_added = True
        result = subprocess.run(
            ["git", "apply", "--3way", "--binary", "-"],
            cwd=temp_root,
            input=patch,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return []
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=temp_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout
        conflicts = sorted(
            line[3:]
            for line in status.splitlines()
            if len(line) >= 3 and line[:2] in {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}
        )
        if conflicts:
            return conflicts
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise SyncError(f"三方应用失败但未发现冲突文件: {detail}")
    finally:
        if worktree_added:
            run_git(config, "worktree", "remove", "--force", str(temp_root), check=False)
        shutil.rmtree(temp_root, ignore_errors=True)


def apply_three_way(config: Config, patch: bytes) -> None:
    result = subprocess.run(
        ["git", "apply", "--3way", "--binary", "-"],
        cwd=config.root,
        input=patch,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise SyncError(f"三方应用失败: {detail}")


def write_report(config: Config, report: dict) -> None:
    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Nova 上游同步候选报告",
        "",
        f"- 生成时间：`{report['generatedAt']}`",
        f"- 上游旧基线：`{report['oldUpstreamCommit']}`",
        f"- 上游新提交：`{report['newUpstreamCommit']}`",
        f"- 上游版本：`{report['oldVersion']}` → `{report['newVersion']}`",
        f"- Nova 候选版本：`{report.get('novaCandidateVersion', '未生成')}`",
        f"- Nova 目标分支：`{report['targetRef']}`",
        f"- 候选分支：`{report.get('candidateBranch') or '未创建'}`",
        f"- Provenance：`{report.get('provenancePath', '未生成')}`",
        f"- 应用状态：`{report['applyStatus']}`",
        f"- 自动合并判定：`{report['autoMergeDecision']}`",
        "",
        "## 变更统计",
        "",
    ]
    lines.extend(f"- `{item}`" for item in report["diffStat"] or ["无变更"])
    for title, key in (
        ("冲突文件", "conflicts"),
        ("Critical 路径影响", "criticalPaths"),
        ("人工复核路径影响", "manualReviewPaths"),
        ("删除即停路径", "stopOnDeletePaths"),
    ):
        lines.extend(["", f"## {title}", ""])
        values = report[key]
        lines.extend(f"- `{item}`" for item in values or ["无"])
    lines.extend(
        [
            "",
            "## 必需验证",
            "",
            "- `Validate fusion candidate`",
            "- `git diff --check`",
            "- Go 测试与 lint",
            "- 前端 lint、类型检查、测试与构建",
            "- Nova Docker Compose 构建、启动和健康检查",
            "",
            "> `lastSuccessfulCommit` 只有候选 PR 通过验证并合并后才能更新。",
            "",
        ]
    )
    config.report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: Sequence[str]) -> Config:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--state", type=Path, default=Path("state/upstreams.json"))
    parser.add_argument("--manifest", type=Path, default=Path("state/nova-customizations.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/upstream-sync-report.md"))
    parser.add_argument("--remote", default="upstream")
    parser.add_argument("--upstream-repository", default="Wei-Shaw/sub2api")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--target", default="main")
    parser.add_argument("--commit", dest="requested_commit")
    parser.add_argument("--branch")
    parser.add_argument("--no-branch", dest="create_branch", action="store_false")
    parser.add_argument("--no-apply", dest="apply", action="store_false")
    parser.add_argument("--commit-candidate", dest="commit", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    return Config(
        root=root,
        state_path=(root / args.state).resolve(),
        manifest_path=(root / args.manifest).resolve(),
        report_path=(root / args.report).resolve(),
        upstream_remote=args.remote,
        upstream_repository=args.upstream_repository,
        upstream_ref=args.ref,
        target_ref=args.target,
        requested_commit=args.requested_commit,
        branch=args.branch,
        commit=args.commit,
        create_branch=args.create_branch,
        apply=args.apply,
    )


def is_upstream_ancestor(config: Config, old: str, new: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", old, new],
        cwd=config.root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = result.stderr.decode("utf-8", errors="replace").strip()
    raise SyncError(f"无法验证上游提交祖先关系：{detail}")


def main(argv: Sequence[str] | None = None) -> int:
    config = parse_args(argv or sys.argv[1:])
    try:
        state = load_json(config.state_path)
        manifest = load_json(config.manifest_path)
        ensure_clean(config)
        ensure_paths_exist(config, manifest)
        verify_upstream_remote(config)
        if not config.requested_commit:
            run_git(config, "fetch", "--prune", config.upstream_remote)
        old = resolve_commit(config, state["lastSuccessfulCommit"])
        target = resolve_commit(config, config.target_ref)
        current = resolve_commit(config, "HEAD")
        if current != target:
            raise SyncError(
                f"当前 HEAD ({current[:12]}) 不是目标分支 {config.target_ref} ({target[:12]})，请先切换到目标分支"
            )
        new = resolve_commit(config, config.requested_commit or f"{config.upstream_remote}/{config.upstream_ref}")
        if old == new:
            print(f"没有上游更新：{new}")
            return 0
        if config.requested_commit:
            new = resolve_commit(config, config.requested_commit)
        if len(old) != 40 or len(new) != 40:
            raise SyncError("上游 old/new 提交必须是完整 SHA")
        verify_upstream_object(config, old)
        verify_upstream_object(config, new)
        if not is_upstream_ancestor(config, old, new):
            raise SyncError(f"上游新提交不是旧成功基线的后代：{old} -> {new}")
        paths = changed_paths(config, old, new)
        policy = manifest["protectedPathPolicy"]
        critical = [path for path in paths if path_matches(path, policy["criticalPaths"])]
        manual = [path for path in paths if path_matches(path, policy["manualReviewPaths"])]
        stop_deleted = [path for path in deleted_paths(config, old, new) if path_matches(path, policy["stopOnDeletePaths"])]
        patch = patch_bytes(config, old, new)
        conflicts = preflight_three_way(config, patch)
        blocked = bool(conflicts or stop_deleted)
        report = {
            "generatedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "oldUpstreamCommit": old,
            "newUpstreamCommit": new,
            "oldVersion": version_at(config, old),
            "newVersion": version_at(config, new),
            "novaCandidateVersion": nova_version(version_at(config, new)),
            "targetRef": config.target_ref,
            "candidateBranch": None,
            "applyStatus": "blocked" if blocked else "ready",
            "autoMergeDecision": "blocked" if blocked or critical or manual else "eligible-after-required-checks",
            "diffStat": diff_stat(config, old, new),
            "conflicts": conflicts,
            "criticalPaths": critical,
            "manualReviewPaths": manual,
            "stopOnDeletePaths": stop_deleted,
        }
        if config.apply and not blocked:
            if config.create_branch:
                branch = config.branch or f"sync/upstream-{new[:12]}-{dt.date.today().isoformat()}"
                run_git(config, "switch", "-c", branch)
                report["candidateBranch"] = branch
            apply_three_way(config, patch)
            updated_versions = update_nova_versions(config, report["newVersion"])
            report["updatedVersionFiles"] = updated_versions
            provenance_path = write_provenance(config, report, patch)
            report["provenancePath"] = provenance_path
            config.report_path.parent.mkdir(parents=True, exist_ok=True)
            write_report(config, report)
            if config.commit:
                stage_paths = [*paths, *updated_versions, provenance_path]
                try:
                    stage_paths.append(str(config.report_path.relative_to(config.root)))
                except ValueError:
                    pass
                run_git(config, "add", "--", *stage_paths)
                run_git(config, "commit", "-m", f"同步：融合上游 {new[:12]}")
        else:
            write_report(config, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if blocked else 0
    except (KeyError, SyncError) as exc:
        print(f"同步停止：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
