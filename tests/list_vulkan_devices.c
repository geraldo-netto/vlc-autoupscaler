// SPDX-License-Identifier: GPL-2.0-or-later
#include "vulkan_devices.h"
#include <stdio.h>

int main(void)
{
    unsigned indices[16];
    int count = up_vk_devices(indices);
    if (count < 0) return 1;
    putchar('[');
    for (int i = 0; i < count; i++) printf("%s%u", i ? "," : "", indices[i]);
    puts("]");
    return fflush(stdout) == EOF || ferror(stdout) ? 1 : 0;
}
