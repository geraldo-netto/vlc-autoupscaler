// SPDX-License-Identifier: GPL-2.0-or-later
#define UP_POOL_BARRIER_TIMEOUT_MS 250
#ifdef TEST_RETIRE_ZIMG
#define ZIMG_TEST_DEFINE_MODULE_NAME
#include "zimg_test_util.h"
#include "../src/scaler_zimg.c"
#else
#include "../src/usm_pool.c"
#endif
#include "test_harness.h"

#include <errno.h>
#include <stdatomic.h>
#include <unistd.h>

static atomic_bool fail_joins;
static atomic_bool release_callbacks;
static atomic_int join_attempts;
static atomic_int entered;
static atomic_int completed;
static void (*original_run)(void *, int);

static void require_zero(int result)
{
    CHECK_EQ(result, 0);
    if (result != 0) abort();
}

int __real_pthread_join(pthread_t thread, void **result);
int __wrap_pthread_join(pthread_t thread, void **result)
{
    if (atomic_load(&fail_joins)) {
        atomic_fetch_add(&join_attempts, 1);
        return EINVAL;
    }
    return __real_pthread_join(thread, result);
}

static void pause_briefly(void)
{
    const struct timespec delay = { .tv_nsec = 1000000 };
    (void)nanosleep(&delay, NULL);
}

static void held_run(void *owner, int index)
{
    atomic_fetch_add(&entered, 1);
    while (!atomic_load(&release_callbacks)) pause_briefly();
    original_run(owner, index);
    atomic_fetch_add(&completed, 1);
}

static void *release_after_join_failures(void *unused)
{
    (void)unused;
    while (atomic_load(&join_attempts) < 2) pause_briefly();
    const struct timespec delay = { .tv_nsec = 50000000 };
    (void)nanosleep(&delay, NULL);
    atomic_store(&release_callbacks, true);
    return NULL;
}

static void hold_pool(up_worker_pool_t *pool, up_worker_pool_ops_t *ops)
{
    *ops = *pool->ops;
    original_run = ops->run;
    ops->run = held_run;
    pool->ops = ops;
    atomic_store(&fail_joins, true);
}

static void finish_probe(up_worker_pool_t *pool, pthread_t releaser, bool safe)
{
    CHECK_EQ(up_worker_pool_stop(pool), -1);
    CHECK_EQ(__real_pthread_join(releaser, NULL), 0);
    atomic_store(&fail_joins, false);
    CHECK_EQ(up_worker_pool_stop(pool), 0);
    CHECK_EQ(atomic_load(&entered), 2);
    CHECK_EQ(atomic_load(&completed), 2);
    CHECK(atomic_load(&join_attempts) >= 4);
    CHECK(safe);
}

#ifdef TEST_RETIRE_ZIMG
static void test_borrowed_frame_retirement(void)
{
    BEGIN("UB-13: zimg fatal return waits for callbacks after repeated join failure");
    zt_pic_t source, destination;
    require_zero(zt_pic_alloc(&source, VLC_CODEC_I420, 64, 64));
    require_zero(zt_pic_alloc(&destination, VLC_CODEC_I420, 128, 128));
    zt_pic_fill(&source, 42);
    scaler_ctx_t context;
    zt_ctx_init(&context, VLC_CODEC_I420, 64, 64, 128, 128, 2, 1);
    require_zero(zimg_open(&context));
    require_zero(zimg_process(&context, &source.pic, &destination.pic));
    zimg_priv_t *private = context.priv;
    up_worker_pool_ops_t ops;
    hold_pool(&private->pool, &ops);
    pthread_t releaser;
    require_zero(pthread_create(&releaser, NULL, release_after_join_failures, NULL));
    CHECK_EQ(zimg_process(&context, &source.pic, &destination.pic), SCALER_PROCESS_FATAL);
    const bool safe = atomic_load(&completed) == 2;
    finish_probe(&private->pool, releaser, safe);
    zimg_close(&context);
    zt_pic_free(&destination);
    zt_pic_free(&source);
    END();
}
#else
static void test_borrowed_frame_retirement(void)
{
    BEGIN("UB-13: USM uncertain return waits for callbacks after repeated join failure");
    uint8_t image[16 * 16] = {0};
    usm_pool_t *pool = up_usm_pool_create(2, 16, 16, 8);
    CHECK(pool != NULL);
    if (pool == NULL) abort();
    up_worker_pool_ops_t ops;
    hold_pool(&pool->pool, &ops);
    pthread_t releaser;
    require_zero(pthread_create(&releaser, NULL, release_after_join_failures, NULL));
    CHECK_EQ(up_usm_pool_apply(pool, image, 16, image, 16, 51), UP_USM_APPLY_OUTPUT_UNCERTAIN);
    const bool safe = atomic_load(&completed) == 2;
    finish_probe(&pool->pool, releaser, safe);
    up_usm_pool_destroy(pool);
    END();
}
#endif

int main(void)
{
    alarm(15);
    test_borrowed_frame_retirement();
    return test_harness_report();
}
