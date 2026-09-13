// SPDX-License-Identifier: GPL-2.0-or-later
#include "profile_internal.h"
static cpu_set_t affinity_mask;
static int affinity_enabled, affinity_error;
static up_worker_pool_ops_t affinity_ops;

static void affinity_spawn(void *owner, int index, pthread_t thread)
{
    (void)owner;
    (void)index;
    cpu_set_t actual;
    int rc = pthread_setaffinity_np(thread, sizeof affinity_mask, &affinity_mask);
    if (!rc) rc = pthread_getaffinity_np(thread, sizeof actual, &actual);
    if (!rc && !CPU_EQUAL(&actual, &affinity_mask)) rc = EINVAL;
    if (rc) affinity_error = rc;
}

static void affinity_config(up_worker_pool_t *pool, const up_worker_pool_ops_t *ops,
                            void *owner, int workers, size_t size)
{
    if (affinity_enabled) {
        if (!affinity_ops.run) {
            affinity_ops = *ops;
            affinity_ops.on_spawn = affinity_spawn;
        }
        ops = &affinity_ops;
    }
    up_worker_pool_config(pool, ops, owner, workers, size);
}

#define up_worker_pool_config affinity_config
#define up_worker_pool_dispatch up_profile_dispatch
#include "../src/usm_pool.c"
#undef up_worker_pool_dispatch
#undef up_worker_pool_config

int up_profile_usm_affinity(int first, int count)
{
    affinity_enabled = affinity_error = 0;
    CPU_ZERO(&affinity_mask);
    if (first < 0 || count < 0 || first >= CPU_SETSIZE) return -1;
    if (count > CPU_SETSIZE - first) return -1;
    if (!count) return 0;
    cpu_set_t allowed;
    if (sched_getaffinity(0, sizeof allowed, &allowed)) return -1;
    for (int cpu = first; cpu < first + count; cpu++) {
        if (!CPU_ISSET(cpu, &allowed)) return -1;
        CPU_SET(cpu, &affinity_mask);
    }
    affinity_enabled = 1;
    return 0;
}

int up_profile_usm_affinity_status(void) { return affinity_error; }

void up_profile_usm_mode(int mode) { up_profile_trace.mode = mode; }
void up_profile_usm_experiment(int mode)
{
    up_profile_executor_mode = mode;
}
void up_profile_usm_finish(void) { up_profile_experiment_finish(); }
up_profile_frame_t up_profile_usm_frame(void) { return up_profile_trace.frame; }

int up_profile_usm_sched(const usm_pool_t *pool, up_profile_sched_t *out)
{
    *out = (up_profile_sched_t){ 0 };
    return up_profile_pool_sched(&pool->pool, out);
}
