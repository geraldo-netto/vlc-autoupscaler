// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef UP_VULKAN_BENCH_UTIL_H
#define UP_VULKAN_BENCH_UTIL_H
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static inline bool up_vulkan_bench_mode_valid(const char *mode)
{
    return strcmp(mode, "cpu") == 0 || strcmp(mode, "gpu") == 0;
}

static inline double up_vulkan_bench_now_us(clockid_t clock)
{
    struct timespec time;
    if (clock_gettime(clock, &time)) { perror("clock_gettime"); exit(1); }
    return (double)time.tv_sec * 1e6 + (double)time.tv_nsec / 1000;
}
#endif
