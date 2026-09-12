// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef AUTOUPSCALE_PIPELINE_METRICS_H
#define AUTOUPSCALE_PIPELINE_METRICS_H

#include "worker_tuner.h"
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

#define UP_METRICS_WINDOW 256
#define UP_METRICS_FIELDS 4
#ifndef UP_METRICS_CLOCK
#define UP_METRICS_CLOCK clock_gettime
#endif

enum { UP_METRICS_SCALE, UP_METRICS_USM, UP_METRICS_TOTAL, UP_METRICS_CPU };

typedef struct {
    double samples[UP_METRICS_FIELDS][UP_METRICS_WINDOW];
    uint64_t start_wall, start_cpu;
    double stage_us[2];
    unsigned attempts, failed, invalid, used;
    bool valid;
} up_pipeline_metrics_t;

static inline bool up_metrics_clock(clockid_t clock, uint64_t *value)
{
    struct timespec now;
    if (UP_METRICS_CLOCK(clock, &now) != 0) return false;
    if (now.tv_sec < 0 || now.tv_nsec < 0 || now.tv_nsec >= 1000000000L)
        return false;
    const uint64_t nanos = (uint64_t)now.tv_nsec;
    if ((uint64_t)now.tv_sec > (UINT64_MAX - nanos) / UINT64_C(1000000000))
        return false;
    *value = (uint64_t)now.tv_sec * UINT64_C(1000000000) + nanos;
    return true;
}

static inline uint64_t up_metrics_mark(up_pipeline_metrics_t *m)
{
    uint64_t now = 0;
    if (m && !up_metrics_clock(CLOCK_MONOTONIC, &now)) m->valid = false;
    return now;
}

static inline void up_metrics_begin(up_pipeline_metrics_t *m)
{
    if (!m) return;
    m->stage_us[0] = m->stage_us[1] = 0;
    m->valid = up_metrics_clock(CLOCK_MONOTONIC, &m->start_wall);
    if (!up_metrics_clock(CLOCK_PROCESS_CPUTIME_ID, &m->start_cpu))
        m->valid = false;
}

static inline void up_metrics_stage(up_pipeline_metrics_t *m, unsigned stage,
                                    uint64_t start)
{
    if (!m || stage >= 2) return;
    const uint64_t end = up_metrics_mark(m);
    if (end < start) m->valid = false;
    else m->stage_us[stage] = (double)(end - start) / 1000.0;
}

static inline void up_metrics_store(up_pipeline_metrics_t *m, uint64_t wall,
                                    uint64_t cpu)
{
    if (!m->valid || m->used >= UP_METRICS_WINDOW) return;
    m->samples[UP_METRICS_SCALE][m->used] = m->stage_us[0];
    m->samples[UP_METRICS_USM][m->used] = m->stage_us[1];
    m->samples[UP_METRICS_TOTAL][m->used] = (double)(wall - m->start_wall) / 1000.0;
    m->samples[UP_METRICS_CPU][m->used] = (double)(cpu - m->start_cpu) / 1000.0;
    m->used++;
}

static inline bool up_metrics_end(up_pipeline_metrics_t *m, bool output)
{
    if (!m) return false;
    uint64_t wall = 0, cpu = 0;
    if (!up_metrics_clock(CLOCK_MONOTONIC, &wall)) m->valid = false;
    if (!up_metrics_clock(CLOCK_PROCESS_CPUTIME_ID, &cpu)) m->valid = false;
    if (wall < m->start_wall || cpu < m->start_cpu) m->valid = false;
    m->attempts++;
    if (!output) m->failed++;
    if (!m->valid) m->invalid++;
    if (output) up_metrics_store(m, wall, cpu);
    return m->attempts >= UP_METRICS_WINDOW;
}

static inline up_tuner_score_t up_metrics_score(up_pipeline_metrics_t *m,
                                                unsigned field)
{
    if (!m->used || field >= UP_METRICS_FIELDS) return (up_tuner_score_t){0};
    return up_tuner_score(m->samples[field], (int)m->used);
}

static inline void up_metrics_reset(up_pipeline_metrics_t *m)
{
    m->attempts = m->failed = m->invalid = m->used = 0;
}

#endif
