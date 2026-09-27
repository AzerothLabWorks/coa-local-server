# COA WeakAuras Range (optional client addon)

The 3.3.5 `LibRangeCheck-2.0` bundled with QuestHelper uses original WotLK class spell tables. Its estimated range can remain at 35–40 yards even when a COA-class spell is in range. This small addon loads after WeakAuras and adds verified COA spell probes for hostile `target` range checks; it does not change the worldserver or third-party addon files.

Supported probes: Seismic Crash (spell 803981, 0–20 yards) and Lichfrost (spells 501969 and 801722, 0–30 yards). These ranges were checked in the supplied COA `Spell.dbc` and `SpellRange.dbc`. An out-of-range or unavailable spell probe leaves WeakAuras' original estimate unchanged. Other classes/spells and friendly-unit range checks are not yet covered.

A positive probe supplies a coarse upper bound of 20 or 30 yards, not an exact distance. It can replace a finer library estimate, so use the matching `<= 20` or `<= 30` threshold; arbitrary melee, 10-yard, or lower-bound checks are not validated by this helper.

With the WoW client **closed**, copy the `COAWeakAurasRange` directory to `C:\Games\Ascension-WOW\Interface\AddOns\` (or the corresponding `Interface/AddOns` directory for another installation). Enable the addon on the character-selection AddOns screen. To undo the change, close the client and remove this one directory.

For verification, on a character who knows Seismic Crash, target a hostile mob and compare the `Seismic Crash` WeakAura at less than 20 yards and beyond 20 yards. The read-only in-game probe is:

```text
/run local a,b=WeakAuras.GetRange('target');print('WA range',a,b,'Seismic',WeakAuras.IsSpellInRange(803981,'target'))
```

Inside Seismic Crash range, the addon should report `WA range 0 20` and the Range Check trigger set to `<= 20` should activate. Outside, the original estimate returns and the trigger should clear. Test Lichfrost analogously on a character who knows it, using spell ID `501969` or `801722` in the read-only probe.
