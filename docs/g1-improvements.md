# G1 improvements and acceptance

This is the current public-release summary, not a claim that all upstream CoA content is complete.
The reference realm and community installer have separate verification records.

## Server and bots

- CoA classes and specialization-aware bot builds reuse the Zyth CoA bot implementation and authored profiles,
  alongside the upstream Playerbots engine. Personal bot selections and strategies are preserved.
- Role recruitment uses `.playerbots coa tank`, `.playerbots coa heal`, and `.playerbots coa dps`.
  A damage player normally adds one tank, one healer and two damage bots, or uses available LFG matchmaking.
- Tank pulling/aggro, healing, damage, looting, drinking, travel and resurrection have been observed in play.
  The player reported full Wailing Caverns and Stockades clears, including normal LFG completion in Stockades.
- Followers attempt the player's selected mount, including eligible flying mounts such as Blossomback Arboon.
  Ground-mounted bots can switch when the leader takes off, subject to safe mount-change conditions. The player
  confirmed sustained flight and landing/dismounting in the tested scenario. See [playerbot mount matching](playerbots.md#mount-matching-and-flight).
- The reference realm runs 1,000 bots with positive local gameplay and performance reports. The longer-term
  1,500-bot target is planned testing, not the tested population of this release.
- Non-LLM social behavior adds contextual replies and party recovery/status messages with shared pacing limits.
  It does not use an external AI account or language-model service.

## Dungeons and progression

- Burning Crusade and Wrath Dungeon Finder access is enabled. Entrance requirements still apply; a client
  listing alone does not override a dungeon's actual level restrictions.
- Final-encounter lookup, repeat random rewards and status reporting have focused native checks. The LFG
  companion addon displays server-authoritative completion and supports reload/re-entry without guessing from loot.
- Auchenai Crypts testing established successful matchmaking, teleport, combat, recovery and boss completion.
  The initial unknown objective prompted the later tracker repair. A subsequent player run confirmed an accurate
  objective and the expected completion/exit prompt. Every mapped dungeon has not been cleared manually.
- Native talent persistence includes the Defiance/Hellfire Imp correction. The player confirmed saving and
  retaining those selections across logout/login.
- Upstream updates resolved reported Tinker pet-health and turret-display behavior in local play. These are
  observed results, not a claim that AzerothLabWorks authored every underlying upstream fix.
- Book of Artisans filtering respects the primary-profession limit and offers appropriate profession upgrades.
  Duplicate development-profession entries and recipe-list oddities remain known observations.

## Profession and client quality of life

- Crafting and gathering skill gains are configured to four points. Mining, Engineering and later Blacksmith
  crafting were confirmed by the player. Skill-up chances and profession rank caps remain separate rules.
- Crafting, smelting, mining and skinning have a maximum two-second cast time; naturally faster casts stay faster.
  Combat spells, ordinary item use and fishing's channel are outside this cap.
- Native wardrobe/vanity application and logout/login persistence were confirmed after the compatibility repairs.
  Some unsupported catalogue entries can still fail; the repair does not bypass ownership or invent missing assets.
- Generic range support preserves existing WeakAuras. The retired spell-specific helper is not installed.
- Gathering Alerts use actual nearby spawned nodes and the player's active tracking. The player confirmed visual
  minimap pings on nodes. Sound uses the familiar MapPing cue; universal sound-device/zoom/client testing is not claimed.
- Optional CoA GM tools and Resource Monitor improve local administration and multi-resource visibility.
- Optional CoAVolFog adds fog/water rendering. It is a separate credited project with a narrow local rendering fix;
  the player reported successful outdoor/flying/water use without an observed FPS problem on their hardware.

## Boundaries

Character databases, credentials, personal action bars and WeakAuras profiles are never release artifacts.
The release is a reproducible source integration. Fresh installer verification does not establish compatibility
with every existing private-server database, client archive or addon combination.
