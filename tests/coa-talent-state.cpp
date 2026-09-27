#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

using uint8 = std::uint8_t;
using uint16 = std::uint16_t;
using uint32 = std::uint32_t;
constexpr uint32 SPEC_MASK_ALL = 3;
constexpr uint32 CHAT_MSG_WHISPER = 7;
constexpr uint32 LANG_ADDON = 0xFFFFFFFF;
constexpr uint32 SPELL_EFFECT_LEARN_SPELL = 36;
#define MOD_PLAYERBOTS
template <typename... Args> void MockLog(Args&&...) {}
#define LOG_INFO(...) MockLog(__VA_ARGS__)

#include "CoaTalentStateConstants.h"

struct ObjectGuid
{
    uint32 Value = 1;
    uint32 GetCounter() const { return Value; }
};

struct PlayerSetting
{
    uint32 value = 0;
    bool operator==(PlayerSetting const& other) const { return value == other.value; }
};
using PlayerSettingVector = std::vector<PlayerSetting>;
using PlayerSettingMap = std::map<std::string, PlayerSettingVector>;

struct WorldPacket
{
    std::string Message;
};

struct WorldSession
{
    bool Bot = false;
    std::vector<std::string> Packets;
    bool IsBot() const { return Bot; }
    void SendPacket(WorldPacket const* packet) { Packets.push_back(packet->Message); }
};

struct Player
{
    WorldSession* Session = nullptr;
    uint8 Class = 31;
    uint8 Level = 13;
    PlayerSettingMap Settings;
    std::set<uint32> Spells;
    std::set<uint32> InactiveSpells;
    std::map<uint32, std::set<uint32>> RemoveDependents;
    std::set<uint32> InactiveOnFirstLearn;
    bool LearnAllowed = true;
    std::map<uint32, uint32> LearnAttempts;
    std::map<uint32, std::set<uint32>> FailedLearnAttempts;
    uint32 Learned = 0;
    uint32 Removed = 0;
    uint32 Writes = 0;

    uint8 getClass() const { return Class; }
    uint8 GetLevel() const { return Level; }
    ObjectGuid GetGUID() const { return {}; }
    WorldSession* GetSession() const { return Session; }
    std::string GetName() const { return "Beruwa"; }
    bool HasSpell(uint32 spell) const { return Spells.count(spell) != 0; }
    bool HasActiveSpell(uint32 spell) const { return HasSpell(spell) && !InactiveSpells.count(spell); }
    void learnSpell(uint32 spell, bool)
    {
        ++Learned;
        uint32 const attempt = ++LearnAttempts[spell];
        if (LearnAllowed && !FailedLearnAttempts[spell].count(attempt))
        {
            Spells.insert(spell);
            if (attempt == 1 && InactiveOnFirstLearn.count(spell))
                InactiveSpells.insert(spell);
            else
                InactiveSpells.erase(spell);
        }
    }
    void removeSpell(uint32 spell, uint32 mask, bool)
    {
        assert(mask == SPEC_MASK_ALL);
        ++Removed;
        Spells.erase(spell);
        InactiveSpells.erase(spell);
        for (uint32 dependent : RemoveDependents[spell])
            Spells.erase(dependent);
    }
    PlayerSettingVector const* FindPlayerSettings(std::string const& source) const
    {
        auto const found = Settings.find(source);
        return found == Settings.end() ? nullptr : &found->second;
    }
    void UpdatePlayerSetting(std::string const& source, uint32 index, uint32 value)
    {
        auto& values = Settings[source];
        if (values.size() <= index)
            values.resize(index + 1);
        values[index].value = value;
        ++Writes;
    }
};

bool IsAscensionCustomClass(Player const* player)
{
    return player && player->getClass() >= 12 && player->getClass() <= 32;
}

namespace AscensionCompatData
{
struct CoATalentEntry
{
    uint32 EntryId;
    uint8 ClassId;
    uint16 SpecId;
    uint8 SpellCount;
    uint8 AECost;
    uint8 TECost;
    uint8 RequiredLevel;
    std::array<uint32, 3> SpellIds;
};
std::array<CoATalentEntry, 80> CoATalentEntries;
}

struct SpellInfo
{
    bool IsDeprecatedForPlayers = false;
    bool Valid = true;
    bool LearnEffect = false;
    bool HasEffect(uint32 effect) const { return effect == SPELL_EFFECT_LEARN_SPELL && LearnEffect; }
};

struct SpellMgr
{
    std::set<uint32> Missing;
    std::map<uint32, SpellInfo> Overrides;
    std::map<uint32, uint32> NextRanks;
    SpellInfo Default;
    SpellInfo const* GetSpellInfo(uint32 id) const
    {
        if (!id || Missing.count(id))
            return nullptr;
        auto const found = Overrides.find(id);
        return found == Overrides.end() ? &Default : &found->second;
    }
    uint32 GetNextSpellInChain(uint32 id) const
    {
        auto const found = NextRanks.find(id);
        return found == NextRanks.end() ? 0 : found->second;
    }
    static bool IsSpellValid(SpellInfo const* info) { return info && info->Valid; }
} SpellManager;
SpellMgr* sSpellMgr = &SpellManager;

struct ChatHandler
{
    Player* Character = nullptr;
    std::vector<std::string> Messages;
    explicit ChatHandler(Player* player) : Character(player) {}
    explicit ChatHandler(WorldSession*) {}
    Player* GetPlayer() const { return Character; }
    template <typename... Args>
    void PSendSysMessage(char const* message, Args&&...) { Messages.emplace_back(message); }
    static void BuildChatPacket(WorldPacket& packet, uint32 type, uint32 language, ObjectGuid sender,
        ObjectGuid receiver, std::string const& message, uint32 achievement, std::string const& senderName,
        std::string const& receiverName, uint32 tag, bool gmMessage)
    {
        assert(type == CHAT_MSG_WHISPER && language == LANG_ADDON);
        assert(sender.Value == receiver.Value && senderName == receiverName);
        assert(!achievement && !tag && !gmMessage);
        packet.Message = message;
    }
};

class AscensionClassService
{
public:
    std::unordered_map<uint32, uint32> _activeSpecializations;
    std::map<uint32, uint32> FreeGroups;
    bool AutomaticAllowed = true;
    uint32 Synchronizations = 0;
    static AscensionClassService& Instance()
    {
        static AscensionClassService service;
        return service;
    }
    static uint32 GetSelectableFreeGroup(uint32 entryId)
    {
        auto const found = Instance().FreeGroups.find(entryId);
        return found == Instance().FreeGroups.end() ? 0 : found->second;
    }
    static bool CanGrantAutomaticEntry(Player const*, AscensionCompatData::CoATalentEntry const&, uint32)
    {
        return Instance().AutomaticAllowed;
    }
    uint32 SynchronizeProgression(Player*) { ++Synchronizations; return 0; }

    // Exact definitions extracted from the candidate/release source, including
    // the real specialization-switch branches rather than a simulated switch.
#include "CoaTalentStateService.h"
};

// Exact native command handlers. The doubles model only their external APIs.
#include "CoaTalentStateCommands.h"

struct Fixture
{
    WorldSession Session;
    Player Character;
    ChatHandler Handler{&Character};
    AscensionClassService& Service = AscensionClassService::Instance();

    Fixture()
    {
        Character.Session = &Session;
        Service._activeSpecializations = {{1, 60}};
        Service.FreeGroups = {{107, 1}, {108, 1}, {109, 1}};
        Service.AutomaticAllowed = true;
        Service.Synchronizations = 0;
        SpellManager.Missing.clear();
        SpellManager.Overrides.clear();
        SpellManager.NextRanks.clear();
        auto& entries = AscensionCompatData::CoATalentEntries;
        entries[0] = {100, 31, 0, 3, 1, 0, 0, {1000, 1001, 1002}};
        entries[1] = {101, 31, 60, 1, 0, 1, 0, {1010, 0, 0}};
        entries[2] = {102, 31, 61, 1, 0, 1, 0, {1020, 0, 0}};
        entries[3] = {103, 23, 43, 1, 0, 1, 0, {1030, 0, 0}};
        entries[4] = {104, 31, 60, 1, 0, 0, 0, {1040, 0, 0}};
        entries[5] = {105, 31, 60, 1, 0, 1, 20, {1050, 0, 0}};
        entries[6] = {106, 31, 60, 1, 0, 1, 0, {0, 0, 0}};
        entries[7] = {107, 31, 60, 1, 0, 0, 0, {1070, 0, 0}};
        entries[8] = {108, 31, 60, 1, 0, 0, 0, {1080, 0, 0}};
        entries[9] = {109, 31, 61, 1, 0, 0, 0, {1090, 0, 0}};
        entries[10] = {110, 31, 60, 1, 0, 1, 0, {1100, 0, 0}};
        entries[11] = {111, 31, 60, 2, 0, 0, 0, {1110, 1111, 0}};
        for (std::size_t index = 12; index < entries.size(); ++index)
            entries[index] = {uint32(10000 + index), 31, 60, 1, 0, 1, 0, {uint32(20000 + index), 0, 0}};
    }
    void Seed(uint32 entry, uint32 rank)
    {
        Character.Settings[std::string(ASCENSION_TALENT_SETTING_PREFIX) + std::to_string(entry)] = {{rank}};
    }
    uint32 Rank(uint32 entry) const { return Service.GetRecordedTalentRank(&Character, entry); }
};

void CheckReadOnly(Fixture& f, std::string const& talents, std::string const& records = "0 0")
{
    auto const before = f.Character.Settings;
    auto const spells = f.Character.Spells;
    uint32 const writes = f.Character.Writes;
    uint32 const learned = f.Character.Learned;
    uint32 const removed = f.Character.Removed;
    uint32 const syncs = f.Service.Synchronizations;
    f.Session.Packets.clear();
    assert(HandleLocalSpecStateCommand(&f.Handler));
    assert((f.Session.Packets == std::vector<std::string>{
        "ASC_LOCAL_SPEC\t" + std::to_string(f.Service.GetActiveSpecialization(&f.Character)),
        "ASC_LOCAL_RECORDS\t" + records, "ASC_LOCAL_TALENTS\t" + talents}));
    assert(f.Character.Settings == before && f.Character.Spells == spells);
    assert(f.Character.Writes == writes && f.Character.Learned == learned && f.Character.Removed == removed);
    assert(f.Service.Synchronizations == syncs);
}

int main()
{
    // A legacy spellbook is not evidence of a chosen rank. Repeated queries
    // return an empty complete map and never create setting rows or spells.
    {
        Fixture f;
        f.Character.Spells = {1000, 1010, 1040};
        assert(f.Rank(100) == 0);
        CheckReadOnly(f, "");
        CheckReadOnly(f, "");
        assert(f.Character.Settings.empty());
    }

    // Exercise accepted native commands, then serialize only persistent
    // settings and recreate the player/session to simulate a complete relog.
    {
        Fixture f;
        assert(HandleLocalTalentCommand(&f.Handler, 100, 2));
        assert(HandleLocalTalentCommand(&f.Handler, 101, 1));
        assert(f.Rank(100) == 2 && f.Rank(101) == 1);
        assert(f.Character.HasSpell(1001) && f.Character.HasSpell(1010));
        CheckReadOnly(f, "100:2 101:1", "1 1");
        std::map<std::string, std::string> persisted;
        for (auto const& row : f.Character.Settings)
        {
            std::ostringstream data;
            for (auto const& setting : row.second)
                data << setting.value << ' ';
            persisted.emplace(row.first, data.str());
        }
        Fixture relog;
        for (auto const& row : persisted)
        {
            std::istringstream data(row.second);
            uint32 value;
            while (data >> value)
                relog.Character.Settings[row.first].push_back({value});
        }
        // No spellbook is loaded into this fixture; selected ranks still work.
        CheckReadOnly(relog, "100:2 101:1", "1 1");
        assert(HandleLocalTalentCommand(&relog.Handler, 100, 0));
        assert(HandleLocalTalentCommand(&relog.Handler, 101, 0));
        assert(relog.Rank(100) == 0 && relog.Rank(101) == 0);
        CheckReadOnly(relog, "", "1 1");
    }

    // Native same-spec synchronization must retain selections. An actual
    // switch uses the existing full refund, clearing only this class's rows.
    {
        Fixture f;
        f.Seed(100, 1);
        f.Seed(101, 1);
        f.Seed(103, 1);
        f.Character.Spells = {1000, 1010, 1030};
        assert(f.Service.SwitchSpecialization(&f.Character, 60));
        assert(f.Rank(100) == 1 && f.Rank(101) == 1 && f.Character.Removed == 0);
        assert(f.Service.SwitchSpecialization(&f.Character, 61));
        assert(f.Rank(100) == 0 && f.Rank(101) == 0 && f.Rank(103) == 1);
        assert(f.Character.HasSpell(1030));
        CheckReadOnly(f, "", "1 1");
        auto const before = f.Character.Settings;
        assert(!f.Service.SwitchSpecialization(&f.Character, 999));
        assert(f.Character.Settings == before);
    }

    // Explicit free-choice replacement clears a sibling record, but cannot
    // clear a same-group entry belonging to another specialization.
    {
        Fixture f;
        f.Seed(108, 1);
        f.Seed(109, 1);
        f.Character.Spells = {1080, 1090};
        assert(HandleLocalTalentCommand(&f.Handler, 107, 1));
        assert(f.Rank(107) == 1 && f.Rank(108) == 0 && f.Rank(109) == 1);
        assert(!f.Character.HasSpell(1080) && f.Character.HasSpell(1090));
        CheckReadOnly(f, "107:1", "0 1");
    }
    {
        Fixture f;
        f.Seed(100, 1);
        f.Character.Spells = {1000, 90000};
        assert(HandleLocalTalentCommand(&f.Handler, 100, 2));
        assert(f.Rank(100) == 2);
        assert((f.Character.Spells == std::set<uint32>{1001, 90000}));

        // A failed re-grant of an already selected rank must retain its old
        // ownership; allow a subsequent native rollback attempt to succeed.
        f.Character.FailedLearnAttempts[1001].insert(f.Character.LearnAttempts[1001] + 1);
        assert(HandleLocalTalentCommand(&f.Handler, 100, 2));
        assert(f.Rank(100) == 2);
        assert((f.Character.Spells == std::set<uint32>{1001, 90000}));
    }

    // Rejected, unavailable, failed-learning and automatic-only requests must
    // not produce a purchase record. The handler itself is production code.
    using Case = std::pair<uint32, uint32>;
    for (Case const request : {Case{99, 1}, {103, 1}, {102, 1}, {100, 4}, {105, 1}, {106, 1},
                              {104, 1}, {104, 0}, {111, 1}})
    {
        Fixture f;
        assert(HandleLocalTalentCommand(&f.Handler, request.first, request.second));
        assert(f.Character.Settings.empty() && f.Character.Writes == 0);
    }
    {
        Fixture f;
        SpellManager.Missing.insert(1010);
        assert(HandleLocalTalentCommand(&f.Handler, 101, 1));
        assert(f.Character.Settings.empty());
    }
    {
        Fixture f;
        f.Character.LearnAllowed = false;
        assert(HandleLocalTalentCommand(&f.Handler, 101, 1));
        assert(f.Character.Settings.empty());
    }
    // A failed replacement is not a refund. Preserve both the current rank's
    // spells and its durable record, including selectable-free siblings.
    for (bool freeChoice : {false, true})
        for (uint32 failure : {0, 1, 2, 3, 4, 5})
        {
            Fixture f;
            uint32 const selectedEntry = freeChoice ? 107 : 100;
            uint32 const selectedRank = freeChoice ? 1 : 2;
            uint32 const selectedSpell = freeChoice ? 1070 : 1001;
            f.Seed(freeChoice ? 108 : 100, 1);
            f.Character.Spells = {freeChoice ? 1080U : 1000U, 90000};
            auto const previousSettings = f.Character.Settings;
            auto const previousSpells = f.Character.Spells;
            if (failure == 0)
                f.Character.LearnAllowed = false;
            else if (failure == 1)
                SpellManager.Missing.insert(selectedSpell);
            else if (failure == 2)
                AscensionCompatData::CoATalentEntries[freeChoice ? 7 : 0].SpellIds[selectedRank - 1] = 0;
            else if (failure == 3)
                SpellManager.Overrides[selectedSpell].IsDeprecatedForPlayers = true;
            else if (failure == 4)
                SpellManager.Overrides[selectedSpell].Valid = false;
            else
                SpellManager.Overrides[selectedSpell].LearnEffect = true;
            assert(HandleLocalTalentCommand(&f.Handler, selectedEntry, selectedRank));
            assert(f.Character.Settings == previousSettings);
            assert(f.Character.Spells == previousSpells);
            assert(f.Character.Removed == 0 && f.Character.Writes == 0);
            if (failure != 0)
                assert(f.Character.Learned == 0);
        }
    // A native learner can succeed initially but reject a later re-grant after
    // rank-chain cleanup. Roll back only the involved prior choices, keeping
    // unrelated spells and the original durable selection unchanged.
    for (bool freeChoice : {false, true})
    {
        Fixture f;
        uint32 const selectedEntry = freeChoice ? 107 : 100;
        uint32 const selectedRank = freeChoice ? 1 : 2;
        uint32 const selectedSpell = freeChoice ? 1070 : 1001;
        uint32 const previousSpell = freeChoice ? 1080 : 1000;
        f.Seed(freeChoice ? 108 : 100, 1);
        f.Character.Spells = {previousSpell, 50000, 50001, 90000};
        f.Character.FailedLearnAttempts[selectedSpell].insert(2);
        f.Character.RemoveDependents[previousSpell] = {selectedSpell, 50000, 50001};
        // Native removal traverses ranks not represented by literal catalog
        // IDs. Restore these known descendants too, without scanning unrelated
        // spellbook entries or inferring a durable selection from ownership.
        SpellManager.NextRanks = {{previousSpell, 50000}, {50000, 50001}};
        auto const previousSettings = f.Character.Settings;
        auto const previousSpells = f.Character.Spells;
        assert(HandleLocalTalentCommand(&f.Handler, selectedEntry, selectedRank));
        assert(f.Character.Settings == previousSettings);
        assert(f.Character.Spells == previousSpells);
    }
    // Native downgrades may initially teach a lower rank inactive while the
    // old higher rank exists. Verify activation, and rollback if that fails.
    for (bool failActivation : {false, true})
    {
        Fixture f;
        f.Seed(100, 2);
        f.Character.Spells = {1001, 90000};
        f.Character.InactiveOnFirstLearn.insert(1000);
        if (failActivation)
            f.Character.FailedLearnAttempts[1000].insert(2);
        assert(HandleLocalTalentCommand(&f.Handler, 100, 1));
        if (failActivation)
        {
            assert(f.Rank(100) == 2);
            assert((f.Character.Spells == std::set<uint32>{1001, 90000}));
            assert(f.Character.HasActiveSpell(1001));
        }
        else
        {
            assert(f.Rank(100) == 1);
            assert((f.Character.Spells == std::set<uint32>{1000, 90000}));
            assert(f.Character.HasActiveSpell(1000));
        }
    }
    {
        Fixture f;
        f.Service.AutomaticAllowed = false;
        assert(HandleLocalTalentCommand(&f.Handler, 104, 1));
        assert(f.Character.Settings.empty());
        f.Handler.Character = nullptr;
        assert(!HandleLocalTalentCommand(&f.Handler, 100, 1));
        assert(!HandleLocalSpecStateCommand(&f.Handler));
    }

    // Corrupt/out-of-scope rows remain untouched but cannot leak into a UI
    // snapshot; automatic progression never becomes a recorded paid choice.
    {
        Fixture f;
        f.Seed(100, 2);
        f.Seed(101, 1);
        f.Seed(102, 1);
        f.Seed(103, 1);
        f.Seed(104, 1);
        f.Seed(110, 2);
        f.Seed(999, 1);
        CheckReadOnly(f, "100:2 101:1");
        f.Character.Settings[ASCENSION_TALENT_RECORDS_SETTING] = {{1}, {61}};
        CheckReadOnly(f, "100:2 101:1", "1 0");
    }

    // The real client replaces its entire map on every TALENTS message. A
    // complete high-level build must survive well beyond a 255-byte payload.
    {
        Fixture f;
        std::string expected;
        for (std::size_t index = 12; index < AscensionCompatData::CoATalentEntries.size(); ++index)
        {
            uint32 const id = AscensionCompatData::CoATalentEntries[index].EntryId;
            f.Seed(id, 1);
            if (!expected.empty())
                expected += ' ';
            expected += std::to_string(id) + ":1";
        }
        assert(expected.size() > 255);
        CheckReadOnly(f, expected);
        assert(f.Session.Packets.size() == 3);
    }

    for (uint32 gate : {0, 1, 2})
    {
        Fixture f;
        if (gate == 0)
            f.Character.Class = 1;
        else if (gate == 1)
            f.Character.Session = nullptr;
        else
            f.Session.Bot = true;
        f.Service.SendTalentState(&f.Character);
        assert(f.Session.Packets.empty() && f.Character.Settings.empty());
    }
    std::cout << "Exact production talent record/command/snapshot regression checks passed.\n";
}
