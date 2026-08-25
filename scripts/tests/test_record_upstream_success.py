import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "record_upstream_success.py"
spec = importlib.util.spec_from_file_location("record_upstream_success", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


OLD = "a" * 40
NEW = "b" * 40
NOVA = "c" * 40


def state():
    return {
        "lastSuccessfulCommit": OLD,
        "lastSuccessfulVersion": "0.1.178",
        "syncStatus": "success",
    }


def report():
    return {
        "oldUpstreamCommit": OLD,
        "newUpstreamCommit": NEW,
        "newVersion": "0.1.179",
        "applyStatus": "ready",
        "conflicts": [],
        "stopOnDeletePaths": [],
    }


class RecordUpstreamSuccessTests(unittest.TestCase):
    def test_update_state_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upstreams.json"
            path.write_text(json.dumps(state()) + "\n", encoding="utf-8")
            module.update_state(path, report(), NOVA, "2026-08-22T12:00:00Z")
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(value["lastSuccessfulCommit"], NEW)
            self.assertEqual(value["novaVersion"], "0.1.179-nova")
            self.assertEqual(value["lastSyncCommit"], NOVA)

    def test_rejects_old_baseline_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upstreams.json"
            path.write_text(json.dumps(state()) + "\n", encoding="utf-8")
            invalid = report()
            invalid["oldUpstreamCommit"] = "d" * 40
            with self.assertRaises(module.BaselineError):
                module.update_state(path, invalid, NOVA, "")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), state())

    def test_rejects_conflicts_but_allows_preserved_protected_deletes(self):
        for field in ("conflicts",):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "upstreams.json"
                path.write_text(json.dumps(state()) + "\n", encoding="utf-8")
                invalid = report()
                invalid[field] = ["blocked/path"]
                with self.assertRaises(module.BaselineError):
                    module.update_state(path, invalid, NOVA, "")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upstreams.json"
            path.write_text(json.dumps(state()) + "\n", encoding="utf-8")
            preserved = report()
            preserved["stopOnDeletePaths"] = ["protected/path"]
            module.update_state(path, preserved, NOVA, "")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["lastSuccessfulCommit"], NEW)

    def test_atomic_write_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upstreams.json"
            original = json.dumps(state(), indent=2) + "\n"
            path.write_text(original, encoding="utf-8")
            with mock.patch.object(module.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(module.BaselineError):
                    module.atomic_write_json(path, {"changed": True})
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
