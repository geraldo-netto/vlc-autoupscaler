// SPDX-License-Identifier: GPL-2.0-or-later
#include <vlc_common.h>
#include <vlc_filter.h>
#include <vlc_picture.h>
#include <vlc_video_splitter.h>
#ifndef UP_DISPLAY_TEST
# include <vlc_plugin.h>
#endif
#include <stdlib.h>

struct video_splitter_sys_t {
    filter_chain_t *chain;
};

static picture_t *NewPicture(filter_t *filter)
{
    video_splitter_t *splitter = filter->owner.sys;
    picture_t *pictures[1];
    if (video_splitter_NewPicture(splitter, pictures)) return NULL;
    return pictures[0];
}

static int Split(video_splitter_t *splitter, picture_t *output[], picture_t *input)
{
    output[0] = filter_chain_VideoFilter(splitter->p_sys->chain, input);
    return output[0] ? VLC_SUCCESS : VLC_EGENERIC;
}

static void CloseDisplay(vlc_object_t *object)
{
    video_splitter_t *splitter = (video_splitter_t *)object;
    if (splitter->p_sys) {
        if (splitter->p_sys->chain) filter_chain_Delete(splitter->p_sys->chain);
        free(splitter->p_sys);
    }
    if (splitter->p_output) video_format_Clean(&splitter->p_output[0].fmt);
    free(splitter->p_output);
}

static int OpenDisplay(vlc_object_t *object)
{
    video_splitter_t *splitter = (video_splitter_t *)object;
    splitter->p_sys = calloc(1, sizeof(*splitter->p_sys));
    splitter->p_output = calloc(1, sizeof(*splitter->p_output));
    if (!splitter->p_sys || !splitter->p_output) goto fail;
    filter_owner_t owner = {.sys = splitter, .video = {.buffer_new = NewPicture}};
    splitter->p_sys->chain = filter_chain_NewVideo(splitter, true, &owner);
    if (!splitter->p_sys->chain) goto fail;
    es_format_t input;
    es_format_Init(&input, VIDEO_ES, splitter->fmt.i_chroma);
    video_format_Copy(&input.video, &splitter->fmt);
    filter_chain_Reset(splitter->p_sys->chain, &input, &input);
    es_format_Clean(&input);
    if (!filter_chain_AppendFilter(splitter->p_sys->chain, "autoupscale", NULL, NULL, NULL)) goto fail;
    const es_format_t *output = filter_chain_GetFmtOut(splitter->p_sys->chain);
    video_format_Copy(&splitter->p_output[0].fmt, &output->video);
    splitter->i_output = 1;
    splitter->pf_filter = Split;
    splitter->pf_mouse = NULL;
    msg_Info(splitter, "AutoUpscale experimental display: %ux%u -> %ux%u",
        splitter->fmt.i_visible_width, splitter->fmt.i_visible_height,
        output->video.i_visible_width, output->video.i_visible_height);
    return VLC_SUCCESS;
fail:
    CloseDisplay(object);
    splitter->p_sys = NULL;
    splitter->p_output = NULL;
    return VLC_EGENERIC;
}

#ifndef UP_DISPLAY_TEST
vlc_module_begin()
    set_shortname("AutoUpscale display experiment")
    set_description("Experimental single-output AutoUpscale adapter")
    set_capability("video splitter", 0)
    set_callbacks(OpenDisplay, CloseDisplay)
    add_shortcut("autoupscale-display")
vlc_module_end()
#endif
