// SPDX-License-Identifier: GPL-2.0-or-later
#include "profile_input.h"
#include "test_harness.h"
#include <unistd.h>

static void test_frames(void)
{
    BEGIN("decoded input: plane layout, successive frames and looping");
    up_profile_input_t input = { .file = tmpfile(), .frame_bytes = 96, .frames = 2 };
    CHECK(input.file != NULL);
    if (!input.file) { END(); return; }
    for (int byte = 0; byte < 192; byte++) CHECK(fputc(byte, input.file) == byte);
    zt_pic_t picture = {0};
    const int allocated = zt_pic_alloc(&picture, VLC_CODEC_I420, 8, 8);
    CHECK(allocated == 0);
    if (allocated) { fclose(input.file); END(); return; }
    CHECK(up_profile_input_read(&input, 1, &picture) == 0);
    CHECK(picture.pic.p[0].p_pixels[7] == 103);
    CHECK(picture.pic.p[1].p_pixels[0] == 160);
    CHECK(picture.pic.p[2].p_pixels[0] == 176);
    CHECK(up_profile_input_read(&input, 2, &picture) == 0);
    CHECK(picture.pic.p[0].p_pixels[0] == 0);
    input.frames = 3;
    CHECK(up_profile_input_read(&input, 2, &picture) != 0);
    zt_pic_free(&picture);
    fclose(input.file);
    END();
}

static void test_incomplete_file(void)
{
    BEGIN("decoded input: reject incomplete frames and empty files");
    char path[] = "/tmp/autoupscale-profile-input-XXXXXX";
    const int descriptor = mkstemp(path);
    CHECK(descriptor >= 0);
    if (descriptor < 0) { END(); return; }
    up_profile_input_t input = {0};
    CHECK(up_profile_input_open(&input, path, 8, 8) != 0);
    if (input.file) fclose(input.file);
    CHECK(write(descriptor, "x", 1) == 1);
    input = (up_profile_input_t){0};
    CHECK(up_profile_input_open(&input, path, 8, 8) != 0);
    if (input.file) fclose(input.file);
    close(descriptor);
    unlink(path);
    END();
}

int main(void)
{
    test_frames();
    test_incomplete_file();
    return test_harness_report();
}
