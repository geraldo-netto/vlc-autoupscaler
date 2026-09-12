// SPDX-License-Identifier: GPL-2.0-or-later
#include "experiment_vulkan.h"
#include "usm_reference.h"
#include "prng.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    int sw, sh, dw, dh;
    size_t input_size, output_size;
    uint8_t *input, *output, *reference, *scaled, *workspace;
    up_vulkan_t *scale, *combined;
} fixture_t;

static double kernel(double x)
{
    x = fabs(x);
    if (x < 1) return 1 + x * (-3.0 / 209 + x * (-453.0 / 209 + x * 13.0 / 11));
    if (x < 2) { x -= 1; return x * (-156.0 / 209 + x * (270.0 / 209 - x * 6.0 / 11)); }
    if (x < 3) { x -= 2; return x * (26.0 / 209 + x * (-45.0 / 209 + x / 11)); }
    return 0;
}

static int mirror(int x, int size)
{
    if (x < 0) x = -x - 1;
    if (x >= size) x = 2 * size - x - 1;
    if (x < 0) return 0;
    return x < size ? x : size - 1;
}

static double horizontal(const uint8_t *row, int width, double position)
{
    int first = (int)floor(position) - 2;
    double value = 0, total = 0;
    for (int tap = 0; tap < 6; tap++) {
        double weight = kernel((double)(first + tap) - position);
        value += weight * row[mirror(first + tap, width)]; total += weight;
    }
    return value / total;
}

static uint8_t reference_pixel(const uint8_t *input, int sw, int sh, double x, double y)
{
    int first = (int)floor(y) - 2;
    double value = 0, total = 0;
    for (int tap = 0; tap < 6; tap++) {
        double weight = kernel((double)(first + tap) - y);
        const uint8_t *row = input + (size_t)mirror(first + tap, sh) * (size_t)sw;
        value += weight * horizontal(row, sw, x); total += weight;
    }
    value = floor(value / total + .5);
    if (value < 0) value = 0;
    if (value > 255) value = 255;
    return (uint8_t)value;
}

static void reference_plane(const uint8_t *input, uint8_t *output, int sw, int sh, int dw, int dh)
{
    for (int y = 0; y < dh; y++) {
        for (int x = 0; x < dw; x++) {
            double px = ((double)x + .5) * sw / dw - .5;
            double py = ((double)y + .5) * sh / dh - .5;
            output[(size_t)y * (size_t)dw + (size_t)x] = reference_pixel(input, sw, sh, px, py);
        }
    }
}

static void reference(fixture_t *f)
{
    if (f->sw == f->dw && f->sh == f->dh) {
        memcpy(f->reference, f->input, f->input_size);
        return;
    }
    const uint8_t *input = f->input;
    uint8_t *output = f->reference;
    for (int plane = 0; plane < 3; plane++) {
        int divisor = plane ? 2 : 1;
        int sw = f->sw / divisor, sh = f->sh / divisor;
        int dw = f->dw / divisor, dh = f->dh / divisor;
        reference_plane(input, output, sw, sh, dw, dh);
        input += (size_t)sw * (size_t)sh;
        output += (size_t)dw * (size_t)dh;
    }
}

static void cleanup(fixture_t *f)
{
    up_vulkan_destroy(f->scale); up_vulkan_destroy(f->combined);
    free(f->input); free(f->output); free(f->reference); free(f->scaled); free(f->workspace);
}

static bool setup(fixture_t *f, unsigned device, const char *separable, const char *usm, const char *fused, unsigned mode)
{
    f->input_size = (size_t)f->sw * (size_t)f->sh * 3 / 2;
    f->output_size = (size_t)f->dw * (size_t)f->dh * 3 / 2;
    f->input = malloc(f->input_size); f->output = malloc(f->output_size);
    f->reference = malloc(f->output_size); f->scaled = malloc(f->output_size);
    f->workspace = malloc(f->output_size);
    up_vulkan_scale_options_t options = {.horizontal = separable, .vertical = separable, .direct = (mode & 1) != 0, .coefficients = (mode & 2) != 0, .fused_shader = mode & 4 ? fused : NULL};
    f->scale = up_vulkan_create_separable(&options, device, f->sw, f->sh, f->dw, f->dh);
    options.usm = usm;
    f->combined = up_vulkan_create_separable(&options, device, f->sw, f->sh, f->dw, f->dh);
    return f->input && f->output && f->reference && f->scaled && f->workspace && f->scale && f->combined;
}

static void fill(fixture_t *f, unsigned pattern)
{
    uint32_t seed = 12345678;
    for (size_t i = 0; i < f->input_size; i++) {
        if (pattern == 0) f->input[i] = 127;
        else if (pattern == 1) f->input[i] = (uint8_t)up_xs32(&seed);
        else f->input[i] = i % 3 ? 0 : 255;
    }
}

static bool within_one(const fixture_t *f)
{
    for (size_t i = 0; i < f->output_size; i++) {
        int delta = abs((int)f->reference[i] - f->scaled[i]);
        if (delta > 1) {
            fprintf(stderr, "oracle mismatch at %zu: CPU=%u GPU=%u\n", i, f->reference[i], f->scaled[i]);
            return false;
        }
    }
    return true;
}

static bool check_amount(fixture_t *f, int amount)
{
    memcpy(f->reference, f->scaled, f->output_size);
    up_usm_plane_io_t io = {f->reference, f->dw, f->scaled, f->dw, f->dw, f->dh};
    if (!up_usm_apply_plane(&io, amount, f->workspace)) return false;
    if (up_vulkan_apply(f->combined, f->input, f->output, amount)) return false;
    return memcmp(f->reference, f->output, f->output_size) == 0;
}

static bool check_pattern(fixture_t *f, unsigned pattern)
{
    fill(f, pattern);
    reference(f);
    if (up_vulkan_apply(f->scale, f->input, f->scaled, 0)) return false;
    if (!within_one(f)) return false;
    static const int amounts[] = {-1, 0, 1, 51, 256, 512, 4096, 5000};
    for (unsigned a = 0; a < sizeof(amounts) / sizeof(amounts[0]); a++)
        if (!check_amount(f, amounts[a])) return false;
    return true;
}

static bool check_readback_contract(fixture_t *f)
{
    if (up_vulkan_apply(f->scale, f->input, NULL, 0) != -1) return false;
    up_vulkan_readback(f->scale, false);
    if (up_vulkan_apply(f->scale, f->input, NULL, 0)) return false;
    up_vulkan_readback(f->scale, true);
    if (up_vulkan_apply(f->scale, f->input, f->output, 0)) return false;
    return memcmp(f->scaled, f->output, f->output_size) == 0;
}

static bool check_shape(const int *shape, unsigned device, char **argv, unsigned mode)
{
    fixture_t f = {.sw = shape[0], .sh = shape[1], .dw = shape[2], .dh = shape[3]};
    bool ok = setup(&f, device, argv[1], argv[2], argv[3], mode);
    if (ok) ok = up_vulkan_enable_timing(f.combined, true) == 0;
    for (unsigned p = 0; ok && p < 3; p++) ok = check_pattern(&f, p);
    if (ok) ok = check_readback_contract(&f);
    printf("device=%u mode=%u %dx%d -> %dx%d: %s\n", device, mode,
           f.sw, f.sh, f.dw, f.dh, ok ? "PASS" : "FAIL");
    cleanup(&f);
    return ok;
}

int main(int argc, char **argv)
{
    if (argc != 4) return 2;
    static const int shapes[][4] = {{2, 2, 2, 2}, {4, 2, 10, 6}, {16, 10, 34, 22},
        {64, 36, 128, 72}, {2, 2, 8, 6}, {72, 10, 136, 22}};
    for (unsigned device = 0; device < 2; device++) {
        for (unsigned direct = 0; direct < 8; direct++) {
            for (unsigned shape = 0; shape < sizeof(shapes) / sizeof(shapes[0]); shape++)
                if (!check_shape(shapes[shape], device, argv, direct)) return 1;
        }
        const int large[] = {3840, 2160, 3840, 2160};
        if (!check_shape(large, device, argv, 7)) return 1;
    }
    puts("BUILD-45: null-output and readback transition checks passed");
    return 0;
}
