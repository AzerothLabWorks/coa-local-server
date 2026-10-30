# CoA client setup for the G1 source release

Use your own compatible Ascension/CoA 3.3.5a (build 12340) client. This repository does not contain a game
client, executable, MPQ archive, terrain package, or saved character settings. Server and client compatibility
must be checked together: a generic WotLK client is not a substitute for the matching CoA client/data.

The G1 release has three native-client repair families, ordinary addons, and an optional graphics extension.
The number of modified files is not a count of independent features.

| Component | What it does | Installation path |
| --- | --- | --- |
| Native talent loaders | Stops loading the retired local talent compatibility bridge so the native G1 talent protocol can work. | Reviewed archive repair below. |
| Range library and WeakAuras | Discovers usable learned CoA spells for range checks; removes the old single-spell wrapper when that exact wrapper is present. | Reviewed archive/loose-file repair below. |
| Wardrobe and vanity | Uses the native appearance Apply and vanity delivery calls, including the required Apply argument. | Reviewed archive repair below. |
| CoALfgTracker | Displays the supported dungeon's authoritative final objective and completion state. | Ordinary addon; matching server bridge required. |
| CoAGatheringAlerts | Pings nearby active tracked herbs/minerals, privately, with repeat suppression. | Ordinary addon; matching server bridge required. |
| GMCommandCenter_CoA | CoA GM command interface, with commands disabled until configured for the intended realm. | Ordinary addon. |
| COAResourceMonitor | Shows the custom classes' simultaneous resources. | Ordinary addon. |
| CoAVolFog | Optional volumetric fog and modern water from the separate upstream graphics project. | Separate source build and optional manual installation below. |

The local G1 client has player acceptance for talent persistence, the tested appearance/vanity paths, range
checks, dungeon objectives, gathering visual pings, and outdoor fog/water. This does not certify every client
distribution, appearance, map, GPU, or addon combination. Sound and alert preferences remain user settings.

## Ordinary addons

The canonical packages and installer live in [AzerothLabWorks/addons](https://github.com/AzerothLabWorks/addons).
Use its CoA packages, not similarly named WotLK or Legion variants. From that repository:

```powershell
python tools/coa-release/package.py --output dist/coa-g1-20261029
pwsh scripts/Install-CoAAddons.ps1 -ClientPath 'D:\Games\CoA' -PackageDirectory dist/coa-g1-20261029 -Action Check
```

Review the check output, fully close the game, then use `-Action Install`. The installer supports selecting
individual addons with `-Addons` and receipt-based rollback. Keep its backup/receipt folder. It does not copy
our account settings, WeakAuras, action bars, or SavedVariables into your client.

The gathering protocol is `COAGATHER` version 1; the dungeon tracker uses `COA_LFG_STATUS` version 1.
The corresponding server components are part of the matching `g1-20261029` release. Installing only the
client addon on an unrelated server does not add the server's node detection or dungeon status support.

## Reviewed native client repair

[`scripts/client-patches.py`](../scripts/client-patches.py) has separate `prepare`, `install`, and `rollback`
commands. It accepts a client directory instead of a developer's fixed machine path. It repairs only the
fingerprints recorded in [`g1-client-manifest.json`](../client-patches/g1-client-manifest.json): the five known
G1 archive checkpoints, matching executable/extension identities, and exact member preimages. Unknown inputs
stop with an error before client files are written. **This is not yet a universal Ascension client installer.**

The manifest includes source provenance and the reviewed Windows MPQ utility build:
[mpqcli](https://github.com/thegraydot/mpqcli), revision
`4bd21908966bafbafc55c6dd293c68488684d212`, executable SHA-256
`5dc56b130432098d18e911fdf4b3464adf850432b7fbb35003a2feff7c30a79f`.
Supply that utility yourself; this repository does not include or download it. A different build needs separate
qualification before its fingerprint is accepted. Python 3.11+ on native Windows is required; installation and
rollback intentionally refuse WSL because the game-process check must cover the Windows client.

Create a new artifact directory **outside the client, on the same drive**, for each preparation. Its parent
must exist. It will contain local copies of your original archive and extracted files: keep it private and do
not commit it to GitHub. For example, from this server repository:

```powershell
python scripts/client-patches.py prepare --client 'D:\Games\CoA' --artifacts 'D:\CoA-Backups\g1-client-001' --mpq-tool 'D:\Tools\mpqcli.exe'
```

Preparation does not change the client and may run while it is open. It rejects unsafe archive paths and
duplicate names, checks every named member after extraction, applies only the reviewed source changes, and
verifies all unrelated ordinary members byte-for-byte. Generated MPQ metadata may change. It records the
prepared archive's actual hash instead of assuming different MPQ packing runs produce identical archives.

If WeakAuras is installed, its `Prototypes.lua` must match the known original or repaired fingerprint. The
repair preserves mixed line endings and checks the exact resulting bytes. Unknown customized versions stop
for review; the tool does not overwrite them with a bundled copy. An absent WeakAuras installation is allowed.
The retired `COAWeakAurasRange` addon is moved to the artifact directory at installation, with its original
files retained. SavedVariables are not moved or replaced.

After reviewing `prepared.json`, fully close every game client and MMgr64, then run:

```powershell
python scripts/client-patches.py install --client 'D:\Games\CoA' --artifacts 'D:\CoA-Backups\g1-client-001'
```

Installation rechecks the source package, prepared files, original client inputs and closed-game state. Each
file is replaced atomically; the complete multi-file operation is not a transaction. If a later step fails,
keep the game closed and use the same artifact directory to restore the exact original files:

```powershell
python scripts/client-patches.py rollback --client 'D:\Games\CoA' --artifacts 'D:\CoA-Backups\g1-client-001'
```

Rollback refuses to overwrite files changed since installation. Preserve the artifact directory until you
have tested the client. After any failure or interruption, use rollback rather than repeating installation.
The tool never starts the client, changes a realm address, downloads an archive, or modifies server databases.

The older `Install-CoA*Staging.ps1` helpers are historical machine-specific procedures. Do not use them as
community installers. The source diffs and manifest are the portable recipe; a matching client is still needed.

## Optional environmental graphics

Our graphics enhancement comes from [jealous-sound/coa-vfog](https://github.com/jealous-sound/coa-vfog), not from
the Classic 1.12.1 `comfyatmosphere` build. CoAVolFog targets the CoA 12340 Direct3D 9 client. It changes fog and
water rendering locally and is independent of server gameplay. See the upstream [design, requirements and
limitations](https://github.com/jealous-sound/coa-vfog/blob/main/README.md).

[`client-patches/coa-graphics`](../client-patches/coa-graphics/README.md) pins the tested source revision and
includes our small water-render-state correction and its regression tests. No graphics DLLs, fog/water data,
or game assets are mirrored in this repository. Building the upstream project obtains its data and dependencies
from their original locations. Review their provenance and terms rather than assuming a software license
establishes permission for every third-party game asset.

Install Visual Studio 2022 C++ x86 tools, a Windows SDK with `fxc`, CMake, Git, Python 3.8+ and PowerShell 7.
Run from a Visual Studio Developer PowerShell with `git`, `cmake`, `ctest` and Python on its PATH. Use an
ordinary local checkout and two new directories whose parents already exist; linked folders and OneDrive
reparse-point paths are refused. If Python is not on PATH, supply its full path with `-PythonExecutable`:

```powershell
pwsh scripts/Build-CoAGraphics.ps1 -SourceDirectory 'D:\CoA-Builds\vfog-source' -BuildDirectory 'D:\CoA-Builds\vfog-build'
```

This clones the fixed upstream revision, applies the bundled source/test patch, sets the compatibility preset
`FarClipMax=0`, and runs the upstream build and test harness. A successful run produces
`coa-graphics-build.json` and the five files described by the upstream installation guide. **It does not install
anything into your client.** The receipt names both required tests, `vfog_harness` and `comments`; missing
tests cause failure. On 2026-10-29, the complete helper passed from new source and build directories on
Windows with VS2022 x86 tools, Windows SDK 10.0.26100.0 and Python 3.12: both tests passed, including the
Direct3D 9 rendering harness. This verifies the build recipe on that toolchain; fresh-machine prerequisite
installation and in-game acceptance on other hardware remain separate checks.

For installation, close the client and first back up any existing `version.dll`, `CoAVolFog.dll`,
`CoAVolFog.ini`, `fogdata.bin` and `waterdata.bin`. A pre-existing `version.dll` may belong to another loader:
do not overwrite it without resolving that conflict. Follow the upstream instructions to place the matched
build's files beside `Ascension.exe`. Keep existing INI preferences; compare keys against the new defaults
instead of replacing settings blindly. Test on your own GPU. An offline rendering harness does not prove
in-game appearance or performance. Restore your exact pre-install files to undo the graphics change.

## Settings and future compatibility

FPS limits, VSync, refresh rate, quality and sound preferences belong to the player. The community package
does not import our WTF folder or automatically impose our display settings. Use the in-game controls and
back up your settings before optional tuning.

For a new client version, capture file/member fingerprints and compare the actual code before adding a
manifest entry. Keep the native talent, range and wardrobe changes together; restoring an older complete
archive can silently undo a newer fix. Ordinary addon updates should remain separate from archive repairs.

Tests for this tooling use synthetic clients and copies of retained archives. They are not a claim that a
new user's client was installed or that its rendering has been tested. No local playable client needs to be
replaced when publishing these source recipes.
