# Install and manage G1

The G1 installer creates a new local realm from the exact public source revisions and reviewed patches in
[`releases/g1-20261029/manifest.json`](../releases/g1-20261029/manifest.json). It does not update an existing
realm or import a player's saved characters. Check the [qualification record](g1-verification.md) before using
the release; tests of an existing realm and tests of a fresh installation are separate evidence.
This recipe remains frozen at **`g1-20261029`**. Later fixes tested on the local reference realm do not enter
an installation automatically; they require a separately qualified public release.

Start with the host and data prerequisites below, then run `check`, install into a new directory, create
your account, and connect your compatible client. Optional client repairs, addons and graphics are separate
steps described in [client setup](client-setup.md). The server installer does not supply or configure a client.

## Prepare the host and data

Use a regular Linux user with Python **3.11 or newer**, Git, Docker Engine, and Docker Compose v2.
Ubuntu in WSL2 is supported by the workflow. Docker must be running and accessible to that user; do not run
the installer with `sudo`. Keep the runtime on the Linux filesystem, such as `~/coa-g1`, rather than `/mnt/c`.
At least 30 GiB of free build space is checked, in addition to the supplied game data and room for backups.

Supply your compatible CoA data. The repository does not distribute a client or extracted game assets.
The installer checks every DBC fingerprint recorded in the release and requires non-empty `maps`, `vmaps`,
and `mmaps` directories. Terrain fingerprints, when present in the release manifest, are also enforced.
These checks are not a substitute for extracting matching terrain from the intended client. A stock WotLK
DBC directory is not interchangeable with the CoA set. Linked data paths are rejected; provide ordinary files
and directories. The same data may be shared read-only with another installation.

Data preparation is still a separate prerequisite, not a one-click step in this release. Use the matching
CoA source/client extraction workflow for your client revision. The historical `scripts/prepare-coa-data.sh`
downloads standard terrain and is **not the G1 terrain preparation path**: using it can reintroduce geometry
mismatches in modified towns. The source build produces extraction tools, but this release does not yet qualify
a portable end-to-end terrain extraction recipe. Keep your extracted data versioned alongside your client.
If you do not already have the compatible client and extracted data, resolve that prerequisite before running
`install`. Do not bypass a fingerprint failure or substitute stock terrain to make the check pass; report the
release ID and the mismatched file name/hash without uploading game assets.

The following placeholders describe three locations you supply:

| Option | Contents |
| --- | --- |
| `--data-dir /path/to/compatible/data` | Base game-data directory used by the server. |
| `--dbc-dir /path/to/compatible/dbc` | Flat directory containing the release-compatible DBC files. Defaults to `DATA/dbc`. |
| `--terrain-dir /path/to/matching/terrain` | Directory containing `maps/`, `vmaps/`, and `mmaps/`. Defaults to `DATA`. |

## Check and install

Clone this repository, then run the check from its root:

```bash
git clone https://github.com/AzerothLabWorks/coa-local-server.git
cd coa-local-server

python3 scripts/g1.py check \
  --dir ~/coa-g1 \
  --data-dir /path/to/compatible/data \
  --dbc-dir /path/to/compatible/dbc \
  --terrain-dir /path/to/matching/terrain
```

`check` validates release artifacts, data, disk space, Docker availability, unused ports, and unused Docker
resource names. It changes no files, containers, or databases. `install --dry-run` performs the same check.

Repeat the command with `install` in place of `check` when ready. The installer:

1. Creates the previously absent runtime directory with private permissions.
2. Fetches the exact public core and Playerbots commits, applies checked patches, and verifies exported files.
3. Builds a Docker toolchain, then runs the core's `tools/verify_all.py` source, build, and unit stages.
   This build needs network access to download the GoogleTest revision pinned by the core's CMake recipe.
   The build runs before database credentials or containers are created.
4. Creates a separately named Docker network, database volume, and services, with generated database credentials.
5. Initializes a proven-empty database, records migration identities and checksums, and writes local configuration.
6. Starts the realm and checks that its login and world listeners become available.

Compilation and initial bot creation take time. The default population is **1,000**, matching the reference G1
configuration; this is not a promise that every machine can support that population. `--bots 0` is useful for
an isolated installation qualification without automatic bot login. The retained reference account-pool settings
can still create bot accounts and characters with `--bots 0`; that option disables automatic login, not pool creation.
Choose the desired count during installation; the first release does not provide an automatic population-change
command. `--no-start` builds and initializes
the realm but leaves its game services stopped. Its database remains running.

The default login port is **33727** and world port **38088**, both bound to `127.0.0.1`. The database has no
published host port. Another installation needs different unused ports, for example
`--auth-port 33728 --world-port 38089`. Resource names derive from the runtime path, or can be assigned with
`--project coa-g1-myrealm`. Existing directories, names, and volumes are never adopted or overwritten.
This release is intended for local play, not remote/public hosting.

If Docker has exhausted its automatic address pools, choose an unused private `/24` for this new realm with
`--network-subnet 10.203.29.0/24`. The example is not a universally free range: the installer rejects overlaps
with existing Docker networks and non-default IPv4 host routes, both during preflight and immediately before
network creation. This option requires the `ip` command from `iproute2` and accepts only aligned RFC1918 IPv4
`/24` networks. It configures this installation's network only; it does not prune old networks or alter Docker's
global address pools. Check VPN or other routes that may become active later before choosing a range.

The toolchain's base and MySQL images are digest-pinned. The MySQL command-line client is copied from that same
pinned MySQL 8.4 image; native bootstrap requires its `--no-login-paths` option, absent from Ubuntu's 8.0 client.
Docker verifies support while building the toolchain, and the installer checks it again before compiling source.
Build packages come from Ubuntu's package repositories,
so the recipe does not claim identical binary bytes across all build dates. An expert may supply
`--toolchain-image IMAGE` to use an already available compatible image; its exact Docker image ID is recorded.
That override must be qualified separately from the default toolchain.

## Create your account and connect

Open the server console after startup:

```bash
python3 scripts/g1.py console --dir ~/coa-g1
```

Type these commands in that console, replacing `ACCOUNT` and `PASSWORD` with your own values. Console commands
have no leading dot. Account names and passwords cannot contain spaces in this command format.

```text
account create ACCOUNT PASSWORD
account set addon ACCOUNT 2
```

For an optional local administrator account, also enter:

```text
account set gmlevel ACCOUNT 3 -1
```

Detach from the console with **Ctrl+P, then Ctrl+Q**. Do not use Ctrl+C to detach.
Keep console output private when entering credentials.

Point your compatible client at `127.0.0.1:33727`, or the login port selected during installation. Configure a
separate client copy when you also play another realm. Follow [client setup](client-setup.md) for the optional
G1 patches, addons, and graphics. The server installer does not modify your client.
WeakAuras is available as a [separate CoA compatibility package](https://github.com/AzerothLabWorks/addons/blob/main/docs/weakauras-coa.md);
neither server installation nor the four-addon G1 installer installs it. Its addon files and the shared
client range-library repair have separate installation and rollback steps.

## Daily controls

Run these commands from this repository; the runtime directory identifies the realm:

```bash
python3 scripts/g1.py status --dir ~/coa-g1
python3 scripts/g1.py logs --dir ~/coa-g1 --follow
python3 scripts/g1.py stop --dir ~/coa-g1
python3 scripts/g1.py start --dir ~/coa-g1
```

`stop` stops the world and login services and retains the running database. Add `--database` to stop that service
too. `start` starts the existing services; it never bootstraps or migrates their databases. Management verifies
installation ownership and the generated Compose file, and starting a ready installation verifies its recorded
binary hashes. Readiness checks both the internal service listeners and the published ports, since Docker's
port proxy may accept connections before the server is initialized. This does not certify gameplay or completion
of bot population login.

Configuration is under `RUNTIME/etc/`; initialization and verification records are under `RUNTIME/state/`.
The installation record and generated Compose file bind management to that runtime. Do not copy them to a
different path and expect management to adopt it. There is no command that deletes the database volume.

## Back up and recover

Log out, stop the game services, and make a backup while the database remains running:

```bash
python3 scripts/g1.py stop --dir ~/coa-g1
python3 scripts/g1.py backup --dir ~/coa-g1
python3 scripts/g1.py start --dir ~/coa-g1
```

The backup contains authentication, characters, world, and Playerbots schemas in a compressed SQL file under
`RUNTIME/backups/`. With game services stopped, the dump takes a global database read lock and checks successful
completion. A sidecar records its SHA-256, installation identity, and `restore_tested: false`. Credentials and
player data make these files private: store a copy elsewhere, with access controls appropriate for your accounts.
The backup command does not include game assets, binaries, client settings, or the runtime's configuration files;
preserve the release recipe and a private copy of `etc/`, `state/`, and `installation.json` separately.

There is no automatic restore or in-place upgrade command in this release. A completed dump is not a proved
restore. Before relying on a backup for maintenance, restore it into a separate disposable database with the
matching release and verify character/account counts and login behavior. Never restore an older dump over a
realm with newer character progress.

If installation fails, its files and isolated database are retained and the installation is marked incomplete.
Inspect command output, `state/verification/`, and Docker logs for that project. The installer refuses to replay
an ambiguous bootstrap or overwrite the directory. Do not point the historical installer at the partial database.
`stop --dir RUNTIME --database` can stop its retained services after ownership verification, even when the
installation is incomplete. It does not remove data.
Resolve the cause and qualify a new isolated destination, or review a specific recovery procedure before changing
the retained data. A failed game startup stops the new installation's game services to avoid a restart loop.

See [updates and preservation](g1-updates.md) for the release workflow.
