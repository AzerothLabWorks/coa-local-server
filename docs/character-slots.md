# Twenty characters on one account

The maintained G1 reference realm enabled **20 active characters on one account/realm on November 22, 2026**.
The compatible Ascension client already has a scrolling character list and reads its maximum from the server.
The server had been advertising ten active characters. Aligning the advertised maximum and the realm creation
limit enables the larger roster without a client patch, addon, source rebuild or database migration.

Characters remain ordinary active characters. This recipe does not use portal activation/deactivation,
database hiding, character deletion or extra accounts to switch between classes.

## Release boundary

This is a post-release configuration recipe, separate from the immutable `g1-20261029` and `g1-20261118`
source recipes. Those manifests retain `CoA.CharacterSelectionMaxActive = 10`; installing an older recipe
does not automatically enable twenty active slots. Do not edit a historical manifest or imply that its original
qualification included this later change.

The November 22 reference deployment retained its existing binary, based on upstream
`cddb523d33e63def4c6a50c9c65fcdd104890424`. Its installed client already supports the dynamic count protocol and
scrolling list. Confirm equivalent support in another core/client combination before applying the settings;
a stock WotLK client or an unrelated fork is not established as compatible by this result. Larger limits are
outside this recipe's qualification.

## Required settings

| Configuration | Setting | G1 value | Purpose |
| --- | --- | --- | --- |
| `worldserver.conf` | `CharactersPerRealm` | `20` | Limits character creation on this realm. |
| `worldserver.conf` | `CharactersPerAccount` | `128` | Retains the existing account-wide ceiling; it must not block the realm allowance. |
| Loaded `coa.conf` module file | `CoA.CharacterSelectionEnable` | `1` | Enables the Ascension character-selection protocol. |
| Loaded `coa.conf` module file | `CoA.CharacterSelectionMaxActive` | `20` | Advertises twenty active slots to the compatible client. |

On the reference realm, only `CharactersPerRealm` changed from `128` to `20` and
`CoA.CharacterSelectionMaxActive` changed from `10` to `20`. The account ceiling and protocol switch were
already correct. The account ceiling is separate from the twenty-character allowance on each realm; it does
not mean the client is configured for 128 active characters on G1.

Use the actual loaded files, not just `.conf.dist` templates. For an existing installation, resolve management
routing and its active-runtime marker, then inspect the server command and container mounts to find those
files. Do not assume that a runtime directory from a previous deployment is still active.

## Apply to a compatible installation

1. Record the current effective settings and character counts. If an existing roster already exceeds twenty,
   stop for review rather than lowering its limit or hiding characters.
2. Prepare candidate copies of the loaded configuration. Set the two changed values above and verify the
   retained account ceiling and protocol switch. Preserve all unrelated settings, especially bot population,
   profession gains and the profession cast cap. Do not copy an entire old configuration over the current one.
3. Run the read-only audit against the candidate files:

   ```bash
   python3 scripts/character-slots.py audit \
     --world-config /path/to/candidate/etc/worldserver.conf \
     --coa-config /path/to/candidate/etc/modules/coa.conf
   ```

4. Follow the installation's maintenance procedure. The reference deployment waited for the client to close,
   checked for real players, stopped only the world service cleanly, and verified a fresh backup of the latest
   data, configurations and binaries after final character saves. It then installed the two assignments and
   restarted the same worldserver binary. Do not interrupt an active player or use an old data snapshot.
5. Verify startup, database connectivity and the installed settings. Repeat the audit against the installed
   files, check environment overrides and loaded paths, and retain the configuration change in the deployment
   record. Then perform the client checks below.

The audit does not change files, connect to a database, restart a server or patch the client. It checks the
supplied configuration files; it does not prove which files a running process loaded, that no environment
override applies, or that the client's native list behavior is correct.

It prints a JSON result and exits with `0` for matching settings, `2` for missing, conflicting or unexpected
values, and `3` when the supplied files cannot be audited. Require exit `0` for this reference profile.

## Qualification and client checks

The November 22 qualification used the existing deployed binary and isolated disposable data:

- Twenty characters were created on one account through the native fixture creation flow. Eleven assertions
  passed, including Ascension metadata maximum/total/active/inactive counts of `20/20/20/0` from the first and
  twentieth sessions. Fixture creation was concurrent and socketless; this does not prove a sequential
  twenty-first-character rejection or the full client network flow.
- The existing Blood Elf/Draenei starting-zone scenario passed 42 assertions.
- The installed character-selection Lua passed 170 assertions with mocked native APIs for 10, 11, 15 and 20
  characters, saved ordering expansion, selection/deletion mapping, and creation enabled at nineteen but
  disabled at twenty. These were not rendered client tests.
- The live deployment verified the unchanged running binary, startup and database connectivity, and unchanged
  character/account progression checks. Only the two intended configuration assignments changed; bot and
  profession settings were preserved.

Explicit in-client acceptance beyond ten remains pending. With the compatible client, check creation of
character eleven, scrolling beyond the first ten, selection and login for the new character, and persistence
after closing and reopening the client. As the roster grows, check selection of the first and twentieth
characters, ordering, and the creation boundary at twenty. Do not delete existing characters simply to test
these boundaries. A fresh login with more than ten characters also checks native metadata/event ordering,
which mocked Lua tests cannot establish.

## Preserve through updates and recovery

Run the audit before and after maintenance and keep these values in the candidate's effective configuration.
Treat a return to the old ten-active-character advertisement as a regression for an opted-in G1 realm.
When upstream changes the character-list protocol, enumeration, creation limits or client selection UI,
repeat the focused native and client checks rather than assuming the configuration alone remains sufficient.

Keep the latest character/account data and every existing character. After characters eleven and beyond
exist, do not blindly restore an old ten-slot configuration: it can hide access to otherwise intact characters.
Keep a limit that accommodates the current roster while investigating. This change has no schema migration,
and an older character database is never a repair for a character-selection limit.

See [updates and preservation](g1-updates.md#character-selection-preservation-check) for the maintenance gate
and [improvements and acceptance](g1-improvements.md#november-22-twenty-character-selection) for the change record.
