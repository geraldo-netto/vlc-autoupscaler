// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef AUTOUPSCALE_PROFILE_INPUT_H
#define AUTOUPSCALE_PROFILE_INPUT_H

#include "zimg_test_util.h"
#include "cli_parse.h"
#include <stdio.h>

typedef struct {
    FILE *file;
    off_t frame_bytes, frames;
} up_profile_input_t;

static inline int up_profile_env(const char *name, long low, long high,
                                 long fallback, int *value)
{
    const char *text = getenv(name);
    long parsed = fallback;
    if (text && !up_cli_parse_long(text, low, high, &parsed)) {
        fprintf(stderr, "invalid %s\n", name);
        return -1;
    }
    *value = (int)parsed;
    return 0;
}

static inline int up_profile_input_open(up_profile_input_t *in, const char *path,
                                        int width, int height)
{
    if (!path) return 0;
    in->file = fopen(path, "rb");
    if (!in->file) return -1;
    if (fseeko(in->file, 0, SEEK_END)) return -1;
    const off_t bytes = ftello(in->file);
    in->frame_bytes = (off_t)width * height * 3 / 2;
    if (bytes <= 0 || bytes % in->frame_bytes) return -1;
    in->frames = bytes / in->frame_bytes;
    return fseeko(in->file, 0, SEEK_SET);
}

static inline int up_profile_input_read(up_profile_input_t *in, int frame,
                                        zt_pic_t *picture)
{
    if (!in->file) return 0;
    if (fseeko(in->file, ((off_t)frame % in->frames) * in->frame_bytes, SEEK_SET))
        return -1;
    for (int k = 0; k < picture->pic.i_planes; k++) {
        plane_t *plane = &picture->pic.p[k];
        const size_t width = (size_t)plane->i_visible_pitch;
        for (int y = 0; y < plane->i_visible_lines; y++)
            if (fread(plane->p_pixels + (size_t)y * (size_t)plane->i_pitch,
                       1, width, in->file) != width) return -1;
    }
    return 0;
}

#endif
