#include <vulkan/vulkan.h>
int main(void) {
    VkInstance instance;
    VkInstanceCreateInfo info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    if (vkCreateInstance(&info, 0, &instance)) return 1;
    uint32_t count = 0;
    VkResult result = vkEnumeratePhysicalDevices(instance, &count, 0);
    vkDestroyInstance(instance, 0);
    return result != VK_SUCCESS;
}
