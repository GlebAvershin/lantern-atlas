// Exhaustive, independent shortest-solution oracle for authoring and CI (up to 4x4).
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 7) return 2;
    const int width = std::atoi(argv[1]), shutter = std::atoi(argv[2]);
    const int left = std::atoi(argv[3]), right = std::atoi(argv[4]);
    const int state = std::atoi(argv[5]), proposed = std::atoi(argv[6]);
    if (width < 3 || width > 4) return 2;
    const int n = width * width, limit = 1 << n;
    if (state < 0 || state >= limit || proposed < 0 || proposed >= limit ||
        shutter < 0 || shutter >= limit || (proposed & shutter) ||
        !((left == -1 && right == -1) || (left >= 0 && left < n && right >= 0 && right < n && left != right))) return 2;
    std::vector<int> pulse(n), effect(limit), weight(limit);
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            if (std::abs(i / width - j / width) + std::abs(i % width - j % width) <= 1)
                pulse[i] |= 1 << j;
        }
        if (i == left) pulse[i] ^= 1 << right;
        if (i == right) pulse[i] ^= 1 << left;
    }
    int best = n + 1, no_link = n + 1;
    const int relay = left < 0 ? 0 : (1 << left) | (1 << right);
    for (int mask = 0; mask < limit; ++mask) {
        if (mask) {
            const int parent = mask & (mask - 1);
            effect[mask] = effect[parent] ^ pulse[__builtin_ctz(static_cast<unsigned>(mask))];
            weight[mask] = weight[parent] + 1;
        }
        if ((mask & shutter) || effect[mask] != (state ^ (limit - 1))) continue;
        best = std::min(best, weight[mask]);
        if (!(mask & relay)) no_link = std::min(no_link, weight[mask]);
    }
    std::cout << "{\"par\":" << (best > n ? -1 : best)
              << ",\"par_without_relay\":" << (no_link > n ? -1 : no_link)
              << ",\"scrambled\":" << ((limit - 1) ^ effect[proposed]) << "}\n";
}
