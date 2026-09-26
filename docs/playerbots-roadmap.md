# COA Playerbots development plan

The open-source Playerbots module is the runtime. The repack's `CoA-Bots` package
contains a compiled worldserver, not a patch we can merge, but its
`Dashboard/coa-level-builds.json` provides 65 class/specialization profiles with
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

1. Test `Sukpiapi` in a group: healer role, in-combat emergency heal,
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
