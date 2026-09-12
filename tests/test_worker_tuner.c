// SPDX-License-Identifier: GPL-2.0-or-later
#include "../src/worker_tuner.h"
#include "test_harness.h"

static double cost(int workers, int optimum)
{
    if (workers == optimum) return 50.0;
    return workers < optimum ? 160.0 - workers : 200.0 + workers;
}

static void converge(up_worker_tuner_t *t, int optimum, bool noisy)
{
    for (int i = 0; i < 2000 && t->phase != UP_TUNER_SETTLED; i++) {
        double elapsed = cost(t->current, optimum);
        if (noisy && i % 7 == 0) elapsed *= 100.0;
        up_worker_tuner_observe(t, elapsed);
        CHECK(t->current >= 1 && t->current <= t->limit);
    }
    CHECK(t->phase == UP_TUNER_SETTLED);
    CHECK(t->best == optimum);
}

static void test_search(void)
{
    BEGIN("nonmonotonic timings, outliers and geometry limits");
    const int limits[] = { 1, 2, 3, 8, 12, 16, 23, 32, 48, 64 };
    for (size_t i = 0; i < sizeof limits / sizeof limits[0]; i++) {
        up_worker_tuner_t t;
        up_worker_tuner_init(&t, 12, limits[i]);
        converge(&t, limits[i], true);
    }
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 12, 64);
    converge(&t, 16, true);
    END();
}

static void window(up_worker_tuner_t *t, double elapsed)
{
    const int frames = t->warmup + UP_TUNER_SAMPLES - t->used;
    for (int i = 0; i < frames; i++) up_worker_tuner_observe(t, elapsed);
}

static void test_confirmation(void)
{
    BEGIN("require five percent gain against both baselines");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 2, 4);
    window(&t, 100.0);
    CHECK(t.current == 1);
    window(&t, 80.0);
    CHECK(t.current == 2);
    window(&t, 70.0);
    CHECK(t.best == 2);
    window(&t, 100.0);
    CHECK(t.current == 4);
    window(&t, 96.0);
    window(&t, 100.0);
    CHECK(t.best == 2);
    END();
}

static void test_recheck(void)
{
    BEGIN("sustained drift and periodic exploration");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 12, 32);
    converge(&t, 16, false);
    for (int i = 0; i < UP_TUNER_COOLDOWN_FRAMES; i++)
        up_worker_tuner_observe(&t, 50.0);
    window(&t, 100.0);
    window(&t, 50.0);
    CHECK(t.drift == 0 && t.phase == UP_TUNER_SETTLED);
    for (int i = 0; i < 3; i++) window(&t, 100.0);
    CHECK(t.phase == UP_TUNER_BASE);
    converge(&t, 4, false);
    const int remaining = t.remaining;
    for (int i = 0; i < remaining; i++)
        up_worker_tuner_observe(&t, 50.0);
    CHECK(t.phase == UP_TUNER_BASE);
    converge(&t, 8, false);
    END();
}

static void test_bounded_probes(void)
{
    BEGIN("slow probes exit early and load changes respect cooldown");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 2, 4);
    window(&t, 100.0);
    for (int i = 0; i < UP_TUNER_WARMUP + 4; i++)
        up_worker_tuner_observe(&t, 200.0);
    CHECK(t.phase == UP_TUNER_CONFIRM && t.current == 2);
    window(&t, 100.0);
    CHECK(t.best == 2);
    up_tuner_settle(&t, (up_tuner_score_t){ 100.0, 100.0, 100.0 });
    for (int i = 0; i < UP_TUNER_COOLDOWN_FRAMES - UP_TUNER_SAMPLES; i++)
        up_worker_tuner_observe(&t, 200.0);
    CHECK(t.phase == UP_TUNER_SETTLED && t.drift == 0);
    for (int i = 0; i < 3; i++) window(&t, 200.0);
    CHECK(t.phase == UP_TUNER_BASE);
    END();
}

static void test_invalid(void)
{
    BEGIN("invalid samples and initialization bounds");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, -1, -2);
    CHECK(t.best == 1 && t.limit == 1);
    up_worker_tuner_init(&t, 99, 999);
    CHECK(t.best == 64 && t.limit == 64);
    const double invalid[] = { NAN, INFINITY, -INFINITY, 0.0, -1.0 };
    for (size_t i = 0; i < sizeof invalid / sizeof invalid[0]; i++)
        up_worker_tuner_observe(&t, invalid[i]);
    CHECK(t.used == 0 && t.warmup == UP_TUNER_WARMUP);
    CHECK(up_tuner_next_count(64, 65) == 0);
    END();
}

typedef struct {
    double fast, slow;
    int period, slow_start;
} timing_pattern_t;

static double patterned_cost(const timing_pattern_t *pattern, int sample)
{
    return sample % pattern->period < pattern->slow_start
        ? pattern->fast : pattern->slow;
}

static void patterned_window(up_worker_tuner_t *t,
                             const timing_pattern_t *pattern)
{
    const int frames = t->warmup + UP_TUNER_SAMPLES - t->used;
    for (int i = 0; i < frames; i++)
        up_worker_tuner_observe(t, patterned_cost(pattern, t->used));
}

static void check_pattern_search(const timing_pattern_t *baseline,
                                 const timing_pattern_t *candidate,
                                 int expected)
{
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 2, 4);
    for (int i = 0; i < 32 * UP_TUNER_SAMPLES; i++) {
        const timing_pattern_t *pattern = t.current == 4 ? candidate : baseline;
        const double elapsed = t.current == 1 ? 2000.0
            : patterned_cost(pattern, t.used);
        up_worker_tuner_observe(&t, elapsed);
    }
    CHECK(t.phase == UP_TUNER_SETTLED);
    CHECK(t.best == expected && t.current == expected);
}

static void test_mean_and_tail_selection(void)
{
    static const struct {
        const char *name;
        timing_pattern_t baseline, candidate;
        int expected;
    } cases[] = {
        { "PERF-10: recurring stalls cannot win by median",
          { 100, 100, 16, 16 }, { 50, 1000, 16, 11 }, 2 },
        { "PERF-10: reject higher mean even with matching tails",
          { 100, 1000, 16, 15 }, { 50, 1000, 16, 11 }, 2 },
        { "PERF-10: reject faster mean with worse p95",
          { 100, 100, 16, 16 }, { 50, 200, 16, 13 }, 2 },
        { "PERF-10: reject rare p99 regression",
          { 100, 100, UP_TUNER_SAMPLES, UP_TUNER_SAMPLES },
          { 50, 150, UP_TUNER_SAMPLES, UP_TUNER_SAMPLES - 1 }, 2 },
        { "PERF-10: accept sustained mean and tail gains",
          { 100, 100, 16, 16 }, { 50, 90, 16, 11 }, 4 },
        { "PERF-10: allow tail variation within five percent",
          { 100, 100, 16, 16 }, { 50, 104.9, 16, 11 }, 4 },
        { "PERF-10: accept lower mean despite worse median",
          { 50, 1000, 16, 11 }, { 100, 100, 16, 16 }, 4 },
    };
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; i++) {
        BEGIN(cases[i].name);
        check_pattern_search(&cases[i].baseline, &cases[i].candidate,
                              cases[i].expected);
        END();
    }
}

static void test_tail_monitor(void)
{
    BEGIN("PERF-10: repeated tail drift restarts search without mean drift");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 1, 1);
    window(&t, 100.0);
    for (int i = 0; i < UP_TUNER_COOLDOWN_FRAMES; i++)
        up_worker_tuner_observe(&t, 100.0);
    const timing_pattern_t stalls = { 90, 200, 16, 15 };
    patterned_window(&t, &stalls);
    window(&t, 100.0);
    CHECK(t.drift == 0 && t.phase == UP_TUNER_SETTLED);
    for (int i = 0; i < 3; i++) patterned_window(&t, &stalls);
    CHECK(t.phase == UP_TUNER_BASE);
    END();
}

static void test_mean_monitor(void)
{
    BEGIN("PERF-10: repeated mean drift restarts search with unchanged tails");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 1, 1);
    const timing_pattern_t baseline = { 100, 1000, 16, 15 };
    const timing_pattern_t stalls = { 100, 1000, 16, 11 };
    patterned_window(&t, &baseline);
    for (int i = 0; i < UP_TUNER_COOLDOWN_FRAMES / UP_TUNER_SAMPLES; i++)
        patterned_window(&t, &baseline);
    for (int i = 0; i < 3; i++) patterned_window(&t, &stalls);
    CHECK(t.phase == UP_TUNER_BASE);
    END();
}

static void test_mean_early_abort(void)
{
    BEGIN("PERF-10: early abort accounts for first-four-frame stall");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 2, 4);
    window(&t, 100.0);
    for (int i = 0; i < UP_TUNER_WARMUP + 3; i++)
        up_worker_tuner_observe(&t, 100.0);
    up_worker_tuner_observe(&t, 1000.0);
    CHECK(t.phase == UP_TUNER_CONFIRM && t.current == 2);
    window(&t, 100.0);
    CHECK(t.best == 2);
    END();
}

static void test_tail_confirmation(void)
{
    static const struct { double before, after; int expected; } cases[] = {
        { 80, 100, 2 }, { 100, 80, 2 }, { 100, 100, 1 },
    };
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; i++) {
        BEGIN("PERF-10: tail guard checks both neighboring baselines");
        up_worker_tuner_t t;
        up_worker_tuner_init(&t, 2, 2);
        window(&t, cases[i].before);
        const timing_pattern_t candidate = { 50, 90, 16, 13 };
        patterned_window(&t, &candidate);
        window(&t, cases[i].after);
        CHECK(t.best == cases[i].expected);
        END();
    }
}

int main(void)
{
    test_search();
    test_confirmation();
    test_recheck();
    test_bounded_probes();
    test_invalid();
    test_mean_and_tail_selection();
    test_tail_monitor();
    test_mean_monitor();
    test_mean_early_abort();
    test_tail_confirmation();
    return test_harness_report();
}
