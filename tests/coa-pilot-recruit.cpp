#include "CoaTestPilotAccess.h"

#include <cassert>

static_assert(CanRecruitCoaTestPilot(true, true, true, true, true, 13, 1, 13, 0));
static_assert(CanRecruitCoaTestPilot(true, true, true, true, true, 13, 13, 13, 6));
static_assert(!CanRecruitCoaTestPilot(false, true, true, true, true, 13, 1, 13, 0), "A real GM is required");
static_assert(!CanRecruitCoaTestPilot(true, false, true, true, true, 13, 1, 13, 0), "Never recruit human accounts");
static_assert(!CanRecruitCoaTestPilot(true, true, false, true, true, 13, 1, 13, 0), "Do not take assigned pool bots");
static_assert(!CanRecruitCoaTestPilot(true, true, true, false, true, 13, 1, 13, 0), "Never take an online character");
static_assert(!CanRecruitCoaTestPilot(true, true, true, true, false, 13, 1, 13, 0), "Do not take another party's bot");
static_assert(!CanRecruitCoaTestPilot(true, true, true, true, true, 31, 1, 13, 0), "Only the supported class is eligible");
static_assert(!CanRecruitCoaTestPilot(true, true, true, true, true, 13, 0, 13, 0), "Reject invalid zero-level records");
static_assert(!CanRecruitCoaTestPilot(true, true, true, true, true, 13, 79, 13, 6), "Do not recruit overlevel pilots");
static_assert(!CanRecruitCoaTestPilot(true, true, true, true, true, 13, 13, 13, 4), "Preserve different specializations");

int main()
{
    auto names = ParseCoaTestPilotNames("  aMaRyLa ,\tSURSHI\n, Amaryla ");
    assert((names == std::vector<std::string>{"Amaryla", "Surshi"}));
    assert(std::find(names.begin(), names.end(), "Amary") == names.end());
    assert(ParseCoaTestPilotNames("").empty());
    assert(ParseCoaTestPilotNames("   ").empty());
    assert(ParseCoaTestPilotNames("Amaryla,*").empty());
    assert(ParseCoaTestPilotNames("Amaryla,").empty());
    assert(ParseCoaTestPilotNames(",Amaryla").empty());
    assert(ParseCoaTestPilotNames("Amaryla,,Surshi").empty());
    assert(ParseCoaTestPilotNames("A").empty());
    assert(ParseCoaTestPilotNames("Amaryla123").empty());
    assert(ParseCoaTestPilotNames("Longerthanmaxchar").empty());
    assert(ParseCoaTestPilotNames("Amaryla,Surshi,Evanda,Glinkil").size() == 4);
    assert(ParseCoaTestPilotNames("Amaryla,Surshi,Evanda,Glinkil,Quaesh").empty());
}
