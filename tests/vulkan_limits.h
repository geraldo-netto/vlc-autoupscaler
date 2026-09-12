// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef UP_VULKAN_LIMITS_H
#define UP_VULKAN_LIMITS_H
#include <stdbool.h>
#include <stddef.h>

static inline bool up_vulkan_shape_supported(int width, int height)
{
    if (width < 1 || height < 1 || width > 4096 || height > 4096) return false;
    return (size_t)width * (size_t)height <= (size_t)3840 * 2160;
}
#endif
