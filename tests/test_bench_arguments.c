// SPDX-License-Identifier: GPL-2.0-or-later
#define main benchmark_main
#if defined(TEST_BENCH_PIPELINE)
#include "bench_pipeline.c"
typedef bench_args_t parsed_args_t;
static char *arguments[20] = { "bench_pipeline", "1", "1", "0", "0", "0" };
#define MIN_ARGS 2
#define MAX_ARGS 6
#elif defined(TEST_BENCH_ZIMG)
#include "bench_scaler_zimg.c"
typedef struct bargs parsed_args_t;
#define parse_args parse
static char *arguments[20] = { "bench_scaler_zimg", "1", "i420", "8", "8", "16", "16", "1", "1", "0" };
#define MIN_ARGS 7
#define MAX_ARGS 10
#else
#include "bench_usm_pool.c"
typedef struct bench_args parsed_args_t;
static char *arguments[20] = { "bench_usm_pool", "1", "8", "8", "1", "20", "rand", "out" };
#define MIN_ARGS 4
#define MAX_ARGS 8
#endif
#undef main
#include "test_harness.h"

static int allocations;

void *__wrap_aligned_alloc(size_t alignment, size_t size)
{
    (void)alignment;
    (void)size;
    allocations++;
    return NULL;
}

static void test_count_boundaries(void)
{
    BEGIN("REV-27: required and optional argument count boundaries");
    parsed_args_t parsed;
    for (int argc = 1; argc < MIN_ARGS; argc++)
        CHECK(parse_args(argc, arguments, &parsed) == 2);
    for (int argc = MIN_ARGS; argc <= MAX_ARGS; argc++)
        CHECK(parse_args(argc, arguments, &parsed) == 0);
    END();
}

static void test_extra_arguments(void)
{
    BEGIN("REV-27: extra arguments rejected before allocation");
    static const char *extras[] = { "", "unexpected", "--help", "-1", "0", "99999999999999999999", "\n", "\xff" };
    for (size_t i = 0; i < sizeof extras / sizeof *extras; i++) {
        for (int count = 1; count <= 8; count++) {
            arguments[MAX_ARGS + count - 1] = (char *)extras[i];
            arguments[MAX_ARGS + count] = NULL;
            allocations = 0;
            CHECK(benchmark_main(MAX_ARGS + count, arguments) == 2);
            CHECK(allocations == 0);
        }
    }
    END();
}

#if !defined(TEST_BENCH_PIPELINE) && !defined(TEST_BENCH_ZIMG)
static void test_alias_modes(void)
{
    BEGIN("REV-27: valid and invalid USM alias arguments");
    static const char *modes[] = { "out", "in", "", "invalid", "\xff" };
    parsed_args_t parsed;
    for (size_t i = 0; i < sizeof modes / sizeof *modes; i++) {
        arguments[7] = (char *)modes[i];
        CHECK(parse_args(MAX_ARGS, arguments, &parsed) == (i < 2 ? 0 : 2));
    }
    END();
}
#endif

int main(void)
{
    test_count_boundaries();
    test_extra_arguments();
#if !defined(TEST_BENCH_PIPELINE) && !defined(TEST_BENCH_ZIMG)
    test_alias_modes();
#endif
    return test_harness_report();
}
