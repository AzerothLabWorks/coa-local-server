#include "GatheringAlertsPolicy.h"

#include "CellImpl.h"
#include "Chat.h"
#include "Config.h"
#include "DBCStores.h"
#include "DataMap.h"
#include "GameObject.h"
#include "GameTime.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Player.h"
#include "PlayerScript.h"
#include "StringFormat.h"
#include "WorldPacket.h"
#include "WorldScript.h"
#include "WorldSession.h"

#include <atomic>
#include <vector>

namespace
{
using namespace LocalGatheringAlerts;

constexpr char RequestStateKey[] = "LocalGatheringAlertsRequest";
constexpr uint32 HerbTrackingMask = uint32(1) << (LOCKTYPE_HERBALISM - 1);
constexpr uint32 MineralTrackingMask = uint32(1) << (LOCKTYPE_MINING - 1);
std::atomic<bool> Enabled{true};

struct RequestState final : DataMap::Base
{
    Milliseconds NextRequest = Milliseconds::zero();
};

struct Node
{
    ObjectGuid Guid;
    char Kind;
    float X;
    float Y;
    float Z;
    float DistanceSquared;
};

char TrackedResourceKind(GameObject const* object, uint32 tracking)
{
    LockEntry const* lock = sLockStore.LookupEntry(object->GetGOInfo()->GetLockId());
    if (!lock)
        return 0;

    for (uint8 index = 0; index < 8; ++index)
    {
        if (lock->Type[index] != LOCK_KEY_SKILL)
            continue;
        if (lock->Index[index] == LOCKTYPE_MINING && (tracking & MineralTrackingMask))
            return 'M';
        if (lock->Index[index] == LOCKTYPE_HERBALISM && (tracking & HerbTrackingMask))
            return 'H';
    }
    return 0;
}

std::vector<Node> CollectNodes(Player* player, uint32 radius)
{
    std::vector<Node> result;
    if (!Enabled.load(std::memory_order_relaxed) || !player->IsInWorld() || !player->FindMap() ||
        player->GetSession()->PlayerLoading() || player->IsBeingTeleported() || !player->IsAlive())
        return result;

    uint32 const tracking = player->GetUInt32Value(PLAYER_TRACK_RESOURCES) & (HerbTrackingMask | MineralTrackingMask);
    if (!tracking)
        return result;

    float const radiusSquared = float(radius * radius);
    auto collect = [player, tracking, radiusSquared, &result](GameObject* object)
    {
        if (!object->IsInWorld() || object->GetGoType() != GAMEOBJECT_TYPE_CHEST || !object->isSpawned() ||
            object->getLootState() != GO_READY || !player->HaveAtClient(object) ||
            !player->CanSeeOrDetect(object))
            return;

        float const dx = object->GetPositionX() - player->GetPositionX();
        float const dy = object->GetPositionY() - player->GetPositionY();
        float const distanceSquared = dx * dx + dy * dy;
        if (distanceSquared > radiusSquared)
            return;

        if (char const kind = TrackedResourceKind(object, tracking))
            result.push_back({object->GetGUID(), kind, object->GetPositionX(), object->GetPositionY(),
                object->GetPositionZ(), distanceSquared});
    };

    Acore::GameObjectWorker<decltype(collect)> worker(player, collect);
    Cell::VisitObjects(player, worker, float(radius));
    std::sort(result.begin(), result.end(), [](Node const& left, Node const& right)
    {
        if (left.DistanceSquared != right.DistanceSquared)
            return left.DistanceSquared < right.DistanceSquared;
        return left.Guid.GetRawValue() < right.Guid.GetRawValue();
    });
    if (result.size() > MaximumNodes)
        result.resize(MaximumNodes);
    return result;
}

void SendAddon(Player* player, std::string const& message)
{
    WorldPacket packet;
    ChatHandler::BuildChatPacket(packet, CHAT_MSG_WHISPER, LANG_ADDON, player, player, std::string(Prefix) + message);
    player->SendDirectMessage(&packet);
}

void SendSnapshot(Player* player, Request const& request)
{
    std::vector<Node> const nodes = CollectNodes(player, request.Radius);
    SendAddon(player, Acore::StringFormat("S|1|{}|{}|{}|{}", request.Nonce, player->GetMapId(),
        player->GetInstanceId(), nodes.size()));
    for (Node const& node : nodes)
        SendAddon(player, Acore::StringFormat("N|1|{}|{:016x}|{}|{:.2f}|{:.2f}|{:.2f}", request.Nonce,
            node.Guid.GetRawValue(), node.Kind, node.X, node.Y, node.Z));
    SendAddon(player, "E|1|" + request.Nonce);
}

class GatheringAlertsWorld final : public WorldScript
{
public:
    GatheringAlertsWorld() : WorldScript("LocalGatheringAlertsWorld", {WORLDHOOK_ON_AFTER_CONFIG_LOAD}) { }

    void OnAfterConfigLoad(bool) override
    {
        Enabled.store(sConfigMgr->GetOption<bool>("Local.GatheringAlerts.Enable", true), std::memory_order_relaxed);
    }
};

class GatheringAlertsPlayer final : public PlayerScript
{
public:
    GatheringAlertsPlayer() : PlayerScript("LocalGatheringAlertsPlayer",
        {PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT, PLAYERHOOK_ON_LOGOUT, PLAYERHOOK_ON_MAP_CHANGED}) { }

    bool OnPlayerCanUseChat(Player* player, uint32 type, uint32 language, std::string& message,
        Player* receiver) override
    {
        if (type != CHAT_MSG_WHISPER || language != LANG_ADDON ||
            message.compare(0, Prefix.size(), Prefix) != 0)
            return true;

        if (!player || !player->GetSession() || receiver != player)
            return false;
        if (player->GetSession()->IsBot())
            return false;

        RequestState* state = player->CustomData.GetDefault<RequestState>(RequestStateKey);
        Milliseconds const now = GameTime::GetGameTimeMS();
        if (now < state->NextRequest)
            return false;
        state->NextRequest = now + Milliseconds(MinimumRequestIntervalMs);

        if (auto request = ParseRequest(std::string_view(message).substr(Prefix.size())))
            SendSnapshot(player, *request);
        return false;
    }

    void OnPlayerLogout(Player* player) override
    {
        player->CustomData.Erase(RequestStateKey);
    }

    void OnPlayerMapChanged(Player* player) override
    {
        player->CustomData.Erase(RequestStateKey);
    }
};
}

void AddLocalGatheringAlertsScripts()
{
    new GatheringAlertsWorld();
    new GatheringAlertsPlayer();
}
