// SPDX-License-Identifier: GPL-2.0-or-later
#include "display_test_util.h"
#include <vlc_video_splitter.h>
#define UP_DISPLAY_TEST
#include "experiment_display.c"

const char vlc_module_name[] = "test_display_adapter";

static int picture_new(video_splitter_t *splitter, picture_t *pictures[])
{
    if (fail_picture) return VLC_EGENERIC;
    pictures[0] = picture_NewFromFormat(&splitter->p_output[0].fmt);
    return pictures[0] ? VLC_SUCCESS : VLC_ENOMEM;
}

static void init(video_splitter_t *splitter)
{
    memset(splitter, 0, sizeof(*splitter));
    video_format_Setup(&splitter->fmt, VLC_CODEC_I420, 320, 180, 320, 180, 1, 1);
    splitter->pf_picture_new = picture_new;
    fail_new = fail_append = fail_picture = deleted = 0;
}

static void test_geometry_and_lifetime(void)
{
    BEGIN("REL-16 prototype: single enlarged output preserves picture ownership and timestamp");
    video_splitter_t splitter;
    init(&splitter);
    CHECK(OpenDisplay((vlc_object_t *)&splitter) == VLC_SUCCESS);
    if (!splitter.p_sys) { video_format_Clean(&splitter.fmt); END(); return; }
    CHECK(splitter.i_output == 1);
    CHECK(splitter.p_output[0].fmt.i_visible_width == 1280);
    CHECK(splitter.p_output[0].fmt.i_visible_height == 720);
    CHECK(splitter.fmt.i_visible_width == 320 && splitter.fmt.i_visible_height == 180);
    picture_t *input = picture_NewFromFormat(&splitter.fmt);
    CHECK(input != NULL);
    if (input) {
        picture_t *output[1];
        input->date = 12345;
        CHECK(Split(&splitter, output, input) == VLC_SUCCESS);
        if (output[0]) {
            CHECK(output[0]->date == 12345);
            picture_Release(output[0]);
        }
    }
    CloseDisplay((vlc_object_t *)&splitter);
    CHECK(deleted == 1);
    video_format_Clean(&splitter.fmt);
    END();
}

static void test_open_failure(void)
{
    BEGIN("REL-16 prototype: failed chains release every owned allocation");
    video_splitter_t splitter;
    init(&splitter);
    fail_new = 1;
    CHECK(OpenDisplay((vlc_object_t *)&splitter) != VLC_SUCCESS);
    CHECK(!splitter.p_sys && !splitter.p_output && deleted == 0);
    fail_new = 0; fail_append = 1;
    CHECK(OpenDisplay((vlc_object_t *)&splitter) != VLC_SUCCESS);
    CHECK(!splitter.p_sys && !splitter.p_output && deleted == 1);
    video_format_Clean(&splitter.fmt);
    END();
}

static void test_picture_failure(void)
{
    BEGIN("REL-16 prototype: allocation failure drops and consumes its input");
    video_splitter_t splitter;
    init(&splitter);
    CHECK(OpenDisplay((vlc_object_t *)&splitter) == VLC_SUCCESS);
    if (!splitter.p_sys) { video_format_Clean(&splitter.fmt); END(); return; }
    fail_picture = 1;
    picture_t *input = picture_NewFromFormat(&splitter.fmt);
    CHECK(input != NULL);
    if (input) {
        picture_t *output[1];
        picture_t *held = picture_Hold(input);
        CHECK(Split(&splitter, output, input) != VLC_SUCCESS);
        CHECK(output[0] == NULL);
        picture_Release(held);
    }
    CloseDisplay((vlc_object_t *)&splitter);
    CHECK(deleted == 1);
    video_format_Clean(&splitter.fmt);
    END();
}

int main(void)
{
    test_geometry_and_lifetime();
    test_open_failure();
    test_picture_failure();
    return test_harness_report();
}
