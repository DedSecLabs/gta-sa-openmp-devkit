# SCM layer: mission and world scripts

Use this for anything driven by the game's scripts: missions, shops, timed events, scripted pickups,
garage type changes, cutscene triggers.

`main.scm` and `script.img` are original-game content. Work on **private copies** in the profile's
`tools.privateWorkspace`, never in the installation and never in a Git working tree. Re-hash the copies and
compare with the hashes recorded for the installation before trusting them.

## Choose where to run Sanny Builder

Sanny Builder is an important **optional dependency for decompilation**, not a prerequisite for the whole
skill. Hashing, data exports, declaration checks and research from existing evidence work without it.
For a new claim about script control flow, a verified decompile may be necessary; a byte scan is not a substitute.

Before execution, establish which machine holds the installation and Sanny Builder, where Python runs,
and which access the user has already authorized. `capabilities.py` reports only the local machine.
A path such as a Windows drive path neither connects the agent to that machine nor grants permission.

1. **Local Windows:** run the command below with Python and Sanny Builder installed on that machine.
   Keep `main.scm` and `script.img` together in the private workspace, with hashes matched to the chosen
   installation. Sanny reads additional definitions from the installation; the two scripts alone do not
   establish that every dependency is available. GTA does not need to be running.
2. **Authorized remote Windows:** reuse an existing connection and the project's execution procedure.
   Transfer the wrapper and its `_common.py` dependency as files, verify transfer hashes, and execute on
   Windows using Windows paths. Do not install SSH, change firewall rules or assume credentials. Keep
   script copies and decompiled text there; return the metadata and narrowly extracted findings.
3. **User-run Windows handoff:** if no remote connection exists, give the user the command below with
   their paths, the required Python/Sanny versions and a distinct output filename. Ask them to return the
   wrapper's JSON result, Sanny version/edit mode and hashes of both input scripts. For a particular
   research question, provide a focused local query that returns facts rather than asking for the whole
   decompile. Record that the user ran it and what the agent could and could not verify.

The tested route is **Windows, Sanny Builder 4.2.0, `sa_sbl`**. Linux/Wine usage has been
[reported in Sanny's project discussion](https://github.com/sannybuilder/dev/discussions/217), but this
wrapper has not been validated under Wine or macOS compatibility layers. Do not advertise support or
install a compatibility layer automatically. Other Sanny versions and modes also need their own validation.

## Decompile command (executed on Windows)

Replace the placeholders and quote paths containing spaces. Close Sanny Builder before running the wrapper;
do not run two wrappers against the same Sanny folder at once, because they share `settings.ini`.

```
python <skill>/scripts/sanny_decompile.py --sanny-dir <sannyDir> --game-dir <installDir> --scm <workspace>/main.scm --output <workspace>/main.txt --expected-sha256 <hash>
```

The wrapper sets the game path Sanny Builder needs for the run and restores its `settings.ini` afterwards,
enforces a timeout, and verifies the input is unchanged. Record the Sanny Builder version and edit mode used:
opcode and enum names come from its library and can differ between versions and from gta-reversed, so prefer
numeric values where a name is ambiguous. Labels in the output carry script-relative offsets.

Different readable names can denote the same number. For example, a comparison of two 4.2.0 `sa_sbl`
outputs found only seat/wheel alias substitutions, with equal numeric values in the pinned enum file.
Compare values against that run's definitions before treating a textual difference as a behavior change;
do not assume every difference is harmless. The package CHANGELOG records that comparison's scope.

Accept a run only when it exits successfully with nonempty output, `inputUnchanged: true` and
`settingsRestored: true`. Independently check `script.img` and settings hashes before/after as well; the
wrapper's input hash covers only the supplied SCM file. A forced termination may require recovery of
settings on the next run. Matching counts alone do not establish equivalent script behavior.

Then, for the subsystem in question:

1. find the commands by name or script label in the decompiled text;
2. read the control flow around them, not just the matching line;
3. check the engine side of each command (see [engine-and-exe.md](engine-and-exe.md));
4. record script label, offset, opcode, literal arguments, input hash and tool version. The decompiled text
   itself stays in the workspace.

## Cross-check without a decompile

```
python <skill>/scripts/scan_scm_opcodes.py --scm <workspace>/main.scm --img <workspace>/script.img --opcode 0xNNNN --output <workspace>/facts.json
```

This is a byte-pattern scan. It does not know instruction boundaries, so hits can be false positives, and it
decodes only literal arguments, so commands fed from variables are invisible. Use it to confirm that a
decompile's offsets are real or to size a question. Zero hits never proves a command is unused, and
`complete: false` (truncated hits, damaged archive entries) must be carried into the finding.

## No Sanny Builder, no private copies

Say so. Cite third-party SCM documentation as `documented`, or keep the claim `inferred`. Do not reconstruct
a script's logic from memory.
