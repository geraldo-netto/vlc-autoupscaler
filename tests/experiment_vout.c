// SPDX-License-Identifier: GPL-2.0-or-later
#include <vlc_common.h>
#include <vlc_filter.h>
#include <vlc_modules.h>
#include <vlc_vout_display.h>
#ifndef UP_VOUT_TEST
# include <vlc_plugin.h>
#endif
#include <stdlib.h>
#include <limits.h>

struct vout_display_sys_t {
    filter_chain_t *chain;
    vout_display_t *child;
    picture_pool_t *input_pool, *output_pool;
    picture_t *prepared;
    unsigned input_width, input_height;
};

static vout_window_t *ChildWindow(vout_display_t *child, unsigned type)
{
    return vout_display_NewWindow(child->owner.sys, type);
}

static void DeleteChildWindow(vout_display_t *child, vout_window_t *window)
{
    vout_display_DeleteWindow(child->owner.sys, window);
}

static int SourceCoordinate(int value, unsigned input, unsigned output)
{
    if (!output || value <= 0) return 0;
    const uint64_t scaled = (uint64_t)(unsigned)value * input / output;
    return scaled > INT_MAX ? INT_MAX : (int)scaled;
}

static void MouseEvent(vout_display_t *child, int event, va_list args)
{
    vout_display_t *parent = child->owner.sys;
    const int x = SourceCoordinate(va_arg(args, int), parent->sys->input_width,
                                    child->source.i_width);
    const int y = SourceCoordinate(va_arg(args, int), parent->sys->input_height,
                                    child->source.i_height);
    if (event == VOUT_DISPLAY_EVENT_MOUSE_STATE)
        vout_display_SendEventMouseState(parent, x, y, va_arg(args, int));
    else vout_display_SendEventMouseMoved(parent, x, y);
}

static void ChildEvent(vout_display_t *child, int event, va_list args)
{
    vout_display_t *parent = child->owner.sys;
    switch (event) {
    case VOUT_DISPLAY_EVENT_DISPLAY_SIZE: {
        const int width = va_arg(args, int), height = va_arg(args, int);
        vout_display_SendEventDisplaySize(parent, width, height);
        break;
    }
    case VOUT_DISPLAY_EVENT_MOUSE_MOVED:
    case VOUT_DISPLAY_EVENT_MOUSE_STATE:
        MouseEvent(child, event, args);
        break;
    case VOUT_DISPLAY_EVENT_KEY:
    case VOUT_DISPLAY_EVENT_MOUSE_PRESSED:
    case VOUT_DISPLAY_EVENT_MOUSE_RELEASED:
        vout_display_SendEvent(parent, event, va_arg(args, int));
        break;
    case VOUT_DISPLAY_EVENT_VIEWPOINT_MOVED:
        vout_display_SendEventViewpointMoved(parent, va_arg(args, const vlc_viewpoint_t *));
        break;
    case VOUT_DISPLAY_EVENT_CLOSE:
    case VOUT_DISPLAY_EVENT_MOUSE_DOUBLE_CLICK:
        vout_display_SendEvent(parent, event);
        break;
    default:
        break;
    }
}

static picture_t *OutputPicture(filter_t *filter)
{
    vout_display_t *vd = filter->owner.sys;
    return vd->sys->output_pool ? picture_pool_Get(vd->sys->output_pool) : NULL;
}

static picture_pool_t *InputPool(vout_display_t *vd, unsigned count)
{
    if (!count) return NULL;
    if (!vd->sys->input_pool)
        vd->sys->input_pool = picture_pool_NewFromFormat(&vd->fmt, count);
    return vd->sys->input_pool;
}

static void Prepare(vout_display_t *vd, picture_t *picture, subpicture_t *subtitle)
{
    vout_display_sys_t *sys = vd->sys;
    sys->prepared = filter_chain_VideoFilter(sys->chain, picture_Hold(picture));
    if (sys->prepared && sys->child->prepare)
        sys->child->prepare(sys->child, sys->prepared, subtitle);
}

static void Display(vout_display_t *vd, picture_t *picture, subpicture_t *subtitle)
{
    vout_display_sys_t *sys = vd->sys;
    if (sys->prepared) sys->child->display(sys->child, sys->prepared, subtitle);
    else if (subtitle) subpicture_Delete(subtitle);
    sys->prepared = NULL;
    picture_Release(picture);
}

static unsigned ScaleCoordinate(unsigned value, unsigned input, unsigned output)
{
    if (!input) return 0;
    const uint64_t scaled = (uint64_t)value * output / input;
    return scaled > output ? output : (unsigned)scaled;
}

static void UpdateSource(vout_display_t *vd)
{
    video_format_t *to = &vd->sys->child->source;
    const video_format_t *from = &vd->source;
    to->i_sar_num = from->i_sar_num;
    to->i_sar_den = from->i_sar_den;
    to->i_x_offset = ScaleCoordinate(from->i_x_offset, vd->sys->input_width, to->i_width);
    to->i_y_offset = ScaleCoordinate(from->i_y_offset, vd->sys->input_height, to->i_height);
    to->i_visible_width = ScaleCoordinate(from->i_visible_width, vd->sys->input_width, to->i_width);
    to->i_visible_height = ScaleCoordinate(from->i_visible_height, vd->sys->input_height, to->i_height);
    if (to->i_visible_width > to->i_width - to->i_x_offset)
        to->i_visible_width = to->i_width - to->i_x_offset;
    if (to->i_visible_height > to->i_height - to->i_y_offset)
        to->i_visible_height = to->i_height - to->i_y_offset;
}

static int Control(vout_display_t *vd, int query, va_list args)
{
    vout_display_t *child = vd->sys->child;
    if (query == VOUT_DISPLAY_RESET_PICTURES) return VLC_EGENERIC;
    if (query == VOUT_DISPLAY_CHANGE_SOURCE_ASPECT || query == VOUT_DISPLAY_CHANGE_SOURCE_CROP)
        UpdateSource(vd);
    return child->control(child, query, args);
}

static void CloseVout(vlc_object_t *object)
{
    vout_display_t *vd = (vout_display_t *)object;
    vout_display_sys_t *sys = vd->sys;
    if (!sys) return;
    if (sys->prepared) picture_Release(sys->prepared);
    if (sys->chain) filter_chain_Delete(sys->chain);
    if (sys->input_pool) picture_pool_Release(sys->input_pool);
    if (sys->child) {
        if (sys->child->module) module_unneed(sys->child, sys->child->module);
        video_format_Clean(&sys->child->source);
        video_format_Clean(&sys->child->fmt);
        vlc_object_release(sys->child);
    }
    free(sys);
    vd->sys = NULL;
}

static int OpenChain(vout_display_t *vd)
{
    const filter_owner_t owner = {.sys = vd, .video = {.buffer_new = OutputPicture}};
    vd->sys->chain = filter_chain_NewVideo(vd, true, &owner);
    if (!vd->sys->chain) return VLC_EGENERIC;
    es_format_t input;
    es_format_Init(&input, VIDEO_ES, vd->fmt.i_chroma);
    video_format_Copy(&input.video, &vd->source);
    filter_chain_Reset(vd->sys->chain, &input, &input);
    es_format_Clean(&input);
    return filter_chain_AppendFilter(vd->sys->chain, "autoupscale", NULL, NULL, NULL)
           ? VLC_SUCCESS : VLC_EGENERIC;
}

static int OpenChild(vout_display_t *vd)
{
    vout_display_t *child = vlc_object_create(vd, sizeof(*child));
    if (!child) return VLC_ENOMEM;
    vd->sys->child = child;
    child->module = NULL;
    child->sys = NULL;
    child->pool = NULL;
    child->prepare = NULL;
    child->display = NULL;
    child->control = NULL;
    child->info = (vout_display_info_t){0};
    const video_format_t *format = &filter_chain_GetFmtOut(vd->sys->chain)->video;
    video_format_Copy(&child->source, format);
    video_format_Copy(&child->fmt, format);
    child->fmt.i_sar_num = child->fmt.i_sar_den = 0;
    child->cfg = vd->cfg;
    child->owner = (vout_display_owner_t){.sys = vd, .event = ChildEvent,
                      .window_new = ChildWindow, .window_del = DeleteChildWindow};
    child->module = module_need(child, "vout display", "gl", true);
    if (!child->module) return VLC_EGENERIC;
    if (child->info.has_pictures_invalid) return VLC_EGENERIC;
    video_format_t requested = *format;
    requested.i_sar_num = requested.i_sar_den = 0;
    if (!video_format_IsSimilar(&child->fmt, &requested)) return VLC_EGENERIC;
    vd->sys->output_pool = child->pool(child, 3);
    return vd->sys->output_pool ? VLC_SUCCESS : VLC_ENOMEM;
}

static int OpenVout(vlc_object_t *object)
{
    vout_display_t *vd = (vout_display_t *)object;
    if (vd->fmt.i_chroma != VLC_CODEC_I420 || vd->fmt.orientation != ORIENT_NORMAL)
        return VLC_EGENERIC;
    if (vd->fmt.i_x_offset || vd->fmt.i_y_offset) return VLC_EGENERIC;
    vd->sys = calloc(1, sizeof(*vd->sys));
    if (!vd->sys) return VLC_ENOMEM;
    vd->sys->input_width = vd->source.i_visible_width;
    vd->sys->input_height = vd->source.i_visible_height;
    if (OpenChain(vd) || OpenChild(vd)) {
        CloseVout(object);
        return VLC_EGENERIC;
    }
    vd->pool = InputPool;
    vd->prepare = Prepare;
    vd->display = Display;
    vd->control = Control;
    vd->info.subpicture_chromas = vd->sys->child->info.subpicture_chromas;
    msg_Info(vd, "AutoUpscale native vout: %ux%u -> %ux%u; stock OpenGL presentation",
        vd->source.i_visible_width, vd->source.i_visible_height,
        vd->sys->child->source.i_visible_width, vd->sys->child->source.i_visible_height);
    return VLC_SUCCESS;
}

#ifndef UP_VOUT_TEST
vlc_module_begin()
    set_shortname("AutoUpscale native vout experiment")
    set_description("Experimental video-only upscaling with a native VLC window")
    set_capability("vout display", 0)
    set_callbacks(OpenVout, CloseVout)
    add_shortcut("autoupscale-vout")
vlc_module_end()
#endif
