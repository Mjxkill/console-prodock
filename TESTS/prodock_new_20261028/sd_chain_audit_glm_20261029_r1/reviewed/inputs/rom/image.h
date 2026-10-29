/* SPDX-License-Identifier: MIT */
#ifndef PRODOCK_BOOT_IMAGE_H
#define PRODOCK_BOOT_IMAGE_H
#include <stdint.h>
#define PD_HEADER 40
struct pd_image { uint32_t kind, load, entry, size, crc; };
enum { PD_UBOOT=1, PD_LINUX, PD_LUMA, PD_ORBITAL, PD_LUMA_ASSETS, PD_ORBITAL_ASSETS };
uint32_t pd_crc(const void *data, uint32_t length);
int pd_header(const uint8_t *data, uint32_t file_size, uint32_t kind, struct pd_image *image);
#endif
