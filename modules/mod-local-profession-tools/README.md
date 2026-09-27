# Local profession tools

Adds missing reusable starter tools to player characters when they learn a profession, and checks existing
professions on login. The module uses native skill hooks, so training through the Book of Artisans or another
trainer follows the same behavior.

| Profession | Tools supplied |
| --- | --- |
| Fishing | Fishing Pole (6256) |
| Skinning | Skinning Knife (7005) |
| Mining | Mining Pick (2901) |
| Blacksmithing | Blacksmith Hammer (5956) |
| Engineering | Blacksmith Hammer (5956), Arclight Spanner (6219), Gyromatic Micro-Adjustor (10498) |
| Enchanting | Runed Copper Rod (6218) |
| Inscription | Virtuoso Inking Set (39505) |
| Jewelcrafting | Jeweler's Kit (20815), Simple Grinder (20824) |

Tools go into bags, never replace equipped weapons, and save as ordinary inventory items. Equip the fishing pole
before fishing. The Arclight Spanner requires Engineering 50 to use; receiving it does not bypass that requirement.
Professions without reusable starter tools receive no extra items. Crafting materials, bait, higher-rank
enchanting rods, and advanced Alchemy stones remain part of normal progression.

Existing tools in equipment, bags, or the bank prevent duplicates. Usable upgraded fishing poles, compatible
enchanting rods, and compatible multi-tools count as already owned. A blacksmith/engineer receives only one
hammer. Banked tools stay in the bank. If bags are full, the player receives a message and the next login retries
only the missing tools. Discarded or sold starter tools are also restored on a later login while the profession
is still known. Random Playerbots are excluded.

The installer copies this module into the source tree before CMake configures the build. It requires no SQL
migration or client addon.
