# COA gameplay improvements roadmap

Updated: 2026-10-03. G1 current-build staging baseline accepted by the player; isolated upstream candidate work is underway.
The recorded candidate source, build, unit and talent checks passed. One MSVC-only loot harness is unavailable.
Two migration regressions were caught in isolated trials; both failed clones are stopped and preserved.
The guarded candidate passed fresh retry3 restoration, all 578 migrations including the added binding SQL,
and strict character/talent/Book/bot preservation checks. All six focused native runtime cases passed on
the repaired binary in retry2, including Furline after its recorded failure, and passed again against
migrated retry3. A separate empty-database core installation and original-image recovery/startup drill
have now passed. Native Playerbots initialization and a single worldserver startup/shutdown were independently
qualified after shutdown, with the original console-observer failure preserved. The separate staging client's
legacy talent-loader includes have now been retired for native protocol testing. The candidate's bounded
startup and effective Windows/WSL loopback endpoint checks passed, with 50 online random bots observed.
Phase C player testing is underway. The generic WeakAuras range repair is accepted in staging, including
melee auras and logout/login retention. The Book/profession-tool test passed on a new character; two
level-matched bots attack, follow and use their own ground mounts. Amaryla's Brewing strategies, healing
during a rare-spawn fight with guards, drinking and post-combat following are confirmed. After the
staging-only repair, Amaryla's Furline mounting, Blossomback Arboon airborne following, synchronized
landing/dismounting and repeated combat/drink/remount sequence are player-accepted. Earlier travel
failures remain recorded below; broader bot checks and the companion-readiness batch remain pending.
The player also reports quest-earned Adventurer Caches now deliver rewards; attribution and full
reward-table coverage remain unverified.
The first reported talent-screen failure was tested on the older baseline, not the candidate. A subsequent
correct-candidate login exposed an omitted packet-header compatibility option. Its narrow repair passed
source/build/unit and 43 client-compatibility checks. Those automated checks alone do not establish
actual-client talent or logout/login acceptance.
The live server was stopped cleanly at the player's request on 2026-10-02 and remains stopped;
its source/data and the accepted baseline staging build have not been replaced.

The goal is to bring useful upstream gameplay repairs into our local server while retaining the improvements
already confirmed by players. This roadmap covers character progression, professions, collections, quests,
and dungeon behavior. Class rotations and bot population development continue in the
[Playerbots roadmap](playerbots-roadmap.md).

The [upstream audit](upstream-gameplay-audit.md) records exact revisions, the module comparison, candidate
issues/PRs, and upgrade dependencies. An upstream issue being closed is not sufficient evidence that a fix
exists, applies to our build, or has passed our local tests.

## Starting point

Our accepted old-core Playerbots build uses COA core `a8b28faac98d81b063bb81ff634037f71827d128` plus local patches and
Playerbots `619a06fc795a7220fd5c27d5a5aa4a2fbe383b72`. The reviewed upstream snapshot is
`d48a1123153a3c39e1eaafb7714b375ee67e7689`, 531 commits ahead of that core pin.

That accepted source and binary contain three modules: `mod-ascension-compat`, `mod-playerbots`, and
`mod-local-profession-tools`. Only the last is vendored in this installer repository. Upstream now places
the required COA component in `src/server/coa` and has 24 optional feature modules plus one historical SQL
directory. See the [complete module matrix](upstream-gameplay-audit.md#module-comparison).

Current gameplay regression requirements include talent-tree selections and mount/pet buttons surviving
logout/login, working Book of Artisans, automatic profession tools, Furline riding speed, Lootbot collection,
WeakAuras range triggers, and the four-resource display. Bot acceptance includes healing, following after
kills, death/recovery, mounting/dismounting, flight following, and riding at level 1. Keep the established
50-bot population stage during gameplay integration; the 1,500-bot goal has its own load-test gates.

## Recommended milestone order

| Milestone | Outcome | Status |
| --- | --- | --- |
| G1: Qualify an upstream upgrade | A pinned core/data/configuration candidate that preserves existing characters and local improvements | In progress: range, new-character Book/tools and Amaryla's repaired mount/flight sequence accepted; Cache rewards observed; remaining preservation, companion-readiness and promotion gates stay open |
| G2: Professions and service modules | Reliable profession training/tools and reviewed collection, bank, mail, and travel services | Planned |
| G3: Class and pet mechanics | Verified Primalist fixes first, followed by Necromancer and the bot pilot's class mechanics | Planned |
| G4: Questing and dungeon completion | Correct objectives, wing completion, rewards, and stable mixed player/bot parties | Planned |
| G5: Reproducible delivery and maintenance | Installer coverage, documented deployments, and a maintained upstream intake process | Planned |

## How we progress through a milestone

Work in small, testable batches rather than importing every upstream module at once:

1. Select the intended behavior and its complete source/module/SQL/data dependencies at fixed revisions.
2. Prepare the change in isolated staging, preserving the live realm and its existing local fixes.
3. Run focused automated checks and the affected gameplay/bot regressions. A failed or unavailable check
   stays visible; it is not a completed milestone.
4. Provide a short in-game test checklist with expected results. Coordinate logout only when a live
   deployment or client replacement is ready; staging preparation does not require stopping play.
5. Promote the accepted batch with a tested rollback, update the README/roadmap, and checkpoint the changes
   in Git before starting the next integration batch.

G1 supplies the shared upgrade foundation. G2-G4 then add and verify gameplay in that foundation; the
reproducibility work in G5 starts with the first batch and finishes with fresh-install/upgrade acceptance.
Keep the live population at 50 while doing this. Bot population increases and new class rotations remain
separate milestones with their own functional/performance tests.

### G1: Qualify an upstream upgrade

Use a clean checkout pinned to a reviewed commit and an isolated staging runtime. The large COA component,
talent protocol, data, and Playerbots changes make this a dependency review before a deployment. Urgent,
small fixes can still be ported to our existing pin when their complete dependencies are understood.

1. Record active source/module revisions, local patches, effective configuration, client/server data hashes,
   and applied database migration history. Classify every local customization as preserve, adapt, or retire.
2. Qualify the matching client DBC set in a separate directory. Our current repack files pass the new
   checker's 112 core-table layout checks, but miss four required startup records and several custom talent
   tables. They cannot be used unchanged with the reviewed new core.
3. Reconcile the COA component/configuration move, database table rename, SQL overlay changes, native
   Playerbots hooks, and talent-state protocol. Preserve explicit talent selections and the production client
   bridge until an equivalent path is proven with the actual client; retire conflicting loaders only in staging.
4. Test migrations against disposable copies of the existing databases and also test a fresh install.
   Qualify backup restoration and rollback of the candidate's binary, configuration, and data together.

Acceptance: the candidate starts with qualified data, imports/migrates successfully, retains existing
characters, and passes the gameplay and bot checks listed above. Source presence or an upstream author's
successful bot run does not establish acceptance on our realm.

#### Current prerequisites and remaining work

| Requirement | Preflight finding / next action |
| --- | --- |
| Reviewed source and local-fix inventory | Separate candidate checkout preserves the tested Playerbots and profession-tool modules. The 14-file integration patch includes both SQL guards, the Furline effect-step repair and new binding SQL; source/build/unit/talent checks and clean upstream application passed, but the MSVC loot harness is unavailable |
| Matching client data | Fresh original-client extraction passes 112 core layout checks, all five startup lookups and 368 file-manifest hashes; six custom talent/charge tables are present. It is separate from live data and matches the earlier original-client extractions |
| Complete recovery checkpoint | All four schemas captured and restored; 524 table layouts/indexes/counts agree, with 521 matching raw checksums and exact saved SQL-row proof for three FLOAT tables. Source/config/data and exact runtime images are preserved privately |
| Isolated staging | The first failed candidate and retry1 remain stopped/preserved. Retry2 and retry3 passed six focused checks on disposable copies, with verified test-schema/user/executor cleanup. Fresh retry3 passed complete original-checkpoint restoration and migration preservation in another private volume/network; live and accepted baseline are unchanged |
| Candidate migrations | Fresh retry3 applied all 10 character/568 world additions with exact migration identities/hashes. Final ledgers are 23/53/3698/0 for auth/characters/world/Playerbots. All 193 protected tables passed canonical row preservation, allowing only reviewed name widening and three skill-633 additions; all 171 talent rows, Book model/bindings/4739 recipes and bot data were preserved. Never replay either failed clone |
| Focused native runtime | All six cases passed on retry2's repaired binary and migrated retry3 with both numerical utility checkers registered, real clock/one lane and no reruns or batch sensitivity. See the [runtime evidence](upstream-gameplay-audit.md#g1-focused-native-runtime-checks); this is not client, relog or bot acceptance |
| Empty-database installation | Separate fresh retry2 imported the 318-table COA package and native auth/character bases, then applied the exact reviewed SQL union. Ledgers are 23/49/3696, Book recipes remain 4739 and previously absent Furline bindings were installed. Native Playerbots added 30 tables/31 exact update records, making 520 tables across four schemas. A single native startup/clean shutdown was qualified after shutdown; this is not client/bot acceptance or reproduction of the older community installer |
| Original-image recovery drill | Separate replacement storage restored the original four-schema/524-table checkpoint. Exact old auth/world images reached readiness with no ports, bots or updaters, then exited cleanly; talent choices, Book catalog and ledger identities were unchanged. This proves isolated restoration/startup, not live endpoint failover or client login |
| Native staging client and endpoint | Initial talent preparation changed two loader members and kept 1402 unrelated ordinary members byte-identical. The subsequent range-library repair is player-accepted in staging; production is unchanged and rollback retained. Candidate launcher passed 73 synthetic checks; bounded server startup, actual loopback publications and Windows/WSL TCP passed without a networking restart. Use COA - G1 Candidate; broader gameplay acceptance remains open |
| Bot preparation preservation | The old compatibility component's `.localbotprepare brewing` command and `COA_BREWING_PILOT_NAME` spec auto-selection are absent from the candidate. Native APIs exist, but no combined bounded replacement is implemented. Preserve/retest the existing saved Brewing pilot; restore these preparation safeguards before live promotion |
| Candidate XP policy | Base Kill/Quest/Explore/Pet rates remain 1 in the operational trial, but native Global 0.9295, Profession 0.4/coefficient awards and expansion/elite multipliers are newly active and unaccepted. Validate effective XP, not only the four old base settings |
| Build capacity | About 30 GiB WSL RAM and 537 GiB host disk space were available at preflight. Start with bounded build parallelism, not the upstream Docker default of 17 jobs on this machine |
| Player acceptance | Range repair, new-character Book/tools, Amaryla's combat recovery and repaired mount/flight sequence accepted on 2026-10-03. Quest-earned Cache rewards also observed. Unwanted trades, death/resurrection, remaining talent/collection checks and the expanded companion-readiness gate are not newly accepted by the travel report |

No additional hardware or client download has been identified as necessary at this stage. The data checks
above are prerequisites, not proof that the candidate starts or that every class mechanic works. Review
the checker's string/index notes and the installed client modifications during staging qualification.
No production source, database, client or server-data replacement has been performed for G1 preflight.

The candidate compiles native COA with the tested Playerbots and local profession-tool modules, plus
Destiny Weaver to retain the intended level-scaling policy. Dynamic XP, teleport-actionbar and challenges
settings in old configuration files were inactive: those modules are absent from our running binary and
are kept disabled, along with other unselected features. A configuration key alone does not establish a
deployed feature. The new Book of Artisans catalog module also remains disabled until G2 overlap review.

The first migration failure exposed an optional-table dependency. Retry1 then completed SQL execution and
exact-ledger checks, but an upstream global recipe DELETE removed 56 rows from Book trainer `200001`.
Talents, Book model/bindings and protected character data were unchanged; this is still an acceptance failure.
The second source guard preserves trainers bound to Book creature entries `57500`/`57524` without waiving
the strict preservation checks or enabling G2 catalog changes. Both source guards now pass source/build/unit
checks; fresh retry2 then passed the unchanged strict migration/preservation checks. Do not replay either failed clone.

The original Furline scenario failed in the batch and isolated rerun; the legacy aura removed itself during
mounting before the AfterCast redirect could run. The repaired effect-step path then passed together with
Book summon/trainer/tool/idempotence and all four native talent request/inspect/login-hook/purchase-switch
cases. Those runtime cases did not test actual client rendering or database logout/load. A new narrowly scoped migration
supplies both Furline script bindings; fresh retry3 restore and migration acceptance passed, preserving
the exact bindings and all earlier applied migration hashes. The original checkpoint already had those
bindings, so those checkpoint-based results alone do not prove missing-binding repair or fresh-install coverage. The final six-case
runtime retest on migrated retry3 also passed, with both utility checkers and verified cleanup.
Native talent packets must still be tested with the staging client's narrowly retired embedded old
talent loaders; disabling an addon alone was insufficient. Only the separate staging archive was changed,
and its private rollback is retained. Do not change the live client. Grouped bots,
complete fresh runtime acceptance and deployment failover remain outstanding. See the new
[clean-install and recovery evidence](upstream-gameplay-audit.md#g1-clean-install-and-recovery-qualification-2026-10-02).
The separate empty-database trial now covers installation of those initially absent Furline bindings.
The reviewed core also introduces a once-per-account welcome gift and a Lumber Axe book-vendor row.
These are visible candidate changes to review before live promotion, not accepted live policies.

#### G1 phases and player testing

| Phase | Work and acceptance | When player testing is needed |
| --- | --- | --- |
| A: Current-build recovery baseline | Restore the complete checkpoint into a separate realm using the exact current images/data; prove storage/configuration isolation and startup | Accepted 2026-10-01; profession-catalog observation deferred to G2 |
| B: Upstream candidate integration | Adapt local fixes to the pinned new COA component; test data/configuration, migrations and fresh databases; run automated regressions | After automated checks pass, receive a targeted checklist for the candidate |
| C: Candidate gameplay acceptance | Test existing and new characters, talents, professions/collections and a level-matched bot party | Test the upgraded staging realm, including logout/login and affected mechanics |
| D: Live promotion | Take a fresh live checkpoint, apply accepted migrations to the latest live state and deploy matching images/config/data with rollback | Log out for deployment, then perform a short live smoke test |

Phase A is **not an upstream upgrade**. Its accepted baseline realm is `COA G1 STAGING`, with login
`127.0.0.1:33725` and world port `38086`. The user's separate client is
`C:\Games\Ascension-WOW-Staging`; the original desktop shortcut **COA - G1 Staging** opens only that copy.
It retains the baseline endpoint; `C:\Games\Ascension-WOW` remains unchanged on the live endpoint.
Existing realm-specific profiles were copied once inside the staging client without replacing existing
staging profiles. The staging archive is now prepared for the native candidate, so restore its private
legacy archive before using that old baseline shortcut again. Never restore that archive over production.

Phase A checklist:

1. Log in on Beruwa: level, inventory, quests, professions and talent selections should match the checkpoint.
2. Check mount/companion action buttons, Book of Artisans, profession tools, Furline speed, Lootbot,
   WeakAuras range and the resource display. Log out/in and confirm saved state remains intact.
3. Invite a level-appropriate bot: check combat/healing, post-kill follow/recovery and ground/flight
   mount/dismount following. The target remains 50 online bots; this is not a population increase test.
4. Create a disposable new character if convenient and check starter items and book/profession access.
   Report failures and whether they also occur on live; do not assume a baseline clone contains new fixes.

Phase C uses the separate **COA G1 CANDIDATE** realm, loopback login
`127.0.0.1:33726` and world port `38087`. Bounded process startup and effective Windows/WSL endpoint
qualification passed; 50 random bots were observed online. Use **COA - G1 Candidate**, not the older
baseline shortcut, or run `scripts/Start-CoAStaging.ps1 -Candidate` in
PowerShell from this repository. The helper permits only `C:\Games\Ascension-WOW-Staging` in candidate
mode, restores the original connection afterward, and copies a missing candidate profile once from the
same account's existing `COA G1 STAGING` profile (fallback: `AzerothCore`). It never overwrites existing
profiles. Its 73 checks used synthetic files only, not a game launch.

The copied client's direct taskbar shortcut does not select the candidate: after the connection helper
finishes, the restored settings can point it back at the older baseline. Confirm the candidate realm
before attributing gameplay results to the upgrade. The candidate now explicitly enables
`CoA.PlaintextWorldHeaders=1` for this matching client; normal authentication checks remain enabled and
the distributed default stays encrypted. This transport correction is separate from talent persistence.

Phase C checklist:

1. Existing Beruwa: verify saved talent choices and remaining points before making changes. Save an
   intended selection, fully log out/in, and check the tree, points and learned spells. Report an empty
   tree or incorrect budget rather than resetting the build to hide a persistence failure.
2. Fresh disposable character: check starter gold/bags, Book of Ascension and Book of Artisans access,
   profession training and usable automatic tools without duplicates. The G2 catalog/filtering observation
   remains deferred; unrelated recipes are not newly claimed fixed by G1.
3. Collections and client helpers: verify mount/pet action buttons after logout/login, Furline aura/speed,
   Lootbot collection, WeakAuras range transitions, health/mana/rage/energy display and applicable spell
   charges/recovery. Confirm the unrelated client helpers still load with native talents.
4. Level-safe bot/group: invite an ordinary same-level bot, or recruit existing level-13 Amaryla only after
   the candidate's world-only `COA_TEST_PILOT_NAMES=Amaryla` reservation is verified. For Amaryla, use
   `.playerbots bot add Amaryla`, then read `/w Amaryla co ?` and `/w Amaryla nc ?`; her saved spec 6 should
   retain `coa brewing`/recovery. Check actual party healing, combat, follow/mana recovery after multiple
   kills, death/resurrection recovery, ground mounting, flight following and synchronized dismounting.
   Do not use `.localbotprepare brewing` here: it is absent from this candidate. Do not recruit high-level
   Sukpiapi into this low-level test party. Quest/item mentions must not open an unsolicited empty trade.
   Keep the established 50-bot target and automatic level resets disabled; this is not a population
   increase or full dungeon-role acceptance test. The
   [older healer workflow](playerbots-roadmap.md#level-matched-healer-milestone-initial-playtest-passed-broader-acceptance-pending)
   applies only to the accepted old-core build until candidate preparation is adapted.

Range testing on 2026-10-03 confirmed that the old spell-specific helper produced a coarse 20-yard
upper bound, which could not satisfy a 15-yard trigger even while the spell was in range. A separate
[shared COA range-library repair](../client-patches/coa-range/README.md) now discovers suitable learned
abilities and preserves tighter estimates. All 23 actual-library regressions and three integrations with
the installed WeakAuras range functions pass in Lua 5.1; the unchanged baseline fails the custom-class
discovery case. The staging-only client update was installed on 2026-10-03, with all 1,403 unrelated
ordinary archive members unchanged and the earlier talent-loader repairs preserved. The old helper was
retired recoverably, production remained unchanged, and all 26 focused checks passed against the
packaged library and installed WeakAuras range functions.
Player testing accepted the generic range repair in staging on 2026-10-03: the existing Quake melee aura
and other melee attack auras work, and logout/login preserves the improvements. This acceptance does not
claim precise arbitrary distances, replace WeakAuras, or promote client changes to production.

Current Phase C player test record:

1. **Book and profession tools — passed on a new character, 2026-10-03:** the player reports the Book/tool
   checklist worked well on a new character, covering book access, profession usability and required tool
   delivery without duplicates. This report does not establish new coverage for every existing character
   or profession. The broad profession/recipe list remains deferred to G2.
2. **Level-matched bots — partial, 2026-10-03:** the player invited Surshi (level 13) and Patka (level 15)
   while Beruwa was level 16. Both attack and follow, and use their own Tauren ground mounts rather than
   the leader's Blossomback Arboon. A subsequent test confirmed dismounting together and remounting, but
   flight following failed: after the leader took off, both remained on Kodos and followed on the ground.
   Ground mount/dismount behavior is accepted for these two bots; exact mount matching and flight following
   were not accepted in that initial test. The later repaired Amaryla sequence is recorded separately below;
   these two bots were not individually retested for flight following.

Surshi's later test confirmed attacking and drinking, but no healing while Beruwa was at about 31% health.
The player's live strategy replies contain generic `coa`, not `coa brewing` or `coa brewing recovery`;
read-only database checks also show Surshi's saved specialization is 0 (unassigned). The implemented healer
profile requires Witch Doctor Brewing (spec 6). This test therefore does not establish a healing regression
or healer acceptance. Amaryla retains saved spec 6.

The player then recruited Amaryla and confirmed `coa brewing` and `coa brewing recovery` in her live
strategy replies. On 2026-10-03, the player reported that she healed Beruwa around 80% health. Initial
healer activation and a successful heal are accepted in staging; that initial report did not identify
the exact spell, combat state, emergency thresholds or full rotation. In a subsequent rare-spawn fight
with guards, the player confirmed healing, drinking and following after combat, but Amaryla did not mount.
Combat healing and post-fight recovery/following are accepted for that encounter. Her initial mounting failure
was subsequently repaired and retested; it does not invalidate Surshi and Patka's separate ground-mount results.

Read-only checks show Amaryla online at level 13 with saved Riding 300/300 and all five riding spells.
Her saved spell rows lack Blossomback Arboon (900125) and native Furline (91737); this is not proof of her
complete live mount spellbook or cast eligibility. The player's subsequent `do check mount state` test
returned `failed` twice, with Amaryla nearby at full mana and Beruwa on Sunwarmed Furline. The action was
recognized and passed its initial usefulness/possibility gates; execution did not succeed. This is not
uniquely proof of a cast error, because execution also checks leader and attacker state.

Source comparison identifies an acquisition gap: the candidate excludes bots from both collection-mount
grant paths, while the accepted old build included them. The normal Playerbots factory also skips racial
mount initialization for COA classes. Riding training alone therefore does not supply usable mounts.
A bounded mount-only acquisition and grounded takeoff/reselection repair is now rebuilt and restarted
in the candidate, without randomizing Amaryla, changing her role/build, granting unrelated companions
or bypassing native cast/location restrictions. The baseline method test failed before the repair and
passed afterward; the four focused real-clock native cases and source/build/unit/harness checks passed.
The current saved state was copied only into an isolated test database, and saved human/pilot state,
configuration, other services and migration ledgers were preserved. The
[bot mount repair record](playerbots-roadmap.md#candidate-mount-repair-verification) distinguishes
automated results, retained qualification-wrapper failures, native-only patch exports and player acceptance.

Remaining bot checks include quest/item messages without unwanted trades and death/resurrection recovery.
On 2026-10-03, the player confirmed Amaryla's automatic Furline mounting and Blossomback Arboon airborne
following, then accepted the requested sustained flight, synchronized landing/dismounting and repeated
combat/drink/remount tests. This closes the tested Amaryla travel regression. It does not establish every
healing spell, emergency threshold, class or party role.

The player also reports that Adventurer Caches earned from quests now grant rewards in the candidate,
where production allowed looting without delivering items. Record this as a successful player observation,
not attribution to a particular upstream commit or exhaustive container/reward-table acceptance.

These player results do not declare all G1 integration and promotion gates complete.

The player requested stronger bots before production promotion. The
[companion-readiness gate](playerbots-roadmap.md#companion-readiness-before-production) adds a bounded
healer, tank and damage-profile batch with repeated questing/group combat and a small dungeon test.
This work remains in the candidate at 50 bots; all 70 specializations and the 1,500-bot capacity goal
are not prerequisites for this first playable party. Production promotion waits for the agreed slice
and the existing preservation, XP-policy, delivery and recovery requirements.

The native login code restores the named pilot's saved specialization, and the initial player healing
check passed, but complete bot feature preservation is not established. The bounded level-preparation
command and name-based spec auto-selection removed with the old compatibility component remain pending
G1 work before live promotion.
The operational trial also keeps only the old base XP rates unchanged; native global/profession and
expansion/elite multipliers are newly active candidate policy and need deliberate review and playtesting.

Staging has independent character progress: gains, resets and new characters made there are not transferred
to live. Client preparation is staging-only, not production promotion. Never promote staging databases
over newer live progress. Leave the private recovery checkpoint
and its credentials outside Git. The current-build restore/startup checks are recorded in the
[audit](upstream-gameplay-audit.md#g1-current-build-recovery-baseline).

### G2: Professions and service modules

Prioritize `mod-book-of-artisans` and the merged starter-tool usability/racial fixes in
[PR #5379](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5379). Upstream book training supplies
six basic tools; our module adds broader profession coverage, all-trainer hooks, login recovery, compatible
tool recognition, and bot exclusion. Consolidate the overlapping supplier behavior before enabling both.

Keep the local profession-tool behavior until its replacement meets the same requirements. Check training
through both books and other trainers, existing professions on login, banked/upgraded tools, full bags,
mail delivery where applicable, and repeated training/login without duplicates. Confirm that low-level
characters can actually use supplied tools.

Review Book of Ascension, bank companions, item recovery, portable mail, and travel modules next. Each module
needs its core API, SQL, script registration, configuration, and client interface reviewed together.

Acceptance: new and existing characters can summon/use the books, learn supported professions/ranks,
receive usable tools, and retain their skills and collection buttons after relog. Document deliberate
changes to trainer recipes, class-spell purchases, scaling, or XP policy before deployment.

The [recipe expansion proposal #5899](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5899)
was unmerged at audit time. Track it separately from the implemented book module.

#### Player-reported profession catalog follow-up

During the accepted G1 baseline test on 2026-10-01, the player observed that Book of Artisans displays
recipes for professions the character has not learned and continues to present all professions as learnable.
This is a reported catalog/trainer-state issue, not a confirmed loss of learned skills, and was explicitly
deferred to G2. No trainer SQL or gameplay behavior was changed for this observation.
The player repeated the observation on 2026-10-02 while still connected to that baseline. The candidate
also deliberately preserves the broad catalog; profession-aware filtering and known-recipe presentation
still require G2 reproduction and acceptance, including already learned professions and recipes.

For G2, inspect the book's effective trainer rows and the server's skill/rank eligibility checks. Verify that
recipe availability respects learned professions and required skill/rank; already learned profession ranks
must not be offered as new purchases. Keep genuinely unlearned professions distinguishable from learned ones,
with availability governed by the realm's intended profession policy rather than silently hiding everything.
Test existing and new characters, repeated book use and logout/login, while preserving automatic tool delivery.

### G3: Class and pet mechanics

Start with mechanics relevant to current playtesting, in small batches with observable expected results:

- Primalist: enhanced Boons/Primal Convergence, Wildwalker Mend Animal Spirit acquisition and pet healing,
  then Mountain King damage, defensive effects, resource costs, and talent-derived bonuses.
- Necromancer: summoned-minion cleanup after talent removal/spec changes and preservation of unrelated summons.
- Witch Doctor Brewing: validate underlying healing spells, rank acquisition, resource costs, and targeting
  before expanding the bot's healing priority and movement decisions.

The [candidate list](upstream-gameplay-audit.md#initial-candidate-list) links merged implementations and their
named native scenarios. Reproduce the local discrepancy first: some reported mechanics already work and
should become regression cases rather than new patch claims.

Acceptance: the intended spell/pet mechanic works with the installed data and client, persists or clears
correctly across talent/spec changes and relog, and preserves our talent selection/point accounting.
Complete this foundation before building bot rotations that depend on it.

### G4: Questing and dungeon completion

Review the merged [wing final-boss mappings #5164](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5164)
against our world rows, migration history, and `DungeonEncounterExtra.dbc`. Begin with one accessible classic
dungeon and a level-matched group; then cover additional wings and quest chains in small content batches.

Test quest acceptance/prerequisites, shared objectives, boss death credit, Dungeon Finder completion,
reward delivery, loot, and leaving/re-entering the instance. Use ordinary encounters for acceptance; killing
a full-health boss through a GM shortcut does not establish native completion behavior.

Treat reward proposal [#5916](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5916) and area-lock
proposal [#5914](https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/5914) as separate review items.
Region-lock defaults and race-start changes require a deliberate realm policy compatible with levels 1-80.

Acceptance: a full party can complete a selected dungeon with correct objectives/rewards and usable bot
combat roles. Record unexpected bot damage, movement failures, deaths, and server performance alongside
the content result. This gameplay milestone does not by itself qualify a population increase.

### G5: Reproducible delivery and maintenance

Update the installer and patch checks for the accepted source/module/data pins, COA configuration names,
module SQL discovery, and optional feature selection. Cover both fresh installations and existing-server
upgrades; our current installer creates a new runtime rather than updating one in place.

For each accepted batch, update the README's player-facing behavior and this roadmap's status. Keep the
issue/PR, included commit, dependency files, local comparison, test results, deployment revision, and any
retired local patch in the audit. Add the relevant gameplay checks to the repeatable regression set.

Acceptance: a fresh installation reproduces the tested behavior, an upgrade preserves existing state,
and community documentation clearly distinguishes planned, staged, deployed, and player-confirmed changes.

## Keeping the roadmap current

Review upstream against a new immutable snapshot when starting an integration batch. Recheck open PRs at
that point and follow dependencies/related fixes; issue status and commit titles alone are insufficient.
Prioritize locally reproduced player problems, shared character-state regressions, class mechanics used by
the current bot pilots, and dungeon blockers before optional economy/endgame features.

For a community test report, include our repository/source revisions, data provenance, character class,
spec and level, reproduction steps, expected/actual results, and relevant logs with credentials removed.
Record a failed test as pending work instead of promoting the feature to confirmed status.
