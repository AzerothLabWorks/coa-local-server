# COA Playerbots development plan

Shared gameplay foundations and upstream source/module integration are tracked in the
[gameplay improvements roadmap](gameplay-roadmap.md). Its class, talent, profession, and dungeon checks
also apply to bots before expanding their rotations or treating an upstream upgrade as accepted.

The open-source Playerbots module is the runtime. The repack's `CoA-Bots` package
contains a compiled worldserver, not a patch we can merge, but its
`Dashboard/coa-level-builds.json` provides 70 class/specialization profiles across 21 classes with
spec IDs, intended roles and level-by-level talent picks. Ascension Sidekick is
useful for human-readable build and spell-priority guidance. Neither source is
an executable server implementation. Spell IDs, ranks, targets and effects must
be checked against the installed COA `Spell.dbc` and the server scripts.

## G1 candidate player testing

On 2026-10-03, the player grouped level-13 Surshi and level-15 Patka with level-16 Beruwa in staging.
Both bots attack, follow and use their own Tauren ground mounts. This is partial candidate acceptance,
not confirmation of matching the leader's mount. A subsequent test confirmed dismounting together and
remounting, but both bots stayed on Kodos and followed on the ground when Beruwa flew on Blossomback
Arboon. This initial failed G1 travel regression is retained as history; the later repaired Amaryla
sequence below has now passed player testing.
Surshi subsequently attacked and drank but did not heal the injured leader. Live strategy replies lack
`coa brewing`/`coa brewing recovery`, and her saved specialization is 0 (unassigned). The healer profile
requires Witch Doctor Brewing (spec 6); Amaryla retains that saved selection. This is an unconfigured-healer
test, not a confirmed healing regression. The player then recruited Amaryla, confirmed both Brewing
strategies in her live replies, and observed her healing the leader around 80% health. Initial healer
activation and a successful heal are accepted in staging. A subsequent rare-spawn fight with guards
confirmed healing, drinking and post-combat following, but Amaryla did not mount. Those combat/recovery
checks passed for the encounter; her initial mounting failure was subsequently repaired and retested. This does not confirm every spell,
emergency threshold, full rotation or repeated-cycle behavior. Unwanted-trade suppression and
death/resurrection recovery remain to be checked.
Keep the 50-bot target; this does not qualify a population increase or dungeon party.
The [G1 player test record](gameplay-roadmap.md#g1-phases-and-player-testing) retains the candidate's
preparation/promotion boundaries; older pilot commands below are not automatically available there.

Read-only investigation found that the candidate excludes bots from collection-mount grants, whereas
the accepted old build included them. Both test bots retain riding 300/300 and the riding spells, but
their saved spell records lack Blossomback Arboon (900125). The shared mount-copy action requires the
bot to know the leader's mount spell; fallback can choose a Kodo, and an already-mounted bot does not
reconsider that choice when the leader takes off. This makes lost mount acquisition the likely cause,
not a proven live spellbook/cast result. Confirm live eligibility and restore a bounded bot mount path;
do not globally unlock Azeroth flight or grant every collection indiscriminately.

Amaryla's subsequent mounting report is a separate failure: she remains on foot, unlike the two bots
that chose Kodos. Read-only saved records show Riding 300/300 and all five riding spells on her online
level-13 character, but lack Blossomback Arboon (900125) and native Furline (91737). This does not identify
every live mount option. Mount logic has no Brewing-specific exclusion, and drinking channels can block
casts. The subsequent screenshot shows `check mount state: failed` twice with Amaryla nearby at full mana
and Beruwa on Furline. The action was recognized; do not treat `failed` as uniquely proving a cast error.
The ordinary factory also skips `InitMounts()` for COA classes, so riding grants are not a racial-mount
fallback. A staging-only repair now supplies one requested eligible catalog mount without randomizing
the reserved pilot, resetting her build, granting unrelated companions or bypassing native cast/location checks.

### Candidate mount repair verification

On 2026-10-03, the candidate was rebuilt and the same worldserver restarted after the player logged out.
The repair learns only a human leader's requested mount for an eligible grouped COA bot, subject to the
bot's own collection ownership or the existing unlock-all policy. Riding training alone no longer leaves
a mountless follower stranded. The native Furline alias remains supported; unrelated pets and books are
not granted by this path. Ground-mounted followers can reconsider the leader's flying mount at takeoff.
The upgrade keeps native location/casting restrictions, refuses unsafe airborne or combat dismounts,
and suppresses repeated failed swaps until the leader changes mount or dismounts.

The baseline method regression failed before the repair and passed afterward. Focused source checks,
build/unit checks, mount-travel and actual-service ownership harnesses, and existing talent/client harnesses
passed. Four real-clock native cases passed: requested bot mount acquisition, Furline, Artisans, and native
talent requests. They verify single-spell acquisition, idempotence, refusal controls, real casts/dismounts
and preserved build observations; socketless tests do not establish autonomous flight or client behavior.
There were no native failures, isolated reruns, or acceleration/batch-sensitive cases in this selection.

The current candidate's four-schema snapshot was restored only into a private test database. Exact
serialized row comparisons qualified ten FLOAT-table checksum differences; no candidate rows were restored
or altered. A broad post-test Docker snapshot comparison failed after native tests passed; its evidence is
retained. Independent checks confirmed the executor's isolation/security, unchanged candidate state/config,
other services, and disposable-test cleanup. Human spells/actions, Amaryla's level-13 spec-6 build and
account reservation, and migration ledgers remained unchanged across the candidate restart.

Startup completed in 30 seconds, both localhost endpoints were reachable, and the population reached
50 online random bots. The private test database was shut down after qualification; its volume and
verification evidence are retained. Live production and the client are unchanged. The native-only follow-up patches
are `source-patches/coa-g1-bot-mounts.patch` and `source-patches/playerbots-coa-native-mounts.patch`.
They follow the frozen G1 preservation patch and the already-qualified nine-patch Playerbots stack,
respectively; the legacy installer is not upgraded by these exports.

Player acceptance passed on 2026-10-03: Amaryla mounted on Furline, then matched Blossomback Arboon and
followed in flight. The player subsequently accepted the requested sustained-flight, synchronized
landing/dismounting and repeated combat/drink/remount sequence. This closes Amaryla's tested travel
regression; it is not acceptance of every bot, specialization or dungeon role.
Quest/item trade suppression and death/resurrection recovery remain separate open checks.

## First vertical slice: Witch Doctor Brewing

The first staged profile reads the server's `core.ascension_active_spec` player
setting. Witch Doctor spec 6 is Brewing in the repack catalog. When that spec is
selected, the bot is classified as a healer and uses a small healing priority:

1. Below 40% health: Spirit in a Bottle.
2. Below 65%: Potion Toss if available.
3. Below 80%: Loa's Brew.
4. Otherwise retain the existing offensive spell selection.

These spells and their rank ranges were checked against the installed COA
`Spell.dbc`. The action heals nearby, line-of-sight group members, including a
human GM group leader; it also tops off outside combat. This is an experimental
priority, not a claim that the full repack healer AI has been reproduced.

Randomly generated bots normally have **spec 0**. An opt-in pilot now selects
Brewing for one exact Witch Doctor bot name on login, only if it is a bot with
no selected spec. Set `COA_BREWING_PILOT_NAME` in the runtime `.env` to choose
the pilot; leave it empty to disable new pilot selection. The switch uses the
COA class service, which validates the spec and grants missing progression
spells. It does not alter human characters or overwrite an existing bot spec.
On the local test realm, `Sukpiapi` was selected and saved as spec 6.

## Development and validation order

The class-AI sequence below remains separate from the population capacity
milestone. The requested population ramp can proceed in parallel after its
safeguards are deployed; it does not certify the additional bots for dungeons.

1. Prepare a dedicated, level-matched Brewing pilot; preserve the existing
   high-level `Sukpiapi`. Test healer role, in-combat emergency heal,
   out-of-combat top-off, GM leader healing and damage-spell fallback. Keep the
   online population at the established 50-bot stage during candidate testing.
2. Generalize the bot-only selector from one named pilot to a reviewed
   class/spec distribution using the same class-service switch. Preserve a
   bot's chosen spec across logins and never touch human characters.
3. Add a tank profile, starting with Primalist Mountain King (class 31, spec 60):
   threat/taunt, defensive cooldown, positioning and survival tests. Then add a
   simple DPS profile with a measured spell priority and resource constraints.
4. Drive gear and level-by-level talent picks from reviewed profile data, not
   raw JSON at runtime. Add interrupts, dispels, group buffs and AoE only after
   the three core roles pass group testing.
5. Run an easy five-player dungeon with one human plus tank, healer and two DPS
   bots. Record deaths, heals, damage, threat switches, stuck movement, CPU and
   memory. Recheck these behaviors under the population levels reached below.

## Companion readiness before production

On 2026-10-03, the player requested a good working companion party before G1 production promotion.
Use a bounded role-based batch rather than requiring all 70 specializations. Keep the candidate at
50 bots with levels 1–80, automatic resets disabled, and Amaryla's saved level, spec and account reservation
preserved. No new reference source, rotation SQL, repack executable or population setting has been deployed.

1. Restore the bounded preparation and named-pilot selection safeguards lost with the old compatibility
   module. Preserve existing builds and human talent allocations; repeated preparation must be idempotent.
2. Improve Witch Doctor Brewing first: prefer urgent party healing over offensive casts, check emergency
   healing, out-of-combat top-off, range/line-of-sight recovery, mana conservation and repeated
   combat/drink/follow/remount cycles at the player's level. Existing successful heals are the baseline,
   not proof of all support logic.
3. Qualify one Primalist Mountain King tank and one simple damage profile using reviewed known ranks,
   targets and resource-aware priorities. Test threat/taunt, defensive use, positioning and preserved builds.
   Select the damage specialization after reviewing actual low-level abilities; do not label a generic
   attacking bot as a validated damage rotation.
4. Playtest ordinary questing and repeated multi-mob combat, unwanted-trade suppression and death/recovery.
   Then run an easy five-player dungeon with one human, a tank, healer and two damage bots. Record
   survivability, heals, threat, stuck movement and responsiveness; repeat key checks after relog and level-up.
5. Promote only when that playable slice and the other G1 preservation, XP, delivery and rollback gates pass.
   Broader classes, advanced raid AI and the measured 100 → 1,500 population ramp remain later batches.

### Reviewed bot references

The [Zyth COA fork](https://github.com/Zyth45/mod-playerbots/tree/36c4b93ae0688c19e6baa718f296302071ae30b3)
was reviewed at `36c4b93ae0688c19e6baa718f296302071ae30b3` on 2026-10-03. Its
[specification table](https://github.com/Zyth45/mod-playerbots/blob/36c4b93ae0688c19e6baa718f296302071ae30b3/src/Ai/Coa/CoaSpecStrategies.h)
covers 21 custom classes and 70 specializations. Its
[AI implementation](https://github.com/Zyth45/mod-playerbots/blob/36c4b93ae0688c19e6baa718f296302071ae30b3/src/Ai/Class/Coa/CoaAiObjectContext.cpp)
provides spell classification, known-rank selection, mana reserves and urgent support behavior worth
evaluating for the healer-first batch. The required specialization APIs exist in our native core, but
combined build/runtime compatibility has not been established.

The fork is 219 commits ahead and seven behind our module pin, touching 131 files in the reviewed
[comparison](https://github.com/Zyth45/mod-playerbots/compare/619a06fc795a7220fd5c27d5a5aa4a2fbe383b72...36c4b93ae0688c19e6baa718f296302071ae30b3).
It changes paths occupied by our local fixes. Its recruitment can randomize a level-mismatched bot and
its auto-spec selection can replace a selection lacking its own manual-spec marker. Its configuration
also enables fresh starts/level redistribution and defaults to 500 bots at levels 1–60. Do not copy those
policies or replace the module wholesale. Preserve our pilot, human state, population and travel safeguards.
Ports must retain the upstream GPL notices and attribution.

The [COA spec site](https://river.seedhost.eu/zyth/coa-specs/?lang=en) is useful build and benchmark guidance,
not local acceptance evidence: its level-60 measurements do not establish behavior for our low-level pilot,
host or party. Pin the source/data consulted for each proposed profile and verify spell IDs, targets,
ranks and effects against our own data. Dataset reuse terms have not been established.

The supplied `CoA-Bots-v1.7-main-20260930` repack records core
`df4dea11a0f54f33a942a8292540f53071262d21` and module `36c4b93a`, different from our candidate recipe.
Its `CoA-Bots/Tools/Dashboard/coa-level-builds.json` has 70 profiles and 3,564 picks; some profiles have
missing or repeated levels, so it is review input rather than a ready-to-apply progression policy.
The three files under `CoA-Bots/Database/playerbots/custom` provide 71 authored strategies and 2,544
base rules plus corrections. They depend on matching fork actions/triggers; SQL alone cannot supply AI.
Several deletes/updates lack an owner filter despite comments promising personal-row preservation,
and the base strategy schema begins with `DROP TABLE`. Never import these files wholesale. Any selected
rows require bounded migrations, custom-owner preservation, repeat-application and rollback tests.
The local repack supplies no C++ server source or rotation generator. Do not launch or deploy its compiled
runtime as an integration shortcut, and review generated-data provenance before redistribution.

The UnBot bar is a client-side command interface from the repack. It can keep
controlling standard Playerbots commands; it does not supply the missing AI.

## Population milestone: 1,500 concurrent COA bots

The local target is **1,500 bots online simultaneously**, with a mix of levels
1–80. This is a capacity goal, not a tested limit or a new installer default.
The starting baseline is 12 online bots, 120 generated accounts, and 1,200
saved characters: only 200 characters on 20 accounts are COA classes. Preserve
the 1,000 older classic characters; COA-only login excludes them from capacity.

Increase in measured stages: **50 → 100 → 250 → 500 → 750 → 1,000 → 1,250 → 1,500**.
At each stage, verify actual online count, faction/class/level mix, startup
warnings, restarts, memory/swap, world update latency, and responsive combat
and following with a real player. A short startup check is not a long-running
stability test. Stop increasing when latency, memory pressure, or bot errors
regress; do not compensate by weakening AI until the cause is understood.

The pinned core supports multiple socketless bot sessions per account. A full
account normally holds ten characters, but classic-only and reserved accounts
must be excluded from the eligible pool. Automatic account sizing counts old
classic accounts too, so it is insufficient for this migrated realm. Expand
COA account capacity gradually, with spare candidates beyond the online target
and explicit protection for named test companions. Do not delete/recreate the
existing account pool to reach a count.

Before the first increase, the pilot-account reservation patch must be built
and deployed. `COA_TEST_PILOT_NAMES` protects the whole generated, currently
unassigned account containing an explicitly named COA companion from automatic
roaming-pool and add-class-pool assignment. It does not demote accounts already
assigned to either pool or change human accounts. In this realm, Amaryla's
account must remain unassigned; Sukpiapi remains in the existing roaming pool.
With one reserved COA account and 100 preserved classic accounts, 251 total
accounts is only the theoretical minimum for 1,500 eligible characters; allow
additional headroom for protected characters and roster selection.

Runtime controls exposed through `.env` and Compose:

| Setting | Installation default | Purpose |
| --- | --- | --- |
| `COA_MIN_RANDOM_BOTS` / `COA_MAX_RANDOM_BOTS` | 12 / 12 | Requested online population. |
| `COA_RANDOM_BOT_ACCOUNT_COUNT` | 120 | Account pool; includes preserved classic accounts. |
| `COA_BOT_MIN_LEVEL` / `COA_BOT_MAX_LEVEL` | 1 / 80 | Native level-roll bounds, not rescaling of existing bots. |
| `COA_BOT_RIDING_MIN_LEVEL` | 1 | Minimum for all four bot riding tiers; flight-zone restrictions remain. |
| `COA_BOT_AUTO_TRADE_ON_ITEM_MENTION` | 0 | Stops item mentions from opening a bot trade; explicit trade commands still work. |
| `COA_BOTS_PER_INTERVAL` | 60 | Manager batch limit; use smaller batches during ramp tests. |
| `COA_BOT_STATS_INTERVAL` | 300 seconds | Periodic population statistics. |
| `COA_WORLD_STATS_INTERVAL_MS` | 300000 ms | Interval for slow-world-update logging. |
| `COA_WORLD_SLOW_TICK_MS` | 100 ms | Log threshold; silence does not provide latency percentiles. |

The first stage uses 50/50, the existing 120 accounts, a batch limit
of 5, bot statistics every 60 seconds, and world timing checks every 60000 ms.
Back up before applying a stage, retain the previous worldserver image and runtime
settings, and verify that Amaryla's account remains unassigned with her level
and specialization intact.
Preparation checks passed on 2026-09-27: the complete module patch chain applies
to the pinned revision, installer fast checks pass, and the COA regression suite
passes against an isolated patched module. Reservation tests execute the actual
assignment function, including the first-50 pool and 1,500-slot account arithmetic.
These checks do not substitute for a worldserver build or live load testing.
Startup has accelerated manager cycles, so a batch of five does **not** mean
only five logins every 20 seconds. `.server info` provides rolling update-time
statistics for a GM; Docker CPU/memory alone cannot establish responsiveness.

Observe stabilized stages for at least 20–30 minutes, including a populated
zone and grouped combat; larger stages need longer checks. Initial acceptance
targets are mean world updates below 50 ms, p99 below 100 ms, no growing work
queues or sustained swapping, and at least 20% memory headroom. These are test
gates, not measured host limits. Hold on repeated 200 ms spikes, new restarts,
or noticeable gameplay lag. Record active as well as online bots: idle distant
bots are throttled, so a full online roster alone does not prove combat capacity.

First-stage deployment on 2026-09-27: the worldserver was rebuilt and restarted
at 22:39 UTC; authentication and database services were not restarted. It reached
50 online COA bots across all 21 custom classes, with 23 Alliance and 27 Horde
characters and levels spanning 1–80. Amaryla remained offline, account type 0,
level 13/spec 6, without a random-population add event; Sukpiapi retained level
79/spec 6 in the roaming pool. A console sample at 3 minutes 36 seconds uptime reported
1 ms mean, 5 ms p95, and 6 ms p99 world updates (last 500 samples). No new startup
diagnostic signatures or container restarts were observed. Later first-login
initialization samples reached 2 ms mean, 18 ms p99, and a 153 ms maximum;
worldserver memory was approximately 5 GiB. These are initial
checks only: extended gameplay, group combat, and a sustained-load soak remain
pending before increasing to 100.

Image: `sha256:2122624477c47a73d5383a42fb6a12741413bfcf06531f9fe6c6a1e1f8943aa3`.
Rollback image: `coa-local/worldserver:pre-population50-20260927`.
Runtime settings and a consistent auth/character/playerbots dump are retained in
`/home/ryan/wow-server-coa-dev/state/backups/pre-population50-20260927.mjMXSy`.
No SQL migration was introduced. To undo the population rollout, stop only the
worldserver, restore the previous runtime settings and image, then start it;
do not restore the database dump over newer player progress as a routine rollback.

Keep `LevelBrackets.Enabled`, `ResetBotLevel.Enabled`, and
`DowngradeMaxLevelBot` disabled. Stock redistribution performs full bot
randomization and can reset progression-related state; it is not a safe
selection-only population balancer. Initially retain native randomized levels
within 1–80. Later exact bracket quotas need a durable initialization marker,
protected-pilot handling, and selection-only weighting of existing candidates.
An absent expiring bot event or a character being level 1 is not proof that it
has never been initialized.

Population expansion is separate from dungeon readiness: the Brewing healer
pilot works in the tested cases, while tank AI, broader rotations, reviewed
talent/gear builds, interrupts, dispels, and dungeon acceptance remain pending.

### Level-one riding follow-up

Surshi's September 29 playtest confirmed combat and post-kill following, but
mount checks returned `useless` despite an enabled mount strategy. Stock bot
skill maintenance cleared Riding (762), which also removed its associated
riding spells, then refused to relearn the ranks below the default level-20
threshold. Both refresh and ordinary roaming-bot level-up maintenance could
reach that path; a prepared companion did not exercise the same lifecycle.

The follow-up keeps COA skill ownership with the compatibility/progression
module, which already grants riding 300 and Cold Weather Flying on login through
`AscensionCompat.MaxRidingFromStart = 1`. Stock skill initialization now leaves
COA skills intact. `COA_BOT_RIDING_MIN_LEVEL=1` sets all four Playerbots riding
thresholds to level 1, covering roaming as well as grouped bots. Classic bots
under this explicit all-four-thresholds-at-1 policy also preserve riding during
maintenance and learn missing Cold Weather Flying; other classic configurations
retain their previous behavior. No global Azeroth flying permission is enabled.

Tests execute the actual skill-initialization function and mount-usefulness
checks, including COA classes, classic thresholds, repeated maintenance, Cold
Weather Flying, and level-one roaming bots. Combat, indoor, flight-zone and
native cast restrictions remain. After deployment, retest Surshi mounting and
dismounting with the leader, then repeat after a kill and a level-up. Bot count
stays at 50 until this regression is accepted.

Deployed on 2026-09-29 at 23:01 UTC after the full native worldserver build,
pinned patch-chain checks, installer checks, production-function regression
tests and independent review passed. Only the worldserver was restarted;
authentication and the database stayed running. All 50 bots returned across
the 21 COA classes. Saved-state checks confirmed Riding 300/300 and all five
riding spells (33388, 33391, 34090, 34091, 54197) on every online bot, including
level-13 Surshi and three bots observed at level 1 during startup. Offline bots
receive the existing login grant when they next enter the world. Amaryla stayed
offline and reserved on account type 0, level 13.

At 3 minutes 48 seconds uptime, the last 500 world updates reported 4 ms mean,
11 ms p95, 21 ms p99 and 64 ms maximum. An earlier startup sample had a 230 ms
maximum; these short samples are not a sustained-load acceptance test. The
container had zero restarts and no OOM event. The log comparison found one new
content diagnostic: Eye of Dar'Khan (creature 16320, spawn 8074) has no waypoint
path (id 0), logged twice. Its patrol initialization returns without starting a
path; track this separately from the riding repair. No crash/assert/deadlock or
bot-account-shortage signatures were observed. In-game mounting, dismounting,
post-kill following and post-level-up riding still require player acceptance.

Image: `sha256:36494982b8154124f8de0e027afbd0929f90111454463c77e50d1cacfb708468`.
Rollback image: `coa-local/worldserver:pre-riding-level1-20260929`.
Runtime settings, the previous log and a consistent auth/character/playerbots
backup are retained in
`/home/ryan/wow-server-coa-dev/state/backups/pre-riding-level1-20260929.LPFhOU`.
The installer includes the riding-preservation patch and level-one setting.
No SQL migration or client patch was needed. A routine rollback uses the saved
worldserver image and settings, not a database restore over newer progress.

### Quest sharing and unexpected trade windows

During group questing, Surshi (level 13) reported `Can't take [Tribes at War]`
while Beruwa accepted the quest. The local quest template sets minimum level 14
for `Tribes at War` (ID 878), so that refusal is expected until Surshi reaches
level 14. It is separate from the empty trade window in the screenshot.

The Playerbots chat parser's enabled automatic item-mention path sends both an
inventory query and a trade command; the trade command can open the window
before finding any matching item. This path is consistent with Surshi's
`=== Inventory ===` whisper and empty trade window, although the exact chat
message that triggered it was not captured. The realm now defaults
`COA_BOT_AUTO_TRADE_ON_ITEM_MENTION=0` to suppress these implicit trades.
Explicit player trade commands remain available. Retest quest acceptance and
normal manual trading in game after the config-only worldserver restart.

Deployed on 2026-09-30 at 22:49 UTC by restarting only the worldserver with the
existing image. Compose rendered `AC_AI_PLAYERBOT_ENABLE_AUTO_TRADE_ON_ITEM_MENTION=0`,
and the worldserver log confirmed that Playerbots read this environment override.
Installer fast checks passed. All 50 bots returned across the 21 COA classes,
including Surshi at level 13; container restarts and OOM events stayed at zero.
The startup audit found no new severe warning or error signatures. Runtime
settings, the prior log and a consistent database backup are retained at
`/home/ryan/wow-server-coa-dev/state/backups/pre-auto-trade-off-20260930.kozAnS`.
The initiating chat or addon message was not captured, so the in-game no-popup
result still needs the player's confirmation.

## Level-matched healer milestone (initial playtest passed; broader acceptance pending)

The next slice adds a guarded, explicit test-companion workflow, not automatic
rescaling of the world population. Keep the existing 12 autonomous bots while
testing one additional controlled healer. Tank AI, dedicated DPS rotations,
talent allocation and level-appropriate gear builds remain separate work.

- `COA_TEST_PILOT_NAMES` is an empty-by-default allowlist of exact bot names.
  It permits the existing GM bot-add command for eligible generated test bots;
  it is not an account-ownership bypass for human characters.
- Once grouped with a recruited Witch Doctor, the administrator group leader
  targets it and enters `.localbotprepare brewing`. This only raises a bot to
  the leader's current level (10-80), rejects another specialization, and uses
  the native COA progression service. Both must be alive, out of combat and
  within 30 yards. No downward scaling, inventory wipe or talent reset occurs.
- Repeating preparation at the same level preserves earned XP. Existing
  equipment and talent choices are retained; this does **not** apply the
  repack's talent/gear profile. Preparation refreshes AI strategies and saves
  the bot normally; it does not modify the leader.
- COA by-specialization tank/healer/DPS/ranged checks share a conservative
  profile map. Brewing is healer/ranged. Other profiles remain generic DPS;
  Mountain King will not advertise tanking until tank AI is implemented.
- Brewing's healing list includes native base spells as well as upgraded
  ranks, and still checks that the bot actually knows and can cast each spell.
  A low-level pilot must not be expected to cast every high-level heal.

Acceptance order: confirm equal levels and `coa brewing`; inspect native
abilities/equipment; observe a heal landing on the human in and out of combat;
test attack and follow after a kill; then mount/dismount and death/recovery.
Use a safe same-level enemy and record the combat-log recipient. Do not use a
high-level grouped bot to force damage thresholds on the low-level player.

Local deployment on 2026-09-27: full worldserver build, pinned patch application,
C++ style checks, role/recruitment policy tests, production healing tests and
30 preparation guard-rejection cases passed. The restarted server reached ready
state and logged in all 12 roaming bots. Initial player testing confirmed
level preparation, ranged offense and healing the human leader. Travel failed:
Amaryla remained at a killed enemy and would not mount at level 13. Manually
running `do drop target` released her to drink and follow, isolating missing
combat-engine cleanup rather than a missing follow strategy.
Image: `sha256:c67ab36c850b8d4ac153aafec42888c0c6f0a3a79895bb37e7cff35929f53571`.
Rollback image: `coa-local/worldserver:pre-level-matched-pilot-20260927`.

Travel follow-up deployed on 2026-09-27: both COA combat profiles now
inherit the standard combat triggers, including invalid-target cleanup that
returns the AI to noncombat behavior. Grouped, human-led COA companions with
trained riding may pass the AI-only minimum-level gate; native mount spell,
combat, location and form restrictions remain. The exception also allows the
dismount check after the leader dismounts. Roaming/classic bot mount policy is
unchanged. Full native build, pinned installer patch application, C++ style and
the production-decision regression suite passed. The subsequent player retest
confirmed following after multiple kills, drinking to recover mana, and
mounting/flying with the leader. Amaryla chose a different flying mount in this
test; exact mount matching and a new low-level dismount check were not confirmed.
Image: `sha256:b1e0ee89c884ba538293844250dcfd96a63522f5ba6640513bd6db979b76f55a`.
Rollback image: `coa-local/worldserver:pre-coa-combat-travel-20260927`.
Only the worldserver was restarted; no database migration or client change was needed.
Post-restart checks: all 12 roaming bots logged in, zero container restarts,
and no new error signatures versus the pre-restart log. Existing missing-config,
process-priority and creature 55332/display 7654 warnings remain unchanged.

The local allowlist contains only `Amaryla` (a previously unassigned level-1
Witch Doctor); `Sukpiapi` remains unchanged. To test on Beruwa:

1. Leave any party containing higher-level bots, then enter
   `.playerbots bot add Amaryla`.
2. Once grouped and nearby, target Amaryla and enter `.localbotprepare brewing`.
   Confirm her level matches yours and the command reports Brewing.
3. Whisper `/w Amaryla co ?` and confirm `coa brewing` appears.
4. Test healing and attack/follow on an appropriate enemy, then mount/dismount.
   After a later relog, repeat recruitment if needed and verify level/spec
   persistence. This pilot is an explicit companion, not a new roaming slot.

Follow-up before expanding talent builds: learned talent spells survived login,
but paid UI nodes appeared unselected. Diagnosis confirmed `.localtalent` saved
spells without an allocation ledger, while `.localspecstate` returned no snapshot
to the installed client bridge. The server-side repair now records accepted
paid/selectable talent edits in existing `core.coa_talent.*` character settings
and sends the complete selection map to the installed client bridge. Queries
are read-only; login and same-spec synchronization do not clear allocations.
Actual specialization refunds and explicit removals update their records.
Rejected native learning preserves the previous choice; rank-chain replacement
and downgrade handling have focused regression coverage.

Talent-state deployment on 2026-09-27: full native build, pinned installer patch
application, C++ style and the extended production-method regression suite passed.
Only the worldserver was restarted; no client patch or database migration was needed.
Image: `sha256:de071d2ff50f2d31f4d286fdbad5ba83d57fc05cff771068cf1fb83bda2ee31e`.
Rollback image: `coa-local/worldserver:pre-talent-state-20260927`.
Startup verification: ready, 12 online bots, zero container restarts, and no new
error signatures. Authentication/database stayed running; existing warnings remain.

The player confirmed on 2026-09-27 that the fix worked and talent selections were
retained after logout/login. Existing choices are not inferred from spells;
older characters re-select the intended build once and click **Save Changes**.
For regression testing, reopen the tree, then log out and back in normally and
verify the selected nodes and remaining points. No `.save` command is required.
Existing learned spells are not automatically reset. Future bot talent builds
must also use an explicit allocation path, not just learn spells; this repair
does not implement automatic bot builds or full server-side talent-budget enforcement.

## Existing chat and social behavior

The pinned module already supports template-based ambient announcements and
probabilistic chat replies without an external AI API. The local runtime has
`RandomBotTalk` and broadcasts enabled. General is zone/team scoped, so twelve
bots spread globally may produce little chatter in the player's current zone.

Players can use `/join World` to hear eligible bots' cross-zone announcements.
This version broadcasts to World but ignores incoming World messages; it does
not provide conversations there. General replies are probabilistic and delayed;
a bot's name in a greeting improves the chance of a response. Grouped companions
suppress some unsolicited ambient suggestions. No chat rates were increased for
the healer milestone.

Later social polish should add COA class/spec names to the classic-only chat
labels, review stock meme/toxic replies, and add a shared rate budget before
substantially increasing population. Max channel probability settings are not
messages-per-minute limits.

## Brewing pilot playtest

- Invite `Sukpiapi` to a group and summon the bot nearby. It should be a level
  79 Witch Doctor; the `/w Sukpiapi co ?` strategy query should include
  `coa brewing` when the bot is in combat.
- Allow controlled damage to a group member and watch the combat log. Below
  80% health, the bot should use Loa's Brew; below 65%, Potion Toss may take
  priority; below 40%, Spirit in a Bottle may take priority. Cooldowns, range
  and resource limits can make it fall back to another heal. Do not put a
  low-level character at risk solely to force the emergency threshold.
- Repeat once out of combat to check top-off healing. At full health, order the
  bot to attack an appropriate mob and confirm offensive casting still works.
- Report the bot's strategy response, any spell names seen in the combat log,
  and whether the bot moved into range. The initial slice heals only within
  approximately 35 yards and does not yet include healer positioning AI.

### Observed local pilot result

- `Sukpiapi` (level 79) joined and appeared near `Beruwa` (level 3), and the
  strategy query showed `coa brewing`.
- The player reported a heal after resurrection. The available screenshot's
  combat-log excerpt shows Spirit healing `Sukpiapi`; verify a separate
  `Beruwa gains ... Health from Sukpiapi` entry in a safe, controlled test to
  confirm group-member targeting.
- The UnBot attack command worked: `Sukpiapi` attacked and killed the boar.
  The visible offensive casts were repeated Shadowflare. The current `coa
  attack` fallback intentionally picks the highest-level castable damage spell
  each time; it is not yet a Brewing-specific damage rotation.
- Grouping a level-3 player with a level-79 bot caused nearby mobs to scale to
  approximately level 76 and the player was one-shot. Do not use this pairing
  for further player-participation combat tests. Prepare a separate, level-
  matched Witch Doctor pilot before testing a full healer rotation.
- Following was observed to stop after the player died and resurrected.
  Playerbots had converted the alive bot to persistent `stay` on the master's
  release-spirit event, and its Follow command did not remove `stay`. The
  follow/mount patch removes that stale-state path. Later testing confirmed a
  newly invited bot would approach the player, but it did not mount with the
  player's Blossomback Arboon and could stop following after a fight. The
  current build prioritizes player-led mounting and follow movement over
  optional looting and has additional mount-selection fallbacks. Manual
  `/w <bot> do check mount state` successfully mounted Sukpiapi on the leader's
  ground mount, but mounting and dismounting did not happen automatically.
  COA bot classes lacked the `nc` strategy that owns the mount-state timer.
  The installer now registers that strategy for COA classes. On 2026-09-26,
  a different COA bot, `Grohlganurg` (Sun Cleric), automatically matched the
  leader's ground mount, followed, dismounted with the leader, then matched
  Blossomback Arboon and followed in flight. Post-combat follow after a
  fight or death still needs a separate in-game confirmation.
