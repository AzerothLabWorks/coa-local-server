// The production function is extracted unchanged; only the native APIs are doubled.
#include <cassert>
#include <cstdint>
#include <iostream>
#include <set>
#include <vector>

using uint8 = std::uint8_t;
using uint16 = std::uint16_t;
using uint32 = std::uint32_t;

enum Classes
{
    CLASS_WARRIOR = 1, CLASS_PALADIN, CLASS_HUNTER, CLASS_ROGUE, CLASS_PRIEST,
    CLASS_DEATH_KNIGHT, CLASS_SHAMAN, CLASS_MAGE, CLASS_WARLOCK,
    CLASS_DRUID = 11
};

enum Skills
{
    SKILL_RIDING = 762, SKILL_DEFENSE, SKILL_UNARMED, SKILL_MACES, SKILL_STAVES,
    SKILL_2H_MACES, SKILL_DAGGERS, SKILL_POLEARMS, SKILL_FIST_WEAPONS, SKILL_SWORDS,
    SKILL_AXES, SKILL_BOWS, SKILL_GUNS, SKILL_2H_SWORDS, SKILL_2H_AXES, SKILL_CROSSBOWS,
    SKILL_THROWN, SKILL_DUAL_WIELD, SKILL_PLATE_MAIL, SKILL_WANDS, SKILL_MAIL, SKILL_LOCKPICKING
};

struct Config
{
    uint32 useGroundMountAtMinLevel = 20;
    uint32 useFastGroundMountAtMinLevel = 40;
    uint32 useFlyMountAtMinLevel = 60;
    uint32 useFastFlyMountAtMinLevel = 70;
} sPlayerbotAIConfig;

struct PlayerDouble
{
    uint8 Class = 13;
    uint8 Level = 13;
    uint16 Riding = 300;
    std::set<uint32> Spells{33388, 33391, 34090, 34091, 54197, 91737, 801670};
    std::vector<uint32> Learned;
    unsigned Mutations = 0;

    uint8 getClass() const { return Class; }
    uint8 GetLevel() const { return Level; }
    bool HasSpell(uint32 spell) const { return Spells.count(spell) != 0; }
    void UpdateSkillsForLevel() { ++Mutations; }
    void SetCanDualWield(bool) { ++Mutations; }
    void SetSkill(uint16 id, uint16, uint16 value, uint16)
    {
        ++Mutations;
        if (id != SKILL_RIDING)
            return;
        Riding = value;
        if (!value)
            // Native Player::SetSkill removes skill-line-associated spells.
            for (uint32 spell : {33388, 33391, 34090, 34091, 54197})
                Spells.erase(spell);
    }
    void learnSpell(uint32 spell)
    {
        ++Mutations;
        Spells.insert(spell);
        Learned.push_back(spell);
        if (spell == 33388)
            Riding = 75;
        else if (spell == 33391)
            Riding = 150;
        else if (spell == 34090)
            Riding = 225;
        else if (spell == 34091)
            Riding = 300;
    }
};

struct PlayerbotFactory
{
    PlayerDouble* bot;
    unsigned RandomSkillCalls = 0;
    unsigned TradeSkillCalls = 0;
    unsigned InventorySkillCalls = 0;
    void SetRandomSkill(uint16) { ++RandomSkillCalls; }
    void InitTradeSkills() { ++TradeSkillCalls; }
    void InitInventorySkill() { ++InventorySkillCalls; }
    void InitSkills();
};

#include "CoaRidingProduction.h"

int main()
{
    // All 21 COA classes retain exact native skill/spell state, including Cold
    // Weather Flying, across repeated refresh/level-up/trainer entry calls.
    for (uint8 classId = 12; classId <= 32; ++classId)
    {
        for (uint8 level : {1, 13, 20, 40, 60, 80})
        {
            for (uint16 riding : {0, 75, 150, 225, 300})
            {
                PlayerDouble bot;
                bot.Class = classId;
                bot.Level = level;
                bot.Riding = riding;
                auto const spells = bot.Spells;
                PlayerbotFactory factory{&bot};
                for (unsigned repeat = 0; repeat < 3; ++repeat)
                    factory.InitSkills();
                assert(bot.Mutations == 0 && bot.Learned.empty() && bot.Riding == riding);
                assert(bot.Spells == spells);
                assert(factory.RandomSkillCalls == 0 && factory.TradeSkillCalls == 0 &&
                    factory.InventorySkillCalls == 0);
            }
        }
    }

    // The guard does not grant missing training or alter the configuration's
    // owner: a never-trained COA bot remains unchanged until native login setup.
    PlayerDouble untrained;
    untrained.Riding = 0;
    untrained.Spells.clear();
    PlayerbotFactory untrainedFactory{&untrained};
    untrainedFactory.InitSkills();
    assert(untrained.Riding == 0 && untrained.Spells.empty() && untrained.Mutations == 0);

    // Every stock class still executes the original skill, proficiency and
    // profession initialization, with riding governed by its existing settings.
    for (uint8 classId : {1, 2, 3, 4, 5, 6, 7, 8, 9, 11})
    {
        for (uint8 level : {1, 19, 20, 39, 40, 59, 60, 69, 70, 80})
        {
            PlayerDouble bot;
            bot.Class = classId;
            bot.Level = level;
            PlayerbotFactory factory{&bot};
            factory.InitSkills();
            uint16 const expected = level >= 70 ? 300 : level >= 60 ? 225 :
                level >= 40 ? 150 : level >= 20 ? 75 : 0;
            assert(bot.Riding == expected && bot.Mutations > 0 && factory.RandomSkillCalls >= 2);
            assert(factory.TradeSkillCalls == 1 && factory.InventorySkillCalls == 1);
            assert(bot.Spells.count(91737) && bot.Spells.count(801670));
            assert(!bot.HasSpell(54197)); // Stock policy still removes the riding skill line.
        }
    }

    // With the requested level-1 thresholds, stock classes receive all four
    // riding ranks even at level 1; no hard-coded stock level gate is added.
    sPlayerbotAIConfig = {1, 1, 1, 1};
    for (uint8 classId : {1, 2, 3, 4, 5, 6, 7, 8, 9, 11})
    {
        for (uint8 level : {1, 13, 20, 80})
        {
            PlayerDouble classic;
            classic.Class = classId;
            classic.Level = level;
            PlayerbotFactory classicFactory{&classic};
            classicFactory.InitSkills();
            assert(classic.Riding == 300 && classic.HasSpell(54197));
            assert((classic.Learned == std::vector<uint32>{33388, 33391, 34090, 34091}));

            // Repair missing training, including Cold Weather Flying, through
            // ordinary native learning; a second pass preserves it unchanged.
            classic.Riding = 0;
            classic.Spells.clear();
            classic.Learned.clear();
            classicFactory.InitSkills();
            assert(classic.Riding == 300 && classic.HasSpell(54197));
            assert((classic.Learned == std::vector<uint32>{33388, 33391, 34090, 34091, 54197}));
            classic.Learned.clear();
            classicFactory.InitSkills();
            assert(classic.Riding == 300 && classic.HasSpell(54197));
            assert((classic.Learned == std::vector<uint32>{33388, 33391, 34090, 34091}));
        }
    }

    // A partially lowered policy is not treated as an all-riding override.
    for (unsigned different = 0; different < 4; ++different)
    {
        sPlayerbotAIConfig = {1, 1, 1, 1};
        uint32* thresholds[] = {&sPlayerbotAIConfig.useGroundMountAtMinLevel,
            &sPlayerbotAIConfig.useFastGroundMountAtMinLevel, &sPlayerbotAIConfig.useFlyMountAtMinLevel,
            &sPlayerbotAIConfig.useFastFlyMountAtMinLevel};
        *thresholds[different] = 20;
        PlayerDouble classic;
        classic.Class = CLASS_WARRIOR;
        classic.Level = 1;
        PlayerbotFactory factory{&classic};
        factory.InitSkills();
        assert(!classic.HasSpell(54197));
    }

    // The guard ends at the last supported COA class rather than all future IDs.
    PlayerDouble unsupported;
    unsupported.Class = 33;
    PlayerbotFactory unsupportedFactory{&unsupported};
    unsupportedFactory.InitSkills();
    assert(unsupported.Mutations > 0);

    std::cout << "COA skill preservation and classic riding-threshold tests passed.\n";
}
