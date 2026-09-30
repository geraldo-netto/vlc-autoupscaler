// SPDX-License-Identifier: GPL-2.0-or-later
#define UP_WORKER_POOL_TIMING 1
#include "../src/worker_pool.h"
#include "test_harness.h"
#include <errno.h>

static int fail_start, fail_dispatch, fail_clock;
static int dispatch_calls, clock_calls, destroy_calls;
static int fail_allocate, fail_spawn;

void *__real_aligned_alloc(size_t alignment, size_t size);
void *__wrap_aligned_alloc(size_t alignment, size_t size)
{
    return fail_allocate ? NULL : __real_aligned_alloc(alignment, size);
}

int __real_pthread_create(pthread_t *, const pthread_attr_t *, void *(*)(void *), void *);
int __wrap_pthread_create(pthread_t *thread, const pthread_attr_t *attr,
                         void *(*run)(void *), void *arg)
{
    return fail_spawn ? EAGAIN : __real_pthread_create(thread, attr, run, arg);
}

static int checked_start(up_worker_pool_t *pool)
{
    int result = up_worker_pool_ensure_started(pool);
    return fail_start ? -1 : result;
}

static int checked_dispatch(up_worker_pool_t *pool)
{
    dispatch_calls++;
    return dispatch_calls == fail_dispatch ? -1 : up_worker_pool_dispatch(pool);
}

static int checked_clock(clockid_t clock, struct timespec *value)
{
    clock_calls++;
    return clock_calls == fail_clock ? -1 : clock_gettime(clock, value);
}

static int checked_destroy(up_worker_pool_t *pool)
{
    destroy_calls++;
    int result = up_worker_pool_destroy(pool);
    CHECK(result == 0);
    CHECK(pool->workers == NULL && pool->threads == NULL);
    return result;
}

#define main benchmark_main
#define up_worker_pool_ensure_started checked_start
#define up_worker_pool_dispatch checked_dispatch
#define up_worker_pool_destroy checked_destroy
#define clock_gettime checked_clock
#include "bench_worker_pool.c"
#undef main

static void test_cleanup_failure(int fault)
{
    BEGIN("REV-6: benchmark error retires every initialized pool");
    fail_allocate = fault == 0;
    fail_spawn = fault == 1;
    fail_start = fault == 2;
    fail_dispatch = fault == 3 ? 1 : (fault == 4 ? 101 : 0);
    fail_clock = fault == 5 ? 101 : (fault == 6 ? 103 : 0);
    dispatch_calls = clock_calls = destroy_calls = 0;
    char *args[] = { "bench_worker_pool", fault <= 2 ? "2" : "1", "1" };
    CHECK(benchmark_main(3, args) == 1);
    CHECK(destroy_calls == 1);
    END();
}

static void test_completion_failure(void)
{
    BEGIN("REV-7: completion clock failure rejects measurement and permits next run");
    fail_start = fail_allocate = fail_spawn = fail_dispatch = 0;
    const int failures[] = { 1, 100, 102 };
    for (unsigned i = 0; i < sizeof(failures) / sizeof(failures[0]); i++) {
        fail_clock = failures[i];
        dispatch_calls = clock_calls = destroy_calls = 0;
        char *args[] = { "bench_worker_pool", "1", "1" };
        CHECK(benchmark_main(3, args) == 1);
        CHECK(destroy_calls == 1);
    }
    fail_clock = 0;
    dispatch_calls = clock_calls = destroy_calls = 0;
    char *args[] = { "bench_worker_pool", "1", "1" };
    CHECK(benchmark_main(3, args) == 0);
    CHECK(destroy_calls == 1);
    END();
}

int main(void)
{
    for (int fault = 0; fault < 7; fault++) test_cleanup_failure(fault);
    test_completion_failure();
    return test_harness_report();
}
