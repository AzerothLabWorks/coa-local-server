// Compile exact production definitions against deterministic DB/cache doubles.
#include "CoaTestPilotAccess.h"
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <utility>

using uint8 = std::uint8_t;
using uint32 = std::uint32_t;

struct CharacterCacheEntry
{
    uint32 AccountId;
    uint8 Class;
};

struct CharacterCacheDouble
{
    std::map<std::string, CharacterCacheEntry> Characters;

    CharacterCacheEntry const* GetCharacterCacheByName(std::string const& name) const
    {
        auto const found = Characters.find(name);
        return found == Characters.end() ? nullptr : &found->second;
    }
} characterCache;

auto* sCharacterCache = &characterCache;

struct Field
{
    uint32 Value;
    template <typename T> T Get() const { return static_cast<T>(Value); }
};

struct Rows
{
    std::vector<std::vector<Field>> Data;
    std::size_t Position = 0;
    Field* Fetch() { return Data.at(Position).data(); }
    bool NextRow() { return ++Position < Data.size(); }
};

using QueryResult = std::shared_ptr<Rows>;

std::vector<uint32> generatedAccounts;
std::map<uint32, uint8> databaseAssignments;
std::set<uint32> accountsWithCoaCharacters;
std::vector<std::pair<uint32, uint8>> assignmentWrites;
std::vector<std::pair<std::string, std::vector<std::size_t>>> messages;

template <typename... Values>
void RecordLog(char const*, std::string const& format, Values... values)
{
    messages.push_back({format, {static_cast<std::size_t>(values)...}});
}

#define LOG_INFO(...) RecordLog(__VA_ARGS__)
#define LOG_ERROR(...) RecordLog(__VA_ARGS__)

struct DatabaseDouble
{
    enum Kind { LOGIN, CHARACTERS, PLAYERBOTS } Type;

    QueryResult Query(std::string const& sql)
    {
        assert(Type == PLAYERBOTS && sql == "SELECT account_id, account_type FROM playerbots_account_type");
        auto result = std::make_shared<Rows>();
        for (auto const& [account, type] : databaseAssignments)
            result->Data.push_back({{account}, {type}});
        return result->Data.empty() ? nullptr : result;
    }

    QueryResult Query(std::string const& sql, char const*)
    {
        assert(Type == LOGIN && sql.find("SELECT id FROM account") == 0);
        auto result = std::make_shared<Rows>();
        for (uint32 account : generatedAccounts)
            result->Data.push_back({{account}});
        return result->Data.empty() ? nullptr : result;
    }

    QueryResult Query(std::string const& sql, uint32 account)
    {
        assert(Type == CHARACTERS && sql.find("SELECT 1 FROM characters WHERE account") == 0);
        if (!accountsWithCoaCharacters.count(account))
            return nullptr;
        auto result = std::make_shared<Rows>();
        result->Data.push_back({{1}});
        return result;
    }

    void Execute(std::string const& sql, uint32 account)
    {
        assert(Type == PLAYERBOTS);
        if (sql.find("INSERT INTO playerbots_account_type") == 0)
        {
            databaseAssignments.emplace(account, 0);
            return;
        }
        assert(sql.find("UPDATE playerbots_account_type SET account_type = ") == 0);
        std::size_t const position = sql.find("account_type = ") + std::string("account_type = ").size();
        uint8 const type = static_cast<uint8>(sql.at(position) - '0');
        assert(type <= 2);
        databaseAssignments[account] = type;
        assignmentWrites.emplace_back(account, type);
    }
};

DatabaseDouble LoginDatabase{DatabaseDouble::LOGIN};
DatabaseDouble CharacterDatabase{DatabaseDouble::CHARACTERS};
DatabaseDouble PlayerbotsDatabase{DatabaseDouble::PLAYERBOTS};

struct Config
{
    std::string randomBotAccountPrefix = "rndbot";
    bool randomBotCustomClassesOnly = true;
    uint32 maxRandomBots = 0;
    bool enablePeriodicOnlineOffline = false;
    uint32 periodicOnlineOfflineRatio = 2;
    uint32 addClassAccountPoolSize = 0;
} sPlayerbotAIConfig;

struct RandomPlayerbotFactory
{
    static int CalculateAvailableCharsPerAccount() { return 10; }
};

struct RandomPlayerbotMgr
{
    std::vector<uint32> rndBotTypeAccounts;
    std::vector<uint32> addClassTypeAccounts;
    void AssignAccountTypes();
};

#include "CoaPilotReservationProduction.h"

void Reset(std::vector<uint32> accounts, uint32 pilotAccount)
{
    generatedAccounts = std::move(accounts);
    databaseAssignments.clear();
    accountsWithCoaCharacters.clear();
    assignmentWrites.clear();
    messages.clear();
    sPlayerbotAIConfig = {};
    characterCache.Characters = {{"Amaryla", {pilotAccount, 13}}};
    for (uint32 account : generatedAccounts)
    {
        databaseAssignments[account] = 0;
        accountsWithCoaCharacters.insert(account);
    }
}

bool ReportedShortage(std::string const& pool, std::size_t expected)
{
    return std::any_of(messages.begin(), messages.end(), [&](auto const& message)
    {
        return message.first.find("Not enough unassigned accounts") == 0 &&
            message.first.find(pool) != std::string::npos &&
            message.second == std::vector<std::size_t>{expected};
    });
}

int main()
{
    // Exact parser canonicalizes names; multiple named characters reserve one account.
    Reset({101, 102, 103}, 102);
    characterCache.Characters["Elowen"] = {102, 32};
    auto const names = ParseCoaTestPilotNames(" amaryla , ELOWEN , Amaryla ");
    auto const assignmentsBefore = databaseAssignments;
    assert(GetReservedCoaTestPilotAccounts(names, generatedAccounts, databaseAssignments) == std::set<uint32>{102});
    assert(databaseAssignments == assignmentsBefore && assignmentWrites.empty());

    // Missing names, malformed lists, classic/invalid classes and human accounts reserve nothing.
    for (auto const& input : {"", "Amaryla,*", "Amaryla,", "Amaryla,Elowen,Third,Fourth,Fifth"})
        assert(GetReservedCoaTestPilotAccounts(ParseCoaTestPilotNames(input), generatedAccounts,
            databaseAssignments).empty());
    assert(GetReservedCoaTestPilotAccounts({"Unknown"}, generatedAccounts, databaseAssignments).empty());
    for (uint8 classId : {uint8(11), uint8(33)})
    {
        characterCache.Characters["Amaryla"].Class = classId;
        assert(GetReservedCoaTestPilotAccounts({"Amaryla"}, generatedAccounts, databaseAssignments).empty());
    }
    characterCache.Characters["Amaryla"] = {999, 13};
    databaseAssignments[999] = 0;
    assert(GetReservedCoaTestPilotAccounts({"Amaryla"}, generatedAccounts, databaseAssignments).empty());
    characterCache.Characters["Amaryla"] = {102, 12};
    assert(GetReservedCoaTestPilotAccounts({"Amaryla"}, generatedAccounts, databaseAssignments) == std::set<uint32>{102});
    databaseAssignments.erase(102);
    assert(GetReservedCoaTestPilotAccounts({"Amaryla"}, generatedAccounts, databaseAssignments).empty());

    // Actual assignment code skips a pilot in the middle of ascending RND candidates.
    Reset({101, 102, 103}, 102);
    sPlayerbotAIConfig.maxRandomBots = 20;
    RandomPlayerbotMgr manager;
    manager.AssignAccountTypes();
    assert((manager.rndBotTypeAccounts == std::vector<uint32>{101, 103}));
    assert(databaseAssignments.at(102) == 0);
    assert((assignmentWrites == std::vector<std::pair<uint32, uint8>>{{101, 1}, {103, 1}}));
    assert(CanRecruitCoaTestPilot(true, true, databaseAssignments.at(102) == 0, true, true, 13, 13, 13, 6));

    // Actual AddClass assignment skips the highest pilot account, preserving type 0.
    Reset({101, 102, 103}, 103);
    sPlayerbotAIConfig.maxRandomBots = 10;
    sPlayerbotAIConfig.addClassAccountPoolSize = 1;
    manager.AssignAccountTypes();
    assert((manager.rndBotTypeAccounts == std::vector<uint32>{101}));
    assert((manager.addClassTypeAccounts == std::vector<uint32>{102}));
    assert(databaseAssignments.at(103) == 0);

    // Existing reservations are never silently demoted by adding a pilot name.
    for (uint8 existingType : {uint8(1), uint8(2)})
    {
        Reset({101, 102}, 102);
        databaseAssignments[102] = existingType;
        manager.AssignAccountTypes();
        assert(databaseAssignments.at(102) == existingType);
        assert(assignmentWrites.empty());
    }

    // Missing assignment rows get the existing type-0 initialization, then are reserved.
    Reset({101, 102}, 102);
    databaseAssignments.erase(102);
    sPlayerbotAIConfig.maxRandomBots = 10;
    manager.AssignAccountTypes();
    assert(databaseAssignments.at(102) == 0);
    assert((manager.rndBotTypeAccounts == std::vector<uint32>{101}));

    // No silent capacity inflation: both pools report a truthful shortage.
    Reset({101, 102}, 102);
    sPlayerbotAIConfig.maxRandomBots = 20;
    sPlayerbotAIConfig.addClassAccountPoolSize = 1;
    manager.AssignAccountTypes();
    assert(ReportedShortage("RNDbot", 1));
    assert(ReportedShortage("AddClass", 1));
    assert(databaseAssignments.at(102) == 0);

    // Reservation remains effective without the optional COA-only random-pool filter.
    Reset({101, 102}, 102);
    sPlayerbotAIConfig.randomBotCustomClassesOnly = false;
    sPlayerbotAIConfig.maxRandomBots = 20;
    manager.AssignAccountTypes();
    assert(databaseAssignments.at(102) == 0 && ReportedShortage("RNDbot", 1));

    // Model the audited pool: 100 preserved classic accounts, 20 COA accounts,
    // two current RND accounts, 50 classic AddClass accounts, and pilot account 105.
    std::vector<uint32> auditedAccounts;
    for (uint32 account = 2; account <= 121; ++account)
        auditedAccounts.push_back(account);
    Reset(auditedAccounts, 105);
    accountsWithCoaCharacters.clear();
    for (uint32 account = 102; account <= 121; ++account)
        accountsWithCoaCharacters.insert(account);
    for (uint32 account = 2; account <= 51; ++account)
        databaseAssignments[account] = 2;
    databaseAssignments[102] = databaseAssignments[103] = 1;
    sPlayerbotAIConfig.maxRandomBots = 50;
    sPlayerbotAIConfig.addClassAccountPoolSize = 50;
    manager.AssignAccountTypes();
    assert((manager.rndBotTypeAccounts == std::vector<uint32>{102, 103, 104, 106, 107}));
    assert(databaseAssignments.at(105) == 0 && manager.addClassTypeAccounts.size() == 50);

    // 1,500 simultaneous slots require 150 eligible COA accounts, not 1,500
    // accounts. The one reserved pilot account is additional to that capacity.
    messages.clear();
    sPlayerbotAIConfig.maxRandomBots = 1500;
    manager.AssignAccountTypes();
    assert(manager.rndBotTypeAccounts.size() == 19 && ReportedShortage("RNDbot", 131));
    for (uint32 account = 122; account <= 252; ++account)
    {
        generatedAccounts.push_back(account);
        accountsWithCoaCharacters.insert(account);
    }
    messages.clear();
    manager.AssignAccountTypes();
    assert(generatedAccounts.size() == 251 && manager.rndBotTypeAccounts.size() == 150);
    assert(databaseAssignments.at(105) == 0 && assignmentWrites.size() == 148);
    assert(manager.addClassTypeAccounts.size() == 50 && !ReportedShortage("RNDbot", 1));

    std::cout << "Pilot reservation and assignment regression checks passed.\n";
}
