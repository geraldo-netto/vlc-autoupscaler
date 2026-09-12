// SPDX-License-Identifier: GPL-2.0-or-later
#define ZIMG_TEST_DEFINE_MODULE_NAME
#include "zimg_test_util.h"
#include "profile_stage.h"
#include "test_harness.h"
#include <sched.h>

int __wrap_sched_getaffinity(pid_t pid, size_t size, cpu_set_t *mask)
{
    (void)pid;
    if (size < sizeof *mask) return -1;
    CPU_ZERO(mask);
    for (int cpu = 0; cpu < 8; cpu++) CPU_SET(cpu, mask);
    return 0;
}

static bool pictures_equal(const zt_pic_t *left, const zt_pic_t *right)
{
    for (int k = 0; k < left->pic.i_planes; k++) {
        const plane_t *a = &left->pic.p[k], *b = &right->pic.p[k];
        for (int y = 0; y < a->i_visible_lines; y++)
            if (memcmp(a->p_pixels + (size_t)y * (size_t)a->i_pitch,
                         b->p_pixels + (size_t)y * (size_t)b->i_pitch,
                         (size_t)a->i_visible_pitch)) return false;
    }
    return true;
}

static int process(scaler_ctx_t *context, usm_pool_t *pool,
                    const zt_pic_t *source, zt_pic_t *output)
{
    if (context->backend->process(context, &source->pic, &output->pic)
          != SCALER_PROCESS_OK) return -1;
    plane_t *luma = &output->pic.p[0];
    return up_usm_pool_apply(pool, luma->p_pixels, luma->i_pitch,
                              luma->p_pixels, luma->i_pitch, 51);
}

static void check_grid(const scaler_ctx_t *context, int width)
{
    up_profile_sched_t geometry;
    CHECK(up_profile_zimg_sched(context, &geometry) == 0);
    CHECK(geometry.rows * geometry.cols == 8);
    if (width == 4096) CHECK(geometry.cols > 1);
    else CHECK(geometry.cols == 1);
}

static void compare_grid(int mode, int active, int width, int height)
{
    BEGIN("SCAL-11/ARCH-14: fixed graph scheduling preserves every output byte");
    zt_pic_t source = {0}, expected = {0}, actual = {0};
    scaler_ctx_t context = {0};
    usm_pool_t *pool = NULL;
    const int allocated = zt_pic_alloc(&source, VLC_CODEC_I420, width / 2, height / 2)
        || zt_pic_alloc(&expected, VLC_CODEC_I420, width, height)
        || zt_pic_alloc(&actual, VLC_CODEC_I420, width, height);
    CHECK(!allocated);
    if (allocated) goto cleanup;
    zt_ctx_init(&context, VLC_CODEC_I420, width / 2, height / 2, width, height, 8, 1);
    context.algo = UP_ALGO_SPLINE36;
    const int opened = context.backend->open(&context);
    CHECK(opened == 0);
    if (opened) goto cleanup;
    pool = up_usm_pool_create(8, width, height, 0);
    CHECK(pool != NULL);
    if (!pool) goto cleanup;
    for (int frame = 0; frame < 4; frame++) {
        zt_pic_fill(&source, 1234u + (uint32_t)frame);
        CHECK(process(&context, pool, &source, &expected) == 0);
        check_grid(&context, width);
        up_profile_zimg_experiment(mode, active);
        up_profile_usm_experiment(mode);
        CHECK(process(&context, pool, &source, &actual) == 0);
        CHECK(pictures_equal(&expected, &actual));
        up_profile_zimg_finish();
        up_profile_usm_finish();
    }
cleanup:
    if (context.priv) context.backend->close(&context);
    up_usm_pool_destroy(pool);
    zt_pic_free(&source);
    zt_pic_free(&expected);
    zt_pic_free(&actual);
    END();
}

int main(void)
{
    for (int mode = 1; mode <= 2; mode++) {
        compare_grid(mode, 1, 512, 256);
        compare_grid(mode, 2, 512, 256);
        compare_grid(mode, 4, 4096, 64);
    }
    return test_harness_report();
}
