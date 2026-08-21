#!/usr/bin/env python3
"""Small regression checks for the Nova fusion helpers."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fuse_candidate.py"
spec = importlib.util.spec_from_file_location("fuse_candidate", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.nova_version_for("0.1.179") == "0.1.179-nova"
try:
    module.nova_version_for("0.1.179-nova")
except module.FusionError:
    pass
else:
    raise AssertionError("non-upstream version must be rejected")

config = json.loads((ROOT / "fusion.json").read_text(encoding="utf-8"))
assert config["nova"]["includes_overdraft"] is True
assert config["nova"]["overlay_base_commit"]

with tempfile.TemporaryDirectory() as temporary:
    candidate = Path(temporary)
    (candidate / "backend/cmd/server").mkdir(parents=True)
    (candidate / "FORK_VERSION").write_text("old\n", encoding="utf-8")
    (candidate / "backend/cmd/server/VERSION").write_text("old\n", encoding="utf-8")
    assert module.apply_candidate_version(candidate, "0.1.179") == "0.1.179-nova"
    assert (candidate / "FORK_VERSION").read_text(encoding="utf-8") == "0.1.179-nova\n"
    assert (candidate / "backend/cmd/server/VERSION").read_text(encoding="utf-8") == "0.1.179-nova\n"

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    base = root / "base"
    official = root / "official"
    nova = root / "nova"
    candidate = root / "candidate"
    merge_temp = root / "merge-temp"
    for directory in (base, official, nova, candidate):
        directory.mkdir()
    relative = Path(".github/audit-exceptions.yml")
    (base / relative).parent.mkdir(parents=True)
    (official / relative).parent.mkdir(parents=True)
    (candidate / relative).parent.mkdir(parents=True)
    (base / relative).write_text("same\n", encoding="utf-8")
    (official / relative).write_text("same\n", encoding="utf-8")
    (candidate / relative).write_text("same\n", encoding="utf-8")
    assert module.merge_composite_file(relative, base, official, nova, candidate, merge_temp) == "nova"
    assert not (candidate / relative).exists()

    (official / relative).write_text("official change\n", encoding="utf-8")
    (candidate / relative).write_text("official change\n", encoding="utf-8")
    try:
        module.merge_composite_file(relative, base, official, nova, candidate, merge_temp)
    except module.FusionError as exc:
        assert "delete/modify conflict" in str(exc)
    else:
        raise AssertionError("Nova delete must not override an official modification")

print("Nova fusion helper checks passed")
