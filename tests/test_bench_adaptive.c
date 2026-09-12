// SPDX-License-Identifier: GPL-2.0-or-later
#include <stdio.h>
#include <stdarg.h>
#define ZIMG_TEST_DEFINE_MODULE_NAME
#include "zimg_test_util.h"
#include "../src/usm_adaptive.h"
#include "cli_parse.h"

static char benchmark_output[1024];
static int capture_printf(const char *format, ...);
#define printf capture_printf
#define main benchmark_entry
#include "bench_adaptive.c"
#undef main
#undef printf
#include "test_harness.h"

static int create_calls, fail_create_nth;

static int capture_printf(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    const int result = vsnprintf(benchmark_output, sizeof benchmark_output,
                                  format, args);
    va_end(args);
    return result;
}

usm_pool_t *__real_up_usm_pool_create(int workers, int width, int height, int stripe);
usm_pool_t *__wrap_up_usm_pool_create(int workers, int width, int height, int stripe)
{
    create_calls++;
    if (create_calls == fail_create_nth) return NULL;
    return __real_up_usm_pool_create(workers, width, height, stripe);
}

static void test_default_profile(void)
{
    BEGIN("OBS-17: adaptive benchmark defaults match playback algorithm and pinning");
    char *arguments[] = { "bench", "1", "1024", "64", "64", "1" };
    args_t args;
    CHECK(parse(6, arguments, &args) == 0);
    bench_t bench = { 0 };
    CHECK(initialize(&bench, &args) == 0);
    CHECK(bench.scaler.algo == UP_ALGO_SPLINE36);
    CHECK(bench.scaler.pin_cpus == 1);
    destroy(&bench);
    END();
}

static void test_profile_csv(void)
{
    BEGIN("OBS-17: CSV identifies actual algorithm and pinning");
    char *arguments[] = { "bench", "1", "1024", "64", "64", "1" };
    benchmark_output[0] = '\0';
    CHECK(benchmark_entry(6, arguments) == 0);
    CHECK(strstr(benchmark_output, ",3,1,fixed\n") != NULL);
    END();
}

static void test_fallback_csv(void)
{
    BEGIN("OBS-16: failed adaptive trial is reported as fallback");
    char *arguments[] = { "bench", "-1", "1024", "64", "64", "1" };
    create_calls = 0;
    fail_create_nth = 2;
    benchmark_output[0] = '\0';
    CHECK(benchmark_entry(6, arguments) == 0);
    CHECK(create_calls == 2);
    CHECK(strstr(benchmark_output, ",fallback\n") != NULL);
    fail_create_nth = 0;
    END();
}

static void test_profile_options(void)
{
    BEGIN("OBS-17: all Lanczos/Spline36 and pinning profiles are explicit");
    for (int algorithm = 0; algorithm < 2; algorithm++) {
        for (int pin = 0; pin < 2; pin++) {
            char *arguments[] = { "bench", "1", "1024", "64", "64", "1",
                                  algorithm ? "3" : "2", pin ? "1" : "0" };
            args_t args;
            bench_t bench = { 0 };
            CHECK(parse(8, arguments, &args) == 0);
            CHECK(initialize(&bench, &args) == 0);
            CHECK(bench.scaler.algo == algorithm + 2);
            CHECK(bench.scaler.pin_cpus == pin);
            destroy(&bench);
        }
    }
    END();
}

static void test_late_fallback_csv(void)
{
    BEGIN("OBS-16: fallback stays visible after an earlier settlement");
    char *arguments[] = { "bench", "-1", "1024", "64", "64", "1" };
    args_t args;
    bench_t bench = { 0 };
    CHECK(parse(6, arguments, &args) == 0);
    CHECK(initialize(&bench, &args) == 0);
    bench.settled_frame = 100;
    bench.adaptive.tuner.phase = UP_TUNER_SETTLED;
    bench.adaptive.tuner.current = bench.adaptive.tuner.best == 1 ? 2 : 1;
    fail_create_nth = create_calls + 1;
    CHECK(up_usm_adaptive_select(&bench.adaptive, bench.usm) == bench.usm);
    report(&bench, &args);
    CHECK(strstr(benchmark_output, ",fallback\n") != NULL);
    CHECK(bench.settled_frame == 100);
    fail_create_nth = 0;
    destroy(&bench);
    END();
}

int main(void)
{
    test_default_profile();
    test_profile_csv();
    test_fallback_csv();
    test_profile_options();
    test_late_fallback_csv();
    return test_harness_report();
}
