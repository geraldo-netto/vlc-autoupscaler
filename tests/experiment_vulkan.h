// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef UP_EXPERIMENT_VULKAN_H
#define UP_EXPERIMENT_VULKAN_H
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

typedef struct up_vulkan up_vulkan_t;
typedef struct {
    double host_upload_us, submit_wait_us, host_download_us;
    double gpu_us[5];
    unsigned passes;
} up_vulkan_profile_t;
typedef struct {
    const char *horizontal, *vertical, *usm, *fused_shader;
    bool direct, coefficients;
} up_vulkan_scale_options_t;
up_vulkan_t *up_vulkan_create(const char *shader, unsigned device,
                              int width, int height);
up_vulkan_t *up_vulkan_create_scale(const char *shader, unsigned device,
                                    int src_width, int src_height,
                                    int dst_width, int dst_height);
up_vulkan_t *up_vulkan_create_separable(const up_vulkan_scale_options_t *options,
                                        unsigned device, int sw, int sh, int dw, int dh);
int up_vulkan_enable_timing(up_vulkan_t *ctx, bool enabled);
void up_vulkan_readback(up_vulkan_t *ctx, bool enabled);
up_vulkan_profile_t up_vulkan_profile(const up_vulkan_t *ctx);
int up_vulkan_apply(up_vulkan_t *ctx, const uint8_t *input, uint8_t *output,
                    int amount_q8);
void up_vulkan_destroy(up_vulkan_t *ctx);
const char *up_vulkan_device(const up_vulkan_t *ctx);
#endif
