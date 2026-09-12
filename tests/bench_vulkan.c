// SPDX-License-Identifier: GPL-2.0-or-later
#include "experiment_vulkan.h"
#include "usm_reference.h"
#include "prng.h"
#include "cli_parse.h"
#include "vulkan_bench_util.h"
#include "../src/usm_pool.h"
#include "../src/worker_tuner.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

typedef struct {
    up_vulkan_t *gpu;
    usm_pool_t *cpu;
    uint8_t *input, *output, *reference, *workspace;
    size_t size;
    int width, height;
} fixture_t;

static void cleanup(fixture_t *f)
{
    up_vulkan_destroy(f->gpu);
    up_usm_pool_destroy(f->cpu);
    free(f->input); free(f->output); free(f->reference); free(f->workspace);
}

static bool allocate(fixture_t *f, const char *shader, unsigned device, int workers)
{
    f->size = (size_t)f->width * (size_t)f->height;
    f->input = malloc(f->size); f->output = malloc(f->size);
    f->reference = malloc(f->size); f->workspace = malloc(f->size);
    f->gpu = up_vulkan_create(shader, device, f->width, f->height);
    f->cpu = up_usm_pool_create(workers, f->width, f->height, 8);
    return f->input && f->output && f->reference && f->workspace && f->gpu && f->cpu;
}

static void fill(fixture_t *f, unsigned pattern)
{
    uint32_t seed = 0x12345678;
    for (size_t i = 0; i < f->size; i++) {
        if (pattern == 0) f->input[i] = (uint8_t)up_xs32(&seed);
        else if (pattern == 1) f->input[i] = 127;
        else f->input[i] = (i % 3 == 0) ? 255 : 0;
    }
}

static bool validate_amount(fixture_t *f, int amount)
{
    up_usm_plane_io_t io = {f->reference, f->width, f->input,
                           f->width, f->width, f->height};
    if (!up_usm_apply_plane(&io, amount, f->workspace)) return false;
    if (up_vulkan_apply(f->gpu, f->input, f->output, amount)) return false;
    if (memcmp(f->reference, f->output, f->size)) return false;
    memcpy(f->output, f->input, f->size);
    if (up_usm_pool_apply(f->cpu, f->output, f->width, f->output, f->width, amount)) return false;
    return memcmp(f->reference, f->output, f->size) == 0;
}

static bool validate(fixture_t *f)
{
    static const int amounts[] = {-1, 0, 1, 51, 256, 512, 4096, 5000};
    for (unsigned p = 0; p < 3; p++) {
        fill(f, p);
        for (unsigned a = 0; a < sizeof(amounts) / sizeof(amounts[0]); a++)
            if (!validate_amount(f, amounts[a])) return false;
    }
    return true;
}

static int process(fixture_t *f, bool gpu)
{
    if (gpu) return up_vulkan_apply(f->gpu, f->input, f->output, 51);
    return up_usm_pool_apply(f->cpu, f->output, f->width, f->output, f->width, 51);
}

static int pace(double deadline)
{
    double delay = deadline - up_vulkan_bench_now_us(CLOCK_MONOTONIC);
    if (delay <= 0) return 0;
    struct timespec time = {.tv_sec = (time_t)(delay / 1e6),
        .tv_nsec = (long)((delay - (double)(time_t)(delay / 1e6) * 1e6) * 1000)};
    return nanosleep(&time, NULL);
}

static bool measure(fixture_t *f, bool gpu, int count, int period)
{
    double wall[600], cpu[600];
    fill(f, 0);
    double deadline = up_vulkan_bench_now_us(CLOCK_MONOTONIC);
    for (int i = -20; i < count; i++) {
        memcpy(f->output, f->input, f->size);
        double start_cpu = up_vulkan_bench_now_us(CLOCK_PROCESS_CPUTIME_ID);
        double start = up_vulkan_bench_now_us(CLOCK_MONOTONIC);
        if (process(f, gpu)) return false;
        double elapsed = up_vulkan_bench_now_us(CLOCK_MONOTONIC) - start;
        double used_cpu = up_vulkan_bench_now_us(CLOCK_PROCESS_CPUTIME_ID) - start_cpu;
        if (i >= 0) { wall[i] = elapsed; cpu[i] = used_cpu; }
        deadline += period;
        if (pace(deadline)) return false;
    }
    up_tuner_score_t w = up_tuner_score(wall, count), c = up_tuner_score(cpu, count);
    printf("{\"device\":\"%s\",\"backend\":\"%s\",\"width\":%d,\"height\":%d,"
           "\"frames\":%d,\"period_us\":%d,\"mean_us\":%.3f,\"p95_us\":%.3f,"
           "\"p99_us\":%.3f,\"process_cpu_us\":%.3f,\"byte_exact\":true}\n",
           up_vulkan_device(f->gpu), gpu ? "vulkan-usm" : "cpu-usm", f->width,
           f->height, count, period, w.mean_us, w.p95_us, w.p99_us, c.mean_us);
    return true;
}

static int number(const char *text, int minimum, int maximum)
{
    long value;
    if (!up_cli_parse_long(text, minimum, maximum, &value)) return -1;
    return (int)value;
}

static bool dimensions(fixture_t *f, char **args)
{
    f->width = number(args[3], 1, 4096);
    f->height = number(args[4], 1, 4096);
    return f->width > 0 && f->height > 0;
}

static bool options_valid(int device, int workers, int count, int period)
{
    return device >= 0 && workers > 0 && count > 0 && period >= 0;
}

int main(int argc, char **argv)
{
    if (argc != 9) {
        fprintf(stderr, "usage: %s shader device width height workers frames period_us cpu|gpu\n", argv[0]);
        return 2;
    }
    if (!up_vulkan_bench_mode_valid(argv[8])) return 2;
    fixture_t f = {0};
    int device = number(argv[2], 0, 15), workers = number(argv[5], 1, 64);
    int count = number(argv[6], 1, 600), period = number(argv[7], 0, 1000000);
    if (!dimensions(&f, argv) || !options_valid(device, workers, count, period)) return 2;
    bool ok = allocate(&f, argv[1], (unsigned)device, workers);
    if (ok) ok = validate(&f);
    if (ok) ok = measure(&f, strcmp(argv[8], "gpu") == 0, count, period);
    cleanup(&f);
    return ok ? 0 : 1;
}
