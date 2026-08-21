#!/usr/bin/env python3
"""Regression checks for applying a fusion candidate to a sync checkout."""

from __future__ import annotations

import importlib.util
import json
import os
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
    tracked_dependency = base / "frontend/node_modules/tracked.txt"
    tracked_dependency.parent.mkdir(parents=True)
    tracked_dependency.write_text("keep generated\n", encoding="utf-8")
    (base / "frontend/node_modules-extra").mkdir(parents=True)
    (base / "frontend/node_modules-extra/boundary.js").write_text("boundary\n", encoding="utf-8")
    git(base, "add", ".")
    git(base, "-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-qm", "base")

    (candidate / "keep.txt").write_text("updated\n", encoding="utf-8")
    (candidate / "added.txt").write_text("added\n", encoding="utf-8")
    (candidate / "scripts").mkdir()
    (candidate / "scripts/control.py").write_text("candidate must not apply\n", encoding="utf-8")
    (candidate / ".nova-fusion-metadata.json").write_text(
        json.dumps({"nova": {"overlay_base_commit": "shared-base"}}) + "\n",
        encoding="utf-8",
    )
    (candidate / "frontend/node_modules").mkdir(parents=True)
    (candidate / "frontend/node_modules/generated.js").write_text("generated\n", encoding="utf-8")
    (candidate / "node_modules").mkdir()
    (candidate / "node_modules/root-generated.js").write_text("generated\n", encoding="utf-8")
    (candidate / "frontend/node_modules-extra").mkdir(parents=True)
    (candidate / "frontend/node_modules-extra/boundary.js").write_text("boundary\n", encoding="utf-8")

    symlink_supported = True
    try:
        os.symlink("generated.js", candidate / "frontend/node_modules/link.js")
    except (OSError, NotImplementedError):
        symlink_supported = False

    result = module.apply_candidate(base, candidate, "new-official")
    assert result["changed"] == ["keep.txt"]
    assert result["added"] == ["added.txt"]
    assert result["deleted"] == ["remove.txt"]
    assert result["overlay_base_commit"] == "shared-base"
    assert result["overlay_base_commit"] != "new-official"
    assert not (base / "remove.txt").exists()
    assert (base / "scripts/control.py").read_text(encoding="utf-8") == "target\n"
    assert tracked_dependency.exists()
    assert (base / "frontend/node_modules-extra/boundary.js").read_text(encoding="utf-8") == "boundary\n"
    config = json.loads((base / "fusion.json").read_text(encoding="utf-8"))
    assert config["nova"]["overlay_base_commit"] == "shared-base"

    missing_metadata = Path(temporary) / "missing-metadata-candidate"
    missing_metadata.mkdir()
    try:
        module.apply_candidate(base, missing_metadata, "new-official")
    except module.ExportError as exc:
        assert "metadata" in str(exc)
    else:
        raise AssertionError("candidate without fusion metadata was accepted")

    if symlink_supported:
        business_candidate = Path(temporary) / "business-symlink-candidate"
        business_candidate.mkdir()
        (business_candidate / "source.ts").write_text("source\n", encoding="utf-8")
        os.symlink("source.ts", business_candidate / "business-link.ts")
        try:
            module.candidate_files(business_candidate)
        except module.ExportError:
            pass
        else:
            raise AssertionError("business source symlink was accepted")

print("Nova sync export checks passed")
