# Upstream gameplay and module audit

Reviewed on 2026-10-01 for the [gameplay roadmap](gameplay-roadmap.md). This is an initial, read-only
comparison and prioritized issue sample. No source ports, SQL applications, builds, or deployments were
performed for the initial review. The G1 follow-ups below record data qualification, a separate
current-build staging deployment, and candidate-only source adaptation. No live upgrade has occurred.

## Revisions and evidence

| Layer | Audited state |
| --- | --- |
| Local installer repository | `22615ac` on `main`, with existing uncommitted population/riding/trade improvements |
| Active COA core | `a8b28faac98d81b063bb81ff634037f71827d128` (2026-09-15), plus local core/gameplay patches |
| Active Playerbots module | `619a06fc795a7220fd5c27d5a5aa4a2fbe383b72`, plus local COA AI/travel patches |
| Reviewed upstream core | [`d48a1123153a3c39e1eaafb7714b375ee67e7689`](https://github.com/jealous-sound/azerothcore-wotlk-coa/commit/d48a1123153a3c39e1eaafb7714b375ee67e7689) (2026-10-01) |
| Git comparison | [531 commits ahead, 0 behind](https://github.com/jealous-sound/azerothcore-wotlk-coa/compare/a8b28faac98d81b063bb81ff634037f71827d128...d48a1123153a3c39e1eaafb7714b375ee67e7689) relative to our core pin |
| Running image | `sha256:36494982b8154124f8de0e027afbd0929f90111454463c77e50d1cacfb708468` |
| Effective population target | 50: the running container's minimum/maximum environment overrides supersede stored configuration values |

The runtime's `COA_SOURCE_DIR` points to `/home/ryan/wow-server-coa-playerbots-source`; the older
`runtime/source` checkout is not the active build source. Confirmed the active Git pins, state records,
module directories, and module-registration symbols in the running worldserver. The active source has
substantial local modifications, so a clean Git comparison of the upstream pins does not include all
locally implemented behavior.

Existing local customizations must be reviewed by behavior: starter supplies/rates, collections and
action-bar persistence, Book of Artisans/model repair, profession kits, Lootbot, Furline, talent allocation
state, COA progression validation, and all bot initialization/recruitment/role/healing/travel/riding changes.
The local client bridge, range helper, and resource display also form part of acceptance.

## Module comparison

The installer repository vendors `mod-local-profession-tools`. The active source and binary also include
the upstream `mod-ascension-compat` and separately cloned `mod-playerbots`: three installed modules in total.

The reviewed [upstream module tree](https://github.com/jealous-sound/azerothcore-wotlk-coa/tree/d48a1123153a3c39e1eaafb7714b375ee67e7689/modules)
has 25 `mod-*` directories: 24 feature modules and `mod-ascension`, which holds historical SQL. None of those
25 directories exists under the same name in our active source. Several features overlap our older
compatibility component or local patches, so directory absence is not proof that every related behavior
is missing.

| Upstream directory | Purpose | Relationship to our active build / proposed treatment |
| --- | --- | --- |
| `mod-ascension` | Historical COA SQL; not a compiled module | Compatibility implementation moved to required `src/server/coa`; migrate the component and retain applied SQL identities |
| `mod-book-of-artisans` | Full/beginner profession books, ranks, supplies, six tools | Overlaps working book/model repair and our tool module; prioritize behavior comparison/consolidation |
| `mod-spellbook` | Book of Ascension class/rank training | Review acquisition policy and bot progression before adoption |
| `mod-treasure-keeper` | Personal bank companion and ruleset restrictions | Review against existing bank spell/companion behavior |
| `mod-item-recovery` | Recovery UI using native buyback slots | Candidate service feature; test actual client window and native buyback lifetime |
| `mod-portablemail` | Portable mail, transpolyporter and enchanting altars | Candidate service feature with core/SQL/client dependencies |
| `mod-scrolls-of-retreat` | Retreat/Defense item teleports | Review destination, cooldown and ruleset restrictions |
| `mod-teleport-actionbar` | Teleport-token actions and faction rules | Adjacent to collection-button persistence; validate both together |
| `mod-battlehorn` | Battle Horn item and Bazaar availability | Optional item/service feature |
| `mod-craftsmans-codex` | Additional permanent primary-profession slots | Optional profession policy and character-state migration |
| `mod-woodworking` | Woodcutting/woodworking, recipes, sawmills and Lumber Axe | Optional profession extension; review its separate tool supplier |
| `mod-portable-sawmill` | Portable/Tinker sawmill summons | Evaluate with woodworking and spell/summon dependencies |
| `mod-destiny-weaver` | Per-character level scaling and XP choices | Changes our current global scaling policy; evaluate deliberately |
| `mod-dynamic-xp` | XP presets and level-band curves | Compare against our existing XP overrides before adoption |
| `mod-coa-change-potions` | Race/faction/class/customization consumables | Optional; test character/talent/collection state across changes |
| `mod-coa-prestige` | Prestige progression and rewards | Optional; validate resets and retained state |
| `mod-path-to-ascension` | Tutorial objectives/progress/rewards | Candidate questing feature with UI and migration requirements |
| `mod-hero-call-board` | Daily call boards and event credit | Candidate world-content feature; validate objectives and reset cycle |
| `mod-worldforged-pickups` | Per-character ground pickups and placements | Candidate world-content feature; verify spawns, collision and ownership |
| `mod-worldforged-upgrades` | Worldforged store/upgrade interface | Optional progression feature after pickup behavior is stable |
| `mod-ethereal-bazaar` | Rotating vendor/token economy | Optional economy policy; validate stock, costs and persistence |
| `mod-coa-challenges` | Trials, rules, lives, progress and rewards | Optional game modes with character/world migrations |
| `mod-coa-raid-difficulty` | Raid difficulties, boss scheduling and health scaling | Later endgame feature; evaluate against current instance behavior |
| `mod-coa-titan-scrolls` | Eonar proc and friendly ground healing | Later item mechanic; test proc/target semantics |
| `mod-war-games` | Private group arena challenges | Later PvP feature; test roster and instance lifecycle |

Each adoption must check CMake/script registration, core APIs, distributed configuration, SQL discovery,
pending migrations, data, and client support. Some modules have migrations in both their own directories
and the core's pending updates. Module presence or a successful compile alone does not establish behavior.
Native Playerbots hooks are now in the core; the bot module still comes from a separate repository.

### Profession-tool overlap

The upstream [book implementation](https://github.com/jealous-sound/azerothcore-wotlk-coa/blob/d48a1123153a3c39e1eaafb7714b375ee67e7689/modules/mod-book-of-artisans/src/book_of_artisans.cpp)
supplies Mining Pick (2901), Skinning Knife (7005), Fishing Pole (6256), Blacksmith Hammer (5956),
Jeweler's Kit (20815), and Virtuoso Inking Set (39505) when a previously unknown skill is trained through
either book trainer. It checks exact-item ownership, including the bank, and mails full-bag overflow.

Our [local tool module](../modules/mod-local-profession-tools/README.md) also supplies Engineering's
Arclight Spanner/Micro-Adjustor and hammer, Enchanting's Runed Copper Rod, and Jewelcrafting's Simple Grinder.
It handles native skill hooks from other trainers, repairs existing professions on login, recognizes
compatible upgraded tools, retries full-bag failures, and excludes bot sessions.

Decision: retain the local feature pending consolidation. Running both suppliers without adapting their
ownership checks could grant a basic tool beside an upgraded equivalent. Full-bag mail versus login retry
also needs deliberate testing. `mod-woodworking` adds its own Lumber Axe supplier (6954).

The merged [starter-tool data fix #5379](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5379)
restores usable low-level item data and racial grants; its scope is distinct from automatic tool delivery.
The [included SQL](https://github.com/jealous-sound/azerothcore-wotlk-coa/blob/d48a1123153a3c39e1eaafb7714b375ee67e7689/data/sql/updates/pending_db_world/rev_1790503984571497221.sql)
sets the pick, knife and hammer to level-one requirements. Compare those rows with our effective world
database before porting.

Upstream book SQL also changes the trainer catalog to profession/rank entries, adds a beginner trainer
and trade supplies. It depends on core trainer-list filtering. Its proposed recipe expansion is a separate
unmerged PR; copying the module alone into our old core is insufficient.

## Initial candidate list

The initial review sampled recent open/closed reports and targeted profession, collection, talent,
Primalist, Necromancer, and dungeon searches: 16 issue bodies/comments and 10 PRs were read in detail,
with relevant snapshot source/scenarios inspected. It does not exhaust the tracker, which had more than
1,100 open reports at review time.

Reports include submissions from this fork's in-game form and website with core revisions; see its
[bug-report documentation](https://github.com/jealous-sound/azerothcore-wotlk-coa/blob/d48a1123153a3c39e1eaafb7714b375ee67e7689/docs/coa/github-bug-reports.md).
Establish the expected mechanic independently and reproduce it on our realm before selecting a port.

| Priority / item | Upstream evidence at audit time | Local work required |
| --- | --- | --- |
| G2: tool usability and class racials | [#5220](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/5220), merged [#5379](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5379), commit `c9389794b914f10051c3f6fc2c115970fc2ebaaa` | Compare item data and race/class variant grants; test new and existing characters while retaining automatic tool supply |
| G3: enhanced Primalist Boons | [#4559](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/4559), merged [#6012](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/6012), fix `602b20ca72d5cfa079079029afab3409d7217eed` | Reproduce talent-enhanced Primal Convergence scaling, owner/pet propagation and removal; scenario `primalist-convergence-talented-boons-4559` |
| G3: Mend Animal Spirit acquisition | [#5438](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/5438), merged [#6024](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/6024), fix `f61430fb6057a9458cee69371789182e20d0fd86` | Check Wildwalker/level/parent conditions and actual pet healing; scenario `primalist-mend-animal-spirit-acquisition-5438` |
| G3: Necromancer talent-removal cleanup | [#4532](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/4532), merged [#6004](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/6004), fix `8267695fc4968a4530fb2f109ea81da459596215` | Dismiss affected minions/release Life Force while preserving unrelated summons; scenario `necromancer-talent-removal-dismisses-minion` |
| G4: classic dungeon wing completion | [#5140](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/5140), merged [#5164](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5164), commit `19526e1fbc88b8f14370b9b3f71fc4a7338adffb` | Compare 13 wing mappings, `instance_encounters`, client encounter data and applied `rev_20260925_50_lfg_wing_final_bosses.sql`; test native final-boss completion/rewards |
| Watch: profession recipes/rank presentation | [#5899](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5899) open/unmerged, despite closed [#5818](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/5818) | Review proposed recipes and trainer policy separately; do not describe them as part of the snapshot |
| Watch: dungeon rewards/satchels | [#5916](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5916) open/unmerged | Reproduce reward/loot discrepancies separately from the merged final-boss mappings |
| Optional policy: region locks/race starts | [#5914](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5914) open/unmerged | Evaluate locked-region defaults against our open-world level 1-80 population before adoption |

These implementations are upstream candidates, not locally accepted fixes. The class-batch reports cite
individual passing scenarios but a broader 95-scenario run with one failure; that is not a general stability
pass for our candidate.

Regression/watch items:

- Talent/login reports [#100](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/100) and
  [#6027](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/6027) remained open. Preserve our
  player-tested explicit allocation and client-tree persistence through any upgrade.
- [Spiritbound #4839](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/4839) was verified as
  already working in the batch review. Use its scenario as a guard rather than claiming a new implementation.
- [Automatic tools #5819](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/5819) remained open;
  distinguish automatically supplying tools from buying the book's trade supplies.
- [Loot #6058](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/6058) and
  [Primalist bot damage #5846](https://github.com/jealous-sound/azerothcore-wotlk-coa/issues/5846) lacked
  confirmed local defect/fix evidence. Record reproduction and bot gear/state before deciding on a repair.

## Upgrade dependencies

### Core, configuration and database identity

The [component upgrade guide](https://github.com/jealous-sound/azerothcore-wotlk-coa/blob/d48a1123153a3c39e1eaafb7714b375ee67e7689/docs/coa/README.md)
documents the move from `mod-ascension-compat` to `src/server/coa`, configuration `coa.conf`, `CoA.*` keys,
`AC_CO_A_*` overrides, and `coa` logging. A pending migration renames the provenance table to
`item_template_coa`. Our installer/Compose and gameplay patches use the old paths/names.

Inventory and adapt these together, preserving historical SQL filenames/hashes. Compare applied migration
history and effective rows; a count of SQL files is not a count of missing fixes. Broad overlay-deletion
migrations must be qualified against our data and custom repairs before applying them to staging.

### Client/server data qualification

[PR #1498](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/1498) changed the source of COA data
from generated/SQL copies to original client tables. The snapshot's
[startup gate](https://github.com/jealous-sound/azerothcore-wotlk-coa/blob/d48a1123153a3c39e1eaafb7714b375ee67e7689/src/server/game/DataStores/DBCStores.cpp#L706)
requires five COA-specific records.

Read-only checks on the currently mounted repack `Data/dbc` gave:

| Required record | Present in current files |
| --- | --- |
| `CreatureDisplayInfo` 236827 | Yes |
| `CurrencyTypes` 375250 | No |
| `GameObjectDisplayInfo` 87226 | No |
| `ItemLimitCategory` 2414 | No |
| `Map` 3690 | No |

The new `client_dbc.py check` reported **112 core tables checked, 0 problems**. That result checks layouts;
it does not cover the five-record startup requirement or establish archive provenance. The current
directory also lacks `CharacterAdvancement`, `CharacterAdvancementClassTypes`,
`CharacterAdvancementTabTypes`, `ChrSpecs`, `SpellCharges`, and `SpellChargesCategory` DBCs.
The current data therefore does not qualify for an unchanged switch to the reviewed core.

Extract/check a matching client set into a separate staging directory and record its manifest. Inspect
custom tables, relocated server-only spell IDs, SQL overrides, and any installed client patches before
changing data or import policy. Keep client files and extracted data outside this repository.

#### G1 prerequisite follow-up, 2026-10-01

Two existing original-client extractions, `wow-server-coa-dev-data/dbc` and
`wow-server-coa-v20-data/dbc`, provide a better candidate than the currently mounted repack set. Both have
368 files whose hashes agree with their extraction manifests, pass the snapshot's 112 core-table layout
checks, and contain all five required startup lookup entries. `CurrencyTypes` is indexed by its second
field (`CurrencyTypesfmt = "xnxi"`); its Rune of Ascension row is `(364, 375250, 41, 35)`, so scanning only
the first field would incorrectly report that lookup as absent. The repack set has no such row.

Both extractions also contain `CharacterAdvancement` (179 fields / 692-byte packed records),
`CharacterAdvancementClassTypes`, `CharacterAdvancementTabTypes`, `ChrSpecs`, `SpellCharges`, and
`SpellChargesCategory` with manifest agreement and layouts matching the inspector's reviewed schemas.
Their manifests identify original `patch-B.MPQ.ORIGINAL` and `patch-T.MPQ.ORIGINAL` sources. A fresh extraction
from the installed client's original archives was then completed at 23:01:39 UTC into the separate
`/home/ryan/wow-server-coa-g1-data-20261001/dbc` directory. Its 368 file hashes agree with the new manifest
and the earlier extraction; all five startup lookup entries and the six custom tables are present.
It also passes the 112-table core layout check. Manifest SHA-256:
`d165c1e6f859019f26fd91a9f6349ca14d44caa249c048d94a6ac83e04ea4feb`.
No installed client archive or live server data was replaced.

The checker reports 7,029 out-of-block `Spell` string fields and 25 unindexed `WorldMapArea` rows as notes,
not layout failures. These notes remain part of data/content review; no runtime startup or gameplay pass
is claimed from the layout result.

Infrastructure is available for staging, with ample disk/RAM at preflight. Bound build concurrency before
sharing resources with the live server. The latest inspected backup contains auth, characters and
Playerbots, but not world; archive integrity passed, restoration has not been tested. Capture and restore
all four schemas into an isolated MySQL instance before testing destructive world migrations. Use
separate Docker volumes, loopback ports and image tags, not only a different Compose project name.

#### G1 current-build recovery baseline

Prepared on 2026-10-01. Live auth/world were paused for 27 seconds after player logout while the
four-schema checkpoint was captured; live MySQL stayed running. The game services were resumed before
source/data/image preservation and the isolated restore. No second live restart was needed.

Private checkpoint:
`/home/ryan/wow-server-coa-dev/state/backups/g1-baseline-20261001-uaqpv7kr`.
It holds `databases.sql`, matching `etc` and live connection/configuration records, copied server data,
full active-source and installer archives, and all three exact runtime images. Archive traversal passed;
SHA-256 evidence for the dump/archives and 22,281 copied data files is retained in `checkpoint.json`.
The source archive contains core `a8b28faac98d81b063bb81ff634037f71827d128` and Playerbots
`619a06fc795a7220fd5c27d5a5aa4a2fbe383b72`, including their local modifications.

The captured databases have 524 base tables across auth, characters, world and Playerbots, including
18 MyISAM tables. Auth/world shutdown plus a global-table-lock dump was used rather than assuming a
transaction-only snapshot covers every table. Table/column/index metadata and exact row counts agree
after restoration. Raw extended checksums agree for 521 tables. The three exceptions are
`acore_characters.character_homebind` (559 rows), `acore_characters.characters` (1,203 rows), and
`acore_world.gameobject` (98,138 rows), all containing FLOAT columns.

For those exact tables, the verifier compared every saved INSERT tuple, including every field and duplicate
occurrence, against read-only staging redumps. All tuple multisets and framed SHA-256 hashes match.
`restore-canonical-proof.json` preserves the raw checksum deltas and proof; all other mismatches fail closed.
This establishes SQL-level restoration, **not bit-identical FLOAT storage**. The distinction is consistent
with [MySQL's floating-point dump/reload guidance](https://dev.mysql.com/doc/refman/8.4/en/problems-with-float.html).

The restored baseline uses `/home/ryan/wow-server-coa-staging`, project `coa-staging-g1`, and the checkpoint's
world/auth/MySQL images. It has a separate database volume and internal backend network; auth/world also
have their own ingress bridge so local login ports work. This is separate storage/configuration/network
resources, not an air-gapped firewall boundary. MySQL has no published port. Game ports are loopback-only,
all four database routes use the staging database, and database updaters/SOAP/RA are disabled.
The copied realm route was changed **only in staging** to `COA G1 STAGING`, login port 33725/world port 38086.
The original live route/client remain on 33724/38085.

Automated startup checks confirmed readiness, reachable login/world endpoints, zero container restarts/OOM
events, and 50 online bots. Beruwa is present at level 15/class 31, with 26 saved action buttons and the
persisted explicit talent-allocation rows. The baseline inherits existing data-validation warnings,
including creature 55332/display 7654 and waypoint records; these have not been fixed by cloning the realm.
Startup/data-log comparison and player testing remain distinct from an upstream acceptance claim.

The user's copied `C:\Games\Ascension-WOW-Staging` client is configured exclusively for this test realm.
Executable, patch-B/patch-T, WeakAuras range helper and resource monitor hashes match the live client.
Original staging connection files were preserved privately; no production client file was modified.
The **COA - G1 Staging** desktop shortcut and launcher use that separate client. Existing realm profiles
were copied once within the staging client. Launcher recovery can be invoked with `-RestoreConnection`
after an interruption; focused tests never launch the game or use real client files.

The player accepted Phase A on 2026-10-01, reporting that the baseline checks look good. Book of Artisans
still displays unrelated recipes and all professions as learnable; this catalog/trainer-state observation
is deferred to G2, with learned-skill loss not established. It was not repaired as part of baseline cloning.
The player then confirmed game exit and authorized further development. G1 candidate integration is
underway; two failed migration trials were isolated and preserved, then a fresh guarded trial passed strict
migration preservation. After the recorded Furline failure and repair, all six focused native cases passed.
The added binding SQL passed fresh retry3 migration acceptance and all six focused runtime cases passed
again on that clone; client/bot, fresh-install and rollback checks remain pending. Follow the
[phase checklist](gameplay-roadmap.md#g1-phases-and-player-testing) before replacing the accepted baseline.

#### G1 upstream candidate source and build

The permanent candidate checkout is `/home/ryan/wow-server-coa-g1-candidate-source`, based on the reviewed
`d48a1123153a3c39e1eaafb7714b375ee67e7689` snapshot. The installer remains pinned to the accepted old core;
`source-patches/coa-g1-preservation.patch` is a staging-only integration patch, not automatically applied
by the installer. Its clean application to the immutable upstream checkout passed. Patch SHA-256:
`8085c80765f1a668dbdcb3bd4c8f577a7c654c5614b8af9e8b3d108dbf66e522`.
The 14-file export includes both SQL guards, the Furline effect-step repair and new binding migration.
Fresh retry2 passed the guards' strict migration-preservation proof and all six focused native cases;
the added migration subsequently passed separate fresh retry3 restoration, migration proof and the
six-case runtime retest below.

| Local behavior | Candidate treatment |
| --- | --- |
| Playerbots AI, recruitment, post-combat cleanup and riding | Preserve the exact tested module tree and pin; use native core hooks instead of duplicating the old core hook patch. Actual candidate behavior remains pending |
| Bounded pilot level/spec preparation | Pending: `.localbotprepare brewing` and `COA_BREWING_PILOT_NAME` were in the retired old compatibility component, not the preserved bot module; the native API alone is not an equivalent combined workflow |
| Profession tools | Preserve the exact local supplier module; leave the new Book of Artisans catalog module disabled for G2 overlap review |
| Paid/selectable talent authority | Adapt the existing `core.coa_talent.*` ledger to native talent packets, budget/reset/spec handling; automatic grants remain distinct from explicit player selections, bots retain native spellbook authority |
| Owned companion and mount buttons | Use native companion preparation/save marking; add the owned Furline 91737 grant |
| Artisans visibility and trainer opening | Preserve the unchanged model-fallback SQL and adapt the delayed helper with alive/entry/ownership guards |
| Furline speed/model and starter bags | Adapt the legacy summon redirect to 91737 and retain four-bag provisioning; guard against delayed remounting after dismount |
| Lootbot | Retain native owned/living companion fallback; actual-client collection remains a regression requirement |
| Client range helper and resource monitor | Retain installed client helpers unchanged; native talent protocol must be qualified separately with the old talent overrides disabled only in staging |

Compiled module selection is `mod-playerbots`, `mod-local-profession-tools`, and `mod-destiny-weaver` beside
native COA. Old dynamic-XP, teleport-actionbar and challenge configuration keys were inactive: the running
binary contains none of those modules. They are not enabled in the candidate. SQL discovery must use the
same explicit allowlist, plus the core's always-included historical `mod-ascension` SQL; compilation flags
alone do not restrict SQL discovery.

Verification uses only `tools/verify_all.py`, bounded to four jobs in an isolated toolchain container.
The final build toolchain is pinned to
`coa-local/g1-toolchain@sha256:52d237189ca46c098a379a77ae464f7c696f3e71718bd04dc46c9ff9581db6e2`.
The first build was intentionally interrupted to correct module selection. Two subsequent attempts found
a missing Clang coverage runtime, then an upstream unit-test archive ordering defect. The toolchain now
includes that runtime; the small test-only CMake correction links modules, COA and game in native dependency
order. No tests were stubbed or disabled to obtain a pass.

Completed source/build/unit/harness report, including both SQL guards:
`/home/ryan/wow-server-coa-g1-candidate-source/.cache/verify-all/20261002-021840/report.json`.
Scope: `source,build,unit,harness`, base `d48a1123153a3c39e1eaafb7714b375ee67e7689`, harnesses
`talent_state` and `companion_loot`. Source: **PASSED** (10 checks); build: **PASSED**; unit: **PASSED**
(one registered CTest target: 6,100 GoogleTests passed, 5,486 conditionally skipped, zero failed); talent
harness: **PASSED**. The upstream parameterized suite skips inapplicable cases such as spells without a
cooldown; skipped cases are not additional passes. Companion-loot harness: **UNAVAILABLE** because
the MSVC toolchain is absent. Overall native result: **INCOMPLETE**, not a full verification pass. Gameplay
was not selected in that invocation. Subsequent focused runtime results are recorded below.

The Furline effect-step repair also passed source/build/unit and the talent harness in
`/home/ryan/wow-server-coa-g1-candidate-source/.cache/verify-all/20261002-030945/report.json`.
The overall result remains **INCOMPLETE** for the same unavailable MSVC-only companion-loot harness.
The new binding SQL also passed source/build/unit and the talent harness in
`/home/ryan/wow-server-coa-g1-candidate-source/.cache/verify-all/20261002-032613/report.json`, again
**INCOMPLETE** only for that unavailable harness. These reports are not a full verification pass.
Original migration/build proofs remain immutable; the repaired binary's retry2 runtime evidence is linked
by a separate supplemental build proof, and the original retry2 plan bytes/hash are preserved privately.

The first database-only clone is `/home/ryan/wow-server-coa-g1-candidate-runtime`, project
`coa-staging-g1-candidate`. Its original-checkpoint restore independently passed the complete 524-table
schema/index/count/checksum/canonical-FLOAT proof before the failed trial below. It is now stopped, with
the failed database volume and private diagnostics retained.

The first retry is `/home/ryan/wow-server-coa-g1-candidate-retry1-runtime`, project
`coa-staging-g1-candidate-retry1`. It has its own new volume/internal network, no published ports, and
independently passed the same complete 524-table original-checkpoint restore proof. Its SQL trial completed,
but preservation acceptance failed as recorded below. It is now stopped with its volume and private
diagnostics retained. No candidate auth/world services or gameplay tests started against either failed clone. The accepted baseline
staging playthrough and live database remain unchanged.
Its failed acceptance is retained as historical evidence; the successful fresh retry2 proof is recorded below.

#### G1 first candidate migration trial

The first ordinary `dbimport` trial **FAILED** after partially applying updates to the isolated candidate.
World migration `rev_20260926_81_retreat_and_defense_scrolls.sql` referenced `ethereal_bazaar_pool`, which
is absent because the optional Ethereal Bazaar module was not selected. Core SQL dependencies therefore
need qualification beyond the compiled-module allowlist.

The failed private clone and diagnostics are preserved. No candidate authserver, worldserver or gameplay
tests started, and live plus the accepted current-build staging baseline remain unchanged. The private
`migration-status.json` records `status: unavailable` and does not establish completed migration acceptance;
its `native_migrations_applied: false` must not be read as proof that no SQL was applied.

A source-side guard for the optional-table dependency is now included in the passing source/build/unit
checks in report `20261002-020247`; the preservation patch still applies cleanly to untouched upstream.
These checks do not establish successful SQL migration behavior. The fresh uniquely isolated retry
clone subsequently completed SQL execution, but failed a separate preservation check as recorded below.
**Never replay the updater against the failed, partially migrated clone.**
Candidate gameplay and fresh-install acceptance remain pending.

#### G1 retry1: SQL completed, preservation acceptance failed

Retry1's ordinary `dbimport` applied all 10 planned character and 567 world additions, with exact migration
ledgers matching the reviewed plan. **Acceptance still FAILED**: upstream pending migration
`rev_20260926_41_profession_upgrade_kit_recipes.sql` globally deleted matching recipe spells from
`trainer_spell`, then reinserted them only for ordinary trainers. This removed 56 recipe rows from Book
trainer `200001`.

The 171 talent-setting rows, Book model and creature/trainer bindings were unchanged. A separate read-only
proof passed for all 193 protected tables, including the three expected skill-633 additions. Those results
do not waive the failed Book recipe-preservation check, and do not establish gameplay acceptance.

The second source guard narrows the DELETE to exempt trainers bound to Book creature entries `57500` and
`57524`. Strict recipe/model/binding checks remain required; the optional Book catalog/filtering feature
stays deferred to G2. Both SQL guards are exported and included in passing source/build/unit checks in
report `20261002-021840`; the fresh retry2 restoration and migration acceptance subsequently passed below.
Never replay the updater against either failed clone. Both are stopped and retained privately; no gameplay
was started against those failed clones, and live plus accepted baseline remain unchanged.

#### G1 retry2: migration preservation passed

Fresh retry2 uses `/home/ryan/wow-server-coa-g1-candidate-retry2-runtime`, project
`coa-staging-g1-candidate-retry2`, a separate new database volume/internal network and no published ports.
The complete original-checkpoint 524-table restore proof passed again before one ordinary updater invocation.
Its private `migration-status.json` records **migrations-verified-gameplay-not-started**, the migration
checkpoint captured before the focused runtime invocations below.

All planned additions applied: auth 0, characters 10, world 567, Playerbots 0. Exact final ledger counts are
23 / 53 / 3,697 / 0; existing migration identities and hashes were retained, with no updater replay or rehash.
All 193 original protected tables passed schema/index and complete canonical-row checks, allowing only the
reviewed name-column widening and three new skill-633 rows for existing spell-804154 holders. All 171 saved
talent-setting rows, Book model, trainer bindings and all 4,739 trainer recipe rows were unchanged. The twelve
reviewed new character tables are empty InnoDB tables. No bot/account/character data reset was used.

The first utility preflight rejected an incorrect foreign-key-free assumption. Its replacement verifies
the single exact `required_rev` to `sql_rev` self-reference on `version_db_playerbots`, preserves/rebases
that constraint inside the owned fourth test schema, and keeps foreign-key checks enabled. The private
executor runs as host UID/GID `1000:1000`, retaining 700/600 permissions and restricted capabilities.
Focused native runtime execution then proceeded on disposable core schemas and that separate bot schema;
the migrated source databases remain unchanged. Results and remaining acceptance boundaries follow below.

Do not use `dbimport --dry-run` or `--version` for a read-only preflight: both can initialize the normal
updater. Migration testing uses one ordinary invocation against only the disposable candidate clone.
The updater's temporary client configuration can contain a password, so config, logs and temporary files
stay private and outside Git. Steady-state core updater masks and `Playerbots.Updates.EnableDatabases`
must be zero before starting game services.

#### G1 focused native runtime checks

Utility report:
`/home/ryan/wow-server-coa-g1-candidate-retry2-runtime/utilities-fcc86af716d7/results/report.json`.
Source and build: **PASSED**; gameplay and overall result: **FAILED**. `g1-artisans-summon` passed native
summon/trainer opening, Fishing/Skinning training, starter-tool delivery and duplicate-prevention checks.
`g1-furline-compat` failed in both the batch and isolated rerun: legacy cast `9931327` did not apply the
speed-bearing `91737` aura. Both bindings were present. The legacy aura's mount-interruption flag makes
it remove itself during mounting, so the copied AfterCast aura guard cannot redirect it. The candidate
now intercepts legacy effect 0 before applying that aura, then casts `91737`; its normal speed and
dismount behavior remain the regression requirements. The original failure is not a batch-only failure.

Native talent report:
`/home/ryan/wow-server-coa-g1-candidate-retry2-runtime/utilities-30971ae33f31/results/report.json`.
Source, build, gameplay and overall result: **PASSED**. All four cases passed:
`character-advancement-native-requests`, `character-advancement-native-inspect`,
`login-stock-class-advancement-state`, and `class-talent-switch-purchases-batch-4`.
Both earlier invocations used real clock and one lane, with zero container restarts. Cleanup verified removal of
their disposable core/bot schemas, private users and executors; private reports remain available locally.

Repaired six-case report:
`/home/ryan/wow-server-coa-g1-candidate-retry2-runtime/utilities-eb4dbf0b0c5d/results/report.json`.
Native gameplay detail:
`/home/ryan/wow-server-coa-g1-candidate-retry2-runtime/utilities-eb4dbf0b0c5d/results/gameplay/gameplay.json`.
Source, build, gameplay and scoped overall result: **PASSED**. Both utility scenarios and all four talent
cases passed, with the Furline and Artisans numerical checkers registered. Execution used real clock,
one lane, zero container restarts, no reruns, acceleration or batch-sensitive cases. Cleanup again verified
removal of all disposable test schemas, private users and executor. The earlier failure reports remain
unchanged; this pass establishes the repaired mount path's native contract, not human/client acceptance.

These are native scenario/checker results, not human candidate playtesting. They do not prove actual
client talent rendering, database logout/load retention, collection visuals, or grouped bot AI/navigation.
Bot AI/autologin remained disabled during these checks. The MSVC-only loot harness remains unavailable.
The added SQL subsequently passed retry3 migration acceptance and the final six-case runtime retest below.
At this earlier runtime checkpoint, client/bot regressions, fresh-install and rollback remained outstanding;
it did not make G1 complete or ready for player testing. Later qualification is recorded below.
G2 Book catalog/filtering remains deferred.
Live and the accepted current-build staging baseline remain unchanged.

The six-case runtime checkpoint already contained the Furline bindings. New pending migration
`rev_20261002_00_local_furline_compat.sql` supplies only `(91737, spell_ascension_sunwarmed_furline)` and
`(9931327, spell_ascension_sunwarmed_furline)`: its DELETE matches those exact script-name/spell-ID pairs
before reinsertion, leaving unrelated bindings intact. SHA-1: `ecad59c7931f404230d47f582597f4ee8ae7a45a`.
It does not revise an applied migration or mark itself applied without updater execution. The checkpoint's
native pass does not prove fresh-install or missing-binding repair acceptance.

#### G1 retry3: new binding migration preservation passed

Fresh `/home/ryan/wow-server-coa-g1-candidate-retry3-runtime`, project `coa-staging-g1-candidate-retry3`,
passed complete original-checkpoint restoration into another private volume/internal network with no
published ports. Its 524-table restore proof retained the unchanged dump, source/config/data/image
provenance and exact canonical saved rows for the three FLOAT tables.

One ordinary updater invocation then applied all 578 reviewed additions: auth 0, characters 10, world 568,
Playerbots 0. Final ledgers are 23 / 53 / 3,698 / 0, with every original identity/hash retained and every
new identity/hash matching its planned file. All 193 protected tables passed complete canonical-row and
schema/index preservation, allowing only reviewed name widening and three skill-633 additions. All 171
talent settings, Book model/trainer bindings and all 4,739 recipes were byte-identical; the twelve new
character tables remain empty InnoDB tables. No bot/account/character reset, updater replay or rehash was used.

Private evidence is retained in `provenance.json`, `migration-status.json` and `migration-trial/` under
that runtime. The migration status is **migrations-verified-gameplay-not-started**; the separate restore
provenance records its earlier pre-migration checkpoint rather than being rewritten. The plan's at-restore,
at-migration and current SHA-256 values agree:
`abcdd7773676eb5ffd6cdbb57ab74103e62e32f958f02f3e94e027fb89182acb`.
The source patch remains the unchanged `8085c807...` export above. The new binding's applied ledger entry
matches SHA-1 `ecad59c7931f404230d47f582597f4ee8ae7a45a` and discovery state `PENDING`; both spell bindings remain exact.

The original checkpoint already contained those bindings, so this migration proof does not establish
missing-binding repair or clean-install behavior. Retry2's six-case runtime pass remains separate;
the final six-case run against migrated retry3 also passed. Both failed trials and successful retry2 evidence
remain preserved without relabeling or replay. At that checkpoint no human candidate checklist was ready;
the later startup/endpoint qualification is separate. Live and accepted baseline remain unchanged.

Final retry3 runtime evidence is retained at
`/home/ryan/wow-server-coa-g1-candidate-retry3-runtime/utilities-df4fea65ec3e/status.json`,
with `results/report.json` and `results/gameplay/gameplay.json` beneath that same attempt directory.
Source (10 checks), build, gameplay (six cases) and the selected-scope overall result are **PASSED**.
Both registered Furline and Artisans numerical checkers passed. The run used real clock, one lane,
zero restarts and no reruns or acceleration/batch-sensitive cases. Worldserver exited successfully;
cleanup verified removal of all four disposable schemas, private users and the executor.
The report records source-state SHA-256
`8e9a1485ecd0311e72f22a4c197339029ef24f5e47037bf3c9b732e9d431bf81`
and worldserver SHA-256
`9ea581c164d3692deaf8c3f843a06b9d673cb09e438d87fbef068cfed63236e7`,
matching the migration/build proof. This focused run did not select unit/harness stages, already recorded
separately above, and does not change their unavailable MSVC result. The original migration status still
records its pre-gameplay checkpoint; it was not rewritten to represent this later runtime evidence.

The native core adds a once-per-account welcome gift and a Lumber Axe book-vendor row even with the new
book catalog module disabled. These require candidate observation and deliberate policy review before
live promotion; they are not accepted live behavior. At that checkpoint, matching native talent packets,
actual logout/login, fresh-install qualification, gameplay/bot regressions and deployment rollback remained
outstanding. The next qualification record updates the clean-install and recovery scope.

#### G1 clean-install and recovery qualification, 2026-10-02

At the player's request, all live `coa-local` services in `/home/ryan/wow-server-coa-dev` were stopped
cleanly (exit 0, no OOM or restart). No containers, volumes or data were deleted. Leave live stopped until
resumption or the separately planned deployment; this stop is not an upstream upgrade. The accepted
current-build staging realm, its source/data and migrated candidate retry3 were not replaced.

Clean-install trial `/home/ryan/wow-server-coa-g1-fresh-retry2-runtime`, project
`coa-staging-g1-fresh-retry2`, uses a new private volume/internal network and no published ports. It starts
from empty storage, not the existing checkpoint. Native `world_data.py` verified/imported the pinned
318-table `coa-world-20260912` package; its 82 covered migration hashes were reconciled by the native
bootstrap only on this new installation. Native `dbimport` then created/populated auth/characters and
applied the exact reviewed three-schema SQL union once. The saved `fresh-install-status.json` records:

- Source/build/binary/SQL pins unchanged from the qualified retry3 candidate.
- Final auth/characters/world ledger counts **23/49/3696**, with **7/29/669** native additions.
  These deliberately differ from the migrated clone's 23/53/3698 history; no historical rows were deleted
  or rehashed to force the counts to agree.
- A complete 490-table core signature; zero accounts and characters; the fourth schema initially absent.
- All 4739 original Book recipes, trainer `200001`, creature `57500` model `48501`, and G2 deferral preserved.
- Both Furline bindings were absent in the original package and installed by the narrow pending migration.
  This proves missing-binding installation, which the migrated checkpoint alone could not cover.

Core-install report SHA-256:
`29f1fc7b93f9480816502b552f5c625d0eefdd898e5464b64ed9e57419f1a19c`.

The first two empty-database trials failed before loading package SQL: UID 0 with dropped capabilities
could not access the private owner-only temporary directory, then the original build image's MySQL 8.0
client rejected the native bootstrap's `--no-login-paths` flag. Their databases were verified empty and
stopped; private volumes/logs remain preserved. The successful trial runs as UID 1000 and uses a separate
operational bootstrap image `sha256:4b6c5864074215037a32bfa31ba410ec06e213ec1cc30f60ad5acf86114f673b`.
It contains the exact MySQL 8.4.11 client from the pinned database image, SHA-256
`8206bf76fe1f72ac7deca68c4f8dcca796473f4945af72a96479aadb658f69c8`, with offline link/flag/version checks.
No safety flag was dropped. The native builder, server binary and ordinary `dbimport` executor remain
unchanged.

The separate native Playerbots bootstrap then initialized the previously absent fourth schema during
one worldserver start, with bot AI/account creation disabled, core updaters disabled, the native
Playerbots updater enabled and no authserver or published ports. It reached readiness in approximately
11 seconds. Its console observer missed the ready marker because stdout was buffered, although
`Server.log` recorded readiness durably. Root interrupted only the observer; its reviewed shutdown
handler sent a guarded SIGTERM to the exact private worldserver, which exited 0 without OOM or restart.
The original observer failure and the first post-shutdown finalization failure remain preserved.

Separate `native-finalization-retry1-status.json` qualified that same single boot after shutdown,
without a second startup or SQL replay. File and flushed console logs agree on exactly one readiness
and one shutdown marker. Exact source/build/data/configuration/isolation and core schema/index/ledger
proofs passed, along with the Book catalog/model/trainer and Furline bindings. The native fourth-schema
proof passed **30 tables, 31 released SQL identities/hashes, three updater includes, zero version rows**,
the exact self-referencing foreign key and restored foreign-key enforcement. Across all four schemas
there are **520 tables** (22 auth, 139 characters, 329 world, 30 Playerbots), with zero accounts/characters
and zero bot population/account links.

The six changed core tables were independently classified against native source: one new `uptime`
session; 48 authored outdoor map-571 NPC respawn timers; 303 missing instance reset schedules added and
71 existing schedules refreshed, with all 374 map/difficulty pairs matching qualified DBC/native rules;
three inactive-event `worldstates` clocks initialized plus ordinary event/reset-clock updates; quest
pool rotation with 38 rows retained; and the native `version` revision stamp. The respawn records match
valid authored spawns and native death/scripted-despawn persistence paths; per-NPC combat telemetry was
not recorded. No other core table changed. The first finalizer correctly stopped on the then-unreviewed
respawn table; the separate retry added its explicit source-reviewed lifecycle classification and fixed
only the temporary cleanup query's MySQL `DISTINCT` ordering, preserving every ownership/privilege guard.

The exact temporary restricted user and exited executor were removed only after proof passed; an
independent check confirmed both absent. The initialized databases, private logs and all earlier
evidence remain preserved. Finalization report SHA-256:
`10aa55de2ff197aaa5ebf3565b06605e4d3f49eed95fefa80750c5b0c3ad0e6f`.
This is post-shutdown operational qualification: there was no at-readiness SQL snapshot, client login,
bot-AI execution or gameplay acceptance. It does not convert the original failed observer result into
a successful run.

Recovery trial `/home/ryan/wow-server-coa-g1-rollback-retry2-runtime`, project
`coa-staging-g1-rollback-retry2`, links the qualified upgrade proof to restoration of the preserved
original checkpoint into another empty replacement volume. It verifies exact original dump/archive,
source/configuration/data and image pins; no reverse SQL migration or restore over an upgraded schema
was attempted. All 524 table metadata/index/count checks passed, with 521 matching raw checksums and
exact full saved INSERT-tuple multisets for only the three previously documented FLOAT exceptions
(559 homebind, 1203 character and 98138 gameobject rows). This is not a cryptographic full-row proof of
every table or bit-identical FLOAT storage. Restored ledgers are **23/43/3130/0**.

The old auth/world images then reached their ready markers and private listening sockets, remained
running for the bounded smoke interval, and shut down with exit 0/no OOM/no restarts. All update-ledger
identities/hashes, 171 saved talent rows, Book model/binding and 4739 recipes were unchanged. Schema/index
inventory was unchanged. A separate row audit classified all five post-boot checksum/count changes:
one new `uptime` session, 29 expired outdoor `creature_respawn` timers removed, 33 `instance_reset`
schedule values recalculated, 35 `pool_quest_save` daily choices replaced with the total unchanged, and
five `worldstates` clocks updated for Brewfest, BG/quest/guild daily resets and calendar cleanup.
These match the old source's startup/time-driven behavior; no other table changed. Do not claim
byte-identical database contents after normal boot. All bot,
core/module updater and remote-admin controls were disabled, and no ports were published. Evidence:
`provenance.json`, `verification/restore-canonical-proof.json` and `smoke-status.json`; smoke report SHA-256
`9096a64b30ec4576670d318c88fde666707d050cc3f76257b7683eaf12046ea5`.

Two earlier recovery attempts remain preserved: a mistyped proof hash stopped preflight before resource
allocation; the next restored data correctly but falsely rejected unordered Docker mount enumeration.
The final trial compares identical mount records in stable order, retains complete before/after private
snapshots, and still rejects any changed image, mount access, network, port, identity or running state.
Live remains stopped and the accepted staging/retry3 resources are unchanged.

This qualification proves isolated fresh four-schema installation, post-shutdown native bootstrap
qualification and original-image restoration/startup. It does not establish installer reproduction,
native client/relog behavior, bot AI, dungeon acceptance or
live endpoint failover. The repository installer still pins the older core and local patch path; do not
point that unadapted installer at the new revision. Client inspection also confirmed legacy talent
overrides embedded in staging `patch-B.MPQ`: retire only the reviewed talent loader entries, preserving
other collection, range, resource and bot-controller fixes. No client file was changed during that
qualification phase; the subsequent staging-only preparation is recorded below.
G1 remains in progress; G2 Book recipe/profession filtering remains deferred.

#### G1 staging-only native client preparation, 2026-10-02

Only `C:\Games\Ascension-WOW-Staging\Data\patch-B.MPQ` was prepared for the native candidate.
Exactly two loader members were adapted; the four legacy includes below were removed, not unrelated
collection or UI code:

| MPQ member | Removed legacy includes |
| --- | --- |
| `Interface\FrameXML\FrameXML.toc` | `LocalCharacterAdvancementBridge.lua` |
| `Interface\AddOns\Ascension_Collections\Collections.xml` | `CoATalentNodeData.lua`, `CharacterAdvancementCompat.lua`, `CharacterAdvancementStateCompat.lua` |

Loader references to `ClassInfoCompat` and embedded UI/native talent scripts remain in place. Independent archive inspection
confirmed the exact target content and archive identities, with all **1,402 unrelated ordinary members
byte-identical**. This is narrowly scoped loader retirement to prevent the old bridge overriding native
authority packets, not a wholesale client replacement or acceptance of talent rendering/persistence.
The active staging candidate archive SHA-256 is
`3973dcd6f1b38877bd7c372730b4fc2998e226f41dd6818856038539cd31bfde`.
Production retains its original `00734080...` archive pin unchanged. The original staging archive and
private rollback evidence remain retained outside Git; no client archive is redistributed here.

Private packaging/install report SHA-256:
`bc6bf2b519365558bb27ebe7df6a13a7e78c10cc2d239410d8bc5797904c3ef5`.
Independent archive-verification report SHA-256:
`2527553c506b59aace0887e6545e58b2e460ce38d9eb1182681554515bb4e82f`.
No client was launched during this preparation.

`scripts/Start-CoAStaging.ps1 -Candidate` selects only login `127.0.0.1:33726` and realm
`COA G1 CANDIDATE`, whose reserved world port is `38087`. It rejects arbitrary endpoints and production
or other client directories, using only the separate staging client. Connection backup/recovery is
unchanged; a missing candidate profile is copied once from the same account's existing staging profile,
falling back to `AzerothCore`, without overwriting or changing other profiles. All **73 synthetic fixture
checks** and PowerShell parsing passed; tests never launched the game or used real client files.

The default helper and old **COA - G1 Staging** shortcut still target the accepted baseline at login
`33725` / world `38086`. That old-core test needs the preserved legacy staging archive restored first;
the native candidate uses the new candidate-mode shortcut. Do not apply either client rollback or
candidate archive to production. The launcher/client work alone did not establish a running realm;
separate bounded startup and effective endpoint qualification subsequently passed as recorded below.
Use **COA - G1 Candidate** and the [Phase C checklist](gameplay-roadmap.md#g1-phases-and-player-testing)
for initial player testing. Actual-client and gameplay acceptance remain pending.
Staging progress is independent and must not replace newer live progress; no production promotion occurred.

#### G1 candidate bot-preparation and progression-policy gaps, 2026-10-02

Source audit found that retiring `mod-ascension-compat` also removed `.localbotprepare brewing` and the
`COA_BREWING_PILOT_NAME` name-based specialization assignment. Native specialization/ability APIs exist,
but the candidate has no equivalent combined command with the earlier bounded level-preparation guards.
Restoring that workflow and named-pilot auto-selection is pending G1 preservation work before live
promotion; preserving the bot module tree did not preserve commands implemented in the old component.

The saved `core.ascension_active_spec` value 6 still maps to the retained `coa brewing` and recovery
strategies, and native login code restores the existing selection. Actual candidate healing is untested.
The distinct operational trial preserves worldserver-only `COA_TEST_PILOT_NAMES=Amaryla`: existing GUID
3113, account 105, class 13, level 13, account type 0, saved spec 6. No level reset or spec reconstruction
was introduced. After runtime readiness/reservation is verified, initial tests can recruit this level-safe
existing pilot with `.playerbots bot add Amaryla` and inspect `/w Amaryla co ?` / `/w Amaryla nc ?`, or
invite an ordinary same-level bot. Do not send the absent preparation command or use high-level Sukpiapi
in the low-level acceptance party. Keep the 50-bot target; this is not complete all-bot/rotation acceptance.

The trial preserves effective base `Rate.XP.Kill`, `Rate.XP.Quest`, `Rate.XP.Explore` and `Rate.XP.Pet`
at 1. That does **not** preserve total XP behavior: native `Rate.XP.Global=0.9295`,
`Rate.XP.Profession=0.4` with `BaseFraction=0.02` and profession/difficulty coefficients, plus expansion
and elite multipliers are newly active, unaccepted candidate policies. Profession XP is the upstream's
provisional local formula, not verified live-Ascension parity. Validate rewards and decide these policies
deliberately before production promotion; absence of the optional Dynamic XP module does not disable
native core XP multipliers.

Player-accessible runtime preparation remains separate from the qualified no-port native bootstrap.
Its first preflight failed the strict grant parser because MySQL `--batch` double-escaped identifiers;
the actual CRUD scopes were the four intended isolated schemas. Game-critical metadata remained
unchanged and no game executor was started. The failed trial/evidence remain preserved. A distinct
retry2 passed preparation but was not started; it remains retained while another distinct retry3 adds
the world-only pilot reservation. Do not rewrite those historical outcomes or replay their SQL.
Those preparation records alone did not establish a running realm, human login, healing or gameplay
acceptance. The subsequent process-startup qualification and its endpoint limitation are recorded below.

#### G1 bounded candidate startup and endpoint qualification, 2026-10-02

The distinct human-trial retry3 started the exact qualified auth/world binaries against the already
migrated candidate databases without replaying SQL or resetting bots. Durable login-pool/world-daemon
markers, native listen sockets and six ten-second stability samples passed. Both game services had zero
restarts/OOM events and no detected SQL/updater faults. The original bounded report observed 22 online
random bots while filling toward 50; a subsequent independent read observed all 50. The original report
remains unchanged at SHA-256 `3f97cad4031321652ef477c4bb475af1884f910f0da45549cd98ece65b6ddc8f`.
Exact candidate identities/configuration, restricted four-schema CRUD grants, protected character/talent/
Book/pilot fields and schema metadata were independently checked. Live remains stopped and the accepted
old-core staging services and production client remain unchanged.

**Process readiness did not establish client reachability.** The original helper checked requested
`HostConfig.PortBindings` and native sockets, but not effective `NetworkSettings.Ports` or host TCP.
An independent Windows/WSL connection check caught null effective publications and connection refusals
at both candidate ports: the game services were attached only to the private internal backend. The
existing baseline's separate ingress network did publish its ports correctly. Preserve the successful
process/DB-startup evidence and this failed endpoint observation separately; do not label the original
`available_for_gameplay` field as actual human readiness. Candidate-only ingress and effective binding,
WSL TCP and Windows TCP qualification were therefore required before the Phase C handoff.

A distinct additive endpoint attempt then passed. Only the two exact existing candidate game containers
were hot-connected to a newly owned bridge; the database remains solely on its private backend. The
bridge disables inter-container traffic and masquerading and defaults publication to localhost. Actual
Docker bindings are now exactly `127.0.0.1:33726 -> 3724` and `127.0.0.1:38087 -> 8085`; both WSL and
Windows TCP probes passed. All other container/network/volume snapshots, protected candidate gameplay
rows, source/configuration pins and the original startup proof stayed unchanged. There were no SQL
writes, service recreations or restarts. This follows the reviewed [Docker bridge networking model](https://docs.docker.com/engine/network/drivers/bridge/),
not a global firewall, production route or WSL configuration change.

Additive Linux endpoint report SHA-256:
`9b35460fafbabdb8909118bb459ff7d56d6d50fa2a830276e614ec28ba5ba5e6`.
Separate Windows endpoint/client-archive proof SHA-256:
`bbad2a8194b44d47c1b902754b115ef15af7b47d631a62b1de4050dcabbde745`.
The reports deliberately retain separate Linux/Windows outcomes rather than rewriting the original
startup report. Both stages are now qualified for an initial human handoff, not actual login acceptance.
The candidate-only desktop shortcut is guarded by both reports and fresh Windows TCP checks; no client
was launched during preparation. Use the new **COA - G1 Candidate** shortcut.
Its post-save check initially rejected Windows-normalized target-path letter casing. Independent
verification confirmed the intended Windows PowerShell target under Windows case-insensitive path
semantics and exact candidate arguments, working directory, icon and binary hash. The saved shortcut
and original creation helper were retained unchanged; the failed check was not relabeled as passed.

The log review is not an "error-free server" claim:

- 72 LFG dungeon mappings lack area triggers, including custom content and Naxxramas variants. These
  match the separate fresh native smoke. Dungeon-finder/content acceptance remains G4 work.
- Missing wildcard configuration/default synergy messages and a denied process-priority change also
  match the fresh native smoke. A missing challenges property does not enable that unselected module.
- Ten random bots loaded invalid old skill rows: eight Darnassian (113), two Thrown (176). Native validation
  marks them for deletion on save. The race/class-mask validation also exists in the old source; this
  is real legacy bot cleanup, not proof that every bot skill row stayed unchanged.
- A focused read-only audit found all 77 saved human skill rows valid and still exactly matching the
  checkpoint (Beruwa 34, Faela 22, Kaya 21). Qualified skill DBCs match the checkpoint and the override
  table is empty. Initial isolated human login is permitted; inspect named-human load warnings and
  compare skills after the first logout before promotion.

Native references for the skill audit: `Player::_LoadSkills` in `Player.cpp:14446`,
`Player::_SaveSkills` in `PlayerStorage.cpp:7846`, and qualified `SkillLine`/`SkillRaceClassInfo` DBCs.
Bot preparation, candidate XP policies, actual client/relog behavior and grouped AI acceptance remain
open; this startup qualification does not complete G1 or authorize live promotion.

### Phase C connection correction (2026-10-02 local)

The first talent-chooser report came from `COA G1 STAGING`, not the native candidate: database online
flags, login logs and the copied client's connection settings independently agreed. The direct taskbar
shortcut reused the baseline connection after launcher cleanup. Beruwa's candidate specialization 60,
explicit talent markers, identity spell and learned spells had not changed. That screenshot did not
establish a candidate talent-state regression; use **COA - G1 Candidate** for candidate acceptance.

Correct candidate login then reproduced a separate transport defect. The client authenticated and
connected to the world port, but disconnected about five seconds later. World logs showed the plaintext
ping header `000CDC010000` being decrypted with header crypto initialized. The working baseline had
an explicit plaintext-header compatibility option that was omitted when migrating to native CoA.

The correction caches `CoA.PlaintextWorldHeaders` per connection, gated by enabled CoA compatibility
and loopback/explicit remote-client allowance. Its distributed default is 0; only the isolated matching
client trial sets it to 1. It skips header encryption initialization, not account/challenge/session-key
proof verification. Realm, account, ban, IP, security and packet validation remain unchanged;
`Cluster.Enabled=0` and all database updaters remain disabled. No client/DLL or account reset was used.

Verification and deployment evidence:

- The first harness invocation failed before test execution because its temporary mount lacked execute
  permission. After correcting only that runner prerequisite, the unchanged candidate reproduced three
  transport failures: explicit loopback/allowed-remote plaintext and cached plaintext mode; 40/43 checks
  passed. Reports `20261003-005405` and `20261003-005452` remain preserved.
- After the minimal fix, `VERIFY ALL: PASSED` in `20261003-005734/report.json`: source (10 suites),
  incremental build, the existing unit suite and `client_compat` (43/43 checks). The latter tests the
  production constructor/header-initialization decision with isolated configuration/crypto fixtures;
  it is not an end-to-end authenticated client test. Gameplay was not selected for this transport-only
  change; the earlier six socketless gameplay cases do not prove network authentication.
- Report SHA-256: `cf75c6a9dd3331e54597252ecbb7efc70c555fd930bc5eb089b00b3093358484`.
  The combined native core diff is now 19 files, SHA-256
  `e8a66c80fdd0add9ee9cc23a75d618638022c55ff07c370d817e9c57699bfa07`.
  The exported preservation patch SHA-256 is
  `cbc7e9f329de5a5cccfca573c633070808cd93d83efa9c2029240b8828b47c09`;
  reverse-application checks against the candidate passed. Earlier 14-file/source/binary pins above
  describe the prior trial, not this rebuilt binary.
- World binary SHA-256: `3d98fcf75ad4ab51da20b1de3fbdb9418c5e5316bce63c96399b497555fa58ce`.
  Auth binary is unchanged. Only the existing candidate world container was cleanly stopped/restarted,
  starting `2026-10-03T01:03:20.934469649Z`; original container identity, ports, isolation and mounts remain.
  Previous binary and configuration are retained privately for rollback. Native source/module revisions,
  qualified data, client archive, baseline and live server were not replaced.
- Post-start readiness passed; zero OOM/automatic restarts, correct localhost ports and 37 bots settling
  toward 50 were observed. Beruwa's relevant talent/settings rows and all 1,284 saved spell tuples matched
  the pre-human snapshot. No new malformed headers appeared before a user retry. Existing spell-script
  DBC and missing-SmartAI warnings matched the previous candidate boot; this is not a zero-error claim.

Actual candidate login, saved Mountain King rendering and full logout/login persistence remain pending
player confirmation. The Book's broad profession/recipe list remains deliberately preserved for G2;
the repeated observation and Furline-speed confirmation in the baseline are not native-candidate acceptance.

### Talent authority, training and bot hooks

Our accepted old-core patch records explicit paid/selectable choices in `core.coa_talent.*` and sends the
installed client bridge an allocation snapshot. Unmodified upstream derives talent state from learned
spells and uses native character advancement packets. The candidate adapts the human allocation ledger
to those native packets while retaining spellbook authority for bots. Test that protocol with the actual
staging client; automatic grants and GM-learned
spells must not silently become paid selections. Include Beruwa's existing data, reset/spec switching,
rank replacement, remaining points, and logout/login.

Upstream `CoA.AutoProgression=0` defaults to trainer-based class/rank purchases through `mod-spellbook`;
our old compatibility code grants progression automatically. Review this policy for players and bot
preparation before copying defaults. Destiny Weaver's per-character scaling also differs from our global
scaling configuration.

Merged [PR #3069](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/3069) supplies native Playerbots
hooks and a public specialization/ability API. Reconcile it with our core hook patch and COA adapter rather
than applying duplicate plumbing. The module fork linked in that PR is an evaluation candidate; neither
module replacement nor its reported large-population runs are validated for our realm. Preserve our
Brewing pilot, recruitment safeguards, talent state, healing, target cleanup, travel and riding behavior.

## Evidence required before marking a port complete

For each batch, record the issue/PR and exact included commit, dependent core/module/SQL/client/data changes,
local reproduction or overlap assessment, focused tests, in-game result, and deployment image/source pins.
Retire an overlapping local patch only after its accepted behavior is covered by the replacement.

Run relevant upstream native scenarios in isolated staging with matching data and the local regression
checks for affected behavior. Require successful combined scenario/checker outcomes, not just the
existence of a scenario file. Test a fresh installer and a migrated existing realm before promotion.

Update this snapshot and the roadmap when a new integration batch begins. Upstream issue/PR state can
change after this date; retain completed local validation records and refresh pending candidates.
