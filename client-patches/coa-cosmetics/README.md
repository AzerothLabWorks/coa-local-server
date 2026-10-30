# Native wardrobe and vanity compatibility

The reviewed source patch replaces the old `.localappearance` submission with
`C_Appearance.ApplyPendingAppearances(false)` and uses native vanity delivery for ordinary items and the
previously special-cased heirlooms. It retains native confirmation and error handling. It does not bypass
collection ownership, unsupported appearance checks, item-template requirements, or bag capacity.

`required-apply-argument.patch` repairs the known intermediate version whose Apply call omitted its required
argument. The full `native-appearance-vanity.patch` already contains that correction; do not apply both to
the same starting file.

The [portable client tool](../../scripts/client-patches.py) selects the correct operation by exact input
fingerprint and verifies each output against `../g1-client-manifest.json`. Read
[client setup](../../docs/client-setup.md) before preparing or installing it. Full MPQ archives are not included.

The corrected path was accepted in G1 playtesting for the reported cosmetics/items, including persistence
after logout/login. That is evidence for the tested entries, not every catalogue item. An unsupported weapon
selection can still legitimately cause the native `NOT_REALM_APPROPRIATE` error.
