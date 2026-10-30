# Optional CoAVolFog recipe

This is an optional integration of **[jealous-sound/coa-vfog](https://github.com/jealous-sound/coa-vfog)**.
The upstream project supplies the fog/water renderer. It targets Ascension/CoA 3.3.5a build 12340 using Direct3D 9.
It is not the Classic 1.12.1 `comfyatmosphere` binary.

The reviewed source foundation is `4e31ddf53a326ba9c0ad03488b4c30f7ce23c969` plus
`ripple-state-preservation.patch`. The patch expands the saved/restored pixel-constant range to include the
ripple disturbance constants and adds corresponding state-preservation regression coverage. The graphics
build recipe sets `FarClipMax=0` so this preset leaves the client's view-distance cap in place.

The patch includes only source and tests. This directory intentionally has no DLLs, MPQs, `fogdata.bin`,
`waterdata.bin`, client executables, extracted game assets, or personal settings. The local G1 installation's
renderer, loader and data hashes matched its retained build; its INI has since been customized. Rebuilding
the source need not reproduce the same PE binary hash on a different compiler/toolchain.

Use [`Build-CoAGraphics.ps1`](../../scripts/Build-CoAGraphics.ps1) to prepare a new source/build pair and run
the upstream tests. It records the actual output hashes and never installs them into a client. Requirements,
manual installation checks, rollback and current qualification limits are in [client setup](../../docs/client-setup.md).
The full helper passed a fresh source/build run on Windows on 2026-10-29 with both required tests:
`vfog_harness` and `comments`. The helper requires Python and refuses to qualify a build with either test missing.
The upstream project still needs in-game validation for a user's rendering path and hardware.

## Credit and terms

Upstream identifies the software as **GPL-3.0-only** and states an additional permission for combining it with
the WoW client; see its [README license section](https://github.com/jealous-sound/coa-vfog/blob/main/README.md#license)
and [LICENSE](https://github.com/jealous-sound/coa-vfog/blob/main/LICENSE). A copy is retained as
`LICENSE.coa-vfog`. The source/test patch follows that license and retains upstream attribution.

Dear ImGui is an upstream build dependency with its own notices. The fog/water conversion tools describe
data derived from Classic/Forever inputs; do not infer game-asset redistribution rights from the software
license statement. Keep acquisition and provenance with the original sources. This optional recipe does
not grant rights to redistribute a game client or other third-party assets.
