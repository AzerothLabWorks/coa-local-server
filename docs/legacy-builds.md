# Historical installation paths

The historical `scripts/prepare-coa-data.sh` downloads standard terrain. It is not suitable evidence that
terrain matches the modified G1 client. Follow the current [data prerequisites](g1-installation.md) instead.

The original `scripts/install-coa.sh`, `compose.yaml` and older ordered patches reproduce the earlier
local build. They do not install the native G1 release described on the current landing page.

For G1, use `scripts/g1.py` and `releases/g1-20261029/manifest.json`. Do not append old compatibility
patches to the G1 export, replay an old module SQL import against an existing realm, or replace a current
character database with a historical snapshot.

The historical installer pins core `a8b28faac98d81b063bb81ff634037f71827d128` and Playerbots
`619a06fc795a7220fd5c27d5a5aa4a2fbe383b72` with a different patch stack. Its small initial bot defaults,
container layout and module set are not descriptions of the current G1 reference realm.

Historical material is retained for traceability. Future maintenance should add a new release manifest
and reviewed artifacts rather than silently changing the contents of a published release.
