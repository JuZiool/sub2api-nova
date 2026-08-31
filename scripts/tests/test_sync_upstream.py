import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "sync_upstream.py"
spec = importlib.util.spec_from_file_location("sync_upstream", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


OLD = "a" * 40
NEW = "b" * 40
TARGET = "c" * 40


class SyncUpstreamTests(unittest.TestCase):
    def test_path_matches_files_and_directories(self):
        self.assertTrue(module.path_matches("frontend/src/components/Button.vue", ["frontend/src/components"]))
        self.assertTrue(module.path_matches("deploy", ["deploy"]))
        self.assertFalse(module.path_matches("backend/internal/service/foo.go", ["frontend/src/components"]))

    def test_rejects_non_ancestor_upstream_commits(self):
        config = mock.Mock(root=Path.cwd())
        completed = mock.Mock(returncode=1, stderr=b"", stdout=b"")
        with mock.patch.object(module.subprocess, "run", return_value=completed):
            self.assertFalse(module.is_upstream_ancestor(config, OLD, NEW))

    def test_classifies_preflight_diagnostics(self):
        result = module.parse_preflight_diagnostics(
            "\n".join(
                (
                    "Applied patch to 'conflict.go' with conflicts.",
                    "error: missing.go: does not exist in index",
                    "error: mismatch.go: does not match index",
                    "error: patch failed: failed.go:42",
                    "error: unapplied.go: patch does not apply",
                    "error: unknown git apply failure",
                )
            )
        )

        self.assertTrue(result.blocked)
        self.assertEqual(result.conflicts, ["conflict.go"])
        self.assertEqual(result.missing_index_paths, ["missing.go"])
        self.assertEqual(result.index_mismatch_paths, ["mismatch.go"])
        self.assertEqual(result.unapplied_paths, ["failed.go", "unapplied.go"])
        self.assertEqual(result.diagnostics, ["error: unknown git apply failure"])

    def test_success_path_passes_one_patch_to_apply_and_provenance(self):
        policy = {
            "criticalPaths": [],
            "manualReviewPaths": [],
            "stopOnDeletePaths": [],
        }
        state = {"lastSuccessfulCommit": OLD}
        manifest = {"protectedPathPolicy": policy}
        patch = b"binary patch"

        def resolve(_config, ref):
            if ref == "HEAD" or ref == "main":
                return TARGET
            if ref in {OLD, NEW}:
                return ref
            if ref == "upstream/main":
                return NEW
            raise AssertionError(f"unexpected ref: {ref}")

        def run_git(_config, *args, **_kwargs):
            if args[:2] == ("remote", "get-url"):
                return "https://github.com/Wei-Shaw/sub2api.git"
            return ""

        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.md"
            with (
                mock.patch.object(module, "load_json", side_effect=[state, manifest]),
                mock.patch.object(module, "ensure_clean"),
                mock.patch.object(module, "ensure_paths_exist"),
                mock.patch.object(module, "resolve_commit", side_effect=resolve),
                mock.patch.object(module, "run_git", side_effect=run_git),
                mock.patch.object(module, "is_upstream_ancestor", return_value=True),
                mock.patch.object(module, "changed_paths", return_value=[]),
                mock.patch.object(module, "deleted_paths", return_value=[]),
                mock.patch.object(module, "patch_bytes", return_value=patch),
                mock.patch.object(
                    module,
                    "preflight_three_way",
                    return_value=module.PreflightResult(False, [], [], [], [], []),
                ),
                mock.patch.object(module, "apply_three_way") as apply,
                mock.patch.object(module, "version_at", side_effect=["0.1.178", "0.1.179", "0.1.179"]),
                mock.patch.object(module, "diff_stat", return_value=[]),
                mock.patch.object(module, "update_nova_versions", return_value=[]),
                mock.patch.object(module, "write_provenance", return_value=".nova-upstream-provenance.json") as provenance,
                mock.patch.object(module, "write_report"),
            ):
                result = module.main(
                    [
                        "--root",
                        directory,
                        "--state",
                        "state.json",
                        "--manifest",
                        "manifest.json",
                        "--report",
                        str(report_path),
                        "--branch",
                        "sync/test",
                    ]
                )

        self.assertEqual(result, 0)
        apply.assert_called_once_with(mock.ANY, patch)
        self.assertEqual(provenance.call_args.args[2], patch)


if __name__ == "__main__":
    unittest.main()
