// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef AUTOUPSCALE_EXPERIMENT_EXECUTOR_H
#define AUTOUPSCALE_EXPERIMENT_EXECUTOR_H

#include "../src/worker_pool.h"

typedef struct up_experiment_executor up_experiment_executor_t;
typedef struct {
    alignas(64) up_pool_gate_t gate;
    pthread_t thread;
    up_experiment_executor_t *executor;
    int index;
    bool started;
} up_experiment_slot_t;

struct up_experiment_executor {
    up_worker_pool_t *source;
    up_pool_gate_t shared;
    up_experiment_slot_t *slots;
    int count, active;
    bool isolated, broken;
};

static inline up_pool_gate_t *up_experiment_gate(up_experiment_slot_t *slot)
{
    return slot->executor->isolated ? &slot->gate : &slot->executor->shared;
}

static inline void *up_experiment_worker(void *argument)
{
    up_experiment_slot_t *slot = argument;
    up_experiment_executor_t *e = slot->executor;
    up_pool_gate_t *gate = up_experiment_gate(slot);
    uint64_t seen = 0;
    if (pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, NULL)) {
        up__pool_gate_report_worker_failure(gate);
        return NULL;
    }
    while (up_pool_gate_wait_for_go(gate, &seen) > 0) {
        if (slot->index < e->active)
            for (int cell = slot->index; cell < e->source->n_workers; cell += e->active)
                e->source->ops->run(e->source->owner, cell);
        up_pool_gate_worker_done(gate);
    }
    return NULL;
}

static inline void up_experiment_stop(up_experiment_executor_t *e)
{
    for (int i = 0; i < e->count; i++) {
        up_experiment_slot_t *slot = &e->slots[i];
        if (!slot->started) continue;
        if (up_pool_gate_request_exit(up_experiment_gate(slot)))
            if (pthread_cancel(slot->thread)) abort();
    }
    for (int i = 0; i < e->count; i++) {
        up_experiment_slot_t *slot = &e->slots[i];
        if (slot->started && pthread_join(slot->thread, NULL)) abort();
        up_pool_gate_destroy(&slot->gate);
    }
    up_pool_gate_destroy(&e->shared);
    free(e->slots);
    e->slots = NULL;
    e->count = 0;
}

static inline int up_experiment_spawn(up_experiment_executor_t *e, int index)
{
    up_experiment_slot_t *slot = &e->slots[index];
    slot->executor = e;
    slot->index = index;
    if (e->isolated && up_pool_gate_init(&slot->gate)) return -1;
    if (pthread_create(&slot->thread, NULL, up_experiment_worker, slot)) return -1;
    slot->started = true;
    if (e->source->ops->on_spawn)
        e->source->ops->on_spawn(e->source->owner, index, slot->thread);
    return 0;
}

static inline int up_experiment_start(up_experiment_executor_t *e,
                                      up_worker_pool_t *source, int count,
                                      bool isolated)
{
    if (count < 1 || count > source->n_workers || count > UP_THREADS_MAX) return -1;
    *e = (up_experiment_executor_t){ .source = source, .isolated = isolated };
    const size_t bytes = (size_t)count * sizeof *e->slots;
    e->slots = aligned_alloc(64, bytes);
    if (!e->slots) return -1;
    memset(e->slots, 0, bytes);
    e->count = e->active = count;
    int rc = isolated ? 0 : up_pool_gate_init(&e->shared);
    for (int i = 0; !rc && i < count; i++) rc = up_experiment_spawn(e, i);
    if (rc) up_experiment_stop(e);
    return rc;
}

static inline int up_experiment_wake(up_pool_gate_t *gate, int count)
{
    if (up_pool_gate_lock(gate)) return -1;
    up_pool_gate_arm_locked(gate, count);
    return up_pool_gate_unlock_broadcast(gate);
}

static inline int up_experiment_isolated_dispatch(up_experiment_executor_t *e)
{
    int rc = 0;
    for (int i = 0; !rc && i < e->active; i++)
        rc = up_experiment_wake(&e->slots[i].gate, 1);
    for (int i = 0; !rc && i < e->active; i++)
        rc = up_pool_gate_wait_all(&e->slots[i].gate);
    return rc;
}

static inline int up_experiment_dispatch(up_experiment_executor_t *e, int active)
{
    if (e->broken || active < 1 || active > e->count) return -1;
    e->active = active;
    int rc = 0;
    if (e->isolated) rc = up_experiment_isolated_dispatch(e);
    else {
        rc = up_experiment_wake(&e->shared, e->count);
        if (!rc) rc = up_pool_gate_wait_all(&e->shared);
    }
    if (rc) {
        e->broken = true;
        up_experiment_stop(e);
    }
    return rc;
}

#endif
