# CoA Local Server — G1

Build a local **Conquest of Azeroth** realm with CoA-aware playerbots, Dungeon Finder support,
profession quality-of-life improvements, and companion client addons.

This project builds on [jealous-sound/azerothcore-wotlk-coa](https://github.com/jealous-sound/azerothcore-wotlk-coa),
[AzerothCore](https://www.azerothcore.org/), and the Playerbots community. It publishes a pinned,
reviewable version of the integration used by AzerothLabWorks. You supply the compatible game client
and extracted data; this repository does not contain a full client, character database, or game-data download.

**Current source recipe:** [`g1-20261118`](releases/g1-20261118/manifest.json), synchronized with the
maintained reference realm on upstream `437cf5c65bbb003ae180e9239ed89756e3385579`. It includes the
experience-potion repair, character-specific centaur reputation, skill-aware gathering alerts, and native
Worldforged sparkles and collection tracking. See [changes and acceptance](docs/g1-improvements.md#november-18-source-sync).

The recipe freezes source and patches rather than following upstream `main` during installation.
[Verification](docs/g1-verification.md) distinguishes source/package checks, the deployed realm's tests,
and fresh-install evidence. The November recipe passed an isolated empty-database and native startup probe
using its qualified binaries. The October 29 clean public build remains a separate historical checkpoint;
the current probe did not repeat a clean build or the complete public install command.
For a reusable introduction with links and scope, see the [community announcement](docs/community-announcement.md).

## Start here

1. Read the [installation prerequisites](docs/g1-installation.md#prepare-the-host-and-data). You need a
   compatible CoA client and matching extracted data before installing; this repository does not acquire them.
   The data-preparation workflow is not yet a complete newcomer setup guide.
2. On Ubuntu/Linux or Ubuntu in WSL2, run the read-only installation check below. Continue only when its
   release, data, Docker and port checks pass. Use a new runtime directory for this fresh-install recipe.
3. Follow [account creation and connection](docs/g1-installation.md#create-your-account-and-connect), then
   choose any [optional client addons and repairs](docs/client-setup.md). They are separate from server installation.

The reference setup is Windows 11 with Ubuntu in WSL2 and a separately supplied compatible Windows client.
See [verification](docs/g1-verification.md) for the difference between automated checks, fresh-server startup,
and gameplay observed on the existing reference realm.

## Improvements

| Area | Included behavior |
| --- | --- |
| CoA playerbots | CoA classes and authored specialization profiles, role-based recruitment, combat, recovery, following and mounted travel. |
| Bot mount matching | Followers try the player's selected mount, including supported flying mounts such as Blossomback Arboon for Azeroth travel. |
| Dungeon groups | Tank/healer/DPS recruitment and LFG queues; Classic, Burning Crusade and Wrath enabled with entrance-level checks, completion/reward repairs and an optional objective tracker. |
| Bot interaction | Non-LLM ambient replies and party status messages, including recovery and resurrection callouts, with pacing limits. |
| Professions | Four-point crafting/gathering gains; crafting, smelting, mining and skinning capped at two seconds while preserving faster casts. Fishing's channel is unchanged. |
| Character progression | Native talent persistence, the Defiance/Hellfire Imp correction, improved Book of Artisans profession filtering, and quest-display resynchronization. |
| Gathering alerts | Live nearby herbs/minerals produce private minimap pings when matching tracking is active and the character's learned profession and effective skill meet the node requirement. |
| Experience potion | The vanity Potion of Experience variant uses a short reuse cooldown; additional potions extend duration while keeping the 25% bonus. |
| Centaur clan choices | Gelkis and Magram reputation remains character-specific instead of being raised by another character's rival clan choice. |
| Worldforged pickups | Native in-world sparkles identify uncollected pickups; receiving the item removes the sparkle and prevents another collection by that character. |
| Client compatibility | Reviewed native talent-loader, shared range-library, and wardrobe/vanity patch recipes; compatible installed WeakAuras can use the repaired range checks. |
| Optional client tools | CoA GM Command Center, LFG Tracker, Gathering Alerts, Resource Monitor, a separately packaged Ascension WeakAuras fork, and a separate fog/water graphics setup. |

The reference realm runs **1,000 bots**. Population is configurable; that observation is not a hardware guarantee.
Read the [improvements and acceptance record](docs/g1-improvements.md) for what has actually been tested and
the [roadmap](docs/roadmap.md) for active work and deferred ideas. Not every class, spell or dungeon is certified.
The [playerbots guide](docs/playerbots.md) explains the compiled integration, party commands, mount matching
and flight restrictions.

## Requirements

- Ubuntu/Linux with Python 3.11+, Git and Docker Engine; Windows 11 with Ubuntu in WSL2 is the reference workflow.
- Sufficient disk space for source, a C++ build, compatible map data, and database backups. Keep the runtime on
  the Linux filesystem rather than inside `/mnt/c`.
- The compatible CoA DBC set and matching `maps`, `vmaps`, and `mmaps`. The installer validates the release's
  DBC fingerprints. Stock WotLK data is not a substitute.
- An existing CoA client. The optional Windows client tools use PowerShell 7 and/or Python 3 as documented.

## Install a new server

From Ubuntu/WSL2, choose a **new** runtime directory. `--data-dir` identifies the base game-data directory;
`--dbc-dir` and `--terrain-dir` may identify separately prepared data sets.

```bash
git clone https://github.com/AzerothLabWorks/coa-local-server.git
cd coa-local-server

python3 scripts/g1.py check \
  --dir ~/coa-g1 \
  --data-dir /path/to/compatible/data \
  --dbc-dir /path/to/compatible/dbc \
  --terrain-dir /path/to/matching/terrain \
  --bots 1000
```

Review the check result, then repeat with `install` instead of `check`. The installer verifies the pinned
source and patches, builds the server, initializes a new isolated database, and starts the selected realm.
It refuses an existing runtime directory. Different installations have separate storage and must use available ports.
Initial compilation and bot creation take time; follow the installation output and health checks.

For a step-by-step explanation, account creation and recovery, see [installation and management](docs/g1-installation.md).
The earlier `scripts/install-coa.sh` describes a different, historical build; do not mix its patches or database
bootstrap with this release. See [legacy builds](docs/legacy-builds.md).

## Daily management

```bash
python3 scripts/g1.py status --dir ~/coa-g1
python3 scripts/g1.py logs --dir ~/coa-g1
python3 scripts/g1.py stop --dir ~/coa-g1
python3 scripts/g1.py start --dir ~/coa-g1
python3 scripts/g1.py update-check --dir ~/coa-g1
```

Backups and upgrades are distinct operations. The tooling supports fresh installation and managed backups;
it does not silently migrate an existing server to arbitrary new upstream commits.
See [updates and preservation](docs/g1-updates.md).

## Client setup

- [Client compatibility and optional graphics](docs/client-setup.md): version-aware patch preparation, backup and rollback.
- [AzerothLabWorks addons](https://github.com/AzerothLabWorks/addons): matching `g1-20261029` CoA addon packages and their installer.
  Ready-made ZIPs and checksums are available on the [addon release page](https://github.com/AzerothLabWorks/addons/releases/tag/g1-20261029).
- [WeakAuras on CoA](https://github.com/AzerothLabWorks/addons/blob/main/docs/weakauras-coa.md): installation,
  source attribution, and testing guidance for the separate
  [5.21.2-alw.1 package](https://github.com/AzerothLabWorks/addons/releases/tag/weakauras-coa-5.21.2-alw.1).
  The addon package and the shared client range-library repair are separate steps. Personal aura definitions
  and account settings are not included.
- Gathering Alerts and LFG Tracker require their matching server components. The GM addon requires server-granted
  GM permissions and explicit character/realm opt-in.

## Development and contributions

The [source-recipe manifest](releases/g1-20261118/manifest.json) records upstream revisions, patch hashes, module files,
configuration and data compatibility. [Release maintenance](docs/g1-updates.md) explains how new changes become
repeatable releases. Keep fixes small, include relevant tests and report the exact release and reproduction steps.
Do not attach passwords, account dumps, saved variables or a complete client to bug reports.

Read [verification](docs/g1-verification.md) before claiming a change is tested. Native server checks use
the upstream `tools/verify_all.py` entry point. Installer and addon checks have separate scopes.

Original release tooling is provided under GPL-2.0-or-later. Existing components retain their own notices and
terms; see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
