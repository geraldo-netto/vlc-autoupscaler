// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef UP_VULKAN_DEVICES_H
#define UP_VULKAN_DEVICES_H
#include <vulkan/vulkan.h>

static inline int up_vk_devices(unsigned indices[16])
{
    VkInstance instance = VK_NULL_HANDLE;
    VkInstanceCreateInfo info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    if (vkCreateInstance(&info, NULL, &instance) != VK_SUCCESS) return -1;
    uint32_t count = 16;
    VkPhysicalDevice devices[16];
    VkResult result = vkEnumeratePhysicalDevices(instance, &count, devices);
    int used = 0;
    if (result == VK_SUCCESS) {
        for (uint32_t i = 0; i < count; i++) {
            VkPhysicalDeviceProperties properties;
            vkGetPhysicalDeviceProperties(devices[i], &properties);
            if (properties.deviceType != VK_PHYSICAL_DEVICE_TYPE_CPU)
                indices[used++] = i;
        }
    }
    vkDestroyInstance(instance, NULL);
    return result == VK_SUCCESS ? used : -1;
}
#endif
