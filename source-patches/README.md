# COA source patch recipes

This checkpoint contains two different integration paths. The existing installer uses the accepted
old-core build. The G1 native candidate is staging-only and has separate exports. Committing these
files does not upgrade a running realm or make the installer a qualified production-upgrade tool.

## Accepted legacy installer

Use the ordered patches in [install-coa.sh](../scripts/install-coa.sh) and
[validate-playerbots-patches.sh](../tests/validate-playerbots-patches.sh), pinned to core
`a8b28faac98d81b063bb81ff634037f71827d128` and Playerbots
`619a06fc795a7220fd5c27d5a5aa4a2fbe383b72`. The older compatibility module remains part of this path.
Do not append native-core patches to it.

## Native G1 candidate

Core pin: `d48a1123153a3c39e1eaafb7714b375ee67e7689`. Apply in order:

1. `coa-g1-preservation.patch`
2. `coa-g1-bot-mounts.patch`

Playerbots pin: `619a06fc795a7220fd5c27d5a5aa4a2fbe383b72`. Apply in order:

1. `playerbots-coa.patch`
2. `playerbots-follow-mount.patch`
3. `playerbots-coa-noncombat.patch`
4. `playerbots-coa-roles.patch`
5. `playerbots-coa-heal-ranks.patch`
6. `playerbots-coa-pilot-recruit.patch`
7. `playerbots-coa-pilot-reservation.patch`
8. `playerbots-coa-combat-travel.patch`
9. `playerbots-coa-riding-preservation.patch`
10. `playerbots-coa-native-mounts.patch`

The ordered exports reproduce the covered qualified candidate source. Matching qualified client data,
configuration, native COA and selected modules are still required; these patches alone are not an installer.
The old core hook, compatibility-module, progression and talent-bridge patches are not additional native
dependencies. See the [gameplay roadmap](../docs/gameplay-roadmap.md) and
[migration evidence](../docs/upstream-gameplay-audit.md) for preserved state, remaining features and
production-promotion boundaries. Native verification uses the core's `tools/verify_all.py` entry point;
the legacy validation script is not native build/runtime evidence.

## Historical reference alternatives

`playerbots-coa-compat.patch`, `playerbots-coa-population.patch` and
`playerbots-coa-initialization.patch` are an earlier minimal reference stack, in that order. They overlap
the full Playerbots recipe above and must not be applied alongside it. They are not selected by the installer
or the deployed native candidate recipe and do not contain the full tested healer/travel feature set.

The initialization export's stale hunk headers were corrected for this checkpoint without changing its
code. Exact-context in-memory application against the module pin passed. Adding the separate riding
preservation patch produces a factory file byte-identical to the qualified candidate. This is a narrow
applicability/equivalence check, not a combined build or runtime qualification of the alternative stack.
The fast suite parses every patch to catch malformed exports; parsing is not dependency validation.

Private database snapshots, runtime credentials, client archives and game-data packages are intentionally
excluded from this repository. Retain existing upstream notices and attribution when adapting source.
