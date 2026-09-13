// SPDX-License-Identifier: GPL-2.0-or-later
#define main profile_pipeline_entry
#include "profile_pipeline.c"
#undef main
#include "test_harness.h"

static int fail_create;
usm_pool_t *__real_up_usm_pool_create(int, int, int, int);
usm_pool_t *__wrap_up_usm_pool_create(int n, int w, int h, int stripe)
{
    if (fail_create) return NULL;
    return __real_up_usm_pool_create(n, w, h, stripe);
}

static args_t small_args(void)
{
    return (args_t){.zimg = 1, .usm = 2, .width = 64, .height = 64,
                   .frames = 8, .source_width = 32, .source_height = 32,
                   .zerocopy = 1};
}

static void test_gate_retirement(void)
{
    BEGIN("REL-23: sharpness gate retires the USM pool as playback does");
    pipeline_t p = {0};
    args_t a = small_args();
    a.adaptive = a.sharp_threshold = 1;
    const int rc = initialize(&p, &a);
    CHECK(rc == 0);
    if (!rc) {
        for (int i = 0; i < UP_PROBE_WINDOW_FRAMES; i++)
            probe_source(&p, &p.input[0]);
        CHECK(p.skip_usm == 1);
        CHECK(p.usm == NULL);
        CHECK(!p.adaptive.enabled);
        CHECK(strcmp(adaptive_outcome(&p), "sharpness-bypass") == 0);
    }
    destroy(&p);
    END();
}

static void test_adaptive_pixels(void)
{
    BEGIN("PERF-11: trial counts preserve fixed-pool output pixels");
    pipeline_t fixed = {0}, adaptive = {0};
    args_t a = small_args();
    a.verify_pixels = 1;
    int rc = initialize(&fixed, &a);
    a.adaptive = 1;
    rc = rc || initialize(&adaptive, &a);
    CHECK(rc == 0);
    if (!rc) {
        up_usm_adaptive_init(&adaptive.adaptive, 2, 8, 64, 64, 0);
        for (int i = 0; i < 8; i++) {
            sample_t x, y;
            adaptive.adaptive.tuner.current = 1 << (i % 4);
            CHECK(frame(&fixed, i, &x) == 0);
            CHECK(frame(&adaptive, i, &y) == 0);
            CHECK(picture_hash(&fixed.output) == picture_hash(&adaptive.output));
            CHECK(x.hash == y.hash && y.hash != 0);
            CHECK(y.selected_workers == (1 << (i % 4)));
        }
    }
    destroy(&fixed);
    destroy(&adaptive);
    END();
}

static void test_trial_fallback(void)
{
    BEGIN("PERF-11: failed trial keeps pixels and explicit fallback outcome");
    pipeline_t p = {0}, fixed = {0};
    args_t a = small_args();
    int rc = initialize(&fixed, &a);
    a.adaptive = 1;
    rc = rc || initialize(&p, &a);
    CHECK(rc == 0);
    if (!rc) {
        up_usm_adaptive_init(&p.adaptive, 2, 8, 64, 64, 0);
        sample_t s;
        CHECK(frame(&fixed, 0, &s) == 0);
        p.adaptive.tuner.current = 4;
        fail_create = 1;
        CHECK(frame(&p, 0, &s) == 0);
        CHECK(picture_hash(&fixed.output) == picture_hash(&p.output));
        CHECK(strcmp(adaptive_outcome(&p), "fallback") == 0);
        CHECK(p.usm != NULL);
        fail_create = 0;
    }
    destroy(&p);
    destroy(&fixed);
    END();
}

static void test_affinity(void)
{
    BEGIN("PERF-13: USM placement validates masks and verifies worker affinity");
    cpu_set_t allowed;
    CHECK(sched_getaffinity(0, sizeof allowed, &allowed) == 0);
    int first = 0;
    while (first < CPU_SETSIZE && !CPU_ISSET(first, &allowed)) first++;
    pipeline_t p = {0};
    args_t a = small_args();
    a.usm_cpu_first = first;
    a.usm_cpu_count = 1;
    const int rc = initialize(&p, &a);
    CHECK(rc == 0);
    if (!rc) {
        sample_t s;
        CHECK(frame(&p, 0, &s) == 0);
        CHECK(up_profile_usm_affinity_status() == 0);
    }
    destroy(&p);
    CHECK(up_profile_usm_affinity(CPU_SETSIZE, 1) != 0);
    CHECK(up_profile_usm_affinity(0, 0) == 0);
    END();
}

int main(void)
{
    unsetenv("UP_PROFILE_INPUT");
    test_gate_retirement();
    test_adaptive_pixels();
    test_trial_fallback();
    test_affinity();
    return test_harness_report();
}
