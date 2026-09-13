#ifndef TEST_LIFECYCLE_VLC_COMMON_H
#define TEST_LIFECYCLE_VLC_COMMON_H

#include <stdint.h>

typedef uint32_t vlc_fourcc_t;
typedef struct vlc_object_t { int unused; } vlc_object_t;

int64_t lifecycle_var_inherit(const char *name);

static inline int64_t lifecycle_var_inherit_integer(const char *name)
{
    return lifecycle_var_inherit(name);
}

#define var_InheritInteger(obj, name) \
    ((void)(obj), lifecycle_var_inherit_integer((name)))
#define VLC_SUCCESS  0
#define VLC_EGENERIC (-1)
#define VLC_ENOMEM   (-2)

#define VLC_FOURCC(a, b, c, d) \
    ((vlc_fourcc_t)(a) | ((vlc_fourcc_t)(b) << 8) \
     | ((vlc_fourcc_t)(c) << 16) | ((vlc_fourcc_t)(d) << 24))

#define VLC_CODEC_I420  VLC_FOURCC('I', '4', '2', '0')
#define VLC_CODEC_YV12  VLC_FOURCC('Y', 'V', '1', '2')
#define VLC_CODEC_NV12  VLC_FOURCC('N', 'V', '1', '2')
#define VLC_CODEC_NV21  VLC_FOURCC('N', 'V', '2', '1')
#define VLC_CODEC_I422  VLC_FOURCC('I', '4', '2', '2')
#define VLC_CODEC_I444  VLC_FOURCC('I', '4', '4', '4')
#define VLC_CODEC_RGB24 VLC_FOURCC('R', 'V', '2', '4')
#define VLC_CODEC_RGBA  VLC_FOURCC('R', 'G', 'B', 'A')
#define VLC_CODEC_BGRA  VLC_FOURCC('B', 'G', 'R', 'A')

/* Per-level counters let tests pin the OBS-2 contract: actionable
 * degradations must log at a level VLC shows by default (Info/Err). */
static int lifecycle_dbg_count;
static int lifecycle_warn_count;
static int lifecycle_err_count;
static int lifecycle_info_count;

static inline void lifecycle_msg_sink(int *counter, void *obj, ...)
{
    (void)obj;
    (*counter)++;
}

#define msg_Dbg(obj, ...)  lifecycle_msg_sink(&lifecycle_dbg_count, (obj), __VA_ARGS__)
#define msg_Warn(obj, ...) lifecycle_msg_sink(&lifecycle_warn_count, (obj), __VA_ARGS__)
#define msg_Err(obj, ...)  lifecycle_msg_sink(&lifecycle_err_count, (obj), __VA_ARGS__)
#define msg_Info(obj, ...) lifecycle_msg_sink(&lifecycle_info_count, (obj), __VA_ARGS__)

#endif
