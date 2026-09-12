// SPDX-License-Identifier: GPL-2.0-or-later
#include "experiment_vulkan.h"
#include "vulkan_limits.h"
#include "vulkan_bench_util.h"
#include "vulkan_timing.h"
#include "vulkan_coefficients.h"
#include "../src/usm.h"
#include <vulkan/vulkan.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    VkBuffer buffer;
    VkDeviceMemory memory;
    void *mapped;
    size_t size;
} gpu_buffer_t;

struct up_vulkan {
    VkInstance instance;
    VkPhysicalDevice physical;
    VkDevice device;
    VkQueue queue;
    uint32_t family;
    VkDescriptorSetLayout descriptors;
    VkDescriptorPool descriptor_pool;
    VkDescriptorSet descriptor[3];
    VkPipelineLayout layout;
    VkShaderModule shader[3];
    VkPipeline pipeline[3];
    VkCommandPool commands;
    VkCommandBuffer command;
    VkFence fence;
    gpu_buffer_t buffers[7];
    unsigned passes;
    unsigned inputs[3], outputs[3];
    size_t invocations[3];
    VkQueryPool queries;
    uint32_t timestamp_bits;
    float timestamp_period;
    bool timing;
    bool direct;
    bool coefficients;
    bool fused;
    bool omit_readback;
    up_vulkan_profile_t profile;
    size_t bytes;
    size_t input_bytes, output_bytes;
    int width, height;
    int src_width, src_height;
    int recorded_amount;
    char name[VK_MAX_PHYSICAL_DEVICE_NAME_SIZE];
};

static int checked(VkResult result, const char *operation)
{
    if (result == VK_SUCCESS) return 0;
    fprintf(stderr, "%s failed: VkResult=%d\n", operation, result);
    return -1;
}

static int select_device(up_vulkan_t *c, unsigned index)
{
    VkInstanceCreateInfo info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    if (checked(vkCreateInstance(&info, NULL, &c->instance), "instance")) return -1;
    uint32_t count = 16;
    VkPhysicalDevice devices[16];
    if (checked(vkEnumeratePhysicalDevices(c->instance, &count, devices), "devices")) return -1;
    if (index >= count) return -1;
    c->physical = devices[index];
    VkPhysicalDeviceProperties properties;
    vkGetPhysicalDeviceProperties(c->physical, &properties);
    if (properties.deviceType == VK_PHYSICAL_DEVICE_TYPE_CPU) return -1;
    c->timestamp_period = properties.limits.timestampPeriod;
    memcpy(c->name, properties.deviceName, sizeof(c->name));
    c->name[sizeof(c->name) - 1] = '\0';
    return 0;
}

static int create_device(up_vulkan_t *c)
{
    uint32_t count = 32;
    VkQueueFamilyProperties families[32];
    vkGetPhysicalDeviceQueueFamilyProperties(c->physical, &count, families);
    c->family = count;
    for (uint32_t i = 0; i < count; i++) {
        if (families[i].queueFlags & VK_QUEUE_COMPUTE_BIT) { c->family = i; break; }
    }
    if (c->family == count) return -1;
    c->timestamp_bits = families[c->family].timestampValidBits;
    float priority = 1;
    VkDeviceQueueCreateInfo queue = {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = c->family, .queueCount = 1, .pQueuePriorities = &priority};
    VkDeviceCreateInfo info = {.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &queue};
    if (checked(vkCreateDevice(c->physical, &info, NULL, &c->device), "device")) return -1;
    vkGetDeviceQueue(c->device, c->family, 0, &c->queue);
    return 0;
}

static uint32_t memory_type(up_vulkan_t *c, uint32_t bits, VkMemoryPropertyFlags flags)
{
    VkPhysicalDeviceMemoryProperties properties;
    vkGetPhysicalDeviceMemoryProperties(c->physical, &properties);
    for (uint32_t i = 0; i < properties.memoryTypeCount; i++) {
        if ((bits & (1u << i)) && (properties.memoryTypes[i].propertyFlags & flags) == flags)
            return i;
    }
    return UINT32_MAX;
}

static int create_buffer_storage(up_vulkan_t *c, gpu_buffer_t *b, bool host)
{
    VkBufferCreateInfo info = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = b->size, .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT
            | VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT};
    if (checked(vkCreateBuffer(c->device, &info, NULL, &b->buffer), "buffer")) return -1;
    VkMemoryRequirements needs;
    vkGetBufferMemoryRequirements(c->device, b->buffer, &needs);
    VkMemoryPropertyFlags flags = host
        ? VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT
        : VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;
    uint32_t type = memory_type(c, needs.memoryTypeBits,
                               flags | (host ? VK_MEMORY_PROPERTY_HOST_CACHED_BIT : 0));
    if (type == UINT32_MAX) type = memory_type(c, needs.memoryTypeBits, flags);
    if (type == UINT32_MAX) return -1;
    VkMemoryAllocateInfo allocation = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = needs.size, .memoryTypeIndex = type};
    if (checked(vkAllocateMemory(c->device, &allocation, NULL, &b->memory), "memory")) return -1;
    if (checked(vkBindBufferMemory(c->device, b->buffer, b->memory, 0), "bind")) return -1;
    if (host) return checked(vkMapMemory(c->device, b->memory, 0, b->size, 0, &b->mapped), "map");
    return 0;
}

static int create_buffer(up_vulkan_t *c, unsigned index)
{
    bool host = index < 2 || index == 6 || (c->direct && index < 4);
    return create_buffer_storage(c, &c->buffers[index], host);
}

static int create_descriptors(up_vulkan_t *c)
{
    VkDescriptorSetLayoutBinding bindings[3] = {
        {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
         .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
         .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 2, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
         .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo layout = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount = 3, .pBindings = bindings};
    if (checked(vkCreateDescriptorSetLayout(c->device, &layout, NULL, &c->descriptors), "descriptors")) return -1;
    VkDescriptorPoolSize size = {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 3 * c->passes};
    VkDescriptorPoolCreateInfo pool = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .maxSets = c->passes, .poolSizeCount = 1, .pPoolSizes = &size};
    if (checked(vkCreateDescriptorPool(c->device, &pool, NULL, &c->descriptor_pool), "descriptor pool")) return -1;
    VkDescriptorSetLayout layouts[3] = {c->descriptors, c->descriptors, c->descriptors};
    VkDescriptorSetAllocateInfo allocate = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
        .descriptorPool = c->descriptor_pool, .descriptorSetCount = c->passes, .pSetLayouts = layouts};
    return checked(vkAllocateDescriptorSets(c->device, &allocate, c->descriptor), "descriptor set");
}

static void bind_buffers(up_vulkan_t *c, unsigned pass)
{
    unsigned indices[] = {c->inputs[pass], c->outputs[pass], 6};
    VkDescriptorBufferInfo buffers[3];
    VkWriteDescriptorSet writes[3];
    for (unsigned i = 0; i < 3; i++) {
        gpu_buffer_t *b = &c->buffers[indices[i]];
        buffers[i] = (VkDescriptorBufferInfo){b->buffer, 0, b->size};
        writes[i] = (VkWriteDescriptorSet){.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
            .dstSet = c->descriptor[pass], .dstBinding = i, .descriptorCount = 1,
            .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .pBufferInfo = &buffers[i]};
    }
    vkUpdateDescriptorSets(c->device, 3, writes, 0, NULL);
}

static bool shader_size_valid(size_t size)
{
    return size >= 20 && size % 4 == 0;
}

static int load_shader(up_vulkan_t *c, const char *path, unsigned pass)
{
    FILE *file = fopen(path, "rb");
    if (!file) return -1;
    uint32_t *code = malloc(1024 * 1024);
    if (!code) { fclose(file); return -1; }
    size_t size = fread(code, 1, 1024 * 1024, file);
    int failed = ferror(file) || !shader_size_valid(size) || !feof(file);
    if (fclose(file)) failed = 1;
    VkShaderModuleCreateInfo info = {.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = size, .pCode = code};
    if (!failed) failed = checked(vkCreateShaderModule(c->device, &info, NULL, &c->shader[pass]), "shader");
    free(code);
    return failed ? -1 : 0;
}

static int create_layout(up_vulkan_t *c)
{
    VkPushConstantRange range = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 6 * sizeof(int32_t)};
    VkPipelineLayoutCreateInfo layout = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 1, .pSetLayouts = &c->descriptors,
        .pushConstantRangeCount = 1, .pPushConstantRanges = &range};
    return checked(vkCreatePipelineLayout(c->device, &layout, NULL, &c->layout), "pipeline layout");
}

static int create_pipeline(up_vulkan_t *c, unsigned pass)
{
    int32_t values[] = {c->width, c->height, c->src_width, c->src_height,
                        (int32_t)pass + (c->coefficients ? 16 : 0)};
    VkSpecializationMapEntry entries[5];
    for (uint32_t i = 0; i < 5; i++)
        entries[i] = (VkSpecializationMapEntry){i, i * sizeof(int32_t), sizeof(int32_t)};
    VkSpecializationInfo specialization = {.mapEntryCount = 5, .pMapEntries = entries,
        .dataSize = sizeof(values), .pData = values};
    VkComputePipelineCreateInfo info = {.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
        .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = c->shader[pass], .pName = "main",
            .pSpecializationInfo = &specialization},
        .layout = c->layout};
    return checked(vkCreateComputePipelines(c->device, VK_NULL_HANDLE, 1, &info, NULL, &c->pipeline[pass]), "pipeline");
}

static int create_commands(up_vulkan_t *c)
{
    VkCommandPoolCreateInfo pool = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, .queueFamilyIndex = c->family};
    if (checked(vkCreateCommandPool(c->device, &pool, NULL, &c->commands), "command pool")) return -1;
    VkCommandBufferAllocateInfo allocate = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = c->commands, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1};
    if (checked(vkAllocateCommandBuffers(c->device, &allocate, &c->command), "commands")) return -1;
    VkFenceCreateInfo fence = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    return checked(vkCreateFence(c->device, &fence, NULL, &c->fence), "fence");
}

static int initialize_pipelines(up_vulkan_t *c, const char *const *shaders)
{
    if (create_descriptors(c) || create_layout(c) || create_commands(c)) return -1;
    for (unsigned i = 0; i < c->passes; i++) {
        if (load_shader(c, shaders[i], i) || create_pipeline(c, i)) return -1;
        bind_buffers(c, i);
    }
    return 0;
}

static int initialize(up_vulkan_t *c, const char *const *shaders, unsigned index)
{
    if (select_device(c, index) || create_device(c)) return -1;
    for (unsigned i = 0; i < 7; i++) {
        if (c->buffers[i].size && create_buffer(c, i)) return -1;
    }
    return initialize_pipelines(c, shaders);
}

static void single_pass(up_vulkan_t *c)
{
    c->passes = 1;
    c->inputs[0] = 2; c->outputs[0] = 3;
    c->invocations[0] = c->bytes / 4;
    for (unsigned i = 0; i < 4; i++) c->buffers[i].size = c->bytes;
    c->buffers[6].size = 8;
}

up_vulkan_t *up_vulkan_create(const char *shader, unsigned index, int width, int height)
{
    if (!shader || !up_vulkan_shape_supported(width, height)) return NULL;
    up_vulkan_t *c = calloc(1, sizeof(*c));
    if (!c) return NULL;
    c->width = width; c->height = height;
    c->recorded_amount = -1;
    c->bytes = ((size_t)width * (size_t)height + 3) & ~(size_t)3;
    c->input_bytes = c->output_bytes = (size_t)width * (size_t)height;
    single_pass(c);
    if (initialize(c, &shader, index)) goto fail;
    return c;
fail:
    up_vulkan_destroy(c);
    return NULL;
}

static bool scale_dimensions(int sw, int sh, int dw, int dh)
{
    if (sw < 2 || sh < 2 || dw < sw || dh < sh) return false;
    return up_vulkan_shape_supported(dw, dh) && (sw | sh | dw | dh) % 2 == 0;
}

up_vulkan_t *up_vulkan_create_scale(const char *shader, unsigned index,
                                    int sw, int sh, int dw, int dh)
{
    if (!shader || !scale_dimensions(sw, sh, dw, dh)) return NULL;
    up_vulkan_t *c = calloc(1, sizeof(*c));
    if (!c) return NULL;
    c->width = dw; c->height = dh;
    c->src_width = sw; c->src_height = sh;
    c->recorded_amount = -1;
    c->input_bytes = (size_t)sw * (size_t)sh * 3 / 2;
    c->output_bytes = (size_t)dw * (size_t)dh * 3 / 2;
    c->bytes = (c->output_bytes + 3) & ~(size_t)3;
    single_pass(c);
    if (initialize(c, &shader, index)) {
        up_vulkan_destroy(c);
        return NULL;
    }
    return c;
}

static void barrier(up_vulkan_t *c, VkPipelineStageFlags before, VkAccessFlags source,
                    VkPipelineStageFlags after, VkAccessFlags destination)
{
    VkMemoryBarrier memory = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,
        .srcAccessMask = source, .dstAccessMask = destination};
    vkCmdPipelineBarrier(c->command, before, after, 0, 1, &memory, 0, NULL, 0, NULL);
}

static void separable_passes(up_vulkan_t *c, bool sharpen)
{
    c->passes = sharpen ? 3 : 2;
    c->inputs[0] = 2; c->outputs[0] = 4;
    c->inputs[1] = 4; c->outputs[1] = sharpen ? 5 : 3;
    c->inputs[2] = 5; c->outputs[2] = 3;
    size_t intermediate = (size_t)c->width * (size_t)c->src_height * 3 / 2;
    c->buffers[4].size = intermediate * sizeof(float);
    if (sharpen) c->buffers[5].size = c->bytes;
    c->invocations[0] = intermediate;
    c->invocations[1] = c->invocations[2] = c->bytes / 4;
    c->buffers[6].size = (size_t)(c->width + c->height) * 9 * sizeof(up_vulkan_coefficient_t);
}

static void fill_coefficients(up_vulkan_t *c)
{
    up_vulkan_coefficient_t *table = c->buffers[6].mapped;
    const int src[] = {c->src_width, c->src_width / 2, c->src_height, c->src_height / 2};
    const int dst[] = {c->width, c->width / 2, c->height, c->height / 2};
    for (unsigned axis = 0; axis < 4; axis++) {
        up_vulkan_coefficients(table, src[axis], dst[axis]);
        table += dst[axis] * 6;
    }
}

static bool fused_supported(const up_vulkan_scale_options_t *options, int width)
{
    return options->fused_shader && options->usm && width % 8 == 0;
}

up_vulkan_t *up_vulkan_create_separable(const up_vulkan_scale_options_t *options,
                                        unsigned index, int sw, int sh, int dw, int dh)
{
    if (!options || !options->horizontal || !options->vertical) return NULL;
    if (!scale_dimensions(sw, sh, dw, dh)) return NULL;
    up_vulkan_t *c = calloc(1, sizeof(*c));
    if (!c) return NULL;
    c->width = dw; c->height = dh;
    c->src_width = sw; c->src_height = sh;
    c->input_bytes = (size_t)sw * (size_t)sh * 3 / 2;
    c->output_bytes = (size_t)dw * (size_t)dh * 3 / 2;
    c->bytes = (c->output_bytes + 3) & ~(size_t)3;
    c->recorded_amount = -1;
    c->direct = options->direct;
    c->fused = fused_supported(options, dw);
    c->coefficients = options->coefficients;
    single_pass(c);
    separable_passes(c, options->usm != NULL && !c->fused);
    const char *shaders[] = {options->horizontal,
        c->fused ? options->fused_shader : options->vertical, options->usm};
    if (initialize(c, shaders, index)) { up_vulkan_destroy(c); return NULL; }
    fill_coefficients(c);
    return c;
}

static void stamp(up_vulkan_t *c, unsigned query, VkPipelineStageFlagBits stage)
{
    if (c->timing) vkCmdWriteTimestamp(c->command, stage, c->queries, query);
}

static void dispatch_groups(up_vulkan_t *c, unsigned pass)
{
    if (c->fused && pass == 1) {
        uint32_t rows = (uint32_t)((c->height + 3) / 4 + 2 * ((c->height / 2 + 3) / 4));
        vkCmdDispatch(c->command, (uint32_t)((c->width + 63) / 64), rows, 1);
        return;
    }
    uint32_t groups = (uint32_t)((c->invocations[pass] + 63) / 64);
    uint32_t x = groups < 65535 ? groups : 65535;
    vkCmdDispatch(c->command, x, (groups + x - 1) / x, 1);
}

static void dispatch(up_vulkan_t *c, unsigned pass, int amount)
{
    vkCmdBindPipeline(c->command, VK_PIPELINE_BIND_POINT_COMPUTE, c->pipeline[pass]);
    vkCmdBindDescriptorSets(c->command, VK_PIPELINE_BIND_POINT_COMPUTE, c->layout,
                           0, 1, &c->descriptor[pass], 0, NULL);
    int32_t shape[] = {c->width, c->height, amount, c->src_width, c->src_height,
                       (int32_t)pass + (c->coefficients ? 16 : 0)};
    vkCmdPushConstants(c->command, c->layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(shape), shape);
    dispatch_groups(c, pass);
    barrier(c, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_ACCESS_SHADER_WRITE_BIT,
            VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT | VK_PIPELINE_STAGE_TRANSFER_BIT,
            VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_TRANSFER_READ_BIT);
    stamp(c, pass + 2, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT);
}

static void record_upload(up_vulkan_t *c)
{
    if (!c->direct) {
        VkBufferCopy copy = {.size = (c->input_bytes + 3) & ~(size_t)3};
        vkCmdCopyBuffer(c->command, c->buffers[0].buffer, c->buffers[2].buffer, 1, &copy);
        barrier(c, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_WRITE_BIT,
                VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_ACCESS_SHADER_READ_BIT);
    }
    stamp(c, 1, VK_PIPELINE_STAGE_TRANSFER_BIT);
}

static void record_download(up_vulkan_t *c)
{
    if (c->omit_readback) {
        stamp(c, c->passes + 2, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT);
        return;
    }
    if (!c->direct) {
        VkBufferCopy copy = {.size = c->bytes};
        vkCmdCopyBuffer(c->command, c->buffers[3].buffer, c->buffers[1].buffer, 1, &copy);
        barrier(c, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_WRITE_BIT,
                VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_READ_BIT);
    } else {
        barrier(c, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_ACCESS_SHADER_WRITE_BIT,
                VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_READ_BIT);
    }
    stamp(c, c->passes + 2, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT);
}

static int record(up_vulkan_t *c, int amount)
{
    amount = up_usm__clamp_amount_q8(amount);
    if (c->recorded_amount == amount) return 0;
    if (checked(vkResetCommandBuffer(c->command, 0), "reset command")) return -1;
    VkCommandBufferBeginInfo begin = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    if (checked(vkBeginCommandBuffer(c->command, &begin), "begin")) return -1;
    if (c->timing) vkCmdResetQueryPool(c->command, c->queries, 0, c->passes + 3);
    stamp(c, 0, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT);
    record_upload(c);
    for (unsigned i = 0; i < c->passes; i++) dispatch(c, i, amount);
    record_download(c);
    if (checked(vkEndCommandBuffer(c->command), "end")) return -1;
    c->recorded_amount = amount;
    return 0;
}

static int submit(up_vulkan_t *c)
{
    if (checked(vkResetFences(c->device, 1, &c->fence), "reset fence")) return -1;
    VkSubmitInfo info = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
        .commandBufferCount = 1, .pCommandBuffers = &c->command};
    if (checked(vkQueueSubmit(c->queue, 1, &info, c->fence), "submit")) return -1;
    return checked(vkWaitForFences(c->device, 1, &c->fence, VK_TRUE, UINT64_MAX), "wait");
}

static int profile_queries(up_vulkan_t *c)
{
    uint64_t values[6];
    unsigned count = c->passes + 3;
    if (checked(vkGetQueryPoolResults(c->device, c->queries, 0, count, sizeof(values),
            values, sizeof(values[0]), VK_QUERY_RESULT_64_BIT), "timestamps")) return -1;
    for (unsigned i = 0; i + 1 < count; i++)
        c->profile.gpu_us[i] = up_vulkan_elapsed_us(values[i], values[i + 1],
                                                  c->timestamp_bits, c->timestamp_period);
    c->profile.passes = c->passes;
    return 0;
}

static double clock_us(up_vulkan_t *c)
{
    return c->timing ? up_vulkan_bench_now_us(CLOCK_MONOTONIC) : 0;
}

static void download(up_vulkan_t *c, uint8_t *output)
{
    if (c->omit_readback) return;
    memcpy(output, c->buffers[c->direct ? 3 : 1].mapped, c->output_bytes);
}

int up_vulkan_apply(up_vulkan_t *c, const uint8_t *input, uint8_t *output, int amount)
{
    if (!c || !input) return -1;
    if (!output && !c->omit_readback) return -1;
    double start = clock_us(c);
    void *upload = c->buffers[c->direct ? 2 : 0].mapped;
    memcpy(upload, input, c->input_bytes);
    size_t padding = ((c->input_bytes + 3) & ~(size_t)3) - c->input_bytes;
    memset((uint8_t *)upload + c->input_bytes, 0, padding);
    double copied = clock_us(c);
    if (record(c, amount) || submit(c)) return -1;
    double waited = clock_us(c);
    download(c, output);
    c->profile.host_upload_us = copied - start;
    c->profile.submit_wait_us = waited - copied;
    c->profile.host_download_us = clock_us(c) - waited;
    return c->timing ? profile_queries(c) : 0;
}

int up_vulkan_enable_timing(up_vulkan_t *c, bool enabled)
{
    if (!c) return -1;
    if (enabled && !c->timestamp_bits) return -1;
    if (enabled && !c->queries) {
        VkQueryPoolCreateInfo info = {.sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
            .queryType = VK_QUERY_TYPE_TIMESTAMP, .queryCount = 6};
        if (checked(vkCreateQueryPool(c->device, &info, NULL, &c->queries), "queries")) return -1;
    }
    c->timing = enabled;
    c->recorded_amount = -1;
    return 0;
}

up_vulkan_profile_t up_vulkan_profile(const up_vulkan_t *c) { return c->profile; }

void up_vulkan_readback(up_vulkan_t *c, bool enabled)
{
    c->omit_readback = !enabled;
    c->recorded_amount = -1;
}

static void destroy_buffers(up_vulkan_t *c)
{
    for (unsigned i = 0; i < 7; i++) {
        gpu_buffer_t *b = &c->buffers[i];
        if (b->mapped) vkUnmapMemory(c->device, b->memory);
        vkDestroyBuffer(c->device, b->buffer, NULL);
        vkFreeMemory(c->device, b->memory, NULL);
    }
}

void up_vulkan_destroy(up_vulkan_t *c)
{
    if (!c) return;
    if (c->device) {
        (void)checked(vkDeviceWaitIdle(c->device), "idle before cleanup");
        vkDestroyFence(c->device, c->fence, NULL);
        vkDestroyCommandPool(c->device, c->commands, NULL);
        vkDestroyQueryPool(c->device, c->queries, NULL);
        for (unsigned i = 0; i < c->passes; i++) {
            vkDestroyPipeline(c->device, c->pipeline[i], NULL);
            vkDestroyShaderModule(c->device, c->shader[i], NULL);
        }
        vkDestroyPipelineLayout(c->device, c->layout, NULL);
        vkDestroyDescriptorPool(c->device, c->descriptor_pool, NULL);
        vkDestroyDescriptorSetLayout(c->device, c->descriptors, NULL);
        destroy_buffers(c);
        vkDestroyDevice(c->device, NULL);
    }
    vkDestroyInstance(c->instance, NULL);
    free(c);
}

const char *up_vulkan_device(const up_vulkan_t *c) { return c->name; }
