#!/usr/bin/env python3
"""Execute the production range library with controlled WoW APIs in Lua 5.1."""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "client-patches/coa-range/LibRangeCheck-2.0.lua"
LUA51 = os.environ.get("LUA51")
WEAKAURAS_PROTOTYPE = None
WEAKAURAS_PATCH = ROOT / "client-patches/coa-range/WeakAuras-GetRange.patch"


WOW_FIXTURE = r'''
assert(_VERSION == "Lua 5.1", "the regression requires the WoW Lua 5.1 runtime")
BOOKTYPE_SPELL = "spell"
tinsert, tremove = table.insert, table.remove
function wipe(t) for k in pairs(t) do t[k] = nil end return t end

PlayerClass = "PRIMALIST"
Spellbook, SpellByID, CachedItems, ItemChecks = {}, {}, {}, {}
Units = {
    target = { exists = true, harmful = true, distance = 12 },
    friend = { exists = true, helpful = true, distance = 12 },
    corpse = { exists = true, dead = true, distance = 12 },
    neutral = { exists = true, distance = 12 },
}
SpellQueries, ClassifierQueries, BookQueries = {}, {}, 0

function SetSpellbook(rows)
    Spellbook, SpellByID = rows, {}
    for i, row in ipairs(rows) do
        row.name = row.name or ("fixture spell " .. row.id)
        row.rank = row.rank or "Rank 1"
        SpellByID[row.id] = row
    end
end
function Spell(id, maxRange, helpful, minRange)
    return {id = id, maxRange = maxRange, minRange = minRange or 0,
            helpful = helpful or false, harmful = not helpful, hasRange = true}
end
function UnitClass(unit) return "Custom class", PlayerClass end
function UnitRace(unit) return "Human", "Human" end
function UnitExists(unit) return Units[unit] and Units[unit].exists or false end
function UnitIsDeadOrGhost(unit) return Units[unit] and Units[unit].dead or false end
function UnitCanAttack(player, unit) return Units[unit] and Units[unit].harmful or false end
function UnitCanAssist(player, unit) return Units[unit] and Units[unit].helpful or false end
function UnitIsVisible(unit) return UnitExists(unit) end
function GetSpellName(slot, book)
    BookQueries = BookQueries + 1
    assert(book == BOOKTYPE_SPELL, "spellbook name must use the spell book")
    local row = Spellbook[slot]
    if row then return row.name, row.rank end
end
function GetSpellBookItemInfo(slot, book)
    assert(book == BOOKTYPE_SPELL, "spellbook ID must use the spell book")
    local row = Spellbook[slot]
    if row then return row.itemType or "spell", row.id end
end
function GetSpellLink(slot, book)
    local row = Spellbook[slot]
    if row then return "|Hspell:" .. row.id .. "|h[" .. row.name .. "]|h" end
end
function GetSpellInfo(value)
    local row = SpellByID[value]
    if type(value) == "string" then
        for _, candidate in ipairs(Spellbook) do
            if candidate.name == value then row = candidate break end
        end
    end
    if row then return row.name, row.rank, nil, nil, nil, nil, nil, row.minRange, row.maxRange end
end
function SpellHasRange(slot, book)
    assert(book == BOOKTYPE_SPELL, "SpellHasRange must use the actual spellbook slot")
    local row = Spellbook[slot]
    return row and row.hasRange or false
end
function IsSpellInRange(slot, book, unit)
    assert(book == BOOKTYPE_SPELL, "range must use the actual spellbook slot")
    local row, target = Spellbook[slot], Units[unit]
    SpellQueries[#SpellQueries + 1] = {slot = slot, id = row and row.id, unit = unit}
    if not row or not target or not target.exists or target.dead then return nil end
    if row.response == "unknown" then return nil end
    if row.response ~= nil then return row.response end
    if row.helpful and not target.helpful or row.harmful and not target.harmful then return nil end
    if target.distance >= row.minRange and target.distance <= row.maxRange then return 1 end
    return 0
end
local function classify(id, byID, field)
    assert(byID == true, "native C_Spell classification must explicitly use spell IDs")
    ClassifierQueries[#ClassifierQueries + 1] = {id = id, byID = byID, field = field}
    local row = SpellByID[id]
    return row and row[field] or false
end
C_Spell = {
    IsHarmfulSpell = function(id, byID) return classify(id, byID, "harmful") end,
    IsHelpfulSpell = function(id, byID) return classify(id, byID, "helpful") end,
}
function IsHarmfulSpell(name)
    assert(type(name) == "string", "legacy classifiers must use an actual spell name")
    for _, row in ipairs(Spellbook) do if row.name == name then return row.harmful end end
    return false
end
function IsHelpfulSpell(name)
    assert(type(name) == "string", "legacy classifiers must use an actual spell name")
    for _, row in ipairs(Spellbook) do if row.name == name then return row.helpful end end
    return false
end
function CheckInteractDistance(unit, index)
    local target = Units[unit]
    if not target or not target.exists then return false end
    return target.distance <= ({[2] = 9, [3] = 8, [4] = 28})[index]
end
function GetItemInfoInstant(id) if CachedItems[id] then return id end end
function GetItemInfo(id) if CachedItems[id] then return "fixture item " .. id end end
function IsItemInRange(id, unit) return ItemChecks[id] end
Item = {CreateFromID = function(self, id)
    return {ContinueOnLoad = function(self, callback) callback(id) end}
end}
ItemRefTooltip = {SetHyperlink = function() end}
function GetInventorySlotInfo() return 10 end
function GetInventoryItemLink() return nil end
function GetTime() return 100 end
function CreateFrame()
    return {
        events = {}, scripts = {},
        RegisterEvent = function(self, event) self.events[event] = true end,
        SetScript = function(self, event, callback) self.scripts[event] = callback end,
        Show = function() end, Hide = function() end,
    }
end
RangeLib = {}
LibStub = setmetatable({NewAscensionLibrary = function(self, name)
    assert(name == "LibRangeCheck-2.0") return RangeLib
end}, {__call = function(self, name)
    if name == "LibRangeCheck-2.0" then return RangeLib end
    if name == "SpellRange-1.0" then
        return {IsSpellInRange = function(id, unit)
            for slot, row in ipairs(Spellbook) do
                if row.id == id then return IsSpellInRange(slot, BOOKTYPE_SPELL, unit) end
            end
        end}
    end
    error("unexpected dependency: " .. name)
end})

function LoadLibrary()
    assert(loadfile(arg[1]))()
    assert(type(RangeLib.GetRange) == "function", "the actual production library must load")
    RangeLib:init(true)
    return RangeLib
end
function Same(actual, expected, message)
    assert(actual == expected, (message or "value mismatch") .. ": expected " ..
           tostring(expected) .. ", got " .. tostring(actual))
end
function Range(lib, unit, lower, upper)
    local a, b = lib:GetRange(unit)
    Same(a, lower, "lower range for " .. unit)
    Same(b, upper, "upper range for " .. unit)
end
'''


def actual_weak_auras_prefix():
    if not WEAKAURAS_PROTOTYPE or not WEAKAURAS_PROTOTYPE.is_file():
        raise unittest.SkipTest("WeakAuras integration requires --weakAurasPrototype with the actual Prototypes.lua")
    source = WEAKAURAS_PROTOTYPE.read_text(encoding="utf-8")
    marker = "local RangeCacheStrings ="
    if source.count(marker) != 1:
        raise RuntimeError("WeakAuras prefix boundary is missing or ambiguous")
    prefix = source.split(marker, 1)[0]
    patch = WEAKAURAS_PATCH.read_text(encoding="utf-8").splitlines(keepends=True)
    headers = [i for i, line in enumerate(patch) if line.startswith("@@ ")]
    if len(headers) != 1:
        raise RuntimeError("Expected one reviewed WeakAuras patch hunk")
    header = re.fullmatch(r"@@ -\d+,(\d+) \+\d+,(\d+) @@[^\n]*\n?", patch[headers[0]])
    if not header:
        raise RuntimeError("Unsupported WeakAuras patch header")
    old, new = [], []
    for line in patch[headers[0] + 1:]:
        if not line or line[0] not in " +-":
            raise RuntimeError("Unsupported WeakAuras patch content")
        if line[0] in " -":
            old.append(line[1:])
        if line[0] in " +":
            new.append(line[1:])
    if len(old) != int(header.group(1)) or len(new) != int(header.group(2)):
        raise RuntimeError("WeakAuras patch hunk counts do not match its content")
    old, new = "".join(old), "".join(new)
    if prefix.count(old) == 1:
        prefix = prefix.replace(old, new, 1)
    elif prefix.count(old) != 0 or prefix.count(new) != 1:
        raise RuntimeError("Actual WeakAuras source does not match the reviewed old or installed new wrapper")
    if prefix.count("function WeakAuras.GetRange(") != 1 or prefix.count("function WeakAuras.CheckRange(") != 1:
        raise RuntimeError("Actual WeakAuras public range definitions are missing or ambiguous")
    return prefix


class ProductionRangeLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua = LUA51 or shutil.which("lua5.1") or shutil.which("lua51") or shutil.which("lua")
        if not cls.lua:
            raise RuntimeError("Lua 5.1 unavailable: supply --lua51 or LUA51; no packages are installed by this suite")
        if not LIBRARY.is_file():
            raise RuntimeError(f"Production library unavailable: {LIBRARY}")
        version = subprocess.run([cls.lua, "-e", "io.write(_VERSION)"], capture_output=True, text=True, timeout=10)
        if version.returncode or version.stdout != "Lua 5.1":
            raise RuntimeError("The supplied runtime is not Lua 5.1")

    def lua_case(self, body):
        result = subprocess.run(
            [self.lua, "-", str(LIBRARY)], input=WOW_FIXTURE + "\n" + body,
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_unknown_coa_classes_discover_known_five_twenty_thirty_yard_spells(self):
        for token in ("PRIMALIST", "NECROMANCER"):
            with self.subTest(class_token=token):
                self.lua_case(f'''
PlayerClass = "{token}"
SetSpellbook({{Spell(880001, 5), Spell(880002, 20), Spell(880003, 30)}})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(5) and lib:GetHarmChecker(20) and lib:GetHarmChecker(30))
Range(lib, "target", 5, 20)
assert(#ClassifierQueries > 0)
''')

    def test_rank_and_spellbook_refresh_uses_current_ids_and_slots(self):
        self.lua_case('''
local first = Spell(880002, 20); first.name = "Ranked fixture"
SetSpellbook({first})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(20))
local replacement = Spell(880004, 40); replacement.name = "Ranked fixture"; replacement.rank = "Rank 2"
SetSpellbook({Spell(880005, 5), replacement})
lib:OnEvent("LEARNED_SPELL_IN_TAB")
Same(lib.initialized, nil, "spell learning invalidates cached metadata")
lib:init()
Same(lib:GetHarmChecker(20), nil, "the old rank distance must disappear")
assert(lib:GetHarmChecker(40))
Range(lib, "target", 5, 40)
Same(SpellQueries[1].id, 880004, "range check resolves the replacement rank at its current slot")
assert(lib.frame.events.SPELLS_CHANGED and lib.frame.events.PLAYER_ENTERING_WORLD)
''')

    def test_same_range_unknown_first_candidate_does_not_hide_valid_second(self):
        self.lua_case('''
local unavailable = Spell(880002, 20); unavailable.response = "unknown"
SetSpellbook({Spell(880001, 5), unavailable, Spell(880004, 20), Spell(880003, 30)})
local lib = LoadLibrary()
Same(lib:GetHarmChecker(20)("target"), true)
Range(lib, "target", 5, 20)
''')

    def test_same_range_false_first_candidate_does_not_hide_valid_second(self):
        self.lua_case('''
local unavailable = Spell(880002, 20); unavailable.response = 0
SetSpellbook({Spell(880001, 5), unavailable, Spell(880004, 20)})
local lib = LoadLibrary()
Same(lib:GetHarmChecker(20)("target"), true)
Range(lib, "target", 5, 20)
''')

    def test_all_unknown_spell_results_do_not_manufacture_out_of_range(self):
        self.lua_case('''
local a, b, c = Spell(880001, 5), Spell(880002, 20), Spell(880003, 30)
a.response, b.response, c.response = "unknown", "unknown", "unknown"
SetSpellbook({a, b, c})
local lib = LoadLibrary()
Same(lib:GetHarmChecker(20)("target"), nil)
Range(lib, "target", nil, nil)
''')

    def test_unknown_small_checker_does_not_create_false_lower_bound(self):
        self.lua_case('''
local small = Spell(880001, 5); small.response = "unknown"
SetSpellbook({small, Spell(880002, 20)})
Range(LoadLibrary(), "target", 1, 20)
''')

    def test_known_negative_remains_useful_when_other_checks_are_unknown(self):
        self.lua_case('''
local unknown = Spell(880002, 20); unknown.response = "unknown"
SetSpellbook({Spell(880001, 5), unknown})
Range(LoadLibrary(), "target", 5, nil)
''')

    def test_positive_tight_item_fallback_is_not_widened_by_spell_checkers(self):
        self.lua_case('''
CachedItems[33278], ItemChecks[33278] = true, 1
SetSpellbook({Spell(880002, 20), Spell(880003, 30)})
local lib = LoadLibrary()
Same(lib:GetHarmChecker(8)("target"), true)
Range(lib, "target", 1, 8)
''')

    def test_friend_harm_classification_and_native_id_signature(self):
        self.lua_case('''
SetSpellbook({Spell(880002, 20), Spell(880003, 30, true)})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(20) and lib:GetFriendChecker(30))
Same(lib:GetHarmChecker(30), nil)
Same(lib:GetFriendChecker(20), nil)
Range(lib, "target", 1, 20)
Range(lib, "friend", 1, 30)
for _, query in ipairs(ClassifierQueries) do
    assert(SpellByID[query.id] and query.byID == true)
end
''')

    def test_dead_neutral_and_missing_units_keep_existing_interaction_behavior(self):
        self.lua_case('''
SetSpellbook({Spell(880001, 5, true), Spell(880002, 20, true), Spell(880003, 30)})
local lib = LoadLibrary()
Range(lib, "friend", 5, 20)
local queries = #SpellQueries
Range(lib, "corpse", 9, 28)
Range(lib, "neutral", 9, 28)
Range(lib, "missing", nil, nil)
Same(#SpellQueries, queries, "dead/misc/nonexistent units must not query targeting spells")
''')

    def test_discovery_excludes_minimum_range_nonrange_self_and_invalid_ranges(self):
        self.lua_case('''
local minimum = Spell(880011, 40, false, 8)
local self = Spell(880012, 15); self.hasRange = false
local zero = Spell(880013, 0)
local negative = Spell(880014, -1)
local infinite = Spell(880015, math.huge)
local nan = Spell(880016, 0 / 0)
SetSpellbook({Spell(880002, 20), minimum, self, zero, negative, infinite, nan})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(20))
for _, range in ipairs({40, 15, 0, -1, math.huge}) do Same(lib:GetHarmChecker(range), nil) end
Range(lib, "target", 1, 20)
''')

    def test_missing_classifiers_preserve_fallback_without_guessing_spell_target_type(self):
        self.lua_case('''
C_Spell, IsHarmfulSpell, IsHelpfulSpell = nil, nil, nil
SetSpellbook({Spell(880002, 20)})
local lib = LoadLibrary()
Same(lib:GetHarmChecker(20), nil)
Same(lib:GetFriendChecker(20), nil)
Range(lib, "target", 9, 28)
Same(#SpellQueries, 0)
''')

    def test_legacy_named_classifiers_work_when_native_classifiers_are_absent(self):
        self.lua_case('''
C_Spell = nil
SetSpellbook({Spell(880002, 20), Spell(880003, 30, true)})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(20) and lib:GetFriendChecker(30))
Range(lib, "target", 1, 20)
Range(lib, "friend", 1, 30)
''')

    def test_contradictory_negative_does_not_erase_tighter_positive(self):
        self.lua_case('''
local small, large = Spell(880001, 5), Spell(880003, 30)
small.response, large.response = 1, 0
SetSpellbook({small, large})
Range(LoadLibrary(), "target", 1, 5)
''')

    def test_unclassified_spell_with_positive_range_is_not_inferred_from_range_results(self):
        self.lua_case('''
local unclassified = Spell(880011, 30)
unclassified.helpful, unclassified.harmful, unclassified.response = false, false, 1
SetSpellbook({Spell(880002, 20), unclassified})
local lib = LoadLibrary()
Same(lib:GetHarmChecker(30), nil)
Same(lib:GetFriendChecker(30), nil)
Range(lib, "target", 1, 20)
''')

    def test_same_name_ranks_use_actual_spell_ids_not_first_matching_name(self):
        self.lua_case('''
local first, second = Spell(880011, 40), Spell(880012, 20)
first.name, second.name = "Shared name", "Shared name"
first.rank, second.rank = "Rank 1", "Rank 2"
SetSpellbook({first, second})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(20) and lib:GetHarmChecker(40))
Range(lib, "target", 1, 20)
''')

    def test_spell_link_id_fallback_does_not_require_newer_spellbook_api(self):
        self.lua_case('''
GetSpellBookItemInfo = nil
SetSpellbook({Spell(880001, 5), Spell(880002, 20)})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(20))
Range(lib, "target", 5, 20)
''')

    def test_measurements_do_not_rescan_spellbook_but_registered_events_do(self):
        self.lua_case('''
SetSpellbook({Spell(880001, 5), Spell(880002, 20)})
local lib = LoadLibrary()
local reads = BookQueries
for i = 1, 10 do Range(lib, "target", 5, 20) end
Same(BookQueries, reads, "range measurements reuse cached spellbook metadata")
for _, event in ipairs({"SPELLS_CHANGED", "PLAYER_ENTERING_WORLD", "PLAYER_TALENT_UPDATE"}) do
    lib:OnEvent(event)
    Same(lib.initialized, nil, "event invalidates cached spellbook")
    lib:init()
    assert(BookQueries > reads)
    reads = BookQueries
end
''')

    def test_trusted_stock_melee_and_minimum_range_probes_are_preserved(self):
        self.lua_case('''
PlayerClass = "WARRIOR"
SetSpellbook({Spell(100, 25, false, 8), Spell(772, 0)})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(25) and lib:GetHarmChecker(5))
Range(lib, "target", 8, 25)
''')

    def test_first_positive_same_range_candidate_short_circuits_more_measurements(self):
        self.lua_case('''
SetSpellbook({Spell(880002, 20), Spell(880004, 20)})
local lib = LoadLibrary()
Same(lib:GetHarmChecker(20)("target"), true)
Same(#SpellQueries, 1, "a positive equivalent checker must not query further alternatives")
Same(SpellQueries[1].id, 880002)
''')

    def test_stock_charge_near_normal_and_far_bounds_remain_valid(self):
        self.lua_case('''
PlayerClass = "WARRIOR"
SetSpellbook({Spell(100, 25, false, 8)})
local lib = LoadLibrary()
Units.target.distance = 3
Range(lib, "target", 1, 8)
Units.target.distance = 12
Range(lib, "target", 8, 25)
Units.target.distance = 30
Range(lib, "target", 25, nil)
''')

    def test_stock_hunter_minimum_range_keeps_near_and_far_bounds(self):
        self.lua_case('''
PlayerClass = "HUNTER"
SetSpellbook({Spell(53351, 45, false, 5)})
local lib = LoadLibrary()
assert(lib:GetHarmChecker(45))
Units.target.distance = 3
Range(lib, "target", 1, 5)
Units.target.distance = 50
Range(lib, "target", 45, nil)
''')

    def test_unknown_minimum_range_reference_does_not_claim_outside_charge_maximum(self):
        self.lua_case('''
PlayerClass = "WARRIOR"
CachedItems[33069] = true
local charge = Spell(100, 25, false, 8); charge.response = 0
SetSpellbook({charge, Spell(880004, 40)})
local lib = LoadLibrary()
Same(lib:GetHarmChecker(25)("target"), nil)
Range(lib, "target", 1, 40)
''')


class ActualWeakAurasIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prefix = actual_weak_auras_prefix()
        ProductionRangeLibraryTests.setUpClass.__func__(cls)

    def integration_case(self, preparation, assertions):
        body = preparation + '''
local lib = LoadLibrary()
WeakAuras = {IsLibsOK = function() return true end, L = {}}
''' + self.prefix + "\n" + assertions
        ProductionRangeLibraryTests.lua_case(self, body)

    def test_plain_get_range_and_check_range_share_actual_library_bounds(self):
        self.integration_case('''
SetSpellbook({Spell(880001, 5), Spell(880002, 20), Spell(880003, 30)})
''', '''
local a, b = WeakAuras.GetRange("target", true)
Same(a, 5); Same(b, 20)
Same(WeakAuras.CheckRange("target", "20", "<="), true)
Same(WeakAuras.CheckRange("target", 5, "<="), false)
Same(WeakAuras.CheckRange("target", 30, "<="), true)
Same(WeakAuras.CheckRange("target", 5, ">="), true)
Same(WeakAuras.CheckRange("target", 20, ">="), false)
Units.target.distance = 21
local a, b = WeakAuras.GetRange("target")
Same(a, 20); Same(b, 30)
Same(WeakAuras.CheckRange("target", 20, "<="), false)
Same(WeakAuras.CheckRange("target", 30, "<="), true)
Same(WeakAuras.CheckRange("target", 20, ">="), true)
Same(WeakAuras.CheckRange("target", "not a distance", "<="), nil)
''')

    def test_actual_weak_auras_functions_do_not_turn_unknown_or_missing_into_positive_range(self):
        self.integration_case('''
local unknown = Spell(880002, 20); unknown.response = "unknown"
SetSpellbook({unknown})
''', '''
for _, unit in ipairs({"target", "missing"}) do
    local a, b = WeakAuras.GetRange(unit)
    Same(a, nil); Same(b, nil)
    Same(WeakAuras.CheckRange(unit, 20, "<="), false)
    Same(WeakAuras.CheckRange(unit, 20, ">="), false)
end
''')

    def test_actual_weak_auras_functions_preserve_friendly_and_tighter_item_ranges(self):
        self.integration_case('''
CachedItems[33278], ItemChecks[33278] = true, 1
SetSpellbook({Spell(880002, 20), Spell(880003, 30, true)})
''', '''
local a, b = WeakAuras.GetRange("target")
Same(a, 1); Same(b, 8)
Same(WeakAuras.CheckRange("target", 8, "<="), true)
local a, b = WeakAuras.GetRange("friend")
Same(a, 1); Same(b, 8)
Same(WeakAuras.CheckRange("friend", 8, "<="), true)
''')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lua51", help="Explicit Lua 5.1 executable; no dependency installation is performed")
    parser.add_argument("--baselineLibrary", "--baseline-library", type=Path,
                        help="Run identical regressions against the unchanged baseline (expected RED)")
    parser.add_argument("--weakAurasPrototype", "--weak-auras-prototype", type=Path,
                        help="Actual Prototypes.lua: execute its range prefix with the reviewed plain-wrapper patch")
    args, unittest_args = parser.parse_known_args()
    if args.lua51:
        LUA51 = args.lua51
    if args.baselineLibrary:
        LIBRARY = args.baselineLibrary.resolve()
    if args.weakAurasPrototype:
        WEAKAURAS_PROTOTYPE = args.weakAurasPrototype.resolve()
    print(f"Actual Lua library under test: {LIBRARY}", flush=True)
    unittest.main(argv=[__file__, *unittest_args])
