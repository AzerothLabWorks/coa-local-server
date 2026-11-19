# Updates and preservation

G1 installs a frozen source recipe. Updating a repository checkout or discovering newer upstream commits does
not upgrade an installed realm. The current tooling provides a fresh installer and backups, not an
automatic live migration tool. `g1-20261118` is a new source recipe; `g1-20261029` remains immutable.

## Check for upstream work

```bash
python3 scripts/g1.py update-check --dir ~/coa-g1
```

This read-only command compares the installed core commit with upstream `main` and prints both identities.
It does not fetch into the installed source tree, merge changes, build, modify databases, or restart anything.
A different commit means there is work to assess, not that every upstream change is compatible or that a
reported gameplay issue has been fixed. Playerbots, client patches, and local overlays also need review; the
command is not a complete compatibility assessment.

Our maintenance cadence is a weekly review, with focused fixes when needed. An external scheduler may run the
read-only check, but deployment is a separate maintenance decision. There is no unattended pull-and-restart job
in this repository.

## Prepare the next release

For each proposed update:

1. Record the running binary hash, installed release manifest, source pins, patch hashes, configuration, and
   database migration ledgers. A Git `HEAD` alone does not describe a patched build.
2. Freeze one upstream revision. Review substantive source changes, local patch overlap, migration names and
   checksums, and genuine client/DBC/terrain requirements. Preserve Playerbots integration and authored profiles.
3. Integrate in a separate checkout and runtime. Follow that checkout's `AGENTS.md` and run
   `tools/verify_all.py`. Record failed, skipped, unavailable, and passing checks distinctly.
4. Prove a fresh installation. For an upgrade, separately prove the migration against a recent private copy of
   the current realm's data, including character/account counts, talent persistence, professions, appearances,
   playerbots, LFG completion and rewards, and client acceptance.
5. Publish a new immutable release recipe and its qualification record. Document changed requirements and the
   reviewed upgrade procedure before asking users to apply it.

Keep new feature work out of maintenance unless it is explicitly part of the release. Do not change bot counts
while comparing an upstream refresh. Keep source/module revisions, world-content baseline, and SQL overlays
together; do not mix patches from the historical installer with the G1 recipe.

## Database boundaries

Fresh bootstrap runs only against a new isolated database with no non-system tables. It verifies the core world
baseline, applies the allowed modules through the core importer, initializes the empty Playerbots schema, and
records the reviewed Playerbots migration checksums. Vendor custom SQL is excluded. Runtime core and Playerbots
database updaters are disabled after this deterministic initialization.

The core unconditionally prepares a query against `character_worldforged_loot`. Fresh bootstrap imports the
complete canonical character base, then the one pinned Worldforged character-ledger schema and its migration
checksum before preparing database statements. Its obsolete-cache cleanup is allowed only within the
proven-new schema; this bootstrap must never be used on a player's existing character database.

Core revision `437cf5c65bbb003ae180e9239ed89756e3385579` also accesses `coa_character_challenge` during
startup even when the optional Challenges module is disabled. For that exact revision, fresh bootstrap
additionally imports the hash-checked canonical challenge character schema and records its migration identity.
This supplies the required empty tables and schema definitions; it does not enable challenge gameplay or
import challenge world definitions or seed data. The October 29 revision keeps its original bootstrap
requirements. Unknown core revisions require a reviewed dependency list instead of guessing which SQL to run.

The November 18 recipe compiles **`mod-worldforged-pickups`** for native sparkles and per-character collection.
Compiled modules and modules allowed to run SQL are separate lists: Worldforged's historical world-placement
SQL remains excluded. The reference realm already had the required ledger and needed no new migration to
enable the module. Do not replay old Worldforged placement migrations or clear an existing claim ledger.
The older October 29 recipe imports the required ledger but leaves the pickup module disabled.

The runtime database user has ordinary data-access permissions and table-scoped `DROP` on only
`acore_characters.guild_member_withdraw` and `acore_characters.gm_ticket`. The core's daily guild allowance reset
and GM ticket reset use `TRUNCATE`, which requires that permission in MySQL. Database-wide schema modification
privileges and runtime migration auto-updaters remain disabled.

The empty-database bootstrap is not a live-upgrade mechanism. Do not enable runtime auto-updates or manually
replay every SQL file to make an existing installation resemble a fresh one. Migration filename reuse or a
changed checksum requires investigation; silently rehashing the ledger can hide an incompatible history.

Existing player state belongs to the running realm. Preserve accounts, characters, inventories, progress,
talents, appearances, professions, and Playerbots state. Do not replace these with an old development snapshot,
reseed profiles over live data, reset characters, or overwrite a user's client catalogue during an update.

## Maintenance and rollback

An eventual upgrade requires a confirmed logout window and a backup of the **latest** realm data before the
switch. Keep the existing binary, configuration, release recipe, and database backup until acceptance completes.
Backups must be restored and checked in isolation before being described as rollback-tested.

Switching an older binary back is safe only if it understands the current database schema and data. Restoring an
older database after more gameplay would discard that progress. Rollback planning must state whether schema
changes are reversible and what happens to progress since the backup. If the answer is unknown, do not promise
an automatic rollback.

See [installation and backups](g1-installation.md) for the current commands and limitations, and
[verification](g1-verification.md) for this release's actual evidence.
