"""Portable, hash-verified profiles for Avatar Legends package workspace edits."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath

import pak_probe
import workspace_history


def _assets_dir(profile_path: Path) -> Path:
    return profile_path.with_name(profile_path.stem + ".assets")


def create_profile(profile_path: Path, package: dict, workspace: Path, validation: dict) -> dict:
    if not validation["valid"]:
        raise ValueError("A área de trabalho precisa passar na validação antes de criar o perfil.")
    if profile_path.exists() or _assets_dir(profile_path).exists():
        raise FileExistsError("O perfil ou sua pasta .assets já existe; escolha outro nome.")
    manifest_path = workspace.parent / f"{Path(package['path']).stem}.export-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    originals = {row["path"]: row for row in manifest["entries"]}
    indexed = {row["path"]: row for row in package["entries"]}
    assets = _assets_dir(profile_path)
    assets.mkdir(parents=True)
    changes = []
    try:
        for index, relative in enumerate(sorted(validation["hashes"])):
            current = validation["hashes"][relative]
            original = originals[relative]
            if current["sha256"] == original["sha256"]:
                continue
            replacement_rel = f"assets/{index:04d}-replacement{PurePosixPath(relative).suffix}"
            backup_rel = f"assets/{index:04d}-original.bin"
            replacement = workspace.joinpath(*PurePosixPath(relative).parts)
            shutil.copy2(replacement, assets / replacement_rel)
            item = indexed[relative]
            digest = hashlib.sha256()
            with Path(package["path"]).open("rb") as source, (assets / backup_rel).open("xb") as target:
                source.seek(item["payload_offset"])
                remaining = item["payload_size"]
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError(f"Payload original truncado: {relative}")
                    target.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
            if digest.hexdigest() != original["sha256"]:
                raise ValueError(f"Hash do backup original não confere: {relative}")
            changes.append({
                "path": relative, "original_sha256": original["sha256"], "original_size": original["size"],
                "replacement_sha256": current["sha256"], "replacement_size": current["size"],
                "replacement_asset": replacement_rel, "backup_asset": backup_rel,
            })
        if not changes:
            raise ValueError("A área de trabalho não contém alterações para salvar.")
        profile = {
            "format": "avatar-legends-mod-profile", "version": 1,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source_package": Path(package["path"]).name, "source_sha256": package["sha256"],
            "entry_count": package["record_count"], "changes": changes,
        }
        with profile_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(profile, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        return profile
    except Exception:
        # Keep partial artifacts visible for recovery; never remove user data silently.
        raise


def load_profile(profile_path: Path) -> dict:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile.get("format") != "avatar-legends-mod-profile" or profile.get("version") != 1:
        raise ValueError("Formato ou versão de perfil não reconhecido.")
    changes = profile.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("O perfil não contém alterações.")
    base = _assets_dir(profile_path).resolve()
    seen = set()
    for change in changes:
        internal = change.get("path", "")
        logical = PurePosixPath(internal)
        if not internal or logical.is_absolute() or ".." in logical.parts or "\\" in internal or ":" in internal or internal in seen:
            raise ValueError(f"Caminho interno inválido ou duplicado: {internal!r}")
        seen.add(internal)
        for asset_key, hash_key, size_key in (("replacement_asset", "replacement_sha256", "replacement_size"), ("backup_asset", "original_sha256", "original_size")):
            asset_name = change.get(asset_key, "")
            rel = PurePosixPath(asset_name)
            if not asset_name or rel.is_absolute() or ".." in rel.parts or "\\" in asset_name or ":" in asset_name:
                raise ValueError(f"Caminho de asset inválido: {asset_name!r}")
            asset = base.joinpath(*rel.parts).resolve()
            try:
                asset.relative_to(base)
            except ValueError as exc:
                raise ValueError(f"Asset escapa da pasta do perfil: {asset_name}") from exc
            if not asset.is_file() or asset.stat().st_size != change.get(size_key) or pak_probe.sha256_file(asset) != change.get(hash_key):
                raise ValueError(f"Asset ausente ou hash/tamanho divergente: {asset_name}")
    return profile


def compare_profile(profile: dict, package: dict, workspace: Path) -> list[dict]:
    manifest = json.loads((workspace.parent / f"{Path(package['path']).stem}.export-manifest.json").read_text(encoding="utf-8"))
    current = {row["path"]: row["sha256"] for row in manifest["entries"]}
    available = {row["path"] for row in package["entries"]}
    result = []
    for change in profile["changes"]:
        path = change["path"]
        status = "ausente no pacote" if path not in available else ("base mudou" if current.get(path) != change["original_sha256"] else "base igual")
        result.append({"change": change, "status": status, "current_sha256": current.get(path)})
    return result


def reapply_profile(profile_path: Path, profile: dict, package: dict, workspace: Path, decoder: Path, run_tool) -> int:
    indexed = {row["path"] for row in package["entries"]}
    assets = _assets_dir(profile_path)
    replacements = []
    munged = []
    for change in profile["changes"]:
        relative = change["path"]
        if relative not in indexed:
            raise ValueError(f"Profile path is missing from the selected package: {relative}")
        asset = assets.joinpath(*PurePosixPath(change["replacement_asset"]).parts)
        replacements.append((relative, asset))
        if relative.lower().endswith(".munged"):
            munged.append((change, asset))
    if munged:
        import tempfile
        validation_root = workspace.parent / ".mod_engine_previews"
        validation_root.mkdir(exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix="profile_validate_", dir=validation_root))
        input_dir, output_dir = run_dir / "input", run_dir / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        names = set()
        for change, asset in munged:
            name = PurePosixPath(change["path"]).name
            if name.casefold() in names:
                raise ValueError("Duplicate MUNGED names in profile prevent batch validation.")
            names.add(name.casefold())
            shutil.copy2(asset, input_dir / name)
        run_tool([str(Path(__import__("sys").executable)), str(decoder), str(input_dir), str(output_dir)])
        decoded = {path.stem.casefold() for path in output_dir.rglob("*.png")}
        failed = [change["path"] for change, _asset in munged if PurePosixPath(change["path"]).stem.casefold() not in decoded]
        if failed:
            raise ValueError("Profile MUNGED frames failed to decode: " + ", ".join(failed[:8]))
    workspace_history.apply_changes(
        workspace, replacements, "Reapply mod profile", metadata={"profile": str(profile_path)}
    )
    return len(replacements)
