# G1 improvements and acceptance

This is the current public-release summary, not a claim that all upstream CoA content is complete.
The reference realm and community installer have separate verification records.

## November 22 twenty-character selection

The reference realm now permits **20 active characters on one account/realm**, using the compatible client's
existing scrolling character list. Its server advertised only ten active characters even though the core
and client already had support for larger lists. The update sets `CoA.CharacterSelectionMaxActive = 20` and
`CharactersPerRealm = 20`; `CharactersPerAccount = 128` and `CoA.CharacterSelectionEnable = 1` remain unchanged.
No character activation/deactivation workaround, additional account, client patch, rebuild or database
migration was used.

An isolated native server test created twenty characters on one disposable account and passed eleven
assertions, including advertised maximum/total/active/inactive counts of **20/20/20/0**. The Blood Elf/Draenei
starting-zone regression also passed its 42 assertions. Tests using the installed character-selection Lua
with mocked native APIs passed 170 assertions for list counts, ordering, selection and creation/deletion
mapping. These mocks do not establish native client rendering, event timing or actual selection beyond ten;
explicit in-client creation, scrolling and selection acceptance remains pending.

Deployment verified startup, unchanged binary identity, preserved configuration outside the two assignments,
and unchanged character/account progression checks. The [20-character guide](character-slots.md) records the
configuration, qualification limits and required update audit. This is a separate post-release configuration
recipe: the immutable `g1-20261029` and `g1-20261118` manifests retain their original defaults.

## November 21 wardrobe client repair

Wardrobe set paging could crash the Blood Elf female client when it loaded the Scribe armor family, even
without selecting a set. Two lower-arm models in the client lacked the material and texture lookup data
required by their paired skins. The repair restores the complete models already present in the compatible
client. It preserves the full 3D set grid and normal click-to-try-on behavior.

Both replacement model/skin pairs passed 36 structural checks each. The local installation verified that
38,200 unrelated ordinary archive members were unchanged and that all 38,204 numeric archive identities
were preserved. On November 21 the player confirmed working previews and scrolling through dozens of pages
without another crash. This is acceptance for the reported Blood Elf female failure, not every appearance,
race or unrelated client crash.

The [wardrobe repair guide](../client-patches/coa-wardrobe/README.md) records the diagnosis, exact repair
scope, audit and rollback workflow, and update-preservation requirements. The tool and manifest are separate
from the immutable server release recipes. They use the user's own client assets; no model files, client
archives or crash dumps are published. No server rebuild or database change is involved.

## November 18 source sync

The `g1-20261118` recipe follows the reference realm's upstream base
`437cf5c65bbb003ae180e9239ed89756e3385579`, retaining the previously published bot integration, authored
profiles, dungeon fixes, profession settings and client protocols. Its additions since `g1-20261029` are:

- **Potion of Experience:** item `8180460` uses the same one-second item/category cooldown as the other
  supported potion variants. Repeated use extends the remaining duration at a 25% bonus; it does not increase
  the percentage. Alternate-character eligibility remains enforced. The player reported the repair working.
- **Centaur reputation:** Gelkis and Magram standings remain the individual character's earned values when
  account reputation is shared. A sibling's higher reputation no longer changes the opposing clan choice.
  Legitimate characters friendly with both clans keep that state; this is not a global reputation reset.
  Focused native scenarios cover both choices; follow-up player testing of the affected quest remains pending.
- **Gathering skill filter:** herb/mineral alerts require the learned profession and sufficient effective skill,
  including applicable bonuses, before selecting the nearest eligible nodes. Matching tracking, live-node,
  visibility and privacy checks remain. Ordinary node visibility and harvesting rules are unchanged.
  The existing Gathering Alerts addon and protocol version 1 work without an addon update.
- **Worldforged pickups:** the native pickup module is compiled into the build. An uncollected pickup sparkles
  in the world. Successfully receiving its item records the character's claim, removes its sparkle and makes
  it non-interactable for that character; the object remains as scenery. Opening the loot window alone does
  not consume the claim, and another character has an independent claim.

On November 18 the player confirmed the Worldforged sparkle before collecting Arakor Mace and the lack of
sparkle or interaction afterward. Focused native checks also cover repeat-collection refusal, retained claims
across logout/login, and unrelated ordinary loot. Historical pickups cannot be reconstructed from an empty
claim ledger, so tracking begins when the module is enabled. Prestige resets, full bags, full process-restart
persistence and Worldforged group-roll awards have not been qualified by that focused scenario.

After recovery, the player tanked a dungeon with bots and confirmed objective completion and loot.
It retains **1,000 bots**, four-point crafting/gathering gains and the two-second cap for crafting, smelting,
mining and skinning. This source publication does not alter those population or profession settings.
See [verification](g1-verification.md) for the exact separation of local gameplay and public recipe checks.

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
- Gathering Alerts use actual nearby spawned nodes, the player's active tracking and effective gathering skill.
  The player confirmed visual minimap pings on nodes before the later skill filter. Sound uses the familiar
  MapPing cue; universal sound-device/zoom/client testing is not claimed.
- Optional CoA GM tools and Resource Monitor improve local administration and multi-resource visibility.
- Optional CoAVolFog adds fog/water rendering. It is a separate credited project with a narrow local rendering fix;
  the player reported successful outdoor/flying/water use without an observed FPS problem on their hardware.

## Boundaries

Character databases, credentials, personal action bars and WeakAuras profiles are never release artifacts.
The release is a reproducible source integration. Fresh installer verification does not establish compatibility
with every existing private-server database, client archive or addon combination.
