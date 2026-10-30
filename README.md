# CoA Local Server — G1

Build a local **Conquest of Azeroth** realm with CoA-aware playerbots, Dungeon Finder support,
profession quality-of-life improvements, and companion client addons.

This project builds on [jealous-sound/azerothcore-wotlk-coa](https://github.com/jealous-sound/azerothcore-wotlk-coa),
[AzerothCore](https://www.azerothcore.org/), and the Playerbots community. It publishes a pinned,
reviewable version of the integration used by AzerothLabWorks. You supply the compatible game client
and extracted data; this repository does not contain a full client, character database, or game-data download.

**Release:** [`g1-20261029`](releases/g1-20261029/manifest.json).
Public source reconstruction, clean build/unit checks and isolated fresh-database startup passed;
see [verification](docs/g1-verification.md) for the exact scope and remaining gameplay acceptance.
The release freezes the tested source rather than following upstream `main` during installation.

## Improvements

| Area | Included behavior |
| --- | --- |
| CoA playerbots | CoA classes and authored specialization profiles, role-based recruitment, combat, recovery, following and mounted travel. |
| Bot mount matching | Followers try the player's selected mount, including supported flying mounts such as Blossomback Arboon for Azeroth travel. |
| Dungeon groups | Tank/healer/DPS recruitment and LFG queues; Classic, Burning Crusade and Wrath enabled with entrance-level checks, completion/reward repairs and an optional objective tracker. |
| Bot interaction | Non-LLM ambient replies and party status messages, including recovery and resurrection callouts, with pacing limits. |
| Professions | Four-point crafting/gathering gains; crafting, smelting, mining and skinning capped at two seconds while preserving faster casts. Fishing's channel is unchanged. |
| Character progression | Native talent persistence, the Defiance/Hellfire Imp correction, improved Book of Artisans profession filtering, and quest-display resynchronization. |
| Gathering alerts | Live nearby herbs/minerals produce private minimap pings through the companion addon when the matching tracking is active. |
| Client compatibility | Reviewed native talent-loader, range/WeakAuras, and wardrobe/vanity patch recipes. |
| Optional client tools | CoA GM Command Center, LFG Tracker, Gathering Alerts, Resource Monitor, and a separate fog/water graphics setup. |

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

Backups and upgrades are distinct operations. The first release supports fresh installation and managed backups;
it does not silently migrate an existing server to arbitrary new upstream commits.
See [updates and preservation](docs/g1-updates.md).

## Client setup

- [Client compatibility and optional graphics](docs/client-setup.md): version-aware patch preparation, backup and rollback.
- [AzerothLabWorks addons](https://github.com/AzerothLabWorks/addons): matching `g1-20261029` CoA addon packages and their installer.
  Ready-made ZIPs and checksums are available on the [addon release page](https://github.com/AzerothLabWorks/addons/releases/tag/g1-20261029).
- Gathering Alerts and LFG Tracker require their matching server components. The GM addon requires server-granted
  GM permissions and explicit character/realm opt-in.

## Development and contributions

The [release manifest](releases/g1-20261029/manifest.json) records upstream revisions, patch hashes, module files,
configuration and data compatibility. [Release maintenance](docs/g1-updates.md) explains how new changes become
repeatable releases. Keep fixes small, include relevant tests and report the exact release and reproduction steps.
Do not attach passwords, account dumps, saved variables or a complete client to bug reports.

Read [verification](docs/g1-verification.md) before claiming a change is tested. Native server checks use
the upstream `tools/verify_all.py` entry point. Installer and addon checks have separate scopes.

Original release tooling is provided under GPL-2.0-or-later. Existing components retain their own notices and
terms; see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
