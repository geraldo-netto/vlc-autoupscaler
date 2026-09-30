// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef UP_VULKAN_IDENTITY_H
#define UP_VULKAN_IDENTITY_H
#include <vulkan/vulkan.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    VkPhysicalDeviceProperties properties;
    VkPhysicalDevicePCIBusInfoPropertiesEXT pci;
    bool has_pci;
} up_vk_identity_t;

static inline bool up_vk_pci_available(VkPhysicalDevice device)
{
    uint32_t count = 256;
    VkExtensionProperties extensions[256];
    if (vkEnumerateDeviceExtensionProperties(device, NULL, &count, extensions) != VK_SUCCESS)
        return false;
    for (uint32_t i = 0; i < count; i++)
        if (!strcmp(extensions[i].extensionName, VK_EXT_PCI_BUS_INFO_EXTENSION_NAME)) return true;
    return false;
}

static inline void up_vk_read_identity(VkPhysicalDevice device, up_vk_identity_t *identity)
{
    identity->has_pci = up_vk_pci_available(device);
    identity->pci = (VkPhysicalDevicePCIBusInfoPropertiesEXT){
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PCI_BUS_INFO_PROPERTIES_EXT};
    VkPhysicalDeviceProperties2 properties = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,
        .pNext = identity->has_pci ? &identity->pci : NULL};
    vkGetPhysicalDeviceProperties2(device, &properties);
    identity->properties = properties.properties;
    identity->properties.deviceName[VK_MAX_PHYSICAL_DEVICE_NAME_SIZE - 1] = '\0';
}

static inline bool up_vk_identity(unsigned index, up_vk_identity_t *identity)
{
    VkInstance instance = VK_NULL_HANDLE;
    VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion = VK_API_VERSION_1_1};
    VkInstanceCreateInfo info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app};
    if (vkCreateInstance(&info, NULL, &instance) != VK_SUCCESS) return false;
    uint32_t count = 16;
    VkPhysicalDevice devices[16];
    bool ok = vkEnumeratePhysicalDevices(instance, &count, devices) == VK_SUCCESS;
    ok = ok && index < count;
    if (ok) up_vk_read_identity(devices[index], identity);
    vkDestroyInstance(instance, NULL);
    return ok;
}
#endif
