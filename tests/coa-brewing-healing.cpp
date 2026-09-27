#include <array>
#include <cassert>
#include <cstdint>
#include <initializer_list>
#include <set>
#include <vector>

using uint32 = std::uint32_t;

struct Player;

struct GroupReference
{
    Player* Member = nullptr;
    GroupReference* Following = nullptr;
    Player* GetSource() { return Member; }
    GroupReference* next() { return Following; }
};

struct Group
{
    GroupReference* First = nullptr;
    GroupReference* GetFirstMember() { return First; }
};

struct Player
{
    float Health = 100.0f;
    float Distance = 0.0f;
    bool InWorld = true;
    bool Alive = true;
    bool LineOfSight = true;
    int Map = 1;
    Group* Party = nullptr;
    std::set<uint32> Learned;

    float GetHealthPct() { return Health; }
    Group* GetGroup() { return Party; }
    bool IsInWorld() { return InWorld; }
    bool IsAlive() { return Alive; }
    int GetMap() { return Map; }
    float GetDistance2d(Player* other) { return other->Distance; }
    bool IsWithinLOSInMap(Player* other) { return other->LineOfSight; }
    bool HasSpell(uint32 spell) { return Learned.count(spell) != 0; }
};

using Unit = Player;

struct PlayerbotAI
{
    Player* Bot;
    std::set<uint32> Blocked;
    std::set<uint32> Failed;
    std::vector<uint32> Attempts;
    uint32 Cast = 0;
    Player* Recipient = nullptr;

    Player* GetBot() { return Bot; }
    bool CanCastSpell(uint32 spell, Unit*) { return Blocked.count(spell) == 0; }
    bool CastSpell(uint32 spell, Unit* target)
    {
        Attempts.push_back(spell);
        if (Failed.count(spell))
            return false;

        Cast = spell;
        Recipient = target;
        return true;
    }
};

struct Event
{
};

enum class ActionThreatType
{
    Aoe
};

class Action
{
public:
    Action(PlayerbotAI* ai, char const*) : botAI(ai) {}
    virtual ~Action() = default;
    virtual bool Execute(Event) = 0;
    virtual bool isUseful() = 0;
    virtual ActionThreatType getThreatType() = 0;

protected:
    PlayerbotAI* botAI;
};

// Generated verbatim from the patched module, not a reimplementation of its AI.
#include "CoaBrewingProduction.h"

void ExpectSpell(float health, std::initializer_list<uint32> learned, uint32 expected,
    std::initializer_list<uint32> blocked = {}, std::initializer_list<uint32> failed = {})
{
    Player bot;
    bot.Health = health;
    bot.Learned = learned;
    PlayerbotAI ai{&bot, blocked, failed, {}, 0, nullptr};
    CoaBrewingHealAction action(&ai);
    assert(action.isUseful() == (health < 80.0f));
    assert(action.Execute({}) == (expected != 0));
    assert(ai.Cast == expected);
    if (expected)
        assert(ai.Recipient == &bot);
}

int main()
{
    // Unknown or unlearned spells cannot be cast, including an empty spellbook.
    ExpectSpell(20.0f, {}, 0);
    ExpectSpell(20.0f, {123456}, 0);

    // Base healing works before the first ranked upgrade has been learned.
    ExpectSpell(79.0f, {801670}, 801670);
    ExpectSpell(39.0f, {801696}, 801696);
    ExpectSpell(64.0f, {801661}, 801661);

    // Highest learned and castable rank wins, not the numerically highest ID.
    ExpectSpell(79.0f, {801670, 501198, 501206}, 501206);
    ExpectSpell(79.0f, {801670, 501198, 501206}, 501198, {501206});
    ExpectSpell(79.0f, {801670, 501198}, 801670, {501198});
    ExpectSpell(79.0f, {801670, 501198}, 801670, {}, {501198});
    ExpectSpell(39.0f, {801696, 501207, 501213}, 501213);
    ExpectSpell(64.0f, {801661, 573430, 573435}, 573435);

    // Exact boundaries are strict; cooldown/failure falls through safely.
    ExpectSpell(39.99f, {801670, 801696, 801661}, 801696);
    ExpectSpell(40.0f, {801670, 801696, 801661}, 801661);
    ExpectSpell(64.99f, {801670, 801696, 801661}, 801661);
    ExpectSpell(65.0f, {801670, 801696, 801661}, 801670);
    ExpectSpell(79.99f, {801670, 801696, 801661}, 801670);
    ExpectSpell(80.0f, {801670, 801696, 801661}, 0);
    ExpectSpell(100.0f, {801670, 801696, 801661}, 0);
    ExpectSpell(20.0f, {801670, 801696, 801661}, 801661, {801696});
    ExpectSpell(20.0f, {801670, 801696, 801661}, 801670, {801696, 801661});
    ExpectSpell(20.0f, {801670, 801696, 801661}, 0, {801670, 801696, 801661});

    // Targeting uses real production selection: lowest-health eligible member,
    // same map, alive, within 35 yards, and in line of sight.
    Player bot;
    bot.Health = 70.0f;
    bot.Learned = {801670};
    Player injured;
    injured.Health = 20.0f;
    GroupReference reference{&injured, nullptr};
    Group party{&reference};
    bot.Party = &party;
    assert(FindBrewingHealTarget(&bot) == &injured);
    PlayerbotAI ai{&bot, {}, {}, {}, 0, nullptr};
    CoaBrewingHealAction action(&ai);
    assert(action.Execute({}));
    assert(ai.Recipient == &injured);
    injured.Distance = 36.0f;
    assert(FindBrewingHealTarget(&bot) == &bot);
    injured.Distance = 35.0f;
    assert(FindBrewingHealTarget(&bot) == &injured);
    injured.LineOfSight = false;
    assert(FindBrewingHealTarget(&bot) == &bot);
    injured.LineOfSight = true;
    injured.Alive = false;
    assert(FindBrewingHealTarget(&bot) == &bot);
    injured.Alive = true;
    injured.Map = 2;
    assert(FindBrewingHealTarget(&bot) == &bot);
    injured.Map = 1;
    injured.InWorld = false;
    assert(FindBrewingHealTarget(&bot) == &bot);
}
