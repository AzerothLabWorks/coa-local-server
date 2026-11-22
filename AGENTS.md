# Repository maintenance

Follow the user's authorized scope and the update process in `docs/g1-updates.md`.
Repository documentation/tooling work does not require changing a running realm or client.

## Preserve twenty active character slots

Read `docs/character-slots.md` when preparing a server update, release, recovery, or character-selection change.
The reference G1 realm uses `CharactersPerRealm = 20`, `CharactersPerAccount = 128`,
`CoA.CharacterSelectionEnable = 1`, and `CoA.CharacterSelectionMaxActive = 20`.

- Audit the resolved active and proposed runtime configuration with `scripts/character-slots.py audit`
  before cutover, and repeat against the deployed files after startup. Require a passing result for this
  profile; treat missing files, duplicate keys and unexpected limits as unresolved checks.
- Identify actual configuration paths from management routing, process arguments and container mounts;
  review environment and other module overrides separately. The file audit does not prove loaded settings,
  existing roster sizes or native client behavior.
- Preserve both the realm creation limit and the maximum advertised to the client. Do not revert the
  advertised limit to ten, hide/deactivate existing characters, reset rosters, or restore stale account data.
  Check current roster counts before any intentional future limit change.
- Keep historical release manifests immutable. The November 22 change is a documented configuration override,
  not a rebuilt historical release or a client patch. Carry it into a newly qualified recipe when applicable.
- Keep automated server/Lua evidence separate from manual client acceptance. Character eleven creation,
  scrolling/selection beyond ten and the twentieth-slot boundary remain explicit client checks.

## Preserve the wardrobe model repair

The Blood Elf female Scribe wardrobe crash has a player-accepted client asset repair.
Read `client-patches/coa-wardrobe/README.md` and its `manifest.json` when assessing
an upstream update, client update, archive restoration, or client recovery.

- Include the read-only `scripts/wardrobe-repair.py audit` in client qualification.
  Run it before and after any change to client archives; record its result separately
  from source/build/database checks. Discover the actual client and reviewed MPQ tool
  paths rather than assuming a path from an earlier machine or deployment.
- Preserve the two repaired model members and their matching skins. Server-only
  updates must leave client files alone. Keep full 3D set previews.
- A recognized repaired state needs no reinstallation. A known broken state can be
  prepared using the checked recipe; installation requires the client to be closed
  and a verified current archive backup. Unknown newer models or extra archive
  providers require review, not replacement with an old archive or forced hashes.
- If the client or MPQ tool is unavailable, report the audit as unavailable. Do not
  call that a pass or imply that server tests prove client rendering compatibility.
- Keep game assets, archives, crash dumps, account data and private recovery records
  out of commits. This repository contains the recipe, hashes, tests and documentation.

Run `bash tests/run.sh` for repository tooling changes. Its synthetic tests protect
the repair's version, locale, backup and preservation guards; in-game rendering
acceptance is a separate result. Do not rewrite immutable server release recipes
to add an independently versioned client repair.
