# Blood Elf female Scribe wardrobe model repair

This targeted client repair preserves the full 3D wardrobe set grid. It addresses the repeated crash observed
while paging through sets on a Blood Elf female, including when no set was clicked. On November 21, 2026,
the player confirmed that set previews worked and that scrolling through dozens of pages no longer crashed.

The repository contains the [repair manifest](manifest.json) and
[audit/repair tool](../../scripts/wardrobe-repair.py), not game models, MPQs or minidumps. The tool obtains the
two complete models from the user's own compatible client. See [client setup](../../docs/client-setup.md)
for the separate native Lua, range-library, addon and graphics changes.

## Diagnosis and scope

The repeated exception was an access violation at `Ascension.exe` instruction `0x008369D7`, reading address
`0x2`. The crash dump directly identified
`Item\ObjectComponents\Collections\armor_scribe_d_01_armlower_right_be_f.m2`; all five captured skin arrays
matched its skin in `patch-TA.MPQ`. The renderer attempted to read a material from a null material table.

The installed `patch-U.MPQ` right-arm model had no materials or texture-combination tables, although its paired
skin referenced those tables. The female left arm had the same defect. The complete models and matching
skins were already present in `patch-TA.MPQ`. Attribution of the loaded model to the incomplete U version is
supported by the archive contents and native register/branch evidence; the full loaded M2 header was not
captured in the dump. Archive filename ordering alone was not used as proof of load precedence.

Only these two existing members of `patch-U.MPQ` are repaired:

| Member under `Item\ObjectComponents\Collections\` | Replacement source |
| --- | --- |
| `armor_scribe_d_01_armlower_right_be_f.m2` | Same complete member in the installed `patch-TA.MPQ` |
| `armor_scribe_d_01_armlower_left_be_f.m2` | Same complete member in the installed `patch-TA.MPQ` |

Their skins remain unchanged. Male models, other races, the appearance catalogue, Lua UI, executables and
server data are outside this repair. The Scribe's Noble Attire catalogue entry is set `12605`, appearance
`11816`; Scribe's Opulent and Scribe's Regal use the same model family and are useful follow-up checks.

The complete donor versions have older geometry than the incomplete overrides. Restoring the entire matched
model avoids inventing missing tables or assuming that changed vertex/UV data remain interchangeable. Future
client versions must be reviewed rather than having these older models imposed on them automatically.

## Verification record

The original local repair qualified both complete model/skin pairs with **36 structural checks each**,
including material and texture lookup references, table bounds, geometry indices, bone bindings and nested
transparency tracks. Both incomplete model/skin combinations failed ten required reference checks.

The prepared archive retained **38,204 exact numeric member identities**, with no added or removed entries.
All **38,200 unrelated ordinary members** retained their metadata and compressed bytes. The two intended
models changed; generated MPQ metadata could change. Installed archive and model readback hashes matched the
qualified repair, and the original archive backup was verified.

The subsequent player test confirmed working previews and dozens of pages without a crash. This supports the
reported Blood Elf female Scribe failure. It does not certify every appearance, other races, every recolor,
or unrelated crashes such as earlier failures at a different native instruction.

The reusable tool also has synthetic regression tests for unknown inputs, additional archive providers,
numeric locale collisions, backup drift and install/rollback guards. Its real-asset preparation was checked
against a private copy of the original archive; the installed reference client's audit checks all 77 MPQs,
including locale directories. Native Windows installation/rollback of this reusable Python tool has synthetic
coverage; the player-accepted original repair was installed with a separate local Windows script.

## Safe repair and future updates

Use the manifest and tool from the same repository revision. The read-only audit distinguishes the reviewed
broken and repaired inputs; unknown identities require investigation. Preparation stages a private copy,
checks the exact donor/model/skin fingerprints, and verifies that unrelated archive entries are preserved.
Installation requires a fully closed Windows client and launcher, a verified current backup, and matching
prepared inputs. Rollback refuses to overwrite subsequent changes.

Supply the reviewed Windows `mpqcli.exe` described in [client setup](../../docs/client-setup.md#reviewed-native-client-repair).
The tool checks its fingerprint. Audit and preparation may run from native Windows Python or Ubuntu/WSL
with paths appropriate to that environment. Installation and rollback require native Windows Python so the
process check covers the Windows game and launcher. From this repository on Windows:

```powershell
python scripts/wardrobe-repair.py audit --client 'D:\Games\CoA' --mpq-tool 'D:\Tools\mpqcli.exe'
```

The audit exits `0` for the recognized repaired state, `2` when the reviewed repair is needed, and `3` when
inputs require review. It does not modify the client or silently accept unknown newer assets. For a recognized
broken client, choose a new artifact directory outside the client, on the same drive, whose parent exists:

```powershell
python scripts/wardrobe-repair.py prepare --client 'D:\Games\CoA' --artifacts 'D:\CoA-Backups\wardrobe-001' --mpq-tool 'D:\Tools\mpqcli.exe'
```

Review the preparation result, fully close every game client and MMgr64, then install:

```powershell
python scripts/wardrobe-repair.py install --client 'D:\Games\CoA' --artifacts 'D:\CoA-Backups\wardrobe-001' --mpq-tool 'D:\Tools\mpqcli.exe'
```

If recovery is needed, close the game and launcher and use the same artifact directory:

```powershell
python scripts/wardrobe-repair.py rollback --client 'D:\Games\CoA' --artifacts 'D:\CoA-Backups\wardrobe-001' --mpq-tool 'D:\Tools\mpqcli.exe'
```

Keep artifacts outside the client and outside the repository. They contain copies of the user's game assets
and are recovery material, not release content. Keep the backup and receipt until gameplay acceptance and
retain them for recovery afterward. Preparation also saves the exact manifest and helper scripts under the
artifact directory's `recipe` folder. Receipts bind these by checksum. After a repository update, use that
saved `recipe/scripts/wardrobe-repair.py` with the same arguments for rollback rather than newer tooling.
No server restart is required.

Run the read-only audit before and after client updates, archive restoration or recovery. A recognized
repaired client should be left alone. A recognized regression can be prepared again against its current
inputs. An unknown version may already contain an upstream fix: inspect it and extend the qualified manifest
only after review and testing. Do not copy an old complete MPQ over newer client changes.

MPQ language labels are not a sufficient identity check. The reviewed `mpqcli` maps both neutral locale `0`
and US English `0x409` to the display label `enUS`; adding an explicit `enUS` replacement can create a second
entry instead of replacing the neutral member. The numeric identity check prevents that mistake.

Server-only updates must preserve client files. Include this audit in the
[maintenance preservation check](../../docs/g1-updates.md#client-preservation-check), while keeping the
server's source revision and database migration qualification separate from client rendering acceptance.
