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
from dataclasses import dataclass, replace
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


@dataclass(frozen=True)
class PreflightResult:
    """Classified result of applying the filtered patch in a temporary worktree."""

    failed: bool
    conflicts: list[str]
    unapplied_paths: list[str]
    missing_index_paths: list[str]
    index_mismatch_paths: list[str]
    diagnostics: list[str]

    @property
    def blocked(self) -> bool:
        return self.failed


CONFLICT_DIAGNOSTIC_RE = re.compile(r"^Applied patch to '(.+)' with conflicts\.$")
MISSING_INDEX_DIAGNOSTIC_RE = re.compile(r"^error: (.+): does not exist in index$")
INDEX_MISMATCH_DIAGNOSTIC_RE = re.compile(r"^error: (.+): does not match index$")
PATCH_FAILED_DIAGNOSTIC_RE = re.compile(r"^error: patch failed: (.+):\d+(?::.*)?$")
PATCH_DOES_NOT_APPLY_DIAGNOSTIC_RE = re.compile(r"^error: (.+): patch does not apply$")
WORKTREE_EXISTS_DIAGNOSTIC_RE = re.compile(
    r"^error: (.+): already exists in working directory$"
)


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


def patch_bytes(config: Config, old: str, new: str, paths: Sequence[str] | None = None) -> bytes:
    args = ["git", "diff", "--binary", "--no-renames", old, new]
    if paths is not None:
        args.extend(["--", *paths])
    return subprocess.run(
        args,
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
        "appliedPaths": report.get("appliedPaths", []),
        "adaptedPaths": report.get("adaptedPaths", []),
        "preservedProtectedPaths": report.get("preservedProtectedPaths", []),
        "absorbedNewMigrationPaths": report.get("absorbedNewMigrationPaths", []),
        "pendingNewProtectedPaths": report.get("pendingNewProtectedPaths", []),
        "excludedPaths": report.get("excludedPaths", []),
        "versionPaths": report.get("versionPaths", []),
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


def protected_patterns(policy: dict) -> list[str]:
    """Return the union of every path class that must retain Nova's code."""
    patterns: list[str] = []
    for key in ("criticalPaths", "manualReviewPaths", "stopOnDeletePaths"):
        patterns.extend(policy.get(key, []))
    return list(dict.fromkeys(patterns))


def split_protected_paths(paths: Iterable[str], policy: dict) -> tuple[list[str], list[str]]:
    protected = protected_patterns(policy)
    preserved = sorted({path for path in paths if path_matches(path, protected)})
    applied = sorted({path for path in paths if path not in preserved})
    return applied, preserved


def changed_paths(config: Config, old: str, new: str) -> list[str]:
    output = run_git(config, "diff", "--name-only", "--no-renames", old, new)
    return sorted({line for line in output.splitlines() if line})


def diff_stat(config: Config, old: str, new: str, paths: Sequence[str] | None = None) -> list[str]:
    args = ["diff", "--stat", "--no-renames", old, new]
    if paths is not None:
        args.extend(["--", *paths])
    output = run_git(config, *args)
    return [line for line in output.splitlines() if line.strip()]


def deleted_paths(config: Config, old: str, new: str) -> list[str]:
    output = run_git(config, "diff", "--name-status", "--no-renames", old, new)
    deleted: list[str] = []
    for line in output.splitlines():
        fields = line.split("\t", 2)
        if len(fields) >= 2 and fields[0] == "D":
            deleted.append(fields[1])
    return sorted(deleted)


def added_paths(config: Config, old: str, new: str) -> list[str]:
    """上游新增文件（上游有、Nova 树不存在的路径）。"""
    output = run_git(config, "diff", "--diff-filter=A", "--name-only", "--no-renames", old, new)
    return sorted({line for line in output.splitlines() if line})


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


def parse_preflight_diagnostics(output: str) -> PreflightResult:
    """Classify git-apply diagnostics that do not always reach porcelain status."""
    conflicts: set[str] = set()
    unapplied_paths: set[str] = set()
    missing_index_paths: set[str] = set()
    index_mismatch_paths: set[str] = set()
    diagnostics: list[str] = []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if match := CONFLICT_DIAGNOSTIC_RE.match(line):
            conflicts.add(match.group(1))
            continue
        if match := MISSING_INDEX_DIAGNOSTIC_RE.match(line):
            missing_index_paths.add(match.group(1))
            continue
        if match := INDEX_MISMATCH_DIAGNOSTIC_RE.match(line):
            index_mismatch_paths.add(match.group(1))
            continue
        if match := PATCH_FAILED_DIAGNOSTIC_RE.match(line):
            unapplied_paths.add(match.group(1))
            continue
        if match := PATCH_DOES_NOT_APPLY_DIAGNOSTIC_RE.match(line):
            unapplied_paths.add(match.group(1))
            continue
        if match := WORKTREE_EXISTS_DIAGNOSTIC_RE.match(line):
            unapplied_paths.add(match.group(1))
            continue
        if line.startswith("error:"):
            diagnostics.append(line)

    return PreflightResult(
        failed=True,
        conflicts=sorted(conflicts),
        unapplied_paths=sorted(unapplied_paths),
        missing_index_paths=sorted(missing_index_paths),
        index_mismatch_paths=sorted(index_mismatch_paths),
        diagnostics=diagnostics,
    )


def preflight_three_way(config: Config, patch: bytes) -> PreflightResult:
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
            return PreflightResult(
                failed=False,
                conflicts=[],
                unapplied_paths=[],
                missing_index_paths=[],
                index_mismatch_paths=[],
                diagnostics=[],
            )
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
        diagnostics = parse_preflight_diagnostics(
            "\n".join(
                part
                for part in (
                    result.stdout.decode("utf-8", errors="replace"),
                    result.stderr.decode("utf-8", errors="replace"),
                )
                if part
            )
        )
        return PreflightResult(
            failed=True,
            conflicts=sorted(set(conflicts).union(diagnostics.conflicts)),
            unapplied_paths=diagnostics.unapplied_paths,
            missing_index_paths=diagnostics.missing_index_paths,
            index_mismatch_paths=diagnostics.index_mismatch_paths,
            diagnostics=diagnostics.diagnostics,
        )
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


def report_config_for(config: Config) -> Config:
    """Keep --no-apply reports outside the repository so its tree stays untouched."""
    if config.apply:
        return config
    try:
        config.report_path.relative_to(config.root)
    except ValueError:
        return config
    temp_root = Path(tempfile.mkdtemp(prefix="nova-sync-report-"))
    return replace(config, report_path=temp_root / config.report_path.name)


def display_report_path(config: Config) -> str:
    try:
        return str(config.report_path.relative_to(config.root)).replace("\\", "/")
    except ValueError:
        return str(config.report_path)


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
        f"- 预检报告：`{report['reportPath']}`",
        f"- 预检状态：`{report['preflightStatus']}`",
        f"- Provenance：`{report.get('provenancePath', '未生成')}`",
        f"- 应用状态：`{report['applyStatus']}`",
        f"- 自动合并判定：`{report['autoMergeDecision']}`",
        "",
        "## 变更统计",
        "",
    ]
    lines.extend(f"- `{item}`" for item in report["diffStat"] or ["无变更"])
    for title, key in (
        ("实际应用路径", "appliedPaths"),
        ("已保留 Nova 代码的保护路径", "preservedProtectedPaths"),
        ("吸收的上游新增迁移（backend/migrations/）", "absorbedNewMigrationPaths"),
        ("保护路径新增文件待人工放行", "pendingNewProtectedPaths"),
        ("版本元数据路径", "versionPaths"),
        ("真实三方冲突路径", "conflicts"),
        ("无法应用路径", "unappliedPaths"),
        ("缺失 index 路径", "missingIndexPaths"),
        ("index 不匹配路径", "indexMismatchPaths"),
        ("未归类预检诊断", "preflightDiagnostics"),
        ("Critical 路径影响", "criticalPaths"),
        ("人工复核路径影响", "manualReviewPaths"),
        ("保护路径删除影响", "stopOnDeletePaths"),
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
    report_config = report_config_for(config)
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
        added = added_paths(config, old, new)
        policy = manifest["protectedPathPolicy"]
        applied_paths, preserved_protected_paths = split_protected_paths(paths, policy)
        # 根治"上游新增迁移被保护清单静默过滤"：上游新增文件在 Nova 树中不存在，
        # 没有"Nova 代码要保留"的语义，整批丢弃会让代码引用缺失的列/索引
        # （历史事故见迁移 238/239 与上游 226/228 对照）。
        # - backend/migrations/ 下的上游新增文件自动吸收（幂等 SQL，随链校验）；
        # - 其余保护路径的新增文件仍保留 Nova 侧，但单独登记待人工放行，
        #   不再混在 preservedProtectedPaths 中静默消失。
        protected_added = sorted(path for path in added if path in preserved_protected_paths)
        absorbed_new_migrations = sorted(
            path for path in protected_added if path.startswith("backend/migrations/")
        )
        pending_new_protected = sorted(set(protected_added) - set(absorbed_new_migrations))
        applied_paths = sorted(set(applied_paths) | set(absorbed_new_migrations))
        preserved_protected_paths = sorted(set(preserved_protected_paths) - set(absorbed_new_migrations))
        critical = [path for path in paths if path_matches(path, policy["criticalPaths"])]
        manual = [path for path in paths if path_matches(path, policy["manualReviewPaths"])]
        stop_deleted = [path for path in deleted_paths(config, old, new) if path_matches(path, policy["stopOnDeletePaths"])]
        patch = patch_bytes(config, old, new, applied_paths)
        preflight = preflight_three_way(config, patch)
        version_paths = [
            relative
            for relative in ("FORK_VERSION", "backend/cmd/server/VERSION")
            if (config.root / relative).exists()
        ]
        blocked = preflight.blocked
        report = {
            "generatedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "oldUpstreamCommit": old,
            "newUpstreamCommit": new,
            "oldVersion": version_at(config, old),
            "newVersion": version_at(config, new),
            "novaCandidateVersion": nova_version(version_at(config, new)),
            "targetRef": config.target_ref,
            "candidateBranch": None,
            "reportPath": display_report_path(report_config),
            "preflightStatus": "blocked" if blocked else "passed",
            "applyStatus": "blocked" if blocked else "ready",
            "autoMergeDecision": "blocked" if blocked else "eligible-after-required-checks",
            "diffStat": diff_stat(config, old, new, applied_paths) if applied_paths else [],
            "conflicts": preflight.conflicts,
            "unappliedPaths": preflight.unapplied_paths,
            "missingIndexPaths": preflight.missing_index_paths,
            "indexMismatchPaths": preflight.index_mismatch_paths,
            "preflightDiagnostics": preflight.diagnostics,
            "appliedPaths": applied_paths,
            "preservedProtectedPaths": preserved_protected_paths,
            "absorbedNewMigrationPaths": absorbed_new_migrations,
            "pendingNewProtectedPaths": pending_new_protected,
            "versionPaths": version_paths,
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
            report_config.report_path.parent.mkdir(parents=True, exist_ok=True)
            write_report(report_config, report)
            if config.commit:
                stage_paths = [*applied_paths, *updated_versions, provenance_path]
                try:
                    stage_paths.append(str(report_config.report_path.relative_to(config.root)))
                except ValueError:
                    pass
                run_git(config, "add", "--", *stage_paths)
                run_git(config, "commit", "-m", f"同步：融合上游 {new[:12]}")
        else:
            write_report(report_config, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if blocked else 0
    except (KeyError, SyncError) as exc:
        print(f"同步停止：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
