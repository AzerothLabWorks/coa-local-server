# Attribution and source provenance

Original AzerothLabWorks G1 release tooling and newly authored modules are licensed GPL-2.0-or-later.
The included GPL version 2 text is in `LICENSE`. Existing source, patches, libraries and data retain their
original copyright and license notices; this statement does not relicense third-party assets.

- **AzerothCore** and **jealous-sound/azerothcore-wotlk-coa** supply the server foundation, native CoA systems,
  content fixes, database tools and verification framework. The manifest identifies the exact source revision.
  The pinned fork includes [GPL version 2](https://github.com/jealous-sound/azerothcore-wotlk-coa/blob/bfe93aa95a25c4e60c82995df0d93e083f3bba94/LICENSE)
  and GPL-2.0-or-later file notices; follow each included component's notices.
- **mod-playerbots/mod-playerbots** supplies the bot engine. The public module base and our complete reviewed
  change export are recorded separately; the private development checkpoint commit is not a download dependency.
  Its [license text](https://github.com/mod-playerbots/mod-playerbots/blob/619a06fc795a7220fd5c27d5a5aa4a2fbe383b72/LICENSE)
  is GPL version 2, with GPL-2.0-or-later notices in the source.
- **Zyth45/mod-playerbots / CoA Bots v1.7** supplies the CoA shared AI, specialization/profile implementation
  and authored rule data incorporated in the release. Relevant provenance is retained in the patch and migration
  headers, including reference revision `36c4b93ae0688c19e6baa718f296302071ae30b3`.
- Authored profile data credits **ascensionsidekick.com** in the upstream guide and the safe rotation migration.
- **LibRangeCheck** and **WeakAuras** retain their existing source notices. The client recipe documents the
  compatibility changes without replacing users' saved auras.
- **jealous-sound/coa-vfog** is the optional graphics project. Its GPL-3.0-only license and additional upstream
  permissions are separate from this repository's tooling. The graphics recipe links upstream sources and
  records the local source patch. It does not include a complete client or extracted game-data package.

No server database dump, personal account/character data, repack executable, client executable or MPQ archive
is included. Required game/client data is supplied separately by the installer user.
