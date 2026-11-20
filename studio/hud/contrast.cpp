// Read opaque sRGB foreground/background pairs from a rendered HUD.
#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <string>

using Channels = std::array<double, 3>;

double luminance(Channels channels) {
    std::ranges::transform(channels, channels.begin(), [](double channel) {
        double s = channel / 255.0;
        return s <= 0.04045 ? s / 12.92 : std::pow((s + 0.055) / 1.055, 2.4);
    });
    constexpr Channels weights{0.2126, 0.7152, 0.0722};
    return std::inner_product(channels.begin(), channels.end(), weights.begin(), 0.0);
}

int main() {
    std::string label;
    unsigned samples = 0;
    bool passed = true;
    while (std::cin >> label) {
        Channels fg{}, bg{};
        for (Channels* triplet : {&fg, &bg}) {
            for (auto& channel : *triplet) {
                if (!(std::cin >> channel) || !std::isfinite(channel) || channel < 0 || channel > 255) return 2;
            }
        }
        const double first = luminance(fg), second = luminance(bg);
        const double ratio = (std::max(first, second) + 0.05) / (std::min(first, second) + 0.05);
        passed &= ratio >= 4.5;
        std::cout << label << ' ' << std::fixed << std::setprecision(4) << ratio << '\n';
        ++samples;
    }
    if (!samples) return 2;
    return passed ? 0 : 1;
}
