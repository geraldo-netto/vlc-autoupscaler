// SPDX-License-Identifier: GPL-2.0-or-later
#include <vlc_common.h>
#undef msg_Warn
#define msg_Warn(...) ((void)0)
#include <vlc_filter.h>
#include <vlc_picture.h>
#include <vlc_video_splitter.h>
#include <stdlib.h>
#include "test_harness.h"

struct filter_chain_t {
    filter_owner_t owner;
    es_format_t format;
    filter_t filter;
};

static int fail_new, fail_append, fail_picture, deleted;

static filter_chain_t *chain_new(void *object, bool change, const filter_owner_t *owner)
{
    (void)object;
    CHECK(change);
    if (fail_new) return NULL;
    filter_chain_t *chain = calloc(1, sizeof(*chain));
    if (chain) chain->owner = *owner;
    return chain;
}

static void chain_delete(filter_chain_t *chain)
{
    es_format_Clean(&chain->format);
    free(chain);
    deleted++;
}

static void chain_reset(filter_chain_t *chain, const es_format_t *input, const es_format_t *output)
{
    CHECK(input == output);
    es_format_Copy(&chain->format, input);
}

static filter_t *chain_append(filter_chain_t *chain, const char *name, const config_chain_t *config,
                              const es_format_t *input, const es_format_t *output)
{
    CHECK(strcmp(name, "autoupscale") == 0);
    CHECK(!config && !input && !output);
    if (fail_append) return NULL;
    chain->format.video.i_width = chain->format.video.i_visible_width = 1280;
    chain->format.video.i_height = chain->format.video.i_visible_height = 720;
    chain->filter.owner = chain->owner;
    return &chain->filter;
}

static const es_format_t *chain_output(const filter_chain_t *chain)
{
    return &chain->format;
}

static picture_t *chain_filter(filter_chain_t *chain, picture_t *input)
{
    picture_t *output = chain->owner.video.buffer_new(&chain->filter);
    if (output) picture_CopyProperties(output, input);
    picture_Release(input);
    return output;
}

#undef filter_chain_NewVideo
#define filter_chain_NewVideo chain_new
#define filter_chain_Delete chain_delete
#define filter_chain_Reset chain_reset
#define filter_chain_AppendFilter chain_append
#define filter_chain_GetFmtOut chain_output
#define filter_chain_VideoFilter chain_filter
#undef msg_Info
#define msg_Info(...) ((void)0)
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
