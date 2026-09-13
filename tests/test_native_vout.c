// SPDX-License-Identifier: GPL-2.0-or-later
#include "display_test_util.h"
#include <vlc_modules.h>
#include <vlc_vout_display.h>

static int fail_child, fail_module, fail_pool, closed_modules, controls, displayed;
static int window_created, window_deleted, event_query, event_value;
static int event_x, event_y;
static vout_display_t *expected_parent;
static picture_pool_t *child_pool;
static vout_window_t fixture_window;

static void *object_new(const void *parent, size_t size)
{
    CHECK(parent == expected_parent);
    return fail_child ? NULL : calloc(1, size);
}

static picture_pool_t *module_pool(vout_display_t *child, unsigned count)
{
    if (fail_pool) return NULL;
    if (!child_pool) child_pool = picture_pool_NewFromFormat(&child->fmt, count);
    return child_pool;
}

/* VLC's callback ABI requires mutable display/window parameters. */
// cppcheck-suppress constParameterCallback
static void module_display(vout_display_t *child, picture_t *picture, subpicture_t *subtitle)
{
    CHECK(child->source.i_visible_width == 1280);
    CHECK(picture->date == 12345);
    displayed++;
    picture_Release(picture);
    if (subtitle) subpicture_Delete(subtitle);
}

static int module_control(vout_display_t *child, int query, va_list args)
{
    (void)child;
    CHECK(query == VOUT_DISPLAY_CHANGE_DISPLAY_SIZE);
    CHECK(va_arg(args, const vout_display_cfg_t *) != NULL);
    controls++;
    return VLC_SUCCESS;
}

static module_t *module_open(vout_display_t *child, const char *capability,
                              const char *name, bool strict)
{
    CHECK(strcmp(capability, "vout display") == 0);
    CHECK(strcmp(name, "gl") == 0 && strict);
    if (fail_module) return NULL;
    CHECK(vout_display_NewWindow(child, VOUT_WINDOW_TYPE_INVALID) == &fixture_window);
    child->pool = module_pool;
    child->display = module_display;
    child->control = module_control;
    return (module_t *)child;
}

static void module_close(vout_display_t *child, const module_t *module)
{
    CHECK(module == (module_t *)child);
    vout_display_DeleteWindow(child, &fixture_window);
    if (child_pool) picture_pool_Release(child_pool);
    child_pool = NULL;
    closed_modules++;
}

#undef vlc_object_create
#define vlc_object_create object_new
#undef vlc_object_release
#define vlc_object_release free
#undef module_need
#define module_need module_open
#undef module_unneed
#define module_unneed module_close
#define UP_VOUT_TEST
#include "experiment_vout.c"

const char vlc_module_name[] = "test_native_vout";

// cppcheck-suppress constParameterCallback
static vout_window_t *parent_window(vout_display_t *vd, unsigned type)
{
    CHECK(vd == expected_parent && type == VOUT_WINDOW_TYPE_INVALID);
    window_created++;
    return &fixture_window;
}

// cppcheck-suppress constParameterCallback
static void parent_delete_window(vout_display_t *vd, vout_window_t *value)
{
    CHECK(vd == expected_parent && value == &fixture_window);
    window_deleted++;
}

// cppcheck-suppress constParameterPointer
static void parent_event(vout_display_t *vd, int query, va_list args)
{
    CHECK(vd == expected_parent);
    event_query = query;
    if (query == VOUT_DISPLAY_EVENT_KEY) event_value = va_arg(args, int);
    if (query == VOUT_DISPLAY_EVENT_MOUSE_MOVED) {
        event_x = va_arg(args, int);
        event_y = va_arg(args, int);
    }
}

static void initialize(vout_display_t *vd, const vout_display_cfg_t *config)
{
    memset(vd, 0, sizeof(*vd));
    video_format_Setup(&vd->source, VLC_CODEC_I420, 320, 180, 320, 180, 1, 1);
    video_format_Copy(&vd->fmt, &vd->source);
    vd->cfg = config;
    vd->owner = (vout_display_owner_t){.window_new = parent_window,
                       .window_del = parent_delete_window, .event = parent_event};
    expected_parent = vd;
    fail_new = fail_append = fail_picture = deleted = 0;
    fail_child = fail_module = fail_pool = closed_modules = controls = displayed = 0;
    window_created = window_deleted = event_query = event_value = 0;
}

static void cleanup(vout_display_t *vd)
{
    CloseVout((vlc_object_t *)vd);
    video_format_Clean(&vd->source);
    video_format_Clean(&vd->fmt);
}

static int control_call(vout_display_t *vd, int query, ...)
{
    va_list args;
    va_start(args, query);
    const int rc = Control(vd, query, args);
    va_end(args);
    return rc;
}

static void test_native_window(void)
{
    BEGIN("REL-16: display child uses VLC's native window and forwards controls/events");
    vout_display_t vd;
    const vout_display_cfg_t config = {.display = {.width = 1280, .height = 720}};
    initialize(&vd, &config);
    const int rc = OpenVout((vlc_object_t *)&vd);
    CHECK(rc == VLC_SUCCESS);
    if (!rc) {
        CHECK(window_created == 1);
        CHECK(control_call(&vd, VOUT_DISPLAY_CHANGE_DISPLAY_SIZE, &config) == VLC_SUCCESS);
        CHECK(controls == 1);
        vout_display_SendEventKey(vd.sys->child, 42);
        CHECK(event_query == VOUT_DISPLAY_EVENT_KEY && event_value == 42);
        CHECK(vd.source.i_width == 320 && vd.sys->child->source.i_width == 1280);
    }
    cleanup(&vd);
    CHECK(window_deleted == 1 && closed_modules == 1 && deleted == 1);
    END();
}

static void check_frame(vout_display_t *vd, int fail)
{
    picture_t *input = picture_pool_Get(InputPool(vd, 3));
    CHECK(input != NULL);
    if (!input) return;
    input->date = 12345;
    picture_t *held = picture_Hold(input);
    fail_picture = fail;
    Prepare(vd, input, NULL);
    CHECK(input->date == 12345);
    Display(vd, input, NULL);
    CHECK(vd->sys->prepared == NULL);
    CHECK(held->date == 12345);
    picture_Release(held);
}

static void test_picture_ownership(void)
{
    BEGIN("REL-16: successful and failed output preserve caller picture ownership");
    vout_display_t vd;
    const vout_display_cfg_t config = {0};
    initialize(&vd, &config);
    const int rc = OpenVout((vlc_object_t *)&vd);
    CHECK(rc == VLC_SUCCESS);
    if (!rc) {
        check_frame(&vd, 0);
        check_frame(&vd, 1);
        CHECK(displayed == 1);
        CHECK(InputPool(&vd, 3) == vd.sys->input_pool);
    }
    cleanup(&vd);
    END();
}

static void test_open_failures(void)
{
    BEGIN("REL-16: chain, child, module and pool failures release owned resources");
    int *failures[] = {&fail_new, &fail_append, &fail_child, &fail_module, &fail_pool};
    for (size_t i = 0; i < sizeof failures / sizeof *failures; i++) {
        vout_display_t vd;
        const vout_display_cfg_t config = {0};
        initialize(&vd, &config);
        *failures[i] = 1;
        CHECK(OpenVout((vlc_object_t *)&vd) != VLC_SUCCESS);
        CHECK(vd.sys == NULL && child_pool == NULL);
        CHECK(window_created == window_deleted);
        cleanup(&vd);
    }
    END();
}

static void test_padded_source_and_crop(void)
{
    BEGIN("REL-16: padded source, crop and mouse mapping retain visible coordinates");
    vout_display_t vd;
    const vout_display_cfg_t config = {0};
    initialize(&vd, &config);
    vd.source.i_height = vd.fmt.i_height = 192;
    const int rc = OpenVout((vlc_object_t *)&vd);
    CHECK(rc == VLC_SUCCESS);
    if (!rc) {
        UpdateSource(&vd);
        CHECK(vd.sys->child->source.i_visible_height == 720);
        vd.source.i_x_offset = 32;
        vd.source.i_y_offset = 18;
        vd.source.i_visible_width = 256;
        vd.source.i_visible_height = 144;
        UpdateSource(&vd);
        CHECK(vd.sys->child->source.i_x_offset == 128);
        CHECK(vd.sys->child->source.i_visible_width == 1024);
        CHECK(vd.sys->child->source.i_y_offset == 72);
        CHECK(vd.sys->child->source.i_visible_height == 576);
        vout_display_SendEventMouseMoved(vd.sys->child, 128, 72);
        CHECK(event_x == 32 && event_y == 18);
    }
    cleanup(&vd);
    END();
}

int main(void)
{
    test_native_window();
    test_picture_ownership();
    test_open_failures();
    test_padded_source_and_crop();
    return test_harness_report();
}
