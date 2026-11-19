CoAGatheringAlertsCore = {}
local Core = CoAGatheringAlertsCore

function Core.UInt(value, maximum)
    if type(value) ~= "string" or #value > 10 or not value:match("^%d+$") then return end
    local number = tonumber(value)
    if number and number <= (maximum or 4294967295) then return number end
end

function Core.Coordinate(value)
    if type(value) ~= "string" or #value > 12 or not value:match("^%-?%d+%.?%d*$") then return end
    local number = tonumber(value)
    if number and math.abs(number) <= 100000 then return number end
end

function Core.Fields(message)
    local fields = {}
    for field in (message .. "|"):gmatch("([^|]*)|") do fields[#fields + 1] = field end
    return fields
end

function Core.Receive(pending, message, now, map)
    if not pending or now > pending.expires or type(message) ~= "string" or #message > 240 then return end
    local fields = Core.Fields(message)
    if fields[2] ~= "1" or fields[3] ~= pending.nonce then return end
    if fields[1] == "S" then
        if #fields ~= 6 or pending.started then return end
        local packetMap = Core.UInt(fields[4])
        local instance = Core.UInt(fields[5])
        local count = Core.UInt(fields[6], 12)
        if packetMap ~= map or not instance or not count then return end
        pending.started = true
        pending.map = packetMap
        pending.instance = instance
        pending.count = count
        pending.nodes = {}
        pending.keys = {}
    elseif fields[1] == "N" then
        if #fields ~= 8 or not pending.started or #pending.nodes >= pending.count then return end
        local guid = fields[4]
        if #guid ~= 16 or not guid:match("^[0-9a-f]+$") or guid == "0000000000000000" then return end
        if fields[5] ~= "M" and fields[5] ~= "H" then return end
        local x, y, z = Core.Coordinate(fields[6]), Core.Coordinate(fields[7]), Core.Coordinate(fields[8])
        if not x or not y or not z or pending.keys[guid] then return end
        pending.keys[guid] = true
        pending.nodes[#pending.nodes + 1] = {guid = guid, kind = fields[5], x = x, y = y, z = z}
    elseif fields[1] == "E" then
        if #fields ~= 3 or not pending.started or #pending.nodes ~= pending.count or pending.map ~= map then return end
        return {map = pending.map, instance = pending.instance, nodes = pending.nodes, received = now}
    end
end

function Core.Project(node, playerX, playerY, radius, width, height, facing)
    if type(playerX) ~= "number" or type(playerY) ~= "number" or type(radius) ~= "number" or radius <= 0
        or type(width) ~= "number" or type(height) ~= "number" or width <= 0 or height <= 0 then return end
    local dx, dy = node.x - playerX, node.y - playerY
    local distanceSquared = dx * dx + dy * dy
    if distanceSquared >= radius * radius then return end
    local x, y = -dy, dx
    if facing then
        x = dx * math.sin(facing) - dy * math.cos(facing)
        y = dx * math.cos(facing) + dy * math.sin(facing)
    end
    return x * width / (2 * radius), y * height / (2 * radius), distanceSquared
end

function Core.Observe(memory, snapshot, now)
    for _, node in ipairs(snapshot.nodes) do
        local key = snapshot.map .. ":" .. snapshot.instance .. ":" .. node.guid
        node.key = key
        local seen = memory[key]
        if not seen then
            seen = {alerted = false, lastAlert = -60}
            memory[key] = seen
        elseif now - seen.lastSeen >= 60 and now - seen.lastAlert >= 60 then
            seen.alerted = false
        end
        seen.lastSeen = now
    end
    local entries = {}
    for key, seen in pairs(memory) do
        if now - seen.lastSeen > 600 then
            memory[key] = nil
        else
            entries[#entries + 1] = {key = key, time = seen.lastSeen}
        end
    end
    if #entries > 256 then
        table.sort(entries, function(a, b) return a.time < b.time end)
        for index = 1, #entries - 256 do memory[entries[index].key] = nil end
    end
end
