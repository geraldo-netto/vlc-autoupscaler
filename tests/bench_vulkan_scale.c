// SPDX-License-Identifier: GPL-2.0-or-later
#define ZIMG_TEST_DEFINE_MODULE_NAME
#include "zimg_test_util.h"
#include "experiment_vulkan.h"
#include "cli_parse.h"
#include "vulkan_bench_util.h"
#include "../src/worker_tuner.h"
#include "../src/usm_pool.h"
#include <math.h>
#include <stdio.h>
#include <time.h>

typedef struct {
    zt_pic_t input, cpu_output;
    scaler_ctx_t cpu;
    up_vulkan_t *gpu;
    usm_pool_t *usm;
    bool combined, timing;
    int period, workers, sequence_count;
    uint8_t *sequence;
    const char *variant;
    char fused_shader[4096];
    double stage[8][120];
    uint8_t *packed_input, *packed_output;
    size_t input_size, output_size;
} scale_fixture_t;

static void cleanup(scale_fixture_t *f)
{
    up_vulkan_destroy(f->gpu);
    up_usm_pool_destroy(f->usm);
    if (f->cpu.priv) f->cpu.backend->close(&f->cpu);
    zt_pic_free(&f->input); zt_pic_free(&f->cpu_output);
    free(f->packed_input); free(f->packed_output); free(f->sequence);
}

static bool setup_cpu(scale_fixture_t *f, int factor)
{
    int sw = 960, sh = 540, dw = sw * factor, dh = sh * factor;
    f->input_size = (size_t)sw * (size_t)sh * 3 / 2;
    f->output_size = (size_t)dw * (size_t)dh * 3 / 2;
    f->packed_input = malloc(f->input_size); f->packed_output = malloc(f->output_size);
    if (!f->packed_input || !f->packed_output) return false;
    if (zt_pic_alloc(&f->input, VLC_CODEC_I420, sw, sh)) return false;
    if (zt_pic_alloc(&f->cpu_output, VLC_CODEC_I420, dw, dh)) return false;
    zt_ctx_init(&f->cpu, VLC_CODEC_I420, sw, sh, dw, dh, f->workers, 1);
    f->cpu.algo = UP_ALGO_SPLINE36;
    f->cpu.pin_cpus = 1;
    if (f->cpu.backend->open(&f->cpu)) return false;
    if (f->combined) f->usm = up_usm_pool_create(factor == 2 ? 12 : 16, dw, dh, 8);
    return !f->combined || f->usm;
}

static bool setup_gpu(scale_fixture_t *f, const char *shader, const char *usm, unsigned device)
{
    const char *slash = strrchr(shader, '/');
    size_t prefix = slash ? (size_t)(slash - shader + 1) : 0;
    if (prefix + sizeof("vulkan_fused.spv") > sizeof(f->fused_shader)) return false;
    memcpy(f->fused_shader, shader, prefix);
    memcpy(f->fused_shader + prefix, "vulkan_fused.spv", sizeof("vulkan_fused.spv"));
    if (strcmp(f->variant, "naive") == 0) {
        if (f->combined) return false;
        f->gpu = up_vulkan_create_scale(shader, device, 960, 540, f->cpu.dst_w, f->cpu.dst_h);
    } else {
        up_vulkan_scale_options_t config = {.horizontal = shader, .vertical = shader,
            .usm = f->combined ? usm : NULL, .direct = strstr(f->variant, "direct") != NULL,
            .coefficients = strstr(f->variant, "lookup") != NULL,
            .fused_shader = strstr(f->variant, "fused") ? f->fused_shader : NULL};
        f->gpu = up_vulkan_create_separable(&config, device, 960, 540, f->cpu.dst_w, f->cpu.dst_h);
    }
    if (!f->gpu) return false;
    return up_vulkan_enable_timing(f->gpu, f->timing) == 0;
}

static void pack(scale_fixture_t *f)
{
    uint8_t *output = f->packed_input;
    for (int p = 0; p < 3; p++) {
        const plane_t *plane = &f->input.pic.p[p];
        for (int y = 0; y < plane->i_visible_lines; y++) {
            memcpy(output, plane->p_pixels + (size_t)y * (size_t)plane->i_pitch,
                   (size_t)plane->i_visible_pitch);
            output += plane->i_visible_pitch;
        }
    }
}

static bool process(scale_fixture_t *f, bool gpu)
{
    if (gpu) {
        if (f->sequence_count > 1) pack(f);
        return up_vulkan_apply(f->gpu, f->packed_input, f->packed_output, f->combined ? 51 : 0) == 0;
    }
    if (f->cpu.backend->process(&f->cpu, &f->input.pic, &f->cpu_output.pic) != SCALER_PROCESS_OK) return false;
    if (!f->combined) return true;
    plane_t *p = &f->cpu_output.pic.p[0];
    return up_usm_pool_apply(f->usm, p->p_pixels, p->i_pitch, p->p_pixels, p->i_pitch, 51) == 0;
}

static bool flat_test(scale_fixture_t *f)
{
    zt_pic_memset(&f->input, 127);
    pack(f);
    if (!process(f, true)) return false;
    for (size_t i = 0; i < f->output_size; i++)
        if (f->packed_output[i] != 127) return false;
    return true;
}

static void quality_plane(const plane_t *plane, const uint8_t *gpu, double *squared, int *maximum)
{
    for (int y = 0; y < plane->i_visible_lines; y++) {
        const uint8_t *cpu = plane->p_pixels + (size_t)y * (size_t)plane->i_pitch;
        for (int x = 0; x < plane->i_visible_pitch; x++) {
            int delta = abs((int)cpu[x] - gpu[(size_t)y * (size_t)plane->i_visible_pitch + (size_t)x]);
            *squared += (double)delta * delta;
            if (delta > *maximum) *maximum = delta;
        }
    }
}

static bool quality(scale_fixture_t *f)
{
    if (!process(f, false) || !process(f, true)) return false;
    const uint8_t *gpu = f->packed_output;
    for (int p = 0; p < 3; p++) {
        const plane_t *plane = &f->cpu_output.pic.p[p];
        double squared = 0;
        int maximum = 0;
        quality_plane(plane, gpu, &squared, &maximum);
        size_t pixels = (size_t)plane->i_visible_lines * (size_t)plane->i_visible_pitch;
        printf("{\"quality_plane\":%d,\"max_error\":%d,\"rmse\":%.6f}\n",
               p, maximum, sqrt(squared / (double)pixels));
        gpu += pixels;
    }
    return true;
}

static void collect_stages(scale_fixture_t *f, int frame)
{
    up_vulkan_profile_t p = up_vulkan_profile(f->gpu);
    f->stage[0][frame] = p.host_upload_us;
    f->stage[1][frame] = p.submit_wait_us;
    f->stage[2][frame] = p.host_download_us;
    for (unsigned i = 0; i < 5; i++) f->stage[i + 3][frame] = p.gpu_us[i];
}

static void report_stages(scale_fixture_t *f)
{
    static const char *const names[] = {"host_upload", "submit_wait", "host_download",
        "gpu_upload", "gpu_pass_0", "gpu_pass_1", "gpu_pass_2", "gpu_download"};
    unsigned last = up_vulkan_profile(f->gpu).passes + 4;
    for (unsigned i = 0; i <= last; i++) {
        up_tuner_score_t s = up_tuner_score(f->stage[i], 120);
        const char *name = i == last ? "gpu_download" : names[i];
        printf("{\"stage\":\"%s\",\"mean_us\":%.3f,\"p95_us\":%.3f,\"p99_us\":%.3f}\n",
               name, s.mean_us, s.p95_us, s.p99_us);
    }
}

static bool pace(double deadline)
{
    double delay = deadline - up_vulkan_bench_now_us(CLOCK_MONOTONIC);
    if (delay <= 0) return true;
    struct timespec t = {.tv_sec = (time_t)(delay / 1e6),
        .tv_nsec = (long)(fmod(delay, 1e6) * 1000)};
    return nanosleep(&t, NULL) == 0;
}

static void unpack(scale_fixture_t *f, const uint8_t *input);

static void prepare_frame(scale_fixture_t *f, unsigned frame)
{
    if (f->sequence_count == 1) return;
    size_t index = frame % (unsigned)f->sequence_count;
    unpack(f, f->sequence + index * f->input_size);
}

static void prepare_measure(scale_fixture_t *f, bool gpu)
{
    if (gpu && strstr(f->variant, "resident")) up_vulkan_readback(f->gpu, false);
}

static bool measure(scale_fixture_t *f, bool gpu)
{
    double wall[120], cpu[120];
    prepare_measure(f, gpu);
    double deadline = up_vulkan_bench_now_us(CLOCK_MONOTONIC);
    for (int i = -20; i < 120; i++) {
        prepare_frame(f, (unsigned)(i + 20));
        double start_cpu = up_vulkan_bench_now_us(CLOCK_PROCESS_CPUTIME_ID);
        double start = up_vulkan_bench_now_us(CLOCK_MONOTONIC);
        if (!process(f, gpu)) return false;
        double elapsed = up_vulkan_bench_now_us(CLOCK_MONOTONIC) - start;
        double used = up_vulkan_bench_now_us(CLOCK_PROCESS_CPUTIME_ID) - start_cpu;
        if (i >= 0) { wall[i] = elapsed; cpu[i] = used; collect_stages(f, i); }
        deadline += f->period;
        if (!pace(deadline)) return false;
    }
    up_tuner_score_t w = up_tuner_score(wall, 120), c = up_tuner_score(cpu, 120);
    if (gpu && f->timing) report_stages(f);
    printf("{\"device\":\"%s\",\"backend\":\"%s\",\"width\":%d,\"height\":%d,"
           "\"frames\":120,\"mean_us\":%.3f,\"p95_us\":%.3f,\"p99_us\":%.3f,"
           "\"process_cpu_us\":%.3f,\"variant\":\"%s\",\"combined\":%s,"
           "\"timing\":%s,\"period_us\":%d,\"cpu_workers\":%d,\"sequence_frames\":%d}\n", up_vulkan_device(f->gpu),
           gpu ? "vulkan-spline36" : "zimg-spline36", f->cpu.dst_w,
           f->cpu.dst_h, w.mean_us, w.p95_us, w.p99_us, c.mean_us, f->variant,
           f->combined ? "true" : "false", f->timing ? "true" : "false", f->period, f->workers, f->sequence_count);
    return true;
}

static void unpack(scale_fixture_t *f, const uint8_t *input)
{
    for (int p = 0; p < 3; p++) {
        plane_t *plane = &f->input.pic.p[p];
        for (int y = 0; y < plane->i_visible_lines; y++) {
            memcpy(plane->p_pixels + (size_t)y * (size_t)plane->i_pitch,
                   input, (size_t)plane->i_visible_pitch);
            input += plane->i_visible_pitch;
        }
    }
}

static bool load_input(scale_fixture_t *f, const char *path)
{
    size_t size = f->input_size * (size_t)f->sequence_count;
    f->sequence = malloc(size);
    if (!f->sequence) return false;
    FILE *file = fopen(path, "rb");
    if (!file) return false;
    bool ok = fread(f->sequence, 1, size, file) == size;
    if (fclose(file)) ok = false;
    if (!ok) return false;
    memcpy(f->packed_input, f->sequence, f->input_size);
    unpack(f, f->sequence);
    return true;
}

static bool variant_valid(const char *variant)
{
    static const char *const allowed[] = {"naive", "separable", "direct", "lookup",
        "lookup-direct", "lookup-resident", "resident", "fused", "fused-direct",
        "fused-resident", "lookup-fused", "lookup-fused-direct", "lookup-fused-resident"};
    for (unsigned i = 0; i < sizeof(allowed) / sizeof(allowed[0]); i++)
        if (!strcmp(variant, allowed[i])) return true;
    return false;
}

static bool options(scale_fixture_t *f, int argc, char **argv)
{
    f->variant = argc == 6 ? "naive" : argv[6];
    if (!variant_valid(f->variant)) return false;
    f->workers = 12; f->sequence_count = 1;
    if (argc == 6) return true;
    if (argc >= 11) {
        long workers;
        if (!up_cli_parse_long(argv[10], 1, 64, &workers)) return false;
        f->workers = (int)workers;
    }
    if (argc == 12) {
        long count;
        if (!up_cli_parse_long(argv[11], 1, 32, &count)) return false;
        f->sequence_count = (int)count;
    }
    long timing, period;
    if (!up_cli_parse_long(argv[8], 0, 1, &timing)
        || !up_cli_parse_long(argv[9], 0, 1000000, &period)) return false;
    f->timing = timing != 0; f->period = (int)period;
    f->combined = strcmp(argv[7], "-") != 0;
    return true;
}

static bool run(scale_fixture_t *f, char **argv)
{
    if (!flat_test(f)) return false;
    if (!load_input(f, argv[5])) return false;
    if (!quality(f)) return false;
    return measure(f, strcmp(argv[4], "gpu") == 0);
}

static bool arguments(int argc, char **argv, long *device, long *factor)
{
    if (argc != 6 && (argc < 10 || argc > 12)) return false;
    if (!up_vulkan_bench_mode_valid(argv[4])) return false;
    return up_cli_parse_long(argv[2], 0, 15, device)
        && up_cli_parse_long(argv[3], 2, 4, factor);
}

int main(int argc, char **argv)
{
    long device, factor;
    if (!arguments(argc, argv, &device, &factor)) {
        fprintf(stderr, "usage: %s shader device factor cpu|gpu 960x540.yuv [variant usm.spv|- timing period_us [cpu_workers [sequence_frames]]]\n", argv[0]);
        return 2;
    }
    scale_fixture_t f = {0};
    if (!options(&f, argc, argv)) return 2;
    bool ok = setup_cpu(&f, (int)factor);
    if (ok) ok = setup_gpu(&f, argv[1], argc == 6 ? NULL : argv[7], (unsigned)device);
    if (ok) ok = run(&f, argv);
    cleanup(&f);
    return ok ? 0 : 1;
}
