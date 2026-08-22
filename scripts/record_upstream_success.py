#!/usr/bin/env python3
"""Record a successfully merged upstream synchronization baseline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
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
    if report.get("stopOnDeletePaths"):
        raise BaselineError("同步报告包含删除即停路径，拒绝记录成功基线")
    return report


def nova_version(version: str) -> str:
    base = re.sub(r"-nova(?:\.[0-9]+)?$", "", version)
    return f"{base}-nova"


def update_state(
    state_path: Path,
    report: dict[str, Any],
    nova_commit: str,
    merged_at: str,
) -> None:
    state = load_object(state_path)
    old = required_string(state.get("lastSuccessfulCommit"), "lastSuccessfulCommit")
    report_old = required_string(report["oldUpstreamCommit"], "oldUpstreamCommit")
    if report_old != "provided-by-workflow" and report_old != old:
        raise BaselineError(
            f"同步报告旧基线 {report_old} 与当前成功基线 {old} 不一致，拒绝记录"
        )
    upstream_commit = required_string(report["newUpstreamCommit"], "newUpstreamCommit")
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
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path("state/upstreams.json"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--upstream-commit")
    parser.add_argument("--upstream-version")
    parser.add_argument("--nova-commit", required=True)
    parser.add_argument("--merged-at", default="")
    args = parser.parse_args()
    if args.report and (args.upstream_commit or args.upstream_version):
        parser.error("--report 不能与 --upstream-commit 或 --upstream-version 同时使用")
    if bool(args.upstream_commit) != bool(args.upstream_version):
        parser.error("--upstream-commit 和 --upstream-version 必须同时提供")
    if not args.report and not args.upstream_commit:
        parser.error("必须提供 --report，或同时提供 --upstream-commit 和 --upstream-version")
    return args


def report_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.report:
        return load_report(args.report.resolve())
    return {
        "oldUpstreamCommit": "provided-by-workflow",
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
