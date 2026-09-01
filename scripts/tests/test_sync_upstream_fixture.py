import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "sync_upstream.py"


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


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


class SyncFixture:
    def __init__(self, root: Path, policy: dict[str, list[str]]):
        self.root = root
        git(root, "init", "-b", "main")
        git(root, "config", "user.name", "Nova sync fixture")
        git(root, "config", "user.email", "nova-sync-fixture@example.invalid")
        git(root, "remote", "add", "upstream", "https://github.com/Wei-Shaw/sub2api.git")
        (root / "state").mkdir()
        (root / "backend/cmd/server").mkdir(parents=True)
        (root / "FORK_VERSION").write_text("0.1.179\n", encoding="utf-8")
        (root / "backend/cmd/server/VERSION").write_text("0.1.179\n", encoding="utf-8")
        (root / "tracked.txt").write_text("base\n", encoding="utf-8")
        for path in set(sum(policy.values(), [])):
            target = root / path
            if path.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                (target / ".keep").write_text("fixture\n", encoding="utf-8")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("base\n", encoding="utf-8")
        manifest = {"protectedPathPolicy": policy}
        (root / "state/nova-customizations.json").write_text(
            json.dumps(manifest) + "\n", encoding="utf-8"
        )
        (root / "state/upstreams.json").write_text(
            json.dumps({"lastSuccessfulCommit": "pending"}) + "\n", encoding="utf-8"
        )
        self.old = commit(root, "fixture base")
        (root / "state/upstreams.json").write_text(
            json.dumps({"lastSuccessfulCommit": self.old}) + "\n", encoding="utf-8"
        )
        self.old = commit(root, "fixture baseline")
        # The state commit is the trusted Nova target, while the upstream old
        # commit remains the previous tree from which the patch is generated.
        self.state = json.loads((root / "state/upstreams.json").read_text(encoding="utf-8"))
        self.success_baseline = self.state["lastSuccessfulCommit"]

    def upstream_commit(self, path: str, value: str, message: str) -> str:
        git(self.root, "switch", "-c", "upstream-work")
        (self.root / path).write_text(value, encoding="utf-8")
        new = commit(self.root, message)
        git(self.root, "switch", "main")
        git(self.root, "branch", "-D", "upstream-work")
        return new

    def run(self, new: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(self.root),
                "--state",
                "state/upstreams.json",
                "--manifest",
                "state/nova-customizations.json",
                "--report",
                "artifacts/report.md",
                "--commit",
                new,
                *extra,
            ],
            cwd=self.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )


class SyncUpstreamFixtureTests(unittest.TestCase):
    def test_normal_update_applies_and_never_advances_success_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyncFixture(Path(directory), {"criticalPaths": [], "manualReviewPaths": [], "stopOnDeletePaths": []})
            new = fixture.upstream_commit("tracked.txt", "upstream\n", "upstream ordinary update")
            result = fixture.run(new, "--branch", "sync/fixture", "--commit-candidate")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((fixture.root / "tracked.txt").read_text(encoding="utf-8"), "upstream\n")
            self.assertEqual(json.loads((fixture.root / "state/upstreams.json").read_text(encoding="utf-8"))["lastSuccessfulCommit"], fixture.success_baseline)
            self.assertIn("eligible-after-required-checks", (fixture.root / "artifacts/report.md").read_text(encoding="utf-8"))

    def test_conflict_stops_before_branch_and_preserves_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyncFixture(Path(directory), {"criticalPaths": [], "manualReviewPaths": [], "stopOnDeletePaths": []})
            new = fixture.upstream_commit("tracked.txt", "upstream\n", "upstream conflict")
            (fixture.root / "tracked.txt").write_text("nova\n", encoding="utf-8")
            commit(fixture.root, "nova divergent change")
            result = fixture.run(new, "--branch", "sync/conflict")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("sync/conflict", git(fixture.root, "branch"))
            self.assertEqual(json.loads((fixture.root / "state/upstreams.json").read_text(encoding="utf-8"))["lastSuccessfulCommit"], fixture.success_baseline)
            report = (fixture.root / "artifacts/report.md").read_text(encoding="utf-8")
            self.assertIn("blocked", report)
            self.assertIn("真实三方冲突路径", report)
            self.assertIn("tracked.txt", report)

    def test_missing_index_path_is_reported_without_creating_a_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyncFixture(Path(directory), {"criticalPaths": [], "manualReviewPaths": [], "stopOnDeletePaths": []})
            git(fixture.root, "switch", "-c", "upstream-work", fixture.success_baseline)
            (fixture.root / "tracked.txt").write_text("upstream\n", encoding="utf-8")
            new = commit(fixture.root, "upstream changes historical file")
            git(fixture.root, "switch", "main")
            (fixture.root / "tracked.txt").unlink()
            commit(fixture.root, "nova removes historical file")
            git(fixture.root, "branch", "-D", "upstream-work")

            result = fixture.run(new, "--branch", "sync/missing-index")

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("sync/missing-index", git(fixture.root, "branch"))
            report = (fixture.root / "artifacts/report.md").read_text(encoding="utf-8")
            self.assertIn("缺失 index 路径", report)
            self.assertIn("tracked.txt", report)

    def test_no_apply_keeps_repository_clean_and_writes_report_to_temp_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyncFixture(Path(directory), {"criticalPaths": [], "manualReviewPaths": [], "stopOnDeletePaths": []})
            new = fixture.upstream_commit("tracked.txt", "upstream\n", "upstream ordinary update")

            result = fixture.run(new, "--no-apply")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((fixture.root / "tracked.txt").read_text(encoding="utf-8"), "base\n")
            self.assertFalse((fixture.root / "artifacts/report.md").exists())
            report_path = Path(json.loads(result.stdout)["reportPath"])
            self.assertTrue(report_path.is_file())
            with self.assertRaises(ValueError):
                report_path.relative_to(fixture.root)
            self.assertEqual(git(fixture.root, "status", "--porcelain"), "")

    def test_protected_change_preserves_nova_code_and_stays_mergeable(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = {"criticalPaths": ["critical.txt"], "manualReviewPaths": [], "stopOnDeletePaths": []}
            fixture = SyncFixture(Path(directory), policy)
            new = fixture.upstream_commit("critical.txt", "upstream\n", "upstream critical change")
            result = fixture.run(new, "--branch", "sync/critical")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((fixture.root / "critical.txt").read_text(encoding="utf-8"), "base\n")
            report = (fixture.root / "artifacts/report.md").read_text(encoding="utf-8")
            self.assertIn("critical.txt", report)
            self.assertIn("eligible-after-required-checks", report)
            self.assertIn("已保留 Nova 代码的保护路径", report)

    def test_protected_delete_preserves_nova_file_and_stays_mergeable(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = {"criticalPaths": [], "manualReviewPaths": [], "stopOnDeletePaths": ["stop.txt"]}
            fixture = SyncFixture(Path(directory), policy)
            git(fixture.root, "switch", "-c", "upstream-work")
            (fixture.root / "stop.txt").unlink()
            new = commit(fixture.root, "upstream deletes protected path")
            git(fixture.root, "switch", "main")
            git(fixture.root, "branch", "-D", "upstream-work")
            result = fixture.run(new, "--branch", "sync/delete")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("sync/delete", git(fixture.root, "branch"))
            self.assertTrue((fixture.root / "stop.txt").exists())


if __name__ == "__main__":
    unittest.main()
