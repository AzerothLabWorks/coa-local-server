#include "CoaRoleProfile.h"

// This test compiles the actual profile header from the patched module without
// linking worldserver or needing a database. Failures are compile-time errors.
constexpr bool AllCoaProfilesHaveConservativeRoles()
{
    for (std::uint8_t classId = 12; classId <= 32; ++classId)
    {
        for (std::uint32_t specializationId = 0; specializationId <= 101; ++specializationId)
        {
            CoaRoleProfile profile = GetCoaRoleProfile(classId, specializationId);
            bool const brewing = classId == 13 && specializationId == 6;
            if (profile.Role != (brewing ? CoaCombatRole::Healer : CoaCombatRole::Damage))
                return false;

            if (!profile.Ranged || profile.Role == CoaCombatRole::Tank)
                return false;
        }
    }

    return true;
}

static_assert(AllCoaProfilesHaveConservativeRoles(), "Only the supported Brewing profile may advertise healing");
static_assert(GetCoaRoleProfile(13, 0).Role == CoaCombatRole::Damage, "Unassigned Witch Doctors keep generic offense");
static_assert(GetCoaRoleProfile(31, 60).Role == CoaCombatRole::Damage, "Mountain King needs tank AI before a tank role");
static_assert(GetCoaRoleProfile(13, 0xFFFFFFFF).Role == CoaCombatRole::Damage, "Unknown specs use the safe fallback");
