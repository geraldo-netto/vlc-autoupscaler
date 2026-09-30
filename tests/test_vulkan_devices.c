// SPDX-License-Identifier: GPL-2.0-or-later
#include "vulkan_devices.h"
#include "test_harness.h"
#include <stddef.h>
#include <stdbool.h>
#include <string.h>

static max_align_t tokens[17];
static unsigned available, destroyed;
static bool fail_create, fail_enumerate, software;

VkResult __wrap_vkCreateInstance(const VkInstanceCreateInfo *info,
                                const VkAllocationCallbacks *allocator, VkInstance *instance)
{
    (void)info; (void)allocator;
    if (fail_create) return VK_ERROR_INITIALIZATION_FAILED;
    *instance = (VkInstance)&tokens[16];
    return VK_SUCCESS;
}

VkResult __wrap_vkEnumeratePhysicalDevices(VkInstance instance, uint32_t *count,
                                          VkPhysicalDevice *devices)
{
    (void)instance;
    if (fail_enumerate) return VK_ERROR_INITIALIZATION_FAILED;
    CHECK(*count >= available);
    *count = available;
    for (unsigned i = 0; i < available; i++) devices[i] = (VkPhysicalDevice)&tokens[i];
    return VK_SUCCESS;
}

void __wrap_vkGetPhysicalDeviceProperties(VkPhysicalDevice device,
                                         VkPhysicalDeviceProperties *properties)
{
    (void)device;
    memset(properties, 0, sizeof(*properties));
    properties->deviceType = software ? VK_PHYSICAL_DEVICE_TYPE_CPU : VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU;
}

void __wrap_vkDestroyInstance(VkInstance instance, const VkAllocationCallbacks *allocator)
{
    (void)instance; (void)allocator;
    destroyed++;
}

static void test_enumeration(void)
{
    BEGIN("REV-11: zero, one and multiple native devices retain enumeration indices");
    unsigned indices[16];
    for (available = 0; available <= 2; available++) {
        destroyed = 0;
        CHECK(up_vk_devices(indices) == (int)available);
        CHECK(destroyed == 1);
        for (unsigned i = 0; i < available; i++) CHECK(indices[i] == i);
    }
    software = true;
    CHECK(up_vk_devices(indices) == 0);
    software = false;
    END();
}

static void test_errors(void)
{
    BEGIN("REV-11: enumeration failures retire native instances");
    unsigned indices[16];
    destroyed = 0;
    fail_create = true;
    CHECK(up_vk_devices(indices) == -1 && destroyed == 0);
    fail_create = false;
    fail_enumerate = true;
    CHECK(up_vk_devices(indices) == -1 && destroyed == 1);
    fail_enumerate = false;
    END();
}

int main(void)
{
    test_enumeration();
    test_errors();
    return test_harness_report();
}
