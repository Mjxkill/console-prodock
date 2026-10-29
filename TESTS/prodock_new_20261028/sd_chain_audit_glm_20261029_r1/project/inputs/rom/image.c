// SPDX-License-Identifier: MIT
#include "image.h"
static uint32_t le(const uint8_t *p)
{ return p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24); }
uint32_t pd_crc(const void *data, uint32_t length)
{
    const uint8_t *p=data; uint32_t c=~0U;
    while(length--) { c^=*p++; for(unsigned b=0;b<8;++b)c=(c>>1)^(0xedb88320U&(0U-(c&1))); }
    return ~c;
}
int pd_header(const uint8_t *h, uint32_t file_size, uint32_t kind, struct pd_image *im)
{
    static const uint8_t magic[8]={'P','D','C','K','B','O','O','T'};
    uint32_t base, cap, entry;
    if(file_size<PD_HEADER || kind<PD_UBOOT || kind>PD_ORBITAL_ASSETS)return -1;
    for(unsigned i=0;i<8;++i)if(h[i]!=magic[i])return -1;
    if(le(h+8)!=1 || le(h+12)!=kind || le(h+36)!=pd_crc(h,36))return -1;
    switch(kind) {
    case PD_UBOOT:base=0x06000000;cap=0x00800000;entry=base;break;
    case PD_LINUX:base=0x07c00000;cap=0x02000000;entry=base;break;
    case PD_LUMA:case PD_ORBITAL:base=0xa0000000;cap=0x10000;entry=base+12;break;
    case PD_LUMA_ASSETS:base=0x04000000;cap=0x00800000;entry=0;break;
    default:base=0x05000000;cap=0x00800000;entry=0;break;
    }
    uint32_t size=le(h+24);
    if(le(h+16)!=base || le(h+20)!=entry || !size || size>cap ||
       size!=file_size-PD_HEADER || le(h+32)!=0x1ff ||
       (entry && (entry<base || entry-base>=size)))return -1;
    *im=(struct pd_image){kind,base,entry,size,le(h+28)};return 0;
}
