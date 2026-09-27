#include <cassert>
#include <cstdint>
#include <initializer_list>
#include <set>
#include <string>
#include <type_traits>
#include <vector>

using uint32 = std::uint32_t;

#include "CoaTravelConstants.h"

enum BotState
{
    BOT_STATE_NON_COMBAT,
    BOT_STATE_COMBAT
};

enum ShapeshiftForm
{
    FORM_NONE,
    FORM_TRAVEL,
    FORM_FLIGHT,
    FORM_FLIGHT_EPIC
};
constexpr uint32 UNIT_STATE_IN_FLIGHT = 1;
constexpr uint32 SPELL_AURA_TRANSFORM = 2;
constexpr uint32 SKILL_RIDING = 762;
constexpr uint32 BG_WS_SPELL_WARSONG_FLAG = 23333;
constexpr uint32 BG_WS_SPELL_SILVERWING_FLAG = 23335;
constexpr uint32 BG_EY_NETHERSTORM_FLAG_SPELL = 34976;
constexpr int STATUS_WAIT_JOIN = 1;
constexpr int BG_START_DELAY_30S = 30000;

struct Group
{
};

struct Battleground
{
    int Status = 0;
    int Delay = 0;
    int GetStatus() { return Status; }
    int GetStartDelayTime() { return Delay; }
};

struct PlayerbotAI;

struct Player
{
    std::uint8_t Class = 13;
    std::uint8_t Level = 10;
    std::uint16_t Riding = 75;
    bool Human = false;
    bool Dead = false;
    bool Taxi = false;
    bool Outdoors = true;
    bool Arena = false;
    bool Combat = false;
    bool Mounted = false;
    bool WaterWalk = false;
    bool Transformed = false;
    bool DisallowedForm = false;
    bool InBg = false;
    float Z = 0.0f;
    float Ground = 0.0f;
    ShapeshiftForm Form = FORM_NONE;
    Group* Party = nullptr;
    PlayerbotAI* Ai = nullptr;
    Battleground Bg;
    std::set<uint32> Auras;

    bool isDead() { return Dead; }
    bool HasUnitState(uint32) { return Taxi; }
    bool IsOutdoors() { return Outdoors; }
    bool InArena() { return Arena; }
    bool IsInCombat() { return Combat; }
    bool IsMounted() { return Mounted; }
    bool HasWaterWalkAura() { return WaterWalk; }
    bool HasAuraType(uint32) { return Transformed; }
    bool IsInDisallowedMountForm() { return DisallowedForm; }
    bool InBattleground() { return InBg; }
    bool HasAura(uint32 aura) { return Auras.count(aura) != 0; }
    std::uint8_t getClass() { return Class; }
    std::uint8_t GetLevel() { return Level; }
    std::uint16_t GetPureSkillValue(uint32) { return Riding; }
    Group* GetGroup() { return Party; }
    Battleground* GetBattleground() { return &Bg; }
    ShapeshiftForm GetShapeshiftForm() { return Form; }
    float GetPositionX() { return 0.0f; }
    float GetPositionY() { return 0.0f; }
    float GetPositionZ() { return Z; }
    float GetMapWaterOrGroundLevel(float, float, float) { return Ground; }
};

struct PlayerbotAI
{
    Player* Bot;
    Player* Master;
    bool Vehicle = false;
    bool MountStrategy = true;
    BotState State = BOT_STATE_NON_COMBAT;

    bool IsInVehicle() { return Vehicle; }
    bool HasGameClientMaster() { return Master && Master != Bot && Master->Human; }
    bool HasStrategy(char const*, BotState) { return MountStrategy; }
    BotState GetState() { return State; }
};

#define GET_PLAYERBOT_AI(player) ((player)->Ai)

struct
{
    int useGroundMountAtMinLevel = 20;
} sPlayerbotAIConfig;

struct NextAction
{
    std::string Name;
    float Priority;
    NextAction(char const* name, float priority) : Name(name), Priority(priority) {}
};

struct TriggerNode
{
    std::string Name;
    std::vector<NextAction> Actions;
    TriggerNode(char const* name, std::initializer_list<NextAction> actions) : Name(name), Actions(actions) {}
};

class Strategy
{
public:
    explicit Strategy(PlayerbotAI*) {}
    virtual ~Strategy() = default;
    virtual void InitTriggers(std::vector<TriggerNode*>&) {}
    virtual std::vector<NextAction> getDefaultActions() { return {}; }
    virtual std::string const getName() = 0;
    virtual uint32 GetType() const { return STRATEGY_TYPE_GENERIC; }
};

class CheckMountStateAction
{
public:
    explicit CheckMountStateAction(PlayerbotAI* ai) : botAI(ai), bot(ai->Bot) {}
    bool isUseful();
    bool ShouldFollowMasterMountState(Player* master, bool noAttackers, bool shouldMount) const;
    bool ShouldDismountForMaster(Player* master) const;

private:
    Player* GetMaster() { return botAI->Master; }
    PlayerbotAI* botAI;
    Player* bot;
    Player* master = nullptr;
    ShapeshiftForm masterInShapeshiftForm = FORM_NONE;
    ShapeshiftForm botInShapeshiftForm = FORM_NONE;
};

// Verbatim declarations and bodies extracted from the patched production files.
#include "CoaTravelProduction.h"

static_assert(std::is_base_of<CombatStrategy, CoaCombatStrategy>::value,
    "Generic COA offense must inherit shared combat cleanup");
static_assert(std::is_base_of<CombatStrategy, CoaBrewingStrategy>::value,
    "Brewing must inherit shared combat cleanup");

float Priority(std::vector<NextAction> const& actions, std::string const& name)
{
    for (auto const& action : actions)
        if (action.Name == name)
            return action.Priority;

    return -1.0f;
}

void CheckCombatTriggers(Strategy& strategy)
{
    std::vector<TriggerNode*> triggers;
    strategy.InitTriggers(triggers);
    bool cleanup = false;
    bool mounted = false;
    for (TriggerNode* trigger : triggers)
    {
        if (trigger->Name == "invalid target")
        {
            float const priority = Priority(trigger->Actions, "drop target");
            assert(priority == 99.0f && priority > ACTION_HIGH);
            cleanup = true;
        }
        if (trigger->Name == "mounted")
        {
            assert(Priority(trigger->Actions, "check mount state") > ACTION_HIGH);
            mounted = true;
        }
        delete trigger;
    }
    assert(cleanup && mounted);
}

struct Fixture
{
    Group Party;
    Group OtherParty;
    Player Leader;
    Player Bot;
    PlayerbotAI Ai{&Bot, &Leader};
    CheckMountStateAction Action{&Ai};

    Fixture()
    {
        Leader.Human = true;
        Leader.Mounted = true;
        Leader.Party = &Party;
        Bot.Party = &Party;
        Bot.Ai = &Ai;
    }
};

int main()
{
    Fixture fixture;
    CoaCombatStrategy offense(&fixture.Ai);
    CoaBrewingStrategy brewing(&fixture.Ai);
    CheckCombatTriggers(offense);
    CheckCombatTriggers(brewing);
    auto defaults = brewing.getDefaultActions();
    assert(Priority(defaults, "coa brewing heal") == ACTION_HIGH);
    assert(Priority(defaults, "coa brewing heal") > Priority(defaults, "coa attack"));
    assert(Priority(defaults, "coa attack") > Priority(defaults, "melee"));
    assert((brewing.GetType() & (STRATEGY_TYPE_HEAL | STRATEGY_TYPE_RANGED)) ==
        (STRATEGY_TYPE_HEAL | STRATEGY_TYPE_RANGED));

    // Low-level exception requires a trained, grouped COA follower of a human.
    assert(fixture.Action.isUseful());
    fixture.Bot.Riding = 74;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Riding = 75;
    fixture.Bot.Class = 11;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Class = 33;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Class = 32;
    assert(fixture.Action.isUseful());
    fixture.Bot.Class = 12;
    assert(fixture.Action.isUseful());
    fixture.Ai.Master = nullptr;
    assert(!fixture.Action.isUseful());
    fixture.Ai.Master = &fixture.Bot;
    assert(!fixture.Action.isUseful());
    fixture.Ai.Master = &fixture.Leader;
    fixture.Leader.Human = false;
    assert(!fixture.Action.isUseful());
    fixture.Leader.Human = true;
    fixture.Bot.Party = nullptr;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Party = &fixture.OtherParty;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Party = &fixture.Party;
    fixture.Leader.Party = nullptr;
    assert(!fixture.Action.isUseful());
    fixture.Leader.Party = &fixture.Party;

    // Native environmental, combat and strategy gates remain in force.
    fixture.Bot.InBg = true;
    assert(!fixture.Action.isUseful());
    fixture.Bot.InBg = false;
    fixture.Bot.Arena = true;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Arena = false;
    fixture.Bot.Combat = true;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Combat = false;
    fixture.Ai.State = BOT_STATE_COMBAT;
    assert(!fixture.Action.isUseful());
    fixture.Ai.State = BOT_STATE_NON_COMBAT;
    fixture.Bot.Outdoors = false;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Outdoors = true;
    fixture.Bot.Transformed = true;
    fixture.Bot.DisallowedForm = true;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Transformed = false;
    fixture.Bot.DisallowedForm = false;
    fixture.Ai.MountStrategy = false;
    assert(!fixture.Action.isUseful());
    fixture.Ai.MountStrategy = true;
    fixture.Bot.Dead = true;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Dead = false;
    fixture.Ai.Vehicle = true;
    assert(!fixture.Action.isUseful());
    fixture.Ai.Vehicle = false;
    fixture.Bot.Taxi = true;
    assert(!fixture.Action.isUseful());
    fixture.Bot.Taxi = false;

    // Normal-level classic/unowned bots retain the existing usefulness policy.
    Fixture classic;
    classic.Bot.Class = 1;
    classic.Bot.Level = 20;
    classic.Bot.Riding = 0;
    classic.Ai.Master = nullptr;
    assert(classic.Action.isUseful());
    classic.Bot.InBg = true;
    classic.Bot.Auras.insert(BG_WS_SPELL_WARSONG_FLAG);
    assert(!classic.Action.isUseful());
    classic.Bot.Auras.clear();
    classic.Bot.Bg.Status = STATUS_WAIT_JOIN;
    classic.Bot.Bg.Delay = BG_START_DELAY_30S + 1;
    assert(!classic.Action.isUseful());

    // Test the real follow/dismount predicates, not simulated movement packets.
    assert(fixture.Action.isUseful());
    assert(fixture.Action.ShouldFollowMasterMountState(&fixture.Leader, true, true));
    assert(!fixture.Action.ShouldFollowMasterMountState(&fixture.Leader, false, true));
    fixture.Ai.State = BOT_STATE_COMBAT;
    assert(!fixture.Action.ShouldFollowMasterMountState(&fixture.Leader, true, true));
    fixture.Ai.State = BOT_STATE_NON_COMBAT;
    fixture.Bot.Mounted = true;
    fixture.Leader.Mounted = false;
    assert(fixture.Action.isUseful());
    assert(fixture.Action.ShouldDismountForMaster(&fixture.Leader));
    fixture.Leader.Form = FORM_TRAVEL;
    assert(fixture.Action.isUseful());
    assert(!fixture.Action.ShouldDismountForMaster(&fixture.Leader));
}
