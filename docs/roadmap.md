# Roadmap

G1 is the public source baseline. Work is prioritized by observed gameplay problems and reproducibility,
not by a promise to implement every idea before a release. There are no delivery-date commitments here.

| Status | Work | Acceptance target |
| --- | --- | --- |
| Current release | CoA bot integration, dungeon access/completion fixes, profession improvements, client compatibility, live gathering alerts | See [observed results](g1-improvements.md) and [verification](g1-verification.md). |
| Active | Reproducible community installation and matching client/addon packages | A new isolated installation from public pins, with no personal database snapshot. |
| Active | Playerbot reliability and dungeon feedback | More level ranges, classes, tank/healer/DPS combinations, deaths, reconnects and full dungeon completion; review authored talent coverage beyond level 60. |
| Active | Reviewed upstream updates | Weekly review, frozen revisions, local-fix overlap/migration checks, isolated qualification, then a versioned release. |
| Next | Existing-server update and restore workflow | Latest-data backup, migration identity checks, rehearsal, preservation of accounts/characters/bot profiles, rollback proof. |
| Next | Portable client-data preparation | Qualify matching DBC and terrain extraction from the user's own client, including modified-town geometry. |
| Next | Gathering alert refinement | Feedback on sound, visual alignment, rate, tracking changes and different minimap settings. |
| Planned | Population testing toward 1,500 bots | Measure resource use and gameplay timing while retaining reliable parties and role availability. |
| Planned | Profession-service polish | Investigate Book of Artisans duplicate development entries and recipe requirements against effective data. |
| Deferred | Faster escort NPC travel | Confirm quest scripts, path timing and encounter behavior before changing speed. |
| Deferred | Additional convenience/vanity delivery polish | Reproduce unsupported entries and distinguish missing data, entitlement and UI issues. |
| Deferred | Tracking other gatherable targets | Herbs/minerals first; beasts/skinnable corpses need separate semantics and testing. |
| Deferred | LLM bot conversations | Consider only after gameplay reliability and population goals; no LLM dependency in G1. |

General feature expansion remains secondary to gameplay maintenance and bots. Upstream fixes are preferred
where they meet the need; local patches should be removed when a qualified upstream equivalent supersedes them.

## Feedback that helps

Include the release ID, character level/class/spec, quest/spell/NPC/dungeon name or ID, expected result,
actual result and steps to reproduce. Screenshots and a short relevant log excerpt are useful. Record whether
a relog changes the behavior. Avoid posting account identifiers, credentials, entire saved-variable files or databases.

Historical design and test notes remain in [gameplay-roadmap.md](gameplay-roadmap.md) and
[playerbots-roadmap.md](playerbots-roadmap.md). Their dated build states are historical; this page defines current priorities.
