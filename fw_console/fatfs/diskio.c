// Liaison de FatFs R0.11a à la carte SD (sd.c). Un seul volume, secteurs de 512 octets.
#include "diskio.h"
#include "../sd.h"
static sd_card card;
static unsigned speed=20000000;
void disk_speed(unsigned hz) { speed=hz; }
const sd_card *disk_card(void) { return &card; }
DSTATUS disk_status(BYTE drive) { return drive || !card.ready ? STA_NOINIT : 0; }
DSTATUS disk_initialize(BYTE drive)
{
    if (drive) return STA_NOINIT;
    int status=sd_init(&card,speed);
    return status==SD_OK ? 0 : status==SD_NO_CARD ? STA_NOINIT|STA_NODISK : STA_NOINIT;
}
DRESULT disk_read(BYTE drive, BYTE *data, DWORD sector, UINT count)
{
    if (drive || !card.ready) return RES_NOTRDY;
    return sd_read(&card,sector,data,count)==SD_OK ? RES_OK : RES_ERROR;
}
DRESULT disk_write(BYTE drive, const BYTE *data, DWORD sector, UINT count)
{
    if (drive || !card.ready) return RES_NOTRDY;
    return sd_write(&card,sector,data,count)==SD_OK ? RES_OK : RES_ERROR;
}
DRESULT disk_ioctl(BYTE drive, BYTE command, void *data)
{
    if (drive || !card.ready) return RES_NOTRDY;
    switch (command) {
    case CTRL_SYNC: return RES_OK;                       // sd_write attend la fin de l'écriture
    case GET_SECTOR_COUNT: *(DWORD *)data=card.sectors; return card.sectors ? RES_OK : RES_ERROR;
    case GET_SECTOR_SIZE: *(WORD *)data=512; return RES_OK;
    case GET_BLOCK_SIZE: *(DWORD *)data=8; return RES_OK;
    default: return RES_PARERR;
    }
}
