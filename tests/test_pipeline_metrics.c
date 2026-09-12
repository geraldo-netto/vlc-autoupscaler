// SPDX-License-Identifier: GPL-2.0-or-later
#include <time.h>
#include <stdint.h>
#include "test_harness.h"

static uint64_t wall_clock, cpu_clock;
static unsigned clock_calls;
static int clock_failure;

static int fake_metrics_clock(clockid_t clock, struct timespec *time)
{
    clock_calls++;
    if (clock_failure) return -1;
    uint64_t value = clock == CLOCK_MONOTONIC ? wall_clock : cpu_clock;
    time->tv_sec = (time_t)(value / UINT64_C(1000000000));
    time->tv_nsec = (long)(value % UINT64_C(1000000000));
    return 0;
}

#define UP_METRICS_CLOCK fake_metrics_clock
#include "../src/pipeline_metrics.h"

static void test_disabled(void)
{
    BEGIN("OBS-19: disabled metrics read no clocks");
    clock_calls = 0;
    up_metrics_begin(NULL);
    CHECK(up_metrics_mark(NULL) == 0);
    up_metrics_stage(NULL, UP_METRICS_SCALE, 0);
    CHECK(!up_metrics_end(NULL, true));
    CHECK(clock_calls == 0);
    END();
}

static void test_distribution(void)
{
    BEGIN("OBS-19: bounded windows report actual stage, total and process CPU");
    up_pipeline_metrics_t m = {0};
    for (unsigned i = 1; i <= UP_METRICS_WINDOW; i++) {
        wall_clock = cpu_clock = 1000000;
        up_metrics_begin(&m);
        uint64_t start = up_metrics_mark(&m);
        wall_clock += i * 1000;
        up_metrics_stage(&m, UP_METRICS_SCALE, start);
        start = up_metrics_mark(&m);
        wall_clock += 2000;
        up_metrics_stage(&m, UP_METRICS_USM, start);
        wall_clock += 3000;
        cpu_clock += 7000;
        CHECK(up_metrics_end(&m, true) == (i == UP_METRICS_WINDOW));
    }
    up_tuner_score_t scale = up_metrics_score(&m, UP_METRICS_SCALE);
    CHECK(scale.mean_us == 128.5 && scale.p95_us == 244 && scale.p99_us == 254);
    CHECK(up_metrics_score(&m, UP_METRICS_USM).mean_us == 2);
    CHECK(up_metrics_score(&m, UP_METRICS_TOTAL).mean_us == 133.5);
    CHECK(up_metrics_score(&m, UP_METRICS_CPU).mean_us == 7);
    CHECK(m.used == UP_METRICS_WINDOW && m.failed == 0 && m.invalid == 0);
    up_metrics_reset(&m);
    CHECK(m.used == 0 && m.attempts == 0);
    END();
}

static void test_failed_frames_and_clocks(void)
{
    BEGIN("OBS-19: failures never become zero-latency successful samples");
    up_pipeline_metrics_t m = {0};
    wall_clock = cpu_clock = 10000;
    up_metrics_begin(&m);
    CHECK(!up_metrics_end(&m, false));
    CHECK(m.failed == 1 && m.used == 0);
    clock_failure = 1;
    up_metrics_begin(&m);
    CHECK(!up_metrics_end(&m, true));
    clock_failure = 0;
    CHECK(m.invalid == 1 && m.used == 0);
    up_metrics_begin(&m);
    wall_clock--;
    CHECK(!up_metrics_end(&m, true));
    CHECK(m.invalid == 2 && m.used == 0);
    CHECK(up_metrics_score(&m, UP_METRICS_TOTAL).mean_us == 0);
    END();
}

int main(void)
{
    test_disabled();
    test_distribution();
    test_failed_frames_and_clocks();
    return test_harness_report();
}
