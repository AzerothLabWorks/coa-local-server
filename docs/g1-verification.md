# G1 release verification

Verification describes a particular source release and test scope. A passing source check, a successful
build, and a completed in-game dungeon are different evidence. None certifies every class or dungeon.

## Release candidate: g1-20261029

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
- An actual restore rehearsal before treating a generated backup as restore-qualified.
- Existing-server automatic upgrades; the current tool intentionally does not offer them.

Source packaging and installation checks do not require restarting the established local G1 realm.
