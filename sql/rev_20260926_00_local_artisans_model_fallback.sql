-- The earlier local repair selected display 48503 for Book of Artisans.
-- This COA server DBC does not contain that display, so creature 57500 cannot
-- be summoned. Reuse the valid Flying Book display used by Book of Ascension.
-- Keep this as a new migration; the earlier applied migration must not change.
INSERT INTO `creature_template_model`
    (`CreatureID`, `Idx`, `CreatureDisplayID`, `DisplayScale`, `Probability`, `VerifiedBuild`)
VALUES
    (57500, 0, 48501, 1, 1, NULL)
ON DUPLICATE KEY UPDATE
    `CreatureDisplayID` = VALUES(`CreatureDisplayID`),
    `DisplayScale` = VALUES(`DisplayScale`),
    `Probability` = VALUES(`Probability`);
