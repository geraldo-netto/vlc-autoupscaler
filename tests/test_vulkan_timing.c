// SPDX-License-Identifier: GPL-2.0-or-later
#include "vulkan_timing.h"
#include "test_harness.h"

static void test_wrap(void)
{
    BEGIN("Vulkan timestamps: mask unsupported bits and unsigned rollover");
    CHECK(up_vulkan_elapsed_us(250, 5, 8, 1000) == 11);
    CHECK(up_vulkan_elapsed_us(UINT64_MAX - 4, 5, 64, 1000) == 10);
    CHECK(up_vulkan_elapsed_us(1025, 1035, 8, 500) == 5);
    END();
}

static void test_invalid(void)
{
    BEGIN("Vulkan timestamps: reject absent bits and invalid clock period");
    CHECK(isnan(up_vulkan_elapsed_us(1, 2, 0, 1)));
    CHECK(isnan(up_vulkan_elapsed_us(1, 2, 65, 1)));
    CHECK(isnan(up_vulkan_elapsed_us(1, 2, 64, 0)));
    CHECK(isnan(up_vulkan_elapsed_us(1, 2, 64, INFINITY)));
    END();
}

int main(void)
{
    test_wrap(); test_invalid();
    return test_harness_report();
}
