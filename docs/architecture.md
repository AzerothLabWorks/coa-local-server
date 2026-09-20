# Architecture

## Separation of responsibilities

This repository contains reproducible orchestration only. The upstream COA checkout, compiled images, database
state, extracted client data, and proprietary downloads remain outside Git.

The installer creates a runtime directory on the Linux filesystem. Keeping source builds under `~/` rather than
`/mnt/c` avoids the filesystem overhead and case-sensitivity problems commonly encountered when compiling large
C++ projects through a Windows-mounted path in WSL2.

## Data flow

1. The installer validates Docker, Git, OpenSSL, and prepared server data.
2. It clones the public COA source into `runtime/source` and records the checked-out commit.
3. MySQL creates an empty `acore_world` schema on first initialization.
4. A one-shot helper runs the upstream `world_data.py verify` and `bootstrap` commands against the exact bundled
   baseline archive from that checkout.
5. The upstream `db-import` image initializes auth/characters schemas and applies repository migrations.
6. Authserver and worldserver start only after both one-shot import stages complete successfully.
7. Worldserver mounts the supplied COA data read-only without duplicating its multi-gigabyte map files.

## Why the upstream Compose file is not used directly

The upstream Compose stack includes an `ac-client-data-init` service that downloads standard AzerothCore client
data. The COA source documentation says the worldserver must use the matching COA client's DBC tables. This
repository therefore owns a small Compose definition that builds from upstream source while mounting explicit,
validated COA data and omitting the stock downloader.

## Database lifecycle

MySQL initialization scripts only run when the database volume is empty. Replacing the SQL file does not update
an existing database. Database resets are intentionally not automated because they destroy accounts and
characters. If a reset is needed, identify and remove only the `coa-local-database` volume after making a backup.

## Ports

Defaults are intentionally offset to coexist with existing labs:

| Service | Host | Container |
| --- | ---: | ---: |
| MySQL | 33306 | 3306 |
| Authentication | 33724 | 3724 |
| World | 38085 | 8085 |
| SOAP | 37878 | 7878 |
