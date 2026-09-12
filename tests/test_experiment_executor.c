// SPDX-License-Identifier: GPL-2.0-or-later
#define UP_POOL_BARRIER_TIMEOUT_MS 200
#include "experiment_executor.h"
#include "test_harness.h"
#include <unistd.h>

static int spawn_calls, fail_spawn;
int __real_pthread_create(pthread_t *, const pthread_attr_t *, void *(*)(void *), void *);
int __wrap_pthread_create(pthread_t *thread, const pthread_attr_t *attr,
                          void *(*run)(void *), void *argument)
{
    if (++spawn_calls == fail_spawn) return EAGAIN;
    return __real_pthread_create(thread, attr, run, argument);
}

typedef struct { int cells[32]; bool slow; } fixture_t;
static void cell_run(void *owner, int cell)
{
    fixture_t *fixture = owner;
    if (fixture->slow) usleep(250000);
    fixture->cells[cell]++;
}
static const up_worker_pool_ops_t operations = { .run = cell_run };

static void test_partition(bool isolated)
{
    BEGIN("SCAL-11: changing active count processes every fixed cell exactly once");
    fixture_t fixture = {0};
    up_worker_pool_t source = { .n_workers = 32, .ops = &operations, .owner = &fixture };
    up_experiment_executor_t executor = {0};
    CHECK(up_experiment_start(&executor, &source, 8, isolated) == 0);
    const int counts[] = { 8, 2, 1, 7, 4, 8 };
    for (size_t i = 0; i < sizeof counts / sizeof *counts; i++) {
        CHECK(up_experiment_dispatch(&executor, counts[i]) == 0);
        for (int cell = 0; cell < 32; cell++) CHECK(fixture.cells[cell] == (int)i + 1);
    }
    CHECK(up_experiment_dispatch(&executor, 9) != 0);
    up_experiment_stop(&executor);
    up_experiment_stop(&executor);
    END();
}

static void test_partial_spawn(bool isolated)
{
    BEGIN("ARCH-14: partial spawn retires all started workers without running cells");
    fixture_t fixture = {0};
    up_worker_pool_t source = { .n_workers = 32, .ops = &operations, .owner = &fixture };
    up_experiment_executor_t executor = {0};
    fail_spawn = spawn_calls + 2;
    CHECK(up_experiment_start(&executor, &source, 8, isolated) != 0);
    CHECK(executor.slots == NULL);
    CHECK(executor.count == 0);
    for (int cell = 0; cell < 32; cell++) CHECK(fixture.cells[cell] == 0);
    fail_spawn = 0;
    up_experiment_stop(&executor);
    END();
}

static void test_failed_barrier(bool isolated)
{
    BEGIN("ARCH-14: timed-out dispatch joins writers before returning failure");
    fixture_t fixture = { .slow = true };
    up_worker_pool_t source = { .n_workers = 2, .ops = &operations, .owner = &fixture };
    up_experiment_executor_t executor = {0};
    CHECK(up_experiment_start(&executor, &source, 2, isolated) == 0);
    CHECK(up_experiment_dispatch(&executor, 2) != 0);
    CHECK(executor.broken);
    CHECK(executor.slots == NULL);
    CHECK(fixture.cells[0] == 1);
    CHECK(fixture.cells[1] == 1);
    CHECK(up_experiment_dispatch(&executor, 2) != 0);
    up_experiment_stop(&executor);
    END();
}

int main(void)
{
    for (int mode = 0; mode < 2; mode++) {
        test_partition(mode != 0);
        test_partial_spawn(mode != 0);
        test_failed_barrier(mode != 0);
    }
    return test_harness_report();
}
