# Community announcement

The text below describes the frozen `g1-20261029` server source release and the separately versioned
WeakAuras compatibility package. Later local development is not automatically included in either release.

---

I've published the source and setup tools for my local Conquest of Azeroth project, **AzerothLabWorks G1**, for
others who want to build and enjoy their own local realm.

The build combines the upstream CoA server with integrated CoA-aware playerbots and the improvements we've
been testing through ordinary questing and dungeon runs:

- Tank, healer and DPS recruitment, plus Dungeon Finder support for Classic, Burning Crusade and Wrath.
- Bots that fight, recover, drink and resurrect where their abilities permit, with contextual World and party
  messages that do not require an LLM.
- Followers that try your active mount, including tested Blossomback Arboon flight in Azeroth, subject to riding
  and location requirements.
- Four-point profession skill gains and a two-second maximum for crafting, smelting, mining and skinning,
  while preserving faster casts.
- Live tracked herb/mineral minimap pings and sound, plus talent, appearance, profession-service and dungeon
  objective/completion fixes.
- Companion GM tools, resource display and dungeon tracker addons; a separate Ascension WeakAuras compatibility
  package; and instructions for optional CoAVolFog environmental graphics.

My reference realm runs 1,000 bots. That's an observed result on my system, not a hardware requirement or
performance guarantee. More dungeon/class testing remains active, including authored bot talent coverage
beyond level 60 and measured testing toward 1,500 bots.

This is a **source release with setup tools** for local play. You'll need Ubuntu/Linux or WSL2, Docker, and
your own compatible CoA client and matching extracted data. Data preparation still requires a separate
workflow; the release does not include a client, game-data download or automatic upgrade of an existing realm.
WeakAuras and environmental graphics have their own setup instructions.

- [Server release and installation guide](https://github.com/AzerothLabWorks/coa-local-server/releases/tag/g1-20261029)
- [Four companion addon downloads](https://github.com/AzerothLabWorks/addons/releases/tag/g1-20261029)
- [WeakAuras for CoA download and setup](https://github.com/AzerothLabWorks/addons/blob/main/docs/weakauras-coa.md)
- [Playerbot guide, roles and mount behavior](https://github.com/AzerothLabWorks/coa-local-server/blob/g1-20261029/docs/playerbots.md)
- [Test scope](https://github.com/AzerothLabWorks/coa-local-server/blob/main/docs/g1-verification.md) and [roadmap](https://github.com/AzerothLabWorks/coa-local-server/blob/main/docs/roadmap.md)

Credit goes to the upstream CoA/AzerothCore developers, mod-playerbots, Zyth's CoA Bots, the WeakAuras and
Ascension addon contributors, and the graphics/community contributors whose work makes this possible.
This project focuses on integrating, testing and sharing the local setup and its improvements.

Feedback on installation and gameplay is welcome. Please include your release version and enough steps to
reproduce a problem so we can keep improving the shared build.
