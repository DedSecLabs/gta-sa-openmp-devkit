# Engine layer: source reconstructions and executable bytes

Use this when the behavior lives in the game's code: physics, camera, HUD and radar drawing, AI, streaming,
garage and pickup logic, or the engine side of a script command.

## Sources, weakest assumptions first

- **gta-reversed** reconstructs the engine in C++. Pin a commit and cite file and line. It targets one
  specific executable; read its README for which. Treat what you read as `source-derived` until checked
  against bytes or the running game. Functions that still call the original code (hooks registered as not
  reversed) contain **no recovered logic**: the name tells you a routine exists, not what it does. Comments
  flagging doubt mark unreliable entries.
- **Plugin-SDK** gives structures and addresses per game version. Its tables distinguish several 1.0
  executables and later releases; confirm the build it describes is the one you identified.
- **The executable itself** is the only source that is certainly your build.
- **A live probe** by a person in game: record date, build and what was seen.

Search a pinned checkout with `git -C <path> grep -n <symbol>` rather than opening whole files.

## Rules for executable bytes

1. **Identify the build first**: `python <skill>/scripts/identify_build.py <exe>` gives SHA-256, size, image base and
   `SizeOfImage`. A hash match with a recorded build makes its label usable at that entry's confidence.
2. **Name the address kind every time.** Virtual address (VA), relative virtual address (RVA = VA minus image
   base) and file offset are three different numbers; `module+X` means RVA. Mixing them is the commonest way
   to patch the wrong place.
3. **Disk and memory differ.** A running process may already be patched by a multiplayer client, ASI
   plugins or compatibility patches. Bytes read from memory are not "original" until compared with the file.
4. **A signature proves a spot, not a function.** Record bytes hashed, length, address and whether the
   pattern is unique. A match shows layout compatibility there and nothing about surrounding code.

   ```
   python <skill>/scripts/identify_build.py <exe> --probe 0x<VA> --probe-length 16
   ```

5. **Confidence falls in steps**: bytes are certain; the instruction decode is high confidence; the
   function's identity is inferred unless a symbol, pinned source or trace supports it; its behavior is a
   hypothesis unless traced. State the disassembler, architecture and base address used.
6. **A fragment is not the routine.** List what was not examined, and do not describe a state machine from
   a slice.
7. **Addresses do not travel.** A value from gta-reversed, Plugin-SDK or a forum applies to the build it was
   taken from. Re-confirm against bytes before using it on yours.

Record slice facts (executable hash, VA or RVA, length, hash of the bytes, a decode summary). Do not paste
the bytes or a disassembly listing into project documents.

## No disassembler available

The probe above still hashes a byte range, which is enough to compare two executables at one address. It is
not enough for any claim about what code does; say that the code was not read.

## Private build records

The shipped `assets/known-builds.json` has an empty `builds` list. The tool can still hash and inspect an
executable, but it will report its identity as unknown until it matches a record you supply. Do not infer a
version from a directory name or populate a public table from somebody else's private installation.

Create a private JSON file outside the installed skill, using this structure with your own recorded values:

```json
{
  "schemaVersion": 1,
  "builds": [{
    "id": "my-reference",
    "label": "My documented build label",
    "labelConfidence": "documented-only",
    "exe": {"sha256": "REPLACE_WITH_THE_64_HEX_DIGIT_FILE_HASH", "size": 0},
    "evidence": "Replace with the origin of the label and the checks actually performed."
  }]
}
```

Replace the hash and size with the tool's measured values; the example is not an identified GTA build.
Pass the file explicitly:

```
python <skill>/scripts/identify_build.py <exe> --known-builds <private-table.json>
```

Matching that hash means byte identity with the recorded file. It does not upgrade the label's confidence
or establish that an installation is pristine. Keep `documented-only` until corroborating evidence or an
authoritative reference actually supports a stronger label. Do not commit the private table by default.
