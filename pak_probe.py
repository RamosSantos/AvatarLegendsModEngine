#!/usr/bin/env python3
"""Read-only index lister and bounded extractor for Avatar Legends PACK files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

HEADER_SIZE = 12
RECORD_SIZE = 256
PATH_SIZE = 248
PAYLOAD_ALIGNMENT = 4096
COPY_CHUNK = 1024 * 1024


def read_exact(stream, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f"truncated input: wanted {size} bytes, received {len(data)}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(COPY_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def parse_package(path: Path) -> dict[str, object]:
    file_size = path.stat().st_size
    with path.open("rb") as stream:
        if file_size < HEADER_SIZE:
            raise ValueError("file is shorter than the observed PACK header")
        header = read_exact(stream, HEADER_SIZE)
        if header[:4] != b"PACK":
            raise ValueError(f"unexpected signature: {header[:4]!r}")

        index_offset = int.from_bytes(header[4:8], "little")
        index_size = int.from_bytes(header[8:12], "little")
        if index_offset < HEADER_SIZE or index_offset + index_size != file_size:
            raise ValueError("header index boundary does not match file size")
        if not index_size or index_size % RECORD_SIZE:
            raise ValueError("index size is not a nonzero multiple of 256")

        stream.seek(index_offset)
        entries = []
        ranges = []
        for number in range(index_size // RECORD_SIZE):
            record = read_exact(stream, RECORD_SIZE)
            terminator = record.find(b"\0", 0, PATH_SIZE)
            if terminator <= 0:
                raise ValueError(f"index record {number} has no nonempty NUL-terminated path")
            if any(record[terminator + 1:PATH_SIZE]):
                raise ValueError(f"index record {number} has nonzero path padding")
            try:
                name = record[:terminator].decode("ascii")
            except UnicodeDecodeError as exc:
                raise ValueError(f"index record {number} path is not ASCII") from exc

            logical = PurePosixPath(name)
            if (
                logical.is_absolute()
                or not logical.parts
                or ".." in logical.parts
                or "." in logical.parts
                or "\\" in name
                or ":" in name
            ):
                raise ValueError(f"unsafe package path in record {number}: {name!r}")

            payload_offset = int.from_bytes(record[PATH_SIZE:PATH_SIZE + 4], "little")
            payload_size = int.from_bytes(record[PATH_SIZE + 4:RECORD_SIZE], "little")
            payload_end = payload_offset + payload_size
            if payload_offset % PAYLOAD_ALIGNMENT:
                raise ValueError(f"record {number} payload offset is not 4096-byte aligned")
            if payload_offset < HEADER_SIZE or payload_end > index_offset:
                raise ValueError(f"record {number} payload lies outside the data region")
            entries.append({
                "record": number,
                "path": name,
                "payload_offset": payload_offset,
                "payload_size": payload_size,
            })
            if payload_size:
                ranges.append((payload_offset, payload_end, number))

        names = [entry["path"] for entry in entries]
        if len(set(names)) != len(names):
            raise ValueError("package contains duplicate indexed paths")

        ranges.sort()
        for previous, current in zip(ranges, ranges[1:]):
            if current[0] < previous[1]:
                raise ValueError(f"payload ranges overlap at records {previous[2]} and {current[2]}")

    return {
        "path": str(path.resolve()),
        "size": file_size,
        "sha256": sha256_file(path),
        "index_offset": index_offset,
        "index_size": index_size,
        "record_count": len(entries),
        "entries": entries,
    }


def ensure_output_outside_game(package: Path, output: Path) -> Path:
    output_path = output.resolve()
    if package.parent.name.casefold() == "data_packages":
        game_root = package.parent.parent.resolve()
        try:
            output_path.relative_to(game_root)
        except ValueError:
            pass
        else:
            raise ValueError("choose an extraction directory outside the installed game folder")
    return output_path


def extract_package(package: dict[str, object], output: Path) -> Path:
    source = Path(package["path"])
    output_root = ensure_output_outside_game(source, output)
    package_dir = output_root / source.stem
    manifest_path = output_root / f"{source.stem}.export-manifest.json"
    if package_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing export: {package_dir}")
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite existing manifest: {manifest_path}")

    package_dir.mkdir(parents=True)
    manifest_entries = []
    try:
        with source.open("rb") as stream:
            for entry in package["entries"]:
                parts = PurePosixPath(entry["path"]).parts
                target = package_dir.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                resolved_target = target.resolve()
                try:
                    resolved_target.relative_to(package_dir.resolve())
                except ValueError as exc:
                    raise ValueError(f"output path escaped export directory: {entry['path']}") from exc

                stream.seek(entry["payload_offset"])
                remaining = entry["payload_size"]
                digest = hashlib.sha256()
                with target.open("xb") as destination:
                    while remaining:
                        chunk = read_exact(stream, min(COPY_CHUNK, remaining))
                        destination.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                manifest_entries.append({**entry, "sha256": digest.hexdigest()})

        manifest = {
            "source_package": str(source),
            "source_sha256": package["sha256"],
            "index_offset": package["index_offset"],
            "index_size": package["index_size"],
            "entries": manifest_entries,
        }
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except Exception:
        # Leave partial exports visible for recovery rather than deleting user data.
        raise
    return package_dir


def replace_same_size(
    package: dict[str, object], internal_path: str, replacement: Path, output: Path
) -> dict[str, object]:
    source = Path(package["path"])
    output_path = ensure_output_outside_game(source, output)
    if output_path.suffix.casefold() != ".pak":
        raise ValueError("replacement output must use a .pak extension")
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing package: {output_path}")
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite existing manifest: {manifest_path}")
    if not replacement.is_file():
        raise ValueError(f"replacement is not a file: {replacement}")

    matches = [entry for entry in package["entries"] if entry["path"] == internal_path]
    if len(matches) != 1:
        raise ValueError(f"indexed path must match exactly one entry: {internal_path}")
    entry = matches[0]
    replacement_size = replacement.stat().st_size
    if replacement_size != entry["payload_size"]:
        raise ValueError(
            f"replacement size {replacement_size} differs from indexed size {entry['payload_size']}; "
            "only same-size replacement is supported"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    replacement_hash = hashlib.sha256()
    with source.open("rb") as original, replacement.open("rb") as new_asset, output_path.open("xb") as target:
        remaining = entry["payload_offset"]
        while remaining:
            chunk = read_exact(original, min(COPY_CHUNK, remaining))
            target.write(chunk)
            remaining -= len(chunk)

        remaining = entry["payload_size"]
        while remaining:
            chunk = read_exact(new_asset, min(COPY_CHUNK, remaining))
            target.write(chunk)
            replacement_hash.update(chunk)
            remaining -= len(chunk)

        original.seek(entry["payload_offset"] + entry["payload_size"])
        while chunk := original.read(COPY_CHUNK):
            target.write(chunk)

    rebuilt = parse_package(output_path)
    manifest = {
        "source_package": str(source),
        "source_sha256": package["sha256"],
        "output_package": str(output_path),
        "output_sha256": rebuilt["sha256"],
        "replacement_path": internal_path,
        "payload_offset": entry["payload_offset"],
        "payload_size": entry["payload_size"],
        "replacement_source": str(replacement.resolve()),
        "replacement_sha256": replacement_hash.hexdigest(),
    }
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="+", type=Path, help="One or more local .pak files")
    parser.add_argument("--list", action="store_true", help="include every indexed path and payload range")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--extract", type=Path, metavar="DIR", help="export package contents under DIR")
    action.add_argument("--replace", nargs=2, metavar=("INTERNAL_PATH", "FILE"), help="replace one same-size asset")
    parser.add_argument("--output", type=Path, help="new .pak path for --replace; must be outside the game folder")
    args = parser.parse_args()

    if args.replace and len(args.packages) != 1:
        parser.error("--replace accepts exactly one source package")
    if args.replace and args.output is None:
        parser.error("--replace requires --output")
    if args.output is not None and not args.replace:
        parser.error("--output can only be used with --replace")

    reports = []
    try:
        for package_path in args.packages:
            if not package_path.is_file():
                raise ValueError(f"not a file: {package_path}")
            package = parse_package(package_path)
            if args.replace:
                package["replacement"] = replace_same_size(
                    package, args.replace[0], Path(args.replace[1]), args.output
                )
            elif args.extract is not None:
                package["export_directory"] = str(extract_package(package, args.extract))
            if not args.list:
                package.pop("entries")
            reports.append(package)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(reports, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
