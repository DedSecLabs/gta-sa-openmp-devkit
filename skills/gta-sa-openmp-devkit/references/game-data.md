# Data layer: reading the original files

Use this when the claim is a value stored in the installation: map records, object definitions, handling,
prices, colours, text.

## Procedure

1. Identify the build (`identify_build.py`) and, once per installation, record what it contains:

   ```
   python <skill>/scripts/export_manifest.py --game-dir <installDir> --output <outside>/manifest.json [--reference earlier.json]
   ```

   The manifest holds sizes and SHA-256 per file and per group. `--reference` compares with hashes recorded
   earlier; `matches-recorded` means consistent with that earlier export, not pristine.
2. Read the file in place, read-only. Quote the installation-relative path, line and the file's SHA-256 in
   the finding (`file` source, class `original-observed`).
3. Take only the facts you need. Do not copy whole data files into the project.

## Entrances and garages

```
python <skill>/scripts/export_ipl_records.py --game-dir <installDir> --section enex --output <outside>/enex.json
python <skill>/scripts/export_ipl_records.py --game-dir <installDir> --section grge --output <outside>/grge.json
```

Read the output's `coverage` and `complete` before using it:

- Only text IPLs under `data/maps` are read. Binary IPLs and IPLs streamed from archives are skipped, so a
  missing record is not proof that it does not exist.
- An ENEX row is a raw portal volume plus a destination. It is **not** a safe place to stand or spawn. A
  port needs a separately checked arrival position (collision loaded, correct interior, not inside
  geometry); that check is the project's own work and usually needs someone in game.
- `areaCode` is an interior number, not a region. Names link portal pairs.
- A GRGE `type` is the value in the file. Scripts can change a garage at runtime, and a type name does not
  tell you what the engine does with it: that is an `scm` or `engine` question.

## What data cannot tell you

A value in a file shows what is stored, not how it is used. "The file lists X" is `original-observed`; "so
the game does Y with it" needs a script or engine source of its own. Modded installations change data files
freely, which is why the hash goes into every finding.
