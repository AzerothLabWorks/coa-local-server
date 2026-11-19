# G1 release verification

Verification describes a particular source release and test scope. A passing source check, a successful
build, and a completed in-game dungeon are different evidence. None certifies every class or dungeon.

## Current source recipe: g1-20261118

This recipe synchronizes the published source with the maintained reference realm's upstream base
`437cf5c65bbb003ae180e9239ed89756e3385579` and local overlays. Its public reconstruction and repository-check
results are recorded in the [recipe qualification summary](../releases/g1-20261118/qualification.json).
The October 29 clean public build and empty-database startup evidence below belongs to that earlier recipe;
it does not establish an uninterrupted fresh installation of the November source recipe.

The current repository suite ran **141 checks: 139 passed and two optional external WeakAuras fixture checks
were skipped**. This includes 59 installer checks; command-line help also passed. These tests use fixtures and
do not establish server startup.
The first new empty-database trial exposed a missing canonical challenge character table used unconditionally
by the new core. The fresh bootstrap now imports that hash-checked schema for this exact core revision while
leaving challenge gameplay disabled; the earlier recipe is unchanged. The failed trial was isolated and did
not modify the playable realm. The corrected empty-database bootstrap passed. A separate startup probe then
exposed a race when auth and world started together: auth could mark the realm offline while world was still
initializing. The installer now waits for the world listener and readiness marker before starting auth,
then checks realm-online flags through the native world heartbeat and auth refresh without overwriting them.
The final isolated probe passed the corrected bootstrap and ordered startup with the realm-online check.

Fresh initialization verified all 318 canonical world base tables, the required challenge and Worldforged
character schemas and their migration identities, and the exclusion of Worldforged placement SQL. No player
snapshot was imported: account and character tables began empty. Native pool creation then produced 201 bot
accounts and 2,010 bot characters with automatic login disabled and zero online characters. The experience
potion's one-second cooldown was also verified.

Auth and world internal listeners remained healthy without restarts or OOM termination. The realm's offline
flag cleared through the native heartbeat and stayed online for 25 seconds to cover auth's refresh. That
combined wait took 622.6 seconds, within its 650-second bound; total startup took 654.2 seconds. All test services and the
database stopped cleanly with exit code 0 afterward. Existing spell/DBC and disabled-command validation
warnings remained; no missing-table, prepared-statement, unknown-column or database-connection failure was
found in the final startup.

This probe reused the exact previously qualified binaries and supplied compatible data in an isolated
network namespace. Startup retries used the same newly initialized database. It exercised fresh database
bootstrap and the equivalent ordered startup/read-only realm checks,
not a new C++ build, a fresh Docker toolchain build or an uninterrupted public `install`/`start` invocation.
It did not exercise public ownership labels or published host ports; those guards were covered by repository
fixtures. In-game login and a dungeon on this fresh community installation remain separate acceptance work.

The reference realm's Worldforged deployment reused the unchanged binary that had passed its focused native
source/build qualification. Its SHA-256 is
`4e696a58cb7301d76c639c9329f861aa5186fbf02501a585fd8570dd8b93f46d`.
A source audit matched all 20,781 in-source inventory files to the prepared build record. This is evidence for
the maintained local build, not a promise of identical compiler output on another machine.

On November 18, `tools/verify_all.py` ran the focused `g1-worldforged-arakor-collection` gameplay scenario
against a fresh isolated restoration of the final-save database backup: **VERIFY ALL: PASSED**, 56 assertions,
with a simulated clock. Original table checksums remained unchanged, disposable schemas were removed, and
no migration was applied to the playable realm. That invocation intentionally skipped source, build, unit and
harness stages for the unchanged previously qualified artifact; it was not a new full-suite run.

The scenario covers per-character sparkle/update flags, awarding and claiming the item, repeat-loot refusal,
logout/login persistence, independent party-member claims, and an ordinary-loot control. The player then
confirmed the visible sparkle before collecting Arakor Mace and its removal and interaction lockout afterward.
Client logout/login after that specific pickup has not been separately reported. Full process restart,
prestige reset, full bags and group-roll Worldforged awards remain outside this focused acceptance.

The gathering skill-filter qualification covered its focused native scenarios, including effective skill
bonuses and filtering before the nearest-node limit. The potion and centaur repairs have their own focused
native scenarios. The player reported the potion repair working; the centaur quest follow-up remains pending.
These checks supplement the earlier dungeon, bot and profession evidence; they do not certify every quest,
class, item or world pickup.

## Historical release: g1-20261029

| Scope | Result |
| --- | --- |
| Public source reconstruction | Exact public core and Playerbots pins fetched; complete patches applied and changed-file hashes/modes matched. |
| Native source checks | 15 checks passed against the public core baseline. |
| Fresh toolchain | Dockerfile built from the pinned Ubuntu image; package dependencies installed successfully. |
| Fresh native build | Clean configure/compile and the native unit suite passed through `tools/verify_all.py`. |
| Empty database initialization | Passed against new isolated storage: all 318 world baseline tables verified, canonical character schema and required ledger imported, native migrations and reviewed Playerbots profiles applied. No player snapshot was used. |
| Game service startup | Actual internal login/world listeners and published ports became ready, with no restarts or OOM termination. Runtime updaters were disabled and intended settings verified. |
| Fresh bot/profile data | 71 CoA rotation names and 2,520 rules verified. With automatic login disabled, initial pool creation produced 201 bot accounts and 2,010 bot characters, with zero online characters. |
| Managed backup | Created from the isolated test database with game services stopped. Compressed-stream integrity, completion footer and receipt hash passed; restore has not been rehearsed. |
| Repository fast checks | 119 passed; one existing optional WeakAuras fixture skipped. This includes 41 installer guard tests. |
| Native client patch tooling | 24 synthetic safety/install/rollback tests passed. All five retained archive variants prepared successfully on copies; unrelated ordinary members were preserved. |
| Companion addon packaging | GM, gathering, resource, LFG, deterministic packaging and disposable-client install/rollback tests passed; see the addon repository for scope. |
| Optional graphics | Complete helper execution from new source/build directories passed on Windows with VS2022 x86 and Windows SDK 10.0.26100.0. Both `vfog_harness` (Direct3D 9 rendering checks) and `comments` passed; five output hashes were recorded. Prerequisite installation on a clean machine and in-game acceptance on other hardware remain pending. No client files were installed. |

Qualification ran in stages. The source was reconstructed from public pins and patches, then compiled in a new
toolchain/build directory. The final empty-database and startup probe reused those exact qualified binaries
while testing the corrected bootstrap and management tooling against a new database. This is not a claim that
the final installer was rerun as one uninterrupted end-to-end command after every tooling correction.

Earlier isolated attempts exposed missing build-network access, a MySQL client option mismatch, a mandatory
character-ledger dependency and startup/permission checks. Those issues were corrected and exercised in the
subsequent targeted checks. Failed installations were retained rather than replaying an ambiguous bootstrap.
The existing playable realm and its data were not changed. The [qualification summary](../releases/g1-20261029/qualification.json)
records the tested inputs and scope without publishing private runtime data.

The native `verify_all.py` source, build and unit stages passed; its additional database harness and gameplay
stages were skipped in that build invocation. The separate fresh-bootstrap/startup probe described above and
historical player acceptance are separate evidence, not a substitute for claiming those skipped stages passed.

## October 30 client-tool compatibility update

The current repository additionally recognizes the exact clean `WeakAuras/Prototypes.lua` from the
separately packaged Ascension WeakAuras source, preserving its original bytes. The old wrapper and already
repaired variants remain supported; unknown/customized variants and unreviewed native client identities
still stop for review. This does not update the server baseline frozen by `g1-20261029`.

All **27 focused client-patch tests passed**, including the exact public upstream file, unchanged-byte
installation/rollback fixtures, and unknown-input rejection. The tests use disposable fixtures, not a live
client. Repeat with `python tests/test-client-patches.py --weak-auras-prototype PATH`, where `PATH` is the
clean file extracted from the [separate WeakAuras package](https://github.com/AzerothLabWorks/addons/blob/main/docs/weakauras-coa.md).
Without that optional file, its external-source test is explicitly skipped. This is not an in-game acceptance
claim for the newly packaged download.

## Gameplay evidence

See [improvements and acceptance](g1-improvements.md) for the player's observations on the existing G1 realm:
1,000 bots in the world, full dungeon runs, role availability, recovery/resurrection, profession improvements,
talent persistence and gathering visual alerts. Those observations concern the maintained local G1 build.
Community installer qualification uses independent storage and does not copy its character database.

## Repeating checks

```bash
bash tests/run.sh
```

The fast repository suite requires Python 3.11+, Bash, Git and Lua 5.1. It uses disposable fixtures and does
not deploy a playable server. The optional real-client tests use privately supplied archives; those archives
are not published.

The fresh installer invokes the pinned native source's `tools/verify_all.py` for source, build and unit stages.
Its report is saved beneath the new runtime's `state/verification/report.json`. Additional native gameplay
harnesses may require explicit isolated-database settings and are not silently treated as passing when absent.
Retained development harnesses can refer to historical fixture names and private qualification guards; those
are not production configuration or account data.

The installer checks all recorded DBC fingerprints. Terrain directories are currently checked for presence
and nonempty contents, not a complete byte fingerprint: the operator must supply matching client terrain.
Do not interpret that check as proof that a different terrain extraction is compatible.

## Remaining acceptance

- A community user's fresh client login, character creation, bot population and full dungeon run.
- Rendered acceptance of the new GM character/realm confirmation UI.
- More minimap sizes/zoom settings and sound preferences for gathering alerts.
- A restore rehearsal of the community installer's generated backup before describing that command's output as restore-qualified.
- Existing-server automatic upgrades; the current tool intentionally does not offer them.

Source packaging and installation checks do not require restarting the established local G1 realm.
