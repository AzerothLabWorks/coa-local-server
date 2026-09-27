-- Optional COA-specific range probes for WeakAuras 5.21.2 (3.3.5).
-- The bundled LibRangeCheck uses WotLK class spell tables and cannot measure
-- custom COA classes reliably. Spell IDs/ranges below were verified against
-- the supplied COA Spell.dbc and SpellRange.dbc (both spells have min range 0).
local wa = WeakAuras
if not wa or type(wa.GetRange) ~= "function" or type(wa.IsSpellInRange) ~= "function" then
  return
end

local originalGetRange = wa.GetRange
local hostileSpellProbes = {
  { 803981, 20 }, -- Seismic Crash (SpellRange.dbc index 3)
  { 501969, 30 }, -- Lichfrost (SpellRange.dbc index 4)
  { 801722, 30 }, -- Lichfrost alternate ID (SpellRange.dbc index 4)
}

function wa.GetRange(unit, checkVisible)
  if unit == "target" and UnitExists(unit) and UnitCanAttack("player", unit) then
    for _, probe in ipairs(hostileSpellProbes) do
      -- A positive spell check is an exact upper bound. A nil or out-of-range
      -- result provides no new upper bound, so preserve the original estimate.
      if wa.IsSpellInRange(probe[1], unit) == 1 then
        return 0, probe[2]
      end
    end
  end

  return originalGetRange(unit, checkVisible)
end

-- WeakAuras conditions used the raw library, bypassing GetRange entirely.
function wa.CheckRange(unit, range, operator)
  range = tonumber(range)
  if not range then
    return
  end

  local minRange, maxRange = wa.GetRange(unit, true)
  if operator == "<=" then
    return (maxRange or 999) <= range
  end
  return (minRange or 0) >= range
end
