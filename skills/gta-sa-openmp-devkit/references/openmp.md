# Porting to open.mp / SA-MP and client mods

Use this when a verified finding becomes server or client code, and when a behavior may be changed by the
multiplayer runtime itself.

## 1. Decide who owns the behavior

- **Server (Pawn or a server component)** owns state and rules: money, ownership, permissions, who may enter.
- **Client mod (ASI/CLEO)** only for what the server cannot do, and never as the authority for a rule a
  player could bypass by removing it.
- **Stock client behavior** you rely on is itself a finding: say which client version you observed it on.

## 2. Verify the API before using it

```
python <skill>/scripts/check_native.py SetPlayerInterior OnPlayerEnterCheckpoint --include-dir <includes>
```

Use the include folders the project really compiles with (`target.includeDirs`), at the pinned runtime
version. Then read that version's documentation for behavior and limits; documentation sites track the
latest release, so check version notes. Results are `declared` (textual match without unresolved conditions
in this file), `conditional`, `disabled` or `not-found`. Comments never count. Unresolved branch chains,
include guards and possible `#endinput` remain conditional: inspect them against the actual build's defines
and include order. A match does not prove that the project includes the file or the runtime supplies the
symbol. `not-found` means no supported declaration matched; enum members, const variables and multiline
declarations are not detected. Plugin natives ship in their own includes.

If neither includes nor documentation support a call, say the runtime cannot do it and offer the nearest
supported design. Do not invent a native, a callback or a parameter, and do not present a workaround as if
it were the original behavior.

## 3. Runtime differences are findings

SA-MP and open.mp replace or disable parts of the single-player game (mission scripts do not run; many
world rules are driven by the server instead). So:

- a single-player behavior that comes from `main.scm` does not exist on a server unless you rebuild it;
- an engine behavior may survive, be altered by the client, or be altered by patches players install;
- compare stock versus the running client before attributing a behavior to either, and record the client and
  patch versions (`layer: runtime`).

## 4. Multiplayer checklist

Single player assumes one player, one world and no adversary. Before implementing, answer:

- **Shared world**: what happens when two players trigger this at once, or one is already inside?
- **Authority and trust**: which values come from the client, and what if they are forged?
- **Persistence and reconnect**: what state survives a disconnect, a crash or a server restart?
- **Instances**: interiors and virtual worlds are shared resources; who else is in the same one?
- **Timing**: streaming and collision load after a teleport; a position valid in single player can drop a
  player through the floor. An entrance record gives a portal volume, not an arrival point; arrival positions
  need their own check in game.
- **Economy and permissions**: prices and unlock rules tuned for one player's story rarely fit a server.

State where the port deliberately differs from single player. That is an authored choice, recorded as a
decision, not as a finding about the original game.

## 5. Verification

Compilation and unit tests show the code runs. They do not show that it matches the original or feels
right; say which parts still need someone to check in game.

## Other targets

The research half of this skill applies to MTA, CLEO and ASI projects unchanged. This reference covers
open.mp/SA-MP only; for other runtimes, apply sections 1 and 4 and verify APIs against that runtime's own
pinned documentation.
