#!/usr/bin/env python3
"""Record a successfully merged upstream synchronization baseline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


class BaselineError(RuntimeError):
    """Raised when a synchronization baseline cannot be recorded safely."""


def load_object(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineError(f"无法读取 JSON 文件 {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BaselineError(f"JSON 根节点必须是对象: {path}")
    return value


def required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BaselineError(f"字段 {field} 必须是非空字符串")
    return value.strip()


def load_report(path: Path) -> dict[str, Any]:
    report = load_object(path)
    for field in ("oldUpstreamCommit", "newUpstreamCommit", "newVersion"):
        required_string(report.get(field), field)
    if report.get("applyStatus") != "ready":
        raise BaselineError("同步报告不是 ready 状态，拒绝记录成功基线")
    if report.get("conflicts"):
        raise BaselineError("同步报告包含冲突文件，拒绝记录成功基线")
    return report


def nova_version(version: str) -> str:
    base = re.sub(r"-nova(?:\.[0-9]+)?$", "", version)
    return f"{base}-nova"


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise BaselineError(f"无法原子写入状态文件 {path}: {exc}") from exc

def update_state(
    state_path: Path,
    report: dict[str, Any],
    nova_commit: str,
    merged_at: str,
) -> None:
    state = load_object(state_path)
    if report.get("applyStatus") != "ready":
        raise BaselineError("同步报告不是 ready 状态，拒绝记录成功基线")
    if report.get("conflicts"):
        raise BaselineError("同步报告包含冲突文件，拒绝记录成功基线")
    old = required_string(state.get("lastSuccessfulCommit"), "lastSuccessfulCommit")
    report_old = required_string(report["oldUpstreamCommit"], "oldUpstreamCommit")
    if not re.fullmatch(r"[0-9a-f]{40}", report_old):
        raise BaselineError("同步报告旧基线必须是完整 SHA")
    if report_old != old:
        raise BaselineError(
            f"同步报告旧基线 {report_old} 与当前成功基线 {old} 不一致，拒绝记录"
        )
    upstream_commit = required_string(report["newUpstreamCommit"], "newUpstreamCommit")
    if not re.fullmatch(r"[0-9a-f]{40}", upstream_commit):
        raise BaselineError("同步报告新提交必须是完整 SHA")
    if old == upstream_commit:
        raise BaselineError(f"成功基线已经是 {upstream_commit}，拒绝重复更新")

    version = required_string(report["newVersion"], "newVersion")
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    state.update(
        {
            "lastSuccessfulCommit": upstream_commit,
            "lastSuccessfulVersion": version,
            "lastSyncCommit": nova_commit,
            "lastSuccessfulNovaCommit": nova_commit,
            "lastSyncAt": merged_at or now,
            "lastSyncStatus": "success",
            "lastSyncNote": "上游同步候选已通过 Nova 验证并合并，成功基线已更新。",
            "currentUpstreamCommit": upstream_commit,
            "currentUpstreamVersion": version,
            "currentUpstreamObservedAt": now,
            "novaCommit": nova_commit,
            "novaMainCommitAtSnapshot": nova_commit,
            "novaVersion": nova_version(version),
            "serverVersion": nova_version(version),
            "syncStatus": "success",
            "syncReason": "lastSuccessfulCommit 已由通过验证并合并的同步候选更新。",
        }
    )
    atomic_write_json(state_path, state)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path("state/upstreams.json"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--old-upstream-commit")
    parser.add_argument("--upstream-commit")
    parser.add_argument("--upstream-version")
    parser.add_argument("--nova-commit", required=True)
    parser.add_argument("--merged-at", default="")
    args = parser.parse_args()
    if args.report and (args.upstream_commit or args.upstream_version or args.old_upstream_commit):
        parser.error("--report 不能与手动提交参数同时使用")
    if args.report is None and not all((args.old_upstream_commit, args.upstream_commit, args.upstream_version)):
        parser.error("手动模式必须同时提供 --old-upstream-commit、--upstream-commit 和 --upstream-version")
    return args


def report_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.report:
        return load_report(args.report.resolve())
    return {
        "oldUpstreamCommit": required_string(args.old_upstream_commit, "old_upstream_commit"),
        "newUpstreamCommit": required_string(args.upstream_commit, "upstream_commit"),
        "newVersion": required_string(args.upstream_version, "upstream_version"),
        "applyStatus": "ready",
        "conflicts": [],
        "stopOnDeletePaths": [],
    }


def main() -> int:
    args = parse_args()
    try:
        report = report_from_args(args)
        update_state(args.state.resolve(), report, args.nova_commit, args.merged_at)
    except BaselineError as exc:
        print(f"基线记录停止：{exc}")
        return 1
    print(f"已记录上游成功基线：{report['newUpstreamCommit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
