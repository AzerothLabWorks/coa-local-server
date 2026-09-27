#include "Bag.h"
#include "Chat.h"
#include "Item.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "PlayerScript.h"
#include "WorldSession.h"

#include <array>

namespace
{
struct ProfessionTool
{
    uint32 Skill;
    uint32 ItemId;
};

constexpr std::array<ProfessionTool, 11> ProfessionTools = {{
    {SKILL_FISHING, 6256},         // Fishing Pole
    {SKILL_SKINNING, 7005},        // Skinning Knife
    {SKILL_MINING, 2901},          // Mining Pick
    {SKILL_BLACKSMITHING, 5956},   // Blacksmith Hammer
    {SKILL_ENGINEERING, 5956},     // Blacksmith Hammer (shared with blacksmithing)
    {SKILL_ENGINEERING, 6219},     // Arclight Spanner (usable at Engineering 50)
    {SKILL_ENGINEERING, 10498},    // Gyromatic Micro-Adjustor
    {SKILL_ENCHANTING, 6218},      // Runed Copper Rod
    {SKILL_INSCRIPTION, 39505},    // Virtuoso Inking Set
    {SKILL_JEWELCRAFTING, 20815},  // Jeweler's Kit
    {SKILL_JEWELCRAFTING, 20824}   // Simple Grinder
}};

bool IsEligiblePlayer(Player const* player)
{
    if (!player || !player->IsInWorld() || !player->GetSession() || player->GetSession()->PlayerLoading())
        return false;

#ifdef MOD_PLAYERBOTS
    if (player->GetSession()->IsBot())
        return false;
#endif

    return true;
}

bool IsEquivalentTool(Player const* player, Item const* item, ItemTemplate const* tool)
{
    if (!item)
        return false;

    ItemTemplate const* owned = item->GetTemplate();
    if (owned->ItemId == tool->ItemId)
        return true;

    // Fishing poles do not have a tool category. An already usable upgraded
    // pole counts, including an equipped pole or one kept in the bank.
    if (tool->Class == ITEM_CLASS_WEAPON && tool->SubClass == ITEM_SUBCLASS_WEAPON_FISHING_POLE)
        return owned->Class == ITEM_CLASS_WEAPON && owned->SubClass == ITEM_SUBCLASS_WEAPON_FISHING_POLE &&
            player->CanUseItem(owned) == EQUIP_ERR_OK;

    // This also recognizes upgraded enchanting rods and multi-purpose tools.
    return tool->TotemCategory && player->IsTotemCategoryCompatiableWith(owned, tool->TotemCategory);
}

bool OwnsTool(Player const* player, ItemTemplate const* tool)
{
    // Equipped items, backpack, bank slots, carried bags and bank bags. Do not
    // include vendor buyback: a sold tool is no longer owned by the character.
    for (uint8 slot = EQUIPMENT_SLOT_START; slot < BANK_SLOT_BAG_END; ++slot)
    {
        if (IsEquivalentTool(player, player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot), tool))
            return true;

        bool const bagSlot = (slot >= INVENTORY_SLOT_BAG_START && slot < INVENTORY_SLOT_BAG_END) ||
            (slot >= BANK_SLOT_BAG_START && slot < BANK_SLOT_BAG_END);
        if (bagSlot)
            if (Bag const* bag = player->GetBagByPos(slot))
                for (uint32 bagSlotIndex = 0; bagSlotIndex < bag->GetBagSize(); ++bagSlotIndex)
                    if (IsEquivalentTool(player, bag->GetItemByPos(bagSlotIndex), tool))
                        return true;
    }

    return false;
}

void GrantMissingProfessionTools(Player* player, uint32 learnedSkill = 0)
{
    if (!IsEligiblePlayer(player))
        return;

    for (ProfessionTool const& tool : ProfessionTools)
    {
        if ((learnedSkill && tool.Skill != learnedSkill) || !player->HasSkill(tool.Skill))
            continue;

        ItemTemplate const* itemTemplate = sObjectMgr->GetItemTemplate(tool.ItemId);
        if (!itemTemplate || OwnsTool(player, itemTemplate))
            continue;

        // AddItem uses normal inventory storage and item notification. Never
        // replace equipped weapons or bypass bag capacity to supply a tool.
        if (!player->AddItem(tool.ItemId, 1))
        {
            ChatHandler(player->GetSession()).SendSysMessage(
                "Starter profession tools could not be added. Free bag space and log in again to receive missing tools.");
            return;
        }
    }
}

class LocalProfessionTools : public PlayerScript
{
public:
    LocalProfessionTools() : PlayerScript("LocalProfessionTools", {PLAYERHOOK_ON_LOGIN, PLAYERHOOK_ON_SET_SKILL}) { }

    void OnPlayerLogin(Player* player) override
    {
        GrantMissingProfessionTools(player);
    }

    void OnPlayerSetSkill(Player* player, uint32 skillId, uint32 /*value*/, uint32 /*max*/,
        uint32 /*step*/, uint32 newValue) override
    {
        // The hook runs after the skill is stored. Ignore profession unlearning
        // and mapless character loading; the login hook covers existing skills.
        if (newValue)
            GrantMissingProfessionTools(player, skillId);
    }
};
}

void Addmod_local_profession_toolsScripts()
{
    new LocalProfessionTools();
}
