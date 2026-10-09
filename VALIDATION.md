# Extractor validation

Package: `G:\SteamLibrary\steamapps\common\Avatar Legends The Fighting Game\data_packages\sprites.pak`

Output: `exports/sprites` under the project directory (also retained in `%TEMP%` for this session).

- The exporter parsed 39 records and wrote 39 payloads plus `sprites.export-manifest.json` beside the output directory.
- Independently reread each indexed source range and compared its length and SHA-256 against both the extracted file and the manifest entry.
- Result: 39 entries checked, 0 mismatches.
- Independently hashed the original `.pak` and compared it with the manifest's source hash: matched.
- No original package bytes were modified.

## Same-size package writer

- Replaced `data/ai/aang.ai` with the exported 96-byte file itself, producing `builds/sprites-roundtrip.pak` and its manifest.
- Output `.pak` parsed successfully; its SHA-256 exactly matched the original `sprites.pak` (`a9d779a17a27240f8931dfa65fa79db51fb06954ad382cf4ea6b34f7033cf87b`).
- This confirms byte-for-byte preservation for a no-op replacement. It does not validate changed asset semantics or loading the candidate in the game.

This validates extraction for `sprites.pak`. The other 70 packages pass the structural offset/bounds/overlap scan, but the exporter has not been run against every package.

The same-size replacement command is implemented but has not yet been exercised. No candidate has been launched in the game.
