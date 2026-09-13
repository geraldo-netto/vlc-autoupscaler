#ifndef AUTOUPSCALE_DISPLAY_TEST_UTIL_H
#define AUTOUPSCALE_DISPLAY_TEST_UTIL_H
// SPDX-License-Identifier: GPL-2.0-or-later
#include <vlc_common.h>
#undef msg_Warn
#define msg_Warn(...) ((void)0)
#include <vlc_filter.h>
#include <vlc_picture.h>
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
    picture_t *output = fail_picture ? NULL : chain->owner.video.buffer_new(&chain->filter);
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
#endif
