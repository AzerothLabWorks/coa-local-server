# COA Local Server

Build and run a local Conquest of Azeroth server on Ubuntu/WSL2 with Docker Compose, gameplay repairs,
quality-of-life improvements, and experimental COA Playerbots.

We build on the public [`jealous-sound/azerothcore-wotlk-coa`](https://github.com/jealous-sound/azerothcore-wotlk-coa)
source. This repository contains the installer, configuration, source patches, and our small compatibility
modules. The upstream server is cloned separately. Clients, client patches, extracted game data, database
packages, and repack binaries are not included.

## What players get

| Improvement | Behavior in the current build |
| --- | --- |
| Faster progression | A configurable 3x XP preset and crafting/gathering skill gains set to 4. |
| Starter supplies | New characters start with 5,000 gold; new COA-class characters receive four 30-slot Elementiumweave Bags. |
| Persistent mount and pet buttons | Account-owned mount and companion spells are saved in Playerbots builds, so their action-bar buttons survive logout and login. |
| Working Sunwarmed Furline | The mount renders correctly and uses its native mount aura and riding-speed behavior. Older collection entries keep working. |
| Book of Artisans | The book summons with a valid model and opens its profession trainer so characters can learn professions. |
| Automatic profession tools | Learning a supported profession supplies missing starter tools. Existing characters receive missing tools on login. |
| Lootbot 3000 | A summoned, owned Lootbot can collect nearby loot even when the collection UI has not retained its active-pet selection. |
| COA character compatibility | Valid custom-class spells and skills are preserved at login, and the client's `localspecstate` query no longer floods chat. |
| COA talent-tree persistence | Explicitly saved talent choices are recorded separately from learned spells and restored in the talent UI after logout/login. Existing characters re-select their intended choices once. |
| Grouped bot travel | Eligible COA bots can match the leader's mount, follow on the ground or in flight, and dismount with the leader. |

The upstream local-play defaults also unlock the local appearance and vanity catalogs and grant riding
300/300 plus Cold Weather Flying. Available collection entries depend on the supplied COA data and spell support.

The profession kit covers **Fishing, Skinning, Mining, Blacksmithing, Engineering, Enchanting, Inscription, and
Jewelcrafting**. It checks equipment, bags, and the bank before granting tools, recognizes compatible multi-tools,
and never replaces equipped weapons. See the [tool list and delivery rules](modules/mod-local-profession-tools/README.md).
Crafting materials and advanced crafted tools remain part of normal profession progression.

Sunwarmed Furline may appear twice in the Mounts list because we retain the older collection entry alongside
the native riding-speed spell. This repair does not globally enable flying in Azeroth. After updating an older
server, a mount or pet button already removed by the old login behavior may need to be added once more.

The talent-tree repair uses the existing client bridge and character settings; it needs no client patch or database
migration. It does not guess previous choices from the spellbook or reset existing learned spells at login. For an
older character whose tree appears empty, re-select the intended talents and click **Save Changes** once. Logout/login
retention was confirmed on Beruwa in local playtesting; automatic bot talent allocation remains separate development work.

## Current status

The pinned **Playerbots build is the tested installation path**. It has been built and run on Ubuntu/WSL2 with
12 online bots. The latest gameplay fixes were reported working in local playtesting on 2026-09-27, including
profession training and tool delivery, Furline, mount/pet action-bar persistence, and talent-tree retention. Installer checks, patch
application checks, and the worldserver build passed; the latest deployment introduced no new startup errors.
These are local test results, not coverage of every class, spell, item, or dungeon.

COA bot combat is still experimental. Group invitations, summoning, attacking, and mount/dismount following
have been exercised in game. Complete tank/healer/DPS rotations and reliable dungeon parties are the next stage;
see the [Playerbots roadmap](docs/playerbots-roadmap.md) for observed results and remaining tests.

New installations **without `--with-playerbots` are currently unsupported**: the older non-Playerbots vanity
patch needs rebasing onto upstream `main`. Use the pinned Playerbots path below while that work remains open.

## Requirements

- Ubuntu or another Linux distribution, with WSL2 supported
- Git
- Docker Engine with the Compose v2 plugin
- OpenSSL
- Prepared server data containing at least `dbc`, `maps`, `vmaps`, and `mmaps`

The tested Playerbots build requires the matching repack `Data` directory. Its DBC layout differs from the
client-extracted non-bot data, and the installer checks two layout-sensitive DBC hashes before building.
Stock AzerothCore data is not a compatible substitute. Supply your own legally obtained COA client and server data.

`scripts/prepare-coa-data.sh` remains available for client-extracted data work; its output is not a substitute
for the matching repack data required by the current Playerbots build.

## Quick start

From Ubuntu/WSL2, choose a new runtime directory and point `--data-dir` at your matching repack data:

```bash
git clone https://github.com/AzerothLabWorks/coa-local-server.git
cd coa-local-server

./scripts/install-coa.sh \
  --dir ~/wow-server-coa-bots \
  --data-dir '/mnt/c/Games/COA Repack/CoA-Repack/CoA-Repack/Data' \
  --with-playerbots \
  --dry-run
```

After the preflight succeeds, rerun without `--dry-run`:

```bash
./scripts/install-coa.sh \
  --dir ~/wow-server-coa-bots \
  --data-dir '/mnt/c/Games/COA Repack/CoA-Repack/CoA-Repack/Data' \
  --with-playerbots
```

The installer creates an isolated `coa-local` Compose project, generates a local database password, records
the selected source revisions, imports the upstream COA world baseline, and builds the server components from
source. Playerbots requires core hooks as well as the module; the installer applies both at compatible pinned
revisions and initializes `acore_playerbots`. It also installs the gameplay patches and profession-tool module.
The stock AzerothCore client-data downloader is bypassed.

The first C++ build can take a long time; build output appears in the installation terminal. The installer
refuses to overwrite an existing runtime directory. `--dry-run` validates inputs without creating a server.

### Optional client tools

For a new installation, add `--client-dir` to include the optional
[COA WeakAuras range helper](client-addons/COAWeakAurasRange/README.md). Also add `--playerbots-package-dir`
to copy UnBot from your repack. Close the client first and use WSL paths for Windows directories. Existing
copies of these addons receive timestamped backups. For example, use this instead of the installation command above:

```bash
./scripts/install-coa.sh \
  --dir ~/wow-server-coa-bots \
  --data-dir '/mnt/c/Games/COA Repack/CoA-Repack/CoA-Repack/Data' \
  --with-playerbots \
  --client-dir /mnt/c/Games/Ascension-WOW \
  --playerbots-package-dir '/mnt/c/Games/COA Repack/CoA-Repack/CoA-Repack/CoA-Bots'
```

## Playerbots: working foundation, ongoing AI development

The local compatibility patch also contains an initial COA AI adapter reconstructed from the data and behavior in
the repack package. It permits random characters using custom class IDs, preserves their COA spellbooks during bot
randomization, and selects usable offensive abilities dynamically from their learned spells. A first, experimental
Witch Doctor Brewing healing profile can be enabled for one named bot with `COA_BREWING_PILOT_NAME` in `.env`.
The class service assigns spec 6 only to that bot if it has no spec yet. The adapter is not yet feature-equivalent to
the repack's compiled COA layer:
tanking, broad spec rotations, dispels, interrupts, and `.playerbots coa tank|heal|dps` are still being developed.
See [the Playerbots roadmap](docs/playerbots-roadmap.md) for the staged test sequence and source-of-truth boundaries.

The current test slice adds opt-in, level-matched Brewing companions through `COA_TEST_PILOT_NAMES` and the
administrator-only `.localbotprepare brewing` command. It preserves existing equipment/talents and refuses to
downlevel bots or replace another specialization. Shared role checks and base-rank healing support are included;
local tests confirmed level preparation, ranged attacks, healing the leader, and post-combat follow/recovery.
Full healing-priority and dungeon acceptance remain pending. Setup and safeguards are in the roadmap.

Bots already support built-in chat templates and General-channel replies. On the local realm these are enabled;
`/join World` also exposes eligible cross-zone ambient announcements. World replies are not implemented by the
pinned module. Population and chat frequency remain unchanged while combat behavior is tested.

New Playerbots installations reserve 120 bot accounts and restrict newly generated characters to COA class IDs. This
leaves any pre-existing classic bot characters intact while ensuring the expanded pool contains testable COA bots.
The default online population is 12; override it cautiously with `COA_MIN_RANDOM_BOTS`, `COA_MAX_RANDOM_BOTS`, and
`COA_RANDOM_BOT_ACCOUNT_COUNT` in `.env`. UnBot remains available for the standard Playerbots controls; its bot
management bar is a client-side command interface and does not implement the server AI itself.

When grouped, bots now pause rather than acquire a persistent `stay` command while the leader is dead; the patch
allows following to resume after resurrection. The Follow command clears any prior Stay state, and mount selection
first tries the leader's known mount, with a usable ground-mount fallback when a COA mount cannot be cast. Player-led bots prioritize
mounting and following a moving leader over optional corpse looting. COA classes register the noncombat strategy
that runs the automatic mount-state check. In-game testing confirmed that a grouped COA bot matched the leader's
ground mount, followed, dismounted when the leader did, then matched a Blossomback Arboon and followed in flight.
This applies to eligible COA bots generally, not to one named pilot; ordinary mount requirements still apply.
The latest follow-up restores standard combat target cleanup for both COA combat profiles, so a dead target can
return the AI to following and recovery. Grouped, human-led COA bots with trained riding also bypass the AI-only
level-20 mount threshold, including the dismount check; native spell restrictions and roaming bot policy remain.
The player retest confirmed following after multiple kills, mana recovery, and mounted flight with the leader
(on a different flying mount). Low-level dismounting and switching mount types while the bot remains mounted
still need a dedicated retest. The Brewing healer pilot remains experimental; see the roadmap for results.

## Management

```bash
./scripts/coa-server.sh --dir ~/wow-server-coa-bots status
./scripts/coa-server.sh --dir ~/wow-server-coa-bots logs
./scripts/coa-server.sh --dir ~/wow-server-coa-bots stop
./scripts/coa-server.sh --dir ~/wow-server-coa-bots start
```

Create the first account after the worldserver is running:

```bash
./scripts/coa-server.sh --dir ~/wow-server-coa-bots console
account create admin CHANGE_THIS_PASSWORD
account set gmlevel admin 3 -1
```

## Runtime layout

The quick start uses `~/wow-server-coa-bots`; if `--dir` is omitted, the default is `~/wow-server-coa-dev`:

```text
wow-server-coa-bots/
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

## Existing servers and updates

Pulling this repository does not change a running server. The installer creates fresh runtimes; it is not an
in-place updater. Existing installations need the applicable source/module changes, any new SQL migrations,
and a rebuilt server image. Review the changes and back up affected state before deployment.

Profession-tool checks apply to existing trained characters on login. The 5,000-gold and four-bag defaults
apply to character creation; the installer does not retroactively reset balances or overwrite existing bags.
Characters and accounts live in the database volume and are retained by ordinary rebuilds and restarts.
Prepared server data stays in the `--data-dir` directory and is mounted read-only rather than copied into each build.

## Development

Run the fast checks from Linux or WSL:

```bash
./tests/run.sh
```

For a Playerbots build, also verify that every patch applies to the pinned source revisions:

```bash
./tests/validate-playerbots-patches.sh
```

With Python 3 and a C++17 compiler available, run the focused bot regression tests too:

```bash
COA_VALIDATE_AI=1 bash ./tests/validate-playerbots-patches.sh
# Or reuse an already patched core source tree:
bash ./tests/validate-coa-ai.sh /path/to/azerothcore-wotlk-coa
```

These compile the real role/recruitment policies and exercise extracted production healing, preparation, travel,
and talent-state code against deterministic API doubles. They cover safety guards and decision logic, not live
pathfinding, client rendering, or dungeon play.

Keep this README aligned with verified behavior. Record experimental bot results and remaining work in the
[Playerbots roadmap](docs/playerbots-roadmap.md); do not describe a new behavior as confirmed until it passes an
in-game test. Local `.env` files, client data, and credentials stay outside Git.

Community test reports are welcome. Include the repository revision, character class and level, steps to
reproduce, expected and actual behavior, and relevant client/server logs with credentials removed. Bot reports
should include the bot's class, level, selected specialization, and active strategies. Testing one level-matched
party is more useful at this stage than raising the population before combat roles are validated.

See [docs/architecture.md](docs/architecture.md) for the isolation and data-flow decisions.

## Legal and usage statement

This independent project is intended for private learning, interoperability research, and personal
experimentation. It is not affiliated with or endorsed by Blizzard Entertainment, Project Ascension, or the
upstream COA contributors. Do not commit or redistribute copyrighted client files, extracted game data, database
packages, credentials, or repack contents through this repository.
