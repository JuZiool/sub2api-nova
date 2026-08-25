import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "verify_upstream_candidate.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("verify_upstream_candidate", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


class VerifyUpstreamCandidateTests(unittest.TestCase):
    def test_recomputes_patch_and_manifest_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "-b", "main")
            git(root, "config", "core.autocrlf", "false")
            git(root, "config", "user.name", "test")
            git(root, "config", "user.email", "test@example.invalid")
            manifest_path = root / "state" / "nova-customizations.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(
                json.dumps(
                    {
                        "protectedPathPolicy": {
                            "criticalPaths": ["protected.txt"],
                            "manualReviewPaths": [],
                            "stopOnDeletePaths": [],
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "tracked.txt").write_text("old\n", encoding="utf-8")
            (root / "protected.txt").write_text("nova\n", encoding="utf-8")
            git(root, "add", ".")
            git(root, "commit", "-m", "base")
            old = git(root, "rev-parse", "HEAD")
            (root / "tracked.txt").write_text("new\n", encoding="utf-8")
            (root / "protected.txt").write_text("upstream\n", encoding="utf-8")
            git(root, "add", ".")
            git(root, "commit", "-m", "upstream")
            new = git(root, "rev-parse", "HEAD")
            patch = subprocess.run(
                ["git", "diff", "--binary", "--no-renames", old, new, "--", "tracked.txt"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            git(root, "switch", "-c", "sync/test", old)
            (root / "tracked.txt").write_text("new\n", encoding="utf-8")
            git(root, "add", "tracked.txt")
            git(root, "commit", "-m", "fusion")
            provenance = {
                "schema": 1,
                "generator": "scripts/sync_upstream.py",
                "upstreamRepository": "Wei-Shaw/sub2api",
                "upstreamRef": "main",
                "oldUpstreamCommit": old,
                "newUpstreamCommit": new,
                "newVersion": "0.1.179",
                "targetRef": "main",
                "candidateBranch": "sync/test",
                "baseNovaCommit": old,
                "manifestPath": "state/nova-customizations.json",
                "manifestSha256": module.sha256_file(manifest_path),
                "patchSha256": module.sha256_bytes(patch),
                "applyStatus": "ready",
                "appliedPaths": ["tracked.txt"],
                "preservedProtectedPaths": ["protected.txt"],
                "versionPaths": [],
            }
            provenance_path = root / ".nova-upstream-provenance.json"
            provenance_path.write_text(
                json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            git(root, "add", ".nova-upstream-provenance.json")
            git(root, "commit", "-m", "candidate")
            candidate = git(root, "rev-parse", "HEAD")

            result = module.verify_candidate(
                root,
                provenance_path,
                "state/nova-customizations.json",
                old,
                "sync/test",
                candidate,
            )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["criticalPaths"], ["protected.txt"])
        self.assertEqual(result["preservedProtectedPaths"], ["protected.txt"])
        self.assertEqual(result["appliedPaths"], ["tracked.txt"])
        self.assertEqual(result["manualReviewPaths"], [])

    def test_rejects_candidate_with_extra_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "-b", "main")
            git(root, "config", "core.autocrlf", "false")
            git(root, "config", "user.name", "test")
            git(root, "config", "user.email", "test@example.invalid")
            manifest_path = root / "state" / "nova-customizations.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(
                json.dumps(
                    {
                        "protectedPathPolicy": {
                            "criticalPaths": [],
                            "manualReviewPaths": [],
                            "stopOnDeletePaths": [],
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "tracked.txt").write_text("old\n", encoding="utf-8")
            git(root, "add", ".")
            git(root, "commit", "-m", "base")
            old = git(root, "rev-parse", "HEAD")
            (root / "tracked.txt").write_text("new\n", encoding="utf-8")
            git(root, "add", ".")
            git(root, "commit", "-m", "upstream")
            new = git(root, "rev-parse", "HEAD")
            patch = subprocess.run(
                ["git", "diff", "--binary", old, new],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            provenance = {
                "schema": 1,
                "generator": "scripts/sync_upstream.py",
                "upstreamRepository": "Wei-Shaw/sub2api",
                "upstreamRef": "main",
                "oldUpstreamCommit": old,
                "newUpstreamCommit": new,
                "newVersion": "0.1.179",
                "targetRef": "main",
                "candidateBranch": "sync/test",
                "baseNovaCommit": old,
                "manifestPath": "state/nova-customizations.json",
                "manifestSha256": module.sha256_file(manifest_path),
                "patchSha256": module.sha256_bytes(patch),
                "applyStatus": "ready",
                "appliedPaths": ["tracked.txt"],
                "preservedProtectedPaths": [],
                "versionPaths": [],
            }
            provenance_path = root / ".nova-upstream-provenance.json"
            provenance_path.write_text(json.dumps(provenance) + "\n", encoding="utf-8")
            (root / "unexpected.txt").write_text("extra\n", encoding="utf-8")
            git(root, "add", ".nova-upstream-provenance.json", "unexpected.txt")
            git(root, "commit", "-m", "tampered candidate")
            candidate = git(root, "rev-parse", "HEAD")

            with self.assertRaises(module.VerificationError):
                module.verify_candidate(
                    root,
                    provenance_path,
                    "state/nova-customizations.json",
                    old,
                    "sync/test",
                    candidate,
                )

    def test_rejects_missing_provenance(self):
        with self.assertRaises(module.VerificationError):
            module.verify_candidate(
                Path.cwd(),
                Path("does-not-exist.json"),
                "state/nova-customizations.json",
                "a" * 40,
                "sync/test",
            )


if __name__ == "__main__":
    unittest.main()
