# Playerbots in the G1 build

Playerbots are integrated into the server source and build. They are not a client macro package or a service
that requires an LLM. The release pairs a pinned CoA core with a pinned Playerbots module, our complete CoA
integration patches, the required database/profile setup, and the matching runtime configuration.

The bot engine comes from **mod-playerbots**, and the CoA class AI and authored specialization profiles build
on **Zyth's CoA Bots** work. This release reuses that foundation and adds the local integration and reliability
repairs described below. It does not claim that AzerothLabWorks created every class rotation from scratch.
See [attribution](../THIRD_PARTY_NOTICES.md) and the [source manifest](../releases/g1-20261029/manifest.json).

CoA classes use a shared CoA AI context. Their native specialization selects tank, healer, melee or ranged
strategies, with a dedicated Brewing healer strategy. Authored specialization rotations sit alongside shared
interrupts, defenses and fallback actions. Automatically managed builds buy eligible talents through native
level, prerequisite and point checks; manually selected builds are preserved. Current authored talent picks
stop at level 60 even though bots can level to 80, so complete endgame talent coverage remains an improvement
area rather than an advertised guarantee.

## What the integrated bots do

- Play CoA classes and specializations, with role-aware builds and spell priorities.
- Join parties as tanks, healers or damage dealers, and participate in Dungeon Finder matchmaking.
- Fight, pull, hold aggro, heal, loot, drink, recover, follow and resurrect where their available abilities permit.
- Use contextual non-LLM World and party messages, including recovery and resurrection callouts, with pacing limits.
- Follow a human group leader's mount choice, including supported flying mounts.

The reference realm runs **1,000 bots**. Full Wailing Caverns and Stockades runs, later expansion dungeon
combat/recovery, and a later correct objective/completion prompt have been reported by the player. These are
useful acceptance examples, not a guarantee that every specialization or encounter is complete. Population,
class/role coverage, geography and active gameplay all affect resource use and role availability.

## Mount matching and flight

When a human group leader mounts, a grouped bot first attempts the leader's **currently selected mount spell**.
This includes supported cosmetic/collection mounts such as **Blossomback Arboon**. An eligible CoA bot missing
that spell can learn the single requested catalogue mount under the server's ownership/unlock policy. This
does not copy the player's entire collection or replace the bot's specialization.

This matters when flying around Azeroth: a follower that has already chosen a ground mount can reconsider
that choice when the leader takes off. The G1 configuration enables supported Azeroth flight, so eligible bots
can follow on a flying mount instead of remaining on the ground on their usual racial mount.

Mount changes remain subject to riding skill, ownership policy, location and spell restrictions. The bot avoids
unsafe swaps while airborne, falling, in combat or transferring maps. If it cannot use the leader's mount, it
tries its other usable mount choices; an unsuccessful swap is suppressed until the leader changes or dismounts.
It does not force an immediate cosmetic ground-to-ground swap every time the player selects a different mount.
Mount/dismount synchronization is part of the follow behavior. Northrend's Cold Weather Flying requirement and
native no-fly restrictions still apply; this feature is not unrestricted flight in every location.

Recorded player acceptance includes a follower matching Furline, then Blossomback Arboon, following in sustained
flight and landing/dismounting, and repeating the combat/drink/remount cycle. That validates the tested travel
scenario rather than every mount and class combination. The older [travel investigation](playerbots-roadmap.md)
is retained as history; use the current release manifest, not its historical patch sequence, for installation.

## Forming a dungeon party

For direct role recruitment, use:

```text
.playerbots coa tank
.playerbots coa heal
.playerbots coa dps
```

A damage player normally needs one tank, one healer and two additional damage bots for a five-player party.
You can also use the enabled Dungeon Finder. Level and entrance eligibility still apply. Classic, Burning
Crusade and Wrath support is included in G1; more full dungeon acceptance remains active work.

The optional CoA GM addon exposes compatible bot controls. The optional LFG Tracker displays the server's
objective/completion status. Neither addon supplies the underlying bot AI: it is compiled into the server.

## Maintaining the integration

Fresh installation applies the reviewed schema/profile migrations once to an empty database. Runtime auto-updates
are disabled. Existing bot profiles and player progress must be preserved during maintenance; do not replay a
vendor profile pack over a running realm. Upstream refreshes require checking both core and bot changes against
our patches and repeating relevant qualification.

Next priorities are broader dungeon/class acceptance and measured population testing toward 1,500 bots.
Improved player feedback should guide targeted fixes. See the [current roadmap](roadmap.md).
