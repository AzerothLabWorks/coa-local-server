# Native talent loader repair

`native-talent-loaders.patch` removes the four retired compatibility includes from the reviewed client's
`Interface/FrameXML/FrameXML.toc` and `Interface/AddOns/Ascension_Collections/Collections.xml`. The native
G1 talent protocol replaces those legacy loaders. Other includes and the compatibility source members
themselves remain intact.

Apply only through the fingerprinted [client setup procedure](../../docs/client-setup.md). The before/after
member fingerprints are in `../g1-client-manifest.json`. The patch contains only the reviewed differences;
the client archive and executable are supplied by the user.

This client adjustment was deployed locally on October 2, 2026. Subsequent G1 talent-saving and logout/login
reports confirm the tested path. The archive repair does not independently implement server talent validation.
