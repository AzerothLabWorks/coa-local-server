local Core = CoAGatheringAlertsCore
local prefix = "COAGATHER"
local pollSeconds = 1
local timeoutSeconds = 2.5
local pulseSeconds = 3
local alertSeconds = 8
local frame = CreateFrame("Frame")
local session = string.format("%x_%x", math.floor(GetTime() * 1000), math.random(1, 2147483646))
local sequence = 0
local online = false
local nextPoll = 0
local lastPoll = -pollSeconds
local nextAlert = 0
local nextDraw = 0
local pending
local snapshot
local memory = {}
local pulses = {}
local settings
local tracking = {}

local function Print(message)
    DEFAULT_CHAT_FRAME:AddMessage("|cff80d890Gathering alerts:|r " .. message)
end

local function Supported()
    return Minimap and type(Minimap.GetViewRadius) == "function"
        and type(GetCurrentPlayerPosition) == "function" and type(GetActiveMapID) == "function"
end

local function RefreshTracking()
    local minerals, herbs = GetSpellInfo(2580), GetSpellInfo(2383)
    tracking = {}
    for index = 1, GetNumTrackingTypes() do
        local name, _, active = GetTrackingInfo(index)
        if active then
            if name == minerals then tracking.M = true end
            if name == herbs then tracking.H = true end
        end
    end
end

local function Clear()
    pending = nil
    snapshot = nil
    for _, pulse in ipairs(pulses) do pulse:Hide(); pulse.node = nil end
end

local function IsSelf(sender)
    local name, realm = UnitName("player")
    if sender == name then return true end
    realm = realm or GetRealmName()
    return realm and sender == name .. "-" .. realm:gsub("%s", "")
end

local function CanScan()
    if not online or not settings or not settings.enabled or not Supported() or UnitIsDeadOrGhost("player") then
        return false
    end
    return tracking.M or tracking.H
end

local function Request(now)
    nextPoll = now + pollSeconds
    RefreshTracking()
    if not CanScan() or not Minimap:IsVisible() then Clear(); return end
    if now - lastPoll < pollSeconds then nextPoll = lastPoll + pollSeconds; return end
    if pending and now < pending.expires then return end
    local radius = Minimap:GetViewRadius()
    if type(radius) ~= "number" or radius <= 0 or radius ~= radius then Clear(); return end
    sequence = sequence + 1
    local nonce = session .. "_" .. string.format("%x", sequence)
    if #nonce > 32 then return end
    pending = {nonce = nonce, expires = now + timeoutSeconds}
    lastPoll = now
    SendAddonMessage(prefix, "Q|1|" .. nonce .. "|" .. math.floor(math.max(10, math.min(radius, 250))),
        "WHISPER", UnitName("player"))
end

local function Receive(messagePrefix, message, channel, sender)
    if messagePrefix ~= prefix or channel ~= "WHISPER" or not IsSelf(sender) or not CanScan() then return end
    local now = GetTime()
    local result = Core.Receive(pending, message, now, GetActiveMapID())
    if not result then return end
    snapshot = result
    pending = nil
    Core.Observe(memory, snapshot, now)
end

local function NewPulse()
    local pulse = CreateFrame("Frame", nil, Minimap)
    pulse:SetWidth(32)
    pulse:SetHeight(32)
    pulse:SetFrameLevel(Minimap:GetFrameLevel() + 8)
    pulse:EnableMouse(false)
    local function Texture(path, size)
        local texture = pulse:CreateTexture(nil, "OVERLAY")
        texture:SetTexture("Interface\\Minimap\\UI-Minimap-Ping-" .. path)
        texture:SetPoint("CENTER", pulse, "CENTER", 0, 0)
        texture:SetWidth(size)
        texture:SetHeight(size)
        return texture
    end
    pulse.center = Texture("Center", 15)
    pulse.expander = Texture("Expand", 28)
    pulse.spinner = Texture("Rotate", 32)
    pulse:Hide()
    pulses[#pulses + 1] = pulse
    return pulse
end

local function Draw(now)
    if not snapshot or now - snapshot.received > timeoutSeconds or snapshot.map ~= GetActiveMapID()
        or not CanScan() or not Minimap:IsVisible() then
        for _, pulse in ipairs(pulses) do pulse:Hide(); pulse.node = nil end
        return
    end
    local playerX, playerY = GetCurrentPlayerPosition()
    local radius = Minimap:GetViewRadius()
    local width, height = Minimap:GetWidth(), Minimap:GetHeight()
    local facing = GetCVar("rotateMinimap") == "1" and GetPlayerFacing() or nil
    local visible = {}
    local candidates = {}
    for _, node in ipairs(snapshot.nodes) do
        if tracking[node.kind] then
            local x, y, distance = Core.Project(node, playerX, playerY, radius, width, height, facing)
            if x then
                visible[node.key] = {x = x, y = y}
                local seen = memory[node.key]
                if seen and not seen.alerted then candidates[#candidates + 1] = {node = node, distance = distance} end
            end
        end
    end
    if now >= nextAlert and #candidates > 0 then
        table.sort(candidates, function(a, b) return a.distance < b.distance end)
        for index = 1, math.min(3, #candidates) do
            local pulse = pulses[index] or NewPulse()
            local node = candidates[index].node
            pulse.node = node
            pulse.started = now
            memory[node.key].alerted = true
            memory[node.key].lastAlert = now
        end
        nextAlert = now + alertSeconds
        if settings.sound then PlaySound("MapPing") end
    end
    for _, pulse in ipairs(pulses) do
        local position = pulse.node and visible[pulse.node.key]
        local age = pulse.started and now - pulse.started or pulseSeconds
        if position and age < pulseSeconds then
            pulse:ClearAllPoints()
            pulse:SetPoint("CENTER", Minimap, "CENTER", position.x, position.y)
            pulse:SetAlpha(math.min(1, (pulseSeconds - age) / 0.5))
            local size = 12 + (age % 0.65) / 0.65 * 16
            pulse.expander:SetWidth(size)
            pulse.expander:SetHeight(size)
            pulse.spinner:SetRotation(age * math.pi / 2)
            pulse:Show()
        else
            pulse:Hide()
            pulse.node = nil
        end
    end
end

local function Status()
    if not Supported() then
        Print("this client does not expose the required minimap APIs.")
    elseif not settings.enabled then
        Print("off. Use /gatherping on to enable.")
    else
        RefreshTracking()
        Print("on; sound " .. (settings.sound and "on" or "off") .. "; "
            .. ((tracking.M or tracking.H) and "tracking active." or "enable Find Minerals or Find Herbs."))
    end
end

SLASH_COAGATHERINGALERTS1 = "/gatherping"
SlashCmdList.COAGATHERINGALERTS = function(message)
    local command = (message or ""):lower():match("^%s*(.-)%s*$")
    if not settings then return end
    if command == "on" or command == "off" then
        settings.enabled = command == "on"
        Clear()
        nextPoll = 0
        Status()
    elseif command == "sound" then
        settings.sound = not settings.sound
        Status()
    elseif command == "" or command == "status" then
        Status()
    else
        Print("/gatherping on, off, sound, or status. Pings are local and respect active resource tracking.")
    end
end

frame:SetScript("OnEvent", function(_, event, ...)
    if event == "ADDON_LOADED" then
        local name = ...
        if name ~= "CoAGatheringAlerts" then return end
        CoAGatheringAlertsDB = type(CoAGatheringAlertsDB) == "table" and CoAGatheringAlertsDB or {}
        settings = CoAGatheringAlertsDB
        if type(settings.enabled) ~= "boolean" then settings.enabled = true end
        if type(settings.sound) ~= "boolean" then settings.sound = true end
        if RegisterAddonMessagePrefix then RegisterAddonMessagePrefix(prefix) end
    elseif event == "CHAT_MSG_ADDON" then
        Receive(...)
    else
        if event == "PLAYER_ENTERING_WORLD" or event == "PLAYER_LOGIN" then online = true end
        if event == "PLAYER_LEAVING_WORLD" then online = false end
        RefreshTracking()
        Clear()
        nextPoll = 0
    end
end)

frame:SetScript("OnUpdate", function()
    if not online or not settings or not Supported() then return end
    local now = GetTime()
    if now >= nextPoll then Request(now) end
    if now >= nextDraw then nextDraw = now + 0.05; Draw(now) end
end)

for _, event in ipairs({"ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "PLAYER_LEAVING_WORLD",
    "CHAT_MSG_ADDON", "MINIMAP_UPDATE_TRACKING", "MINIMAP_UPDATE_ZOOM", "PLAYER_DEAD", "PLAYER_ALIVE"}) do
    frame:RegisterEvent(event)
end
