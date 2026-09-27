#include <algorithm>
#include <cassert>
#include <cstdint>
#include <functional>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
constexpr uint8 CLASS_WITCH_DOCTOR = 13;
constexpr uint8 DEFAULT_MAX_LEVEL = 80;
constexpr uint32 PLAYER_XP = 0;
std::vector<std::string> Calls;
#define LOG_INFO(...) do {} while (false)

struct WorldSession
{
    bool Bot = false;
    bool IsBot() const { return Bot; }
};

struct Group
{
    uint32 Leader = 1;
    bool IsLeader(uint32 guid) const { return guid == Leader; }
};

struct Player
{
    WorldSession* Session = nullptr;
    Group* Party = nullptr;
    uint32 Guid = 0;
    uint8 Class = CLASS_WITCH_DOCTOR;
    uint8 Level = 1;
    uint32 Experience = 42;
    uint32 Specialization = 0;
    bool InWorld = true;
    bool Alive = true;
    bool Combat = false;
    bool Teleporting = false;
    bool SameMap = true;
    bool AcceptLevel = true;
    float Distance = 0;
    std::vector<uint32> Inventory{17, 18};
    std::vector<uint32> Talents{19, 20};

    WorldSession* GetSession() const { return Session; }
    uint8 getClass() const { return Class; }
    Group* GetGroup() const { return Party; }
    uint32 GetGUID() const { return Guid; }
    bool IsInWorld() const { return InWorld; }
    bool IsAlive() const { return Alive; }
    bool IsInCombat() const { return Combat; }
    bool IsBeingTeleported() const { return Teleporting; }
    bool IsWithinDistInMap(Player const*, float maximum) const { return SameMap && Distance <= maximum; }
    uint8 GetLevel() const { return Level; }
    void GiveLevel(uint8 level)
    {
        Calls.push_back("level");
        if (AcceptLevel)
            Level = level;
    }
    void SetUInt32Value(uint32 field, uint32 value)
    {
        assert(field == PLAYER_XP);
        Calls.push_back("xp");
        Experience = value;
    }
    void SaveToDB(bool create, bool logout)
    {
        assert(!create && !logout);
        Calls.push_back("save");
    }
    std::string GetName() const { return "Pilot"; }
};

struct PlayerbotAI
{
    Player* Master = nullptr;
    Player* GetMaster() { return Master; }
    void ResetStrategies(bool load = false)
    {
        assert(!load);
        Calls.push_back("reset strategies");
    }
};

struct PlayerbotsMgr
{
    Player* Expected = nullptr;
    PlayerbotAI* AI = nullptr;
    PlayerbotAI* GetPlayerbotAI(Player* player) { return player == Expected ? AI : nullptr; }
} sPlayerbotsMgr;

namespace AscensionCompatData
{
struct CoATalentEntry
{
    uint8 ClassId;
    uint32 SpecId;
};
std::vector<CoATalentEntry> CoATalentEntries;
}

struct AscensionClassService
{
    bool AcceptSpec = true;
    static AscensionClassService& Instance()
    {
        static AscensionClassService service;
        return service;
    }
    uint32 GetActiveSpecialization(Player const* player) const { return player->Specialization; }
    bool SwitchSpecialization(Player* player, uint32 spec)
    {
        Calls.push_back("specialization");
        if (!AcceptSpec)
            return false;
        player->Specialization = spec;
        return true;
    }
    uint32 SynchronizeProgression(Player*) { Calls.push_back("progression"); return 0; }
    void SynchronizeProficiencies(Player*) { Calls.push_back("proficiencies"); }
    bool RepairStarterKit(Player*, bool force)
    {
        assert(!force);
        Calls.push_back("starter kit");
        return true;
    }
};

struct ChatHandler
{
    Player* Leader = nullptr;
    Player* Selected = nullptr;
    std::vector<std::string> Messages;
    Player* GetPlayer() { return Leader; }
    Player* getSelectedPlayer() { return Selected; }
    void SendSysMessage(char const* message) { Messages.emplace_back(message); }
    template <typename... Args>
    void PSendSysMessage(char const* message, Args&&...) { Messages.emplace_back(message); }
};

// Extracted verbatim from the release patch or the patched production source.
#include "CoaPilotPrepareProduction.h"

struct Fixture
{
    WorldSession HumanSession;
    WorldSession BotSession{true};
    Group Party;
    Group OtherParty;
    Player Leader;
    Player Bot;
    PlayerbotAI AI;
    ChatHandler Handler;

    Fixture()
    {
        Leader.Session = &HumanSession;
        Leader.Party = &Party;
        Leader.Guid = 1;
        Leader.Level = 13;
        Bot.Session = &BotSession;
        Bot.Party = &Party;
        Bot.Guid = 2;
        AI.Master = &Leader;
        Handler.Leader = &Leader;
        Handler.Selected = &Bot;
        sPlayerbotsMgr.Expected = &Bot;
        sPlayerbotsMgr.AI = &AI;
        AscensionClassService::Instance().AcceptSpec = true;
        AscensionCompatData::CoATalentEntries = {{CLASS_WITCH_DOCTOR, 6}};
        Calls.clear();
    }
};

void CheckPreserved(Player const& player)
{
    assert((player.Inventory == std::vector<uint32>{17, 18}));
    assert((player.Talents == std::vector<uint32>{19, 20}));
}

int main()
{
    using Mutation = std::pair<char const*, std::function<void(Fixture&)>>;
    std::vector<Mutation> rejected = {
        {"missing leader", [](Fixture& f) { f.Handler.Leader = nullptr; }},
        {"missing leader session", [](Fixture& f) { f.Leader.Session = nullptr; }},
        {"bot leader", [](Fixture& f) { f.Leader.Session = &f.BotSession; }},
        {"missing target", [](Fixture& f) { f.Handler.Selected = nullptr; }},
        {"missing bot session", [](Fixture& f) { f.Bot.Session = nullptr; }},
        {"human target", [](Fixture& f) { f.Bot.Session = &f.HumanSession; }},
        {"wrong class", [](Fixture& f) { f.Bot.Class = 31; }},
        {"missing AI", [](Fixture&) { sPlayerbotsMgr.AI = nullptr; }},
        {"wrong master", [](Fixture& f) { f.AI.Master = &f.Bot; }},
        {"ungrouped leader", [](Fixture& f) { f.Leader.Party = nullptr; }},
        {"ungrouped bot", [](Fixture& f) { f.Bot.Party = nullptr; }},
        {"different group", [](Fixture& f) { f.Bot.Party = &f.OtherParty; }},
        {"not group leader", [](Fixture& f) { f.Party.Leader = 2; }},
        {"leader not in world", [](Fixture& f) { f.Leader.InWorld = false; }},
        {"bot not in world", [](Fixture& f) { f.Bot.InWorld = false; }},
        {"leader dead", [](Fixture& f) { f.Leader.Alive = false; }},
        {"bot dead", [](Fixture& f) { f.Bot.Alive = false; }},
        {"leader in combat", [](Fixture& f) { f.Leader.Combat = true; }},
        {"bot in combat", [](Fixture& f) { f.Bot.Combat = true; }},
        {"leader teleporting", [](Fixture& f) { f.Leader.Teleporting = true; }},
        {"bot teleporting", [](Fixture& f) { f.Bot.Teleporting = true; }},
        {"different map", [](Fixture& f) { f.Bot.SameMap = false; }},
        {"too far", [](Fixture& f) { f.Bot.Distance = 30.01f; }},
        {"leader below ten", [](Fixture& f) { f.Leader.Level = 9; }},
        {"leader above eighty", [](Fixture& f) { f.Leader.Level = 81; }},
        {"downlevel forbidden", [](Fixture& f) { f.Bot.Level = 79; }},
        {"other specialization", [](Fixture& f) { f.Bot.Specialization = 7; }},
        {"missing catalog", [](Fixture&) { AscensionCompatData::CoATalentEntries.clear(); }},
        {"catalog wrong class", [](Fixture&) { AscensionCompatData::CoATalentEntries = {{31, 6}}; }},
        {"catalog wrong spec", [](Fixture&) { AscensionCompatData::CoATalentEntries = {{13, 7}}; }},
    };
    for (auto const& test : rejected)
    {
        Fixture f;
        test.second(f);
        uint8 const level = f.Bot.Level;
        uint32 const xp = f.Bot.Experience;
        uint32 const spec = f.Bot.Specialization;
        assert(HandleLocalBotPrepareCommand(&f.Handler, "brewing"));
        if (!Calls.empty())
            std::cerr << "Unexpected mutation in rejected case: " << test.first << '\n';
        assert(Calls.empty());
        assert(f.Bot.Level == level && f.Bot.Experience == xp && f.Bot.Specialization == spec);
        assert(f.Handler.Messages.size() == 1);
        CheckPreserved(f.Bot);
        CheckPreserved(f.Leader);
    }

    for (std::string const profile : {"", "tank", "Brewing"})
    {
        Fixture f;
        assert(HandleLocalBotPrepareCommand(&f.Handler, profile));
        assert(Calls.empty());
        assert(f.Handler.Messages.front().find("Usage:") == 0);
    }

    // New level-matched pilot: preserve inventory/talents, clear only promoted
    // bot XP, synchronize native progression, refresh AI, then persist.
    {
        Fixture f;
        f.Bot.Distance = 30.0f;
        assert(HandleLocalBotPrepareCommand(&f.Handler, "brewing"));
        assert(f.Bot.Level == 13 && f.Bot.Experience == 0 && f.Bot.Specialization == 6);
        assert((Calls == std::vector<std::string>{"level", "xp", "specialization", "progression",
            "proficiencies", "starter kit", "reset strategies", "save"}));
        assert(f.Leader.Level == 13 && f.Leader.Experience == 42 && f.Leader.Specialization == 0);
        CheckPreserved(f.Bot);
        CheckPreserved(f.Leader);

        // Same-level retry preserves earned XP and does not repeat GiveLevel.
        Calls.clear();
        f.Bot.Experience = 123;
        assert(HandleLocalBotPrepareCommand(&f.Handler, "brewing"));
        assert(f.Bot.Level == 13 && f.Bot.Experience == 123 && f.Bot.Specialization == 6);
        assert((Calls == std::vector<std::string>{"specialization", "progression", "proficiencies",
            "starter kit", "reset strategies", "save"}));
        CheckPreserved(f.Bot);
    }

    for (uint8 level : {10, 80})
    {
        Fixture f;
        f.Leader.Level = level;
        f.Bot.Level = level;
        assert(HandleLocalBotPrepareCommand(&f.Handler, "brewing"));
        assert(f.Bot.Experience == 42 && f.Bot.Specialization == 6);
        assert(Calls.front() == "specialization" && Calls.back() == "save");
    }

    // GiveLevel is void and can be vetoed: verify no spec/XP/save follows.
    {
        Fixture f;
        f.Bot.AcceptLevel = false;
        assert(HandleLocalBotPrepareCommand(&f.Handler, "brewing"));
        assert((Calls == std::vector<std::string>{"level"}));
        assert(f.Bot.Level == 1 && f.Bot.Experience == 42 && f.Bot.Specialization == 0);
        assert(f.Handler.Messages.front().find("server rejected") != std::string::npos);
    }

    // Fail closed if the service ever rejects the prevalidated specialization.
    // This is not transactional: the already accepted level-up remains.
    {
        Fixture f;
        AscensionClassService::Instance().AcceptSpec = false;
        assert(HandleLocalBotPrepareCommand(&f.Handler, "brewing"));
        assert((Calls == std::vector<std::string>{"level", "xp", "specialization"}));
        assert(f.Bot.Level == 13 && f.Bot.Experience == 0 && f.Bot.Specialization == 0);
        assert(f.Handler.Messages.front().find("Could not activate Brewing") == 0);
    }
    std::cout << "30 precondition rejection cases and successful/retry/failure-path checks passed.\n";
}
