import tempfile
from pathlib import Path
import unittest

from repair import RepairError, read_manifest, run, sha256, transform


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.target = self.directory / "browser-service-core.mjs"
        self.backups = self.directory / "backups"
        self.manifest = read_manifest()
        self.original = ("prefix;" + self.manifest["patch"]["before"] + ";suffix").encode()
        self.patched = self.original.replace(self.manifest["patch"]["before"].encode(), self.manifest["patch"]["after"].encode())
        self.manifest = {**self.manifest, "original_sha256": sha256(self.original), "patched_sha256": sha256(self.patched)}
        self.target.write_bytes(self.original)

    def invoke(self, action, **kwargs):
        return run(action, self.target, self.manifest, self.backups, **kwargs)

    def test_apply_restore_round_trip_and_backups(self):
        self.assertTrue(self.invoke("apply")["changed"])
        self.assertEqual(self.target.read_bytes(), self.patched)
        self.assertTrue(self.invoke("restore")["changed"])
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(len(list(self.backups.glob("*.backup.mjs"))), 2)

    def test_default_status_does_not_write(self):
        self.assertEqual(self.invoke("status")["state"], "original")
        self.assertFalse(self.backups.exists())

    def test_apply_is_idempotent(self):
        self.invoke("apply")
        self.assertFalse(self.invoke("apply")["changed"])

    def test_restore_already_original_is_idempotent(self):
        self.assertFalse(self.invoke("restore")["changed"])
        self.assertFalse(self.backups.exists())

    def test_restore_can_reconstruct_original_without_old_backup(self):
        self.target.write_bytes(self.patched)
        self.invoke("restore")
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_unknown_version_is_not_modified(self):
        unknown = self.original + b"updated by vendor"
        self.target.write_bytes(unknown)
        with self.assertRaises(RepairError):
            self.invoke("apply")
        with self.assertRaises(RepairError):
            self.invoke("restore")
        self.assertEqual(self.target.read_bytes(), unknown)
        self.assertFalse(self.backups.exists())

    def test_dry_run_creates_no_backup_and_changes_no_file(self):
        result = self.invoke("apply", dry_run=True)
        self.assertEqual(result["next_state"], "patched")
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse(self.backups.exists())

    def test_wrong_candidate_checksum_is_rejected(self):
        self.manifest["patched_sha256"] = "0" * 64
        with self.assertRaises(RepairError):
            self.invoke("apply")
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse(self.backups.exists())

    def test_ambiguous_source_match_is_rejected(self):
        with self.assertRaises(RepairError):
            transform(self.original + self.original, self.manifest)

    def test_existing_corrupted_backup_is_not_overwritten(self):
        self.backups.mkdir()
        backup = self.backups / f"browser-service-core.{sha256(self.original)}.backup.mjs"
        backup.write_bytes(b"not the original")
        with self.assertRaises(RepairError):
            self.invoke("apply")
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(backup.read_bytes(), b"not the original")


if __name__ == "__main__":
    unittest.main(verbosity=2)
