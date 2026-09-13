// SPDX-License-Identifier: GPL-2.0-or-later
#include "latency_tuner.h"
#include "test_harness.h"

static void window(up_worker_tuner_t *t, double fast, double slow)
{
    const int frames = t->warmup + UP_TUNER_SAMPLES - t->used;
    for (int i = 0; i < frames; i++)
        up_latency_tuner_observe(t, t->used == UP_TUNER_SAMPLES - 1 ? slow : fast);
}

static void test_neighbor_search(void)
{
    BEGIN("PERF-15: latency trials start near incumbent and remain bounded");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 12, 32);
    window(&t, 100, 100);
    CHECK(t.current == 8);
    for (int i = 0; i < 1000; i++) {
        CHECK(t.current >= 6 && t.current <= 24);
        up_latency_tuner_observe(&t, 100);
    }
    CHECK(t.phase == UP_TUNER_SETTLED && t.best == 12);
    END();
}

static void test_latency_confirmation(void)
{
    static const struct { double fast, tail, confirm; int best; } cases[] = {
        {100, 120, 150, 4}, {80, 140, 150, 8},
        {107, 120, 150, 8}, {100, 120, 120, 8},
    };
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; i++) {
        BEGIN("PERF-15: confirm p99 gain with mean and p95 guards");
        up_worker_tuner_t t;
        up_worker_tuner_init(&t, 8, 8);
        window(&t, 100, 150);
        window(&t, cases[i].fast, cases[i].tail);
        window(&t, 100, cases[i].confirm);
        CHECK(t.best == cases[i].best);
        END();
    }
}

static void test_settled_dwell(void)
{
    BEGIN("PERF-15: hold settlement for 1800 frames before drift recheck");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 8, 16);
    t.warmup = 0;
    up_tuner_settle(&t, (up_tuner_score_t){100,100,100});
    for (int i = 0; i < 1799; i++) up_latency_tuner_observe(&t, 200);
    CHECK(t.phase == UP_TUNER_SETTLED);
    for (int i = 0; i < 3; i++) window(&t, 200, 200);
    CHECK(t.phase == UP_TUNER_BASE);
    END();
}

static void test_invalid_and_periodic(void)
{
    BEGIN("PERF-15: retain invalid-sample and periodic-recheck contracts");
    up_worker_tuner_t t;
    up_worker_tuner_init(&t, 1, 1);
    up_latency_tuner_observe(&t, NAN);
    CHECK(t.used == 0 && t.warmup == UP_TUNER_WARMUP);
    window(&t, 100, 100);
    for (int i = 0; i < UP_TUNER_RECHECK_FRAMES; i++)
        up_latency_tuner_observe(&t, 100);
    CHECK(t.phase == UP_TUNER_BASE);
    END();
}

int main(void)
{
    test_neighbor_search();
    test_latency_confirmation();
    test_settled_dwell();
    test_invalid_and_periodic();
    return test_harness_report();
}
