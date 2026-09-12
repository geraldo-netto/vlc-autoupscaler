// SPDX-License-Identifier: GPL-2.0-or-later
#include "vulkan_limits.h"
#include "test_harness.h"
#include <limits.h>

static void test_valid(void)
{
    BEGIN("Vulkan prototype accepts tiny, odd and 4K geometry");
    CHECK(up_vulkan_shape_supported(1, 1));
    CHECK(up_vulkan_shape_supported(17, 9));
    CHECK(up_vulkan_shape_supported(3840, 2160));
    END();
}

static void test_limits(void)
{
    BEGIN("BUILD-43: accepted I420 geometry fits one portable Vulkan dispatch");
    CHECK(!up_vulkan_shape_supported(0, 1));
    CHECK(!up_vulkan_shape_supported(1, -1));
    CHECK(!up_vulkan_shape_supported(INT_MAX, INT_MAX));
    CHECK(!up_vulkan_shape_supported(4096, 4096));
    CHECK(!up_vulkan_shape_supported(3840, 2161));
    CHECK(((size_t)3840 * 2160 * 3 / 2 + 255) / 256 <= 65535);
    END();
}

int main(void)
{
    test_valid();
    test_limits();
    return test_harness_report();
}
