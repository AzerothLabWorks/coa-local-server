# COA Local Server

Local, source-built Conquest of Azeroth server tooling for Ubuntu/WSL2 and Docker Compose.

This repository is the control plane for a private development server. It clones and builds the public
[`jealous-sound/azerothcore-wotlk-coa`](https://github.com/jealous-sound/azerothcore-wotlk-coa) source, but does
not vendor that source or distribute clients, patches, game data, database packages, or other proprietary files.

## Current development status

The installer has been validated end-to-end on Ubuntu/WSL2. It:

- creates an isolated `coa-local` Compose project;
- clones the COA source into a separate runtime directory;
- records the exact upstream commit used for a build;
- generates a strong local database password;
- verifies and imports the world baseline bundled with the selected COA source revision;
- requires user-supplied COA server data;
- builds the authserver, worldserver, and database importer from source;
- configures the realm endpoint to match the published Docker world port;
- deliberately bypasses AzerothCore's stock client-data downloader;
- applies local QoL defaults: 3x XP, 4x profession gains, 5,000 starter gold,
  and four 30-slot bags for newly created characters;
- supports a non-destructive `--dry-run` preflight.
- optionally builds the open-source Playerbots core/module integration and initializes its database.

The installer does not yet download or infer proprietary inputs. Supply legally obtained files yourself.

## Requirements

- Ubuntu or another Linux distribution, with WSL2 supported
- Git
- Docker Engine with the Compose v2 plugin
- OpenSSL
- Prepared server data containing at least `dbc`, `maps`, `vmaps`, and `mmaps`

The COA source specifically requires DBCs extracted from the matching COA client. Stock AzerothCore DBCs are
not a compatible substitute.

Prepare the server data from an existing client and COA source checkout:

```bash
./scripts/prepare-coa-data.sh \
  --client-dir /mnt/c/Games/Ascension-WOW \
  --source-dir /path/to/azerothcore-wotlk-coa \
  --mpqcli /path/to/mpqcli \
  --output ~/wow-server-coa-dev-data
```

This downloads v20 standard map data, then replaces its DBC set with tables extracted from and validated against the
supplied COA client. The client is read-only and is not modified.

## Quick start

From Ubuntu/WSL2:

```bash
git clone https://github.com/AzerothLabWorks/coa-local-server.git
cd coa-local-server

./scripts/install-coa.sh \
  --dir ~/wow-server-coa-dev \
  --data-dir /path/to/prepared-coa-server-data \
  --dry-run
```

After the preflight succeeds, rerun without `--dry-run`:

```bash
./scripts/install-coa.sh \
  --dir ~/wow-server-coa-dev \
  --data-dir /path/to/prepared-coa-server-data
```

### Optional Playerbots build

Playerbots requires its own AzerothCore fork hooks; adding only the module to ordinary COA source is not sufficient.
The installer therefore pins the COA revision used by the repack-era build, applies the audited Playerbots core delta,
and checks out the matching open-source module revision:

```bash
./scripts/install-coa.sh \
  --dir ~/wow-server-coa-bots \
  --data-dir '/mnt/c/Games/COA Repack/CoA-Repack/CoA-Repack/Data' \
  --with-playerbots
```

To also install the repack's UnBot client addon, pass both Windows locations as WSL paths. An existing UnBot folder
is renamed to a timestamped backup before the new copy is installed:

```bash
./scripts/install-coa.sh \
  --dir ~/wow-server-coa-bots \
  --data-dir '/mnt/c/Games/COA Repack/CoA-Repack/CoA-Repack/Data' \
  --with-playerbots \
  --client-dir /mnt/c/Games/Ascension-WOW \
  --playerbots-package-dir '/mnt/c/Games/COA Repack/CoA-Repack/CoA-Repack/CoA-Bots'
```

This installs the open-source Playerbots engine and its `acore_playerbots` database. The repack `Data` directory is
required because its Playerbots DBC layout differs from the client-extracted non-bot data. The installer verifies two
layout-sensitive DBC hashes before building.

The local compatibility patch also contains an initial COA AI adapter reconstructed from the data and behavior in
the repack package. It permits random characters using custom class IDs, preserves their COA spellbooks during bot
randomization, and selects usable offensive abilities dynamically from their learned spells. This is an experimental
combat baseline, not yet feature-equivalent to the repack's compiled COA layer: specialization profiles, healing,
tanking, dispels, interrupts, and `.playerbots coa tank|heal|dps` are still being developed.

New Playerbots installations reserve 120 bot accounts and restrict newly generated characters to COA class IDs. This
leaves any pre-existing classic bot characters intact while ensuring the expanded pool contains testable COA bots.
The default online population is 12; override it cautiously with `COA_MIN_RANDOM_BOTS`, `COA_MAX_RANDOM_BOTS`, and
`COA_RANDOM_BOT_ACCOUNT_COUNT` in `.env`. UnBot remains available for the standard Playerbots controls; its bot
management bar is a client-side command interface and does not implement the server AI itself.

The initial C++ image build can take a long time. Follow progress with:

```bash
cd ~/wow-server-coa-dev
docker compose --env-file .env -f compose.yaml logs -f
```

## Management

```bash
./scripts/coa-server.sh --dir ~/wow-server-coa-dev status
./scripts/coa-server.sh --dir ~/wow-server-coa-dev logs
./scripts/coa-server.sh --dir ~/wow-server-coa-dev stop
./scripts/coa-server.sh --dir ~/wow-server-coa-dev start
```

Create the first account after the worldserver is running:

```bash
./scripts/coa-server.sh --dir ~/wow-server-coa-dev console
account create admin CHANGE_THIS_PASSWORD
account set gmlevel admin 3 -1
```

## Runtime layout

The default runtime directory is `~/wow-server-coa-dev`:

```text
wow-server-coa-dev/
  .env                    generated secrets and local paths
  compose.yaml            installed Compose definition
  source/                 cloned upstream COA source
  orchestration/          copied first-boot helper image inputs
  state/upstream-commit   exact source revision
  state/playerbots-module-commit  exact module revision (Playerbots installs only)
```

Docker database state is stored in the named volume `coa-local-database`. Removing that volume destroys all
accounts, characters, and database state; ordinary stop/start operations preserve it.

The generated `.env` exposes the QoL rates as `COA_XP_RATE`, `COA_PROFESSION_RATE`, and
`COA_STARTER_MONEY_COPPER`. The default XP preset is 3; the included dynamic-XP module also supports presets
1, 5, and 7.

## Included gameplay compatibility fixes

The installer applies a small, auditable source patch for local play. In addition to the QoL defaults above, it:

- equips new Ascension-class characters with four 30-slot Elementiumweave Bags;
- repairs both Sunwarmed Furline collection records and supplies the missing server-side mount display behavior;
- restores the Book of Artisans model and interaction bounds; and
- opens the Book of Artisans profession trainer after it is summoned, allowing professions to be learned normally.

These changes are deliberately limited to the affected collection records and local character initialization.

Prepared server data remains in the directory passed with `--data-dir` and is mounted read-only; the installer
does not duplicate its multi-gigabyte map files.

## Development

Run the fast checks from Linux or WSL:

```bash
./tests/run.sh
```

See [docs/architecture.md](docs/architecture.md) for the isolation and data-flow decisions.

## Legal and usage statement

This independent project is intended for private learning, interoperability research, and personal
experimentation. It is not affiliated with or endorsed by Blizzard Entertainment, Project Ascension, or the
upstream COA contributors. Do not commit or redistribute copyrighted client files, extracted game data, database
packages, credentials, or repack contents through this repository.
