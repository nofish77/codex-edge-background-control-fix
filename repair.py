"""Version-locked, reversible local repair. This does not control a browser."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

ROOT = Path(__file__).resolve().parent


class RepairError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(path: Path = ROOT / "manifest.json") -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise RepairError("Unsupported manifest schema.")
    return manifest


def inspect(target: Path, manifest: dict) -> tuple[Path, bytes, str]:
    target = target.resolve(strict=True)
    if not target.is_file() or target.name != manifest["target_file"]:
        raise RepairError("Choose the explicitly named component file; no path is guessed.")
    data = target.read_bytes()
    digest = sha256(data)
    state = {manifest["original_sha256"]: "original", manifest["patched_sha256"]: "patched"}.get(digest, "unknown")
    return target, data, state


def transform(data: bytes, manifest: dict, reverse: bool = False) -> bytes:
    patch = manifest["patch"]
    before = patch["after" if reverse else "before"].encode("utf-8")
    after = patch["before" if reverse else "after"].encode("utf-8")
    if data.count(before) != 1:
        raise RepairError("Expected exactly one source match. No file was changed.")
    candidate = data.replace(before, after, 1)
    expected = manifest["original_sha256" if reverse else "patched_sha256"]
    if sha256(candidate) != expected:
        raise RepairError("Candidate checksum mismatch. No file was changed.")
    return candidate


def backup_once(directory: Path, data: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"browser-service-core.{sha256(data)}.backup.mjs"
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise RepairError("An existing backup has unexpected contents. Refusing to overwrite it.")
    return path


def replace_checked(target: Path, previous: bytes, replacement: bytes) -> None:
    """Write next to the target, then replace only the version that was inspected."""
    mode = stat.S_IMODE(target.stat().st_mode)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".repair-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        if target.read_bytes() != previous:
            raise RepairError("Component changed during preparation. Refusing to overwrite it.")
        os.replace(temporary, target)
        temporary = None
        if target.read_bytes() != replacement:
            raise RepairError("Post-write verification failed. Keep the backup for recovery.")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run(action: str, target: Path, manifest: dict, backup_directory: Path, dry_run: bool = False) -> dict:
    target, data, state = inspect(target, manifest)
    result = {"action": action, "state": state, "sha256": sha256(data), "changed": False}
    if action == "status":
        return result
    if state == "unknown":
        raise RepairError("Unrecognized component version. Refusing to patch or restore it.")
    desired = "patched" if action == "apply" else "original"
    if action not in {"apply", "restore"}:
        raise RepairError("Unknown action.")
    if state == desired:
        result["message"] = "Already in the requested state."
        return result
    replacement = transform(data, manifest, reverse=action == "restore")
    result.update(next_state=desired, next_sha256=sha256(replacement), dry_run=dry_run)
    if dry_run:
        return result
    # The reverse edit is checksum verified, so restore also works after a fresh
    # clone without distributing or requiring a copy of the vendor's bundle.
    backup = backup_once(backup_directory.resolve(), data)
    replace_checked(target, data, replacement)
    result.update(state=desired, sha256=sha256(replacement), changed=True, backup=str(backup))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "apply", "restore"])
    parser.add_argument("--target", required=True, type=Path, help="Exact installed browser-service-core.mjs path")
    parser.add_argument("--backup-dir", type=Path, default=ROOT / ".local" / "backups")
    parser.add_argument("--dry-run", action="store_true", help="Verify the proposed edit without writing anything")
    options = parser.parse_args()
    try:
        result = run(options.action, options.target, read_manifest(), options.backup_dir, options.dry_run)
    except (OSError, ValueError, RepairError) as error:
        parser.exit(1, f"Repair refused: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
