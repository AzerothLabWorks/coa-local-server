# COA Playerbots development plan

The open-source Playerbots module is the runtime. The repack's `CoA-Bots` package
contains a compiled worldserver, not a patch we can merge, but its
`Dashboard/coa-level-builds.json` provides 70 class/specialization profiles across 21 classes with
spec IDs, intended roles and level-by-level talent picks. Ascension Sidekick is
useful for human-readable build and spell-priority guidance. Neither source is
an executable server implementation. Spell IDs, ranks, targets and effects must
be checked against the installed COA `Spell.dbc` and the server scripts.

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

1. Prepare a dedicated, level-matched Brewing pilot; preserve the existing
   high-level `Sukpiapi`. Test healer role, in-combat emergency heal,
   out-of-combat top-off, GM leader healing and damage-spell fallback. Keep the
   online population at 12 during this test.
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
   memory. Raise bot count in steps only after stability checks at each level.

The UnBot bar is a client-side command interface from the repack. It can keep
controlling standard Playerbots commands; it does not supply the missing AI.

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
