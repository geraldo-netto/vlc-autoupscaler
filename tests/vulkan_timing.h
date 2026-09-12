// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef UP_VULKAN_TIMING_H
#define UP_VULKAN_TIMING_H
#include <stdint.h>
#include <math.h>

static inline double up_vulkan_elapsed_us(uint64_t start, uint64_t end,
                                          unsigned bits, double period_ns)
{
    if (!bits || bits > 64 || !isfinite(period_ns) || period_ns <= 0) return NAN;
    uint64_t mask = bits == 64 ? UINT64_MAX : (UINT64_C(1) << bits) - 1;
    return (double)((end - start) & mask) * period_ns / 1000;
}
#endif
