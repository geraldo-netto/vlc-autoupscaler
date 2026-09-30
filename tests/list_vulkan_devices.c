// SPDX-License-Identifier: GPL-2.0-or-later
#include "vulkan_devices.h"
#include "vulkan_identity.h"
#include "cli_parse.h"
#include <stdio.h>

static void json_string(const char *value)
{
    putchar('"');
    for (const unsigned char *p = (const unsigned char *)value; *p; p++) {
        if (*p == '"' || *p == '\\') { putchar('\\'); putchar(*p); }
        else if (*p < 32) printf("\\u%04x", (unsigned)*p);
        else putchar(*p);
    }
    putchar('"');
}

static int print_identity(const char *value)
{
    long index;
    if (!up_cli_parse_long(value, 0, 15, &index)) return 2;
    up_vk_identity_t identity = {0};
    if (!up_vk_identity((unsigned)index, &identity)) return 1;
    printf("{\"index\":%ld,\"vendor_id\":%u,\"device_id\":%u,\"name\":", index,
           identity.properties.vendorID, identity.properties.deviceID);
    json_string(identity.properties.deviceName);
    printf(",\"pci\":");
    if (identity.has_pci) printf("\"%04x:%02x:%02x.%x\"", identity.pci.pciDomain,
        identity.pci.pciBus, identity.pci.pciDevice, identity.pci.pciFunction);
    else printf("null");
    puts("}");
    return fflush(stdout) == EOF || ferror(stdout) ? 1 : 0;
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "--identity")) return print_identity(argv[2]);
    if (argc != 1) return 2;
    unsigned indices[16];
    int count = up_vk_devices(indices);
    if (count < 0) return 1;
    putchar('[');
    for (int i = 0; i < count; i++) printf("%s%u", i ? "," : "", indices[i]);
    puts("]");
    return fflush(stdout) == EOF || ferror(stdout) ? 1 : 0;
}
