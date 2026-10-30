# COA range library compatibility

For the G1 source release, use the fingerprinted, configurable
[client setup procedure](../../docs/client-setup.md) and `scripts/client-patches.py`.
The machine-specific staging procedure below is retained as deployment history, not a portable installer.

This repair makes the shared native `LibRangeCheck-2.0` discover suitable learned COA spells rather than
depending only on original WotLK class lists. WeakAuras keeps its normal Range Check trigger and range
conditions, including combinations with other triggers. The repair was installed in the separate staging
client on 2026-10-03. All 26 focused checks passed against the packaged library and installed WeakAuras
range functions. Player testing accepted the repair in staging on 2026-10-03: the existing Quake melee
aura and other melee attack auras work, and the improvements survive logout/login. Production promotion
remains pending. Installation retained all 1,406 archive member identities and the bytes of all 1,403
unrelated ordinary members. Production and
unrelated protected client files were verified unchanged, and the current staging rollback is retained.

## What changes

The library caches actual spellbook slots, spell IDs and range metadata when it initializes, then refreshes
after spellbook, talent and world-entry events. It classifies abilities with the client's native helpful and
harmful APIs. Suitable finite, nonzero, zero-minimum ranges become additional checkers without adding
COA spell IDs or assuming every class has the same range. Existing static spell, item and interaction
checks remain available. An unavailable spell check stays unknown rather than becoming an out-of-range result.

Same-distance alternatives can supply a result when another spell is unavailable. Positive checks retain
the tightest supported upper bound, so a 20-yard ability does not overwrite a successful melee estimate.
Ambiguous zero-range self spells and newly discovered minimum-range spells are excluded. The library's
existing trusted static handling of melee and minimum-range spells remains separate.

`WeakAuras-GetRange.patch` removes the earlier Lichfrost-specific override from `Prototypes.lua`.
The staging installer also moves `COAWeakAurasRange` outside active AddOns, retaining its exact files for
rollback. WeakAuras' version, saved auras and other files are not replaced. The server installer no longer
installs the retired helper automatically.

## Estimated ranges

The result is an interval, not a measured distance. A positive 20-yard check alone cannot distinguish
10 yards from 19 yards. A trigger set to `<= 15` therefore remains inactive unless a tighter available
check confirms that upper bound. A suitable learned melee ability can provide a 5-yard check, subject to
the game's combat reach and range rules. Available thresholds differ by character, spells and cached items.

Friendly, hostile, dead and neutral units retain their separate checker lists. Ground-targeted and self-only
abilities must not be treated as universal distance probes. Changing an aura's range value does not teach
the character a new range checker.

## Staging installation and rollback

`scripts/Install-CoARangeStaging.ps1` is deliberately pinned to the reviewed local staging client and archive.
It is not a general installer for other client versions. `-Prepare` creates a fresh private artifact directory
with the current archive, WeakAuras file and helper backups. It verifies archive member identities, all
1,403 unrelated ordinary member hashes, and metadata before producing the candidate. Preparation can
run while the game is open; installation cannot.

After regression checks, close every game client and use `-Install` with the same artifact directory.
The installer rechecks its inputs and only updates staging `patch-B.MPQ`, the one WeakAuras wrapper,
and the active helper directory. The production client, executables, other archives, saved variables,
and game services are outside its write scope. Earlier native talent-loader changes remain in the archive.

Rollback requires the client closed. Restore `patch-B.rollback.MPQ` to staging `Data\patch-B.MPQ`, restore
the exact `Prototypes.rollback.lua` to WeakAuras, and restore the saved helper directory to its original
AddOns location. Use the current-operation backups, not the older archive from before native talent
testing. Do not overwrite any existing helper directory without inspecting it first.

## Verification

The tests execute the actual library in Lua 5.1 with controlled client APIs. Supply an existing Lua 5.1
runtime through `LUA51` or `--lua51`; tests never install dependencies or silently substitute another runtime.
The same regressions can run against the unchanged baseline with `--baseline-library` to reproduce the defect.
The complete repository fast-check entry point is `tests/run.sh`.

Repeatable regression checks include a range-only text aura at `<= 5`, `<= 20` and `<= 30` where the character has
suitable checkers; move in and out of range with options closed. Then combine range with spell usability,
test no target and a friendly target, and confirm behavior after a rank change and logout/login.
The staging acceptance above does not establish that every threshold, target type or rank change was tested.
Do not interpret a passing mocked test as proof that every COA spell has usable native range metadata.

## Source provenance

The base library came from the supplied client's native `Interface\LibraryXML\LibRangeCheck-2.0` member,
SHA256 `f57253d9f771a8bb24a8707147fc450fbae1a3846d1d6463ff3c9c6cee00002e`.
Its existing author attribution and permissive license are retained in the source. No MPQ archive, client
executable or extracted game-data package is included here.
