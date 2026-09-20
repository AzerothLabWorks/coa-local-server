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
- supports a non-destructive `--dry-run` preflight.

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
```

Docker database state is stored in the named volume `coa-local-database`. Removing that volume destroys all
accounts, characters, and database state; ordinary stop/start operations preserve it.

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
