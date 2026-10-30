#ifndef LOCAL_GATHERING_ALERTS_POLICY_H
#define LOCAL_GATHERING_ALERTS_POLICY_H

#include <algorithm>
#include <charconv>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace LocalGatheringAlerts
{
constexpr std::string_view Prefix = "COAGATHER\t";
constexpr std::uint32_t MinimumRadius = 10;
constexpr std::uint32_t MaximumRadius = 250;
constexpr std::size_t MaximumNodes = 12;
constexpr std::uint32_t MinimumRequestIntervalMs = 800;

struct Request
{
    std::string Nonce;
    std::uint32_t Radius;
};

inline std::optional<Request> ParseRequest(std::string_view message)
{
    if (message.size() > 64 || message.substr(0, 4) != "Q|1|")
        return std::nullopt;

    message.remove_prefix(4);
    std::size_t const separator = message.find('|');
    if (separator == std::string_view::npos || separator == 0 || separator > 32)
        return std::nullopt;

    std::string_view const nonce = message.substr(0, separator);
    for (char character : nonce)
        if (!((character >= 'a' && character <= 'z') || (character >= 'A' && character <= 'Z') ||
            (character >= '0' && character <= '9') || character == '_' || character == '-'))
            return std::nullopt;

    std::string_view const radiusText = message.substr(separator + 1);
    std::uint32_t radius = 0;
    auto const [end, error] = std::from_chars(radiusText.data(), radiusText.data() + radiusText.size(), radius);
    if (error != std::errc() || end != radiusText.data() + radiusText.size() || radius == 0)
        return std::nullopt;

    return Request{std::string(nonce), std::clamp(radius, MinimumRadius, MaximumRadius)};
}
}

#endif
