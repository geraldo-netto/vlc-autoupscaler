// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef AUTOUPSCALE_LATENCY_TUNER_H
#define AUTOUPSCALE_LATENCY_TUNER_H
#include "../src/worker_tuner.h"

static inline bool up_latency_improves(up_tuner_score_t score,
                                       up_tuner_score_t baseline)
{
    return score.p99_us <= baseline.p99_us * 0.9
        && score.mean_us / 1.05 <= baseline.mean_us
        && score.p95_us / 1.05 <= baseline.p95_us;
}

static inline void up_latency_begin_trial(up_worker_tuner_t *t,
                                           up_tuner_score_t score)
{
    do {
        t->cursor = up_tuner_next_count(t->cursor, t->limit);
    } while (t->cursor && (t->cursor == t->best || t->cursor < t->best / 2));
    if (!t->cursor || t->cursor > t->best * 2) {
        up_tuner_settle(t, score);
        return;
    }
    t->base = score;
    t->candidate = t->current = t->cursor;
    t->phase = UP_TUNER_TRIAL;
}

static inline void up_latency_confirm(up_worker_tuner_t *t,
                                       up_tuner_score_t score)
{
    if (up_latency_improves(t->trial, t->base)
        && up_latency_improves(t->trial, score)) {
        t->best = t->candidate;
        t->changes++;
    }
    t->current = t->best;
    t->phase = UP_TUNER_BASE;
}

static inline void up_latency_window(up_worker_tuner_t *t,
                                      up_tuner_score_t score)
{
    switch (t->phase) {
    case UP_TUNER_BASE:
        up_latency_begin_trial(t, score);
        break;
    case UP_TUNER_TRIAL:
        t->trial = score;
        t->current = t->best;
        t->phase = UP_TUNER_CONFIRM;
        break;
    case UP_TUNER_CONFIRM:
        up_latency_confirm(t, score);
        break;
    case UP_TUNER_SETTLED:
        if (t->remaining <= UP_TUNER_RECHECK_FRAMES - 1800)
            up_tuner_monitor(t, score);
        break;
    }
}

static inline void up_latency_tuner_observe(up_worker_tuner_t *t, double elapsed)
{
    up_tuner_observe_with(t, elapsed, up_latency_window);
}
#endif
