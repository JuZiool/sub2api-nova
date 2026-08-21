#!/usr/bin/env python3
"""Regression checks for applying a fusion candidate to a sync checkout."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply_candidate.py"
spec = importlib.util.spec_from_file_location("apply_candidate", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary) / "target"
    candidate = Path(temporary) / "candidate"
    base.mkdir()
    candidate.mkdir()
    git(base, "init", "-q")
    (base / "fusion.json").write_text(
        json.dumps({"nova": {"overlay_base_commit": "old"}}) + "\n", encoding="utf-8"
    )
    (base / ".gitignore").write_text("keep\n", encoding="utf-8")
    (base / "keep.txt").write_text("same\n", encoding="utf-8")
    (base / "remove.txt").write_text("remove\n", encoding="utf-8")
    (base / "scripts").mkdir()
    (base / "scripts/control.py").write_text("target\n", encoding="utf-8")
    git(base, "add", ".")
    git(base, "-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-qm", "base")

    (candidate / "keep.txt").write_text("updated\n", encoding="utf-8")
    (candidate / "added.txt").write_text("added\n", encoding="utf-8")
    (candidate / "scripts").mkdir()
    (candidate / "scripts/control.py").write_text("candidate must not apply\n", encoding="utf-8")
    (candidate / ".nova-fusion-metadata.json").write_text("{}\n", encoding="utf-8")

    result = module.apply_candidate(base, candidate, "new-official")
    assert result["changed"] == ["keep.txt"]
    assert result["added"] == ["added.txt"]
    assert result["deleted"] == ["remove.txt"]
    assert not (base / "remove.txt").exists()
    assert (base / "scripts/control.py").read_text(encoding="utf-8") == "target\n"
    config = json.loads((base / "fusion.json").read_text(encoding="utf-8"))
    assert config["nova"]["overlay_base_commit"] == "new-official"

print("Nova sync export checks passed")
