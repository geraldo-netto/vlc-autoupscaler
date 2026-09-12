// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef UP_VULKAN_COEFFICIENTS_H
#define UP_VULKAN_COEFFICIENTS_H
#include <math.h>
#include <stdint.h>
#include <stddef.h>

typedef struct { int32_t index; float weight; } up_vulkan_coefficient_t;
_Static_assert(sizeof(up_vulkan_coefficient_t) == 8, "std430 coefficient stride");
_Static_assert(offsetof(up_vulkan_coefficient_t, weight) == 4, "std430 weight offset");

static inline double up_vulkan_spline(double x)
{
    x = fabs(x);
    if (x < 1) return 1 + x * (-3.0 / 209 + x * (-453.0 / 209 + x * 13.0 / 11));
    if (x < 2) { x -= 1; return x * (-156.0 / 209 + x * (270.0 / 209 - x * 6.0 / 11)); }
    if (x < 3) { x -= 2; return x * (26.0 / 209 + x * (-45.0 / 209 + x / 11)); }
    return 0;
}

static inline int up_vulkan_mirror(int x, int size)
{
    if (x < 0) x = -x - 1;
    if (x >= size) x = 2 * size - x - 1;
    if (x < 0) return 0;
    return x < size ? x : size - 1;
}

static inline void up_vulkan_coefficients(up_vulkan_coefficient_t *table, int src, int dst)
{
    for (int x = 0; x < dst; x++) {
        double position = ((double)x + .5) * src / dst - .5;
        int start = (int)floor(position) - 2;
        double total = 0, weights[6];
        for (int tap = 0; tap < 6; tap++) {
            weights[tap] = up_vulkan_spline((double)(start + tap) - position);
            total += weights[tap];
        }
        for (int tap = 0; tap < 6; tap++) {
            table[x * 6 + tap].index = up_vulkan_mirror(start + tap, src);
            table[x * 6 + tap].weight = (float)(weights[tap] / total);
        }
    }
}
#endif
