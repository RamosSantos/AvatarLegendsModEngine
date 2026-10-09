"""Hash-checked undo/redo history for staged package workspace changes."""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath

import pak_probe


HISTORY_FILE = ".mod_engine_history.json"
HISTORY_DIR = ".mod_engine_history"
CHANGES_FILE = ".mod_engine_changes.json"


def _atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    temporary.replace(path)


def _read_history(workspace: Path) -> dict:
    path = workspace.parent / HISTORY_FILE
    if not path.is_file():
        return {"version": 1, "undo": [], "redo": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("undo"), list) or not isinstance(data.get("redo"), list):
        raise ValueError(f"Unsupported or damaged workspace history: {path}")
    return data


def state(workspace: Path) -> dict:
    history = _read_history(workspace)
    return {
        "can_undo": bool(history["undo"]),
        "can_redo": bool(history["redo"]),
        "undo_label": history["undo"][-1]["description"] if history["undo"] else "",
        "redo_label": history["redo"][-1]["description"] if history["redo"] else "",
    }


def _internal_path(workspace: Path, relative: str) -> Path:
    logical = PurePosixPath(relative)
    if not relative or logical.is_absolute() or ".." in logical.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Unsafe workspace path in history operation: {relative!r}")
    result = workspace.joinpath(*logical.parts).resolve()
    try:
        result.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"Workspace path escapes its root: {relative}") from exc
    return result


def _changes_for_current_files(workspace: Path, operation: dict, backup_paths: dict[str, Path], sources: dict[str, Path]) -> dict:
    changes_path = workspace.parent / CHANGES_FILE
    doc = json.loads(changes_path.read_text(encoding="utf-8")) if changes_path.is_file() else {"changes": []}
    prior = {item["path"]: item for item in doc.get("changes", [])}
    manifest_path = next(workspace.parent.glob("*.export-manifest.json"), None)
    if manifest_path is None:
        raise FileNotFoundError(f"Workspace export manifest missing beside {workspace}")
    exported = json.loads(manifest_path.read_text(encoding="utf-8"))
    original = {item["path"]: item for item in exported["entries"]}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    normal_backup_dir = workspace.parent / ".mod_engine_backups"
    normal_backup_dir.mkdir(exist_ok=True)

    for item in operation["files"]:
        relative = item["path"]
        current = _internal_path(workspace, relative)
        base = original.get(relative)
        if base is None:
            raise ValueError(f"Workspace history path is not in the export manifest: {relative}")
        digest = pak_probe.sha256_file(current)
        existing = prior.get(relative)
        if digest == base["sha256"]:
            prior.pop(relative, None)
            continue
        if existing is None:
            backup = backup_paths.get(relative)
            if backup is None:
                backup = normal_backup_dir / f"history_{stamp}_{len(prior):04d}.bak"
                snapshot = workspace.parent / HISTORY_DIR / item["before_asset"]
                shutil.copy2(snapshot, backup)
            existing = {
                "path": relative,
                "original_sha256": base["sha256"],
                "replacement_source": str(sources.get(relative, "workspace history")),
                "backup": str(backup),
                "updated_at": stamp,
            }
            prior[relative] = existing
        if relative in backup_paths:
            existing["backup"] = str(backup_paths[relative])
        if relative in sources:
            existing["replacement_source"] = str(sources[relative])
        if operation.get("profile"):
            existing["profile"] = operation["profile"]
        existing["staged_sha256"] = digest
        existing["updated_at"] = stamp
    doc["changes"] = list(prior.values())
    return doc


def apply_changes(
    workspace: Path,
    replacements: list[tuple[str, Path]],
    description: str,
    backups: dict[str, Path] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Apply one user action, storing before/after payloads as a single history step."""
    if not replacements:
        raise ValueError("No files were provided for this workspace operation.")
    backup_paths = backups or {}
    names = [relative for relative, _source in replacements]
    if len(set(names)) != len(names):
        raise ValueError("A workspace history operation cannot contain duplicate paths.")
    history_path = workspace.parent / HISTORY_FILE
    history_dir = workspace.parent / HISTORY_DIR
    history_dir.mkdir(exist_ok=True)
    history = _read_history(workspace)
    operation_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid.uuid4().hex[:8]}"
    operation_dir = history_dir / operation_id
    operation_dir.mkdir()
    files = []
    rollback_paths = []
    for index, (relative, source) in enumerate(replacements):
        destination = _internal_path(workspace, relative)
        if not destination.is_file() or not source.is_file():
            raise FileNotFoundError(f"Workspace destination or replacement asset is missing: {relative}")
        if source.resolve() == destination.resolve():
            raise ValueError(f"Replacement already is the workspace file: {relative}")
        before_rel = f"{operation_id}/{index:04d}_before.bin"
        after_rel = f"{operation_id}/{index:04d}_after.bin"
        before_asset = history_dir / before_rel
        shutil.copy2(destination, before_asset)
        files.append({
            "path": relative, "before_asset": before_rel, "after_asset": after_rel,
            "before_sha256": pak_probe.sha256_file(before_asset),
        })
        rollback_paths.append((destination, before_asset))

    changes_path = workspace.parent / CHANGES_FILE
    old_changes = changes_path.read_bytes() if changes_path.is_file() else None
    applied = []
    try:
        for (relative, source), (destination, _before) in zip(replacements, rollback_paths):
            shutil.copy2(source, destination)
            applied.append(destination)
        for item, (destination, _before) in zip(files, rollback_paths):
            after_asset = history_dir / item["after_asset"]
            shutil.copy2(destination, after_asset)
            item["after_sha256"] = pak_probe.sha256_file(after_asset)
        operation = {
            "id": operation_id, "description": description,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "files": files,
            **(metadata or {}),
        }
        new_changes = _changes_for_current_files(
            workspace, operation, backup_paths,
            {relative: source for relative, source in replacements},
        )
        _atomic_json(changes_path, new_changes)
        history["undo"].append(operation)
        history["redo"].clear()
        _atomic_json(history_path, history)
        return operation
    except Exception:
        for destination, before_asset in reversed(rollback_paths):
            if destination in applied:
                shutil.copy2(before_asset, destination)
        if old_changes is None:
            changes_path.unlink(missing_ok=True)
        else:
            changes_path.write_bytes(old_changes)
        raise


def _move(workspace: Path, direction: str) -> dict:
    history = _read_history(workspace)
    source_stack = "undo" if direction == "undo" else "redo"
    target_stack = "redo" if direction == "undo" else "undo"
    if not history[source_stack]:
        raise ValueError(f"Nothing to {direction} in this workspace.")
    operation = history[source_stack][-1]
    expected_key, target_key = ("after", "before") if direction == "undo" else ("before", "after")
    history_dir = workspace.parent / HISTORY_DIR
    rollback_assets = []
    targets = []
    for item in operation["files"]:
        destination = _internal_path(workspace, item["path"])
        expected = history_dir / item[f"{expected_key}_asset"]
        target = history_dir / item[f"{target_key}_asset"]
        if not destination.is_file() or pak_probe.sha256_file(destination) != item[f"{expected_key}_sha256"]:
            raise ValueError(
                f"Cannot {direction}: {item['path']} changed outside the history. "
                "Review the workspace before continuing."
            )
        if not target.is_file() or pak_probe.sha256_file(target) != item[f"{target_key}_sha256"]:
            raise ValueError(f"History snapshot is missing or damaged for {item['path']}.")
        rollback_assets.append((destination, expected))
        targets.append(target)

    changes_path = workspace.parent / CHANGES_FILE
    old_changes = changes_path.read_bytes() if changes_path.is_file() else None
    applied = []
    try:
        for (destination, _expected), target in zip(rollback_assets, targets):
            shutil.copy2(target, destination)
            applied.append(destination)
        changes_doc = _changes_for_current_files(workspace, operation, {}, {})
        _atomic_json(changes_path, changes_doc)
        history[source_stack].pop()
        history[target_stack].append(operation)
        _atomic_json(workspace.parent / HISTORY_FILE, history)
    except Exception:
        for destination, expected in reversed(rollback_assets):
            if destination in applied:
                shutil.copy2(expected, destination)
        if old_changes is None:
            changes_path.unlink(missing_ok=True)
        else:
            changes_path.write_bytes(old_changes)
        raise
    return {"description": operation["description"], "count": len(operation["files"]), "direction": direction}


def undo(workspace: Path) -> dict:
    return _move(workspace, "undo")


def redo(workspace: Path) -> dict:
    return _move(workspace, "redo")
