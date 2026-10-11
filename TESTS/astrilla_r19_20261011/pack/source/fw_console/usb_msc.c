// Disque USB : transport Bulk-Only et commandes SCSI. Voir usb_msc.h.
//
// Règles de transport retenues (le garde BOT du port fournit STALL) :
//  - données vers l'hôte : exactement la longueur demandée par l'hôte est envoyée, complétée
//    par des zéros si la commande en fournit moins ; le résidu de l'état dit ce qui manque ;
//  - données venant de l'hôte : tout ce qu'il annonce est lu, même si la commande échoue ;
//  - l'état (13 octets) n'est écrit qu'une fois les données acquittées, pour rester un paquet
//    à part ;
//  - un reset du bus ou Bulk-Only abandonne la commande en cours et vide les tampons.
//
// Tant que ce module ne sert pas le disque, le matériel répond à l'hôte comme un lecteur sans
// carte. usb_msc_init demande le disque ; il est accordé entre deux commandes de l'hôte, qui
// apprend l'arrivée du support par UNIT ATTENTION. Le matériel le reprend si le firmware cesse
// d'accéder au port plusieurs secondes : usb_msc_poll le redemande alors.
#include <string.h>
#include "usb_msc.h"

enum { REG_ID = 0x00, REG_STATUS = 0x04, REG_RX = 0x08, REG_TX = 0x0c, REG_COMMIT = 0x10, REG_CONTROL = 0x14,
       REG_TX4 = 0x1c, REG_RX4 = 0x20, REG_RX_COUNT = 0x24 };
enum { ST_RX = 1, ST_TX_IDLE = 2, ST_BUS_RESET = 4, ST_BOT_RESET = 8, ST_FLUSHING = 16, ST_ONLINE = 32,
       ST_HIGH_SPEED = 64, ST_LOST = 128, ST_OWNER = 256, ST_SERVE = 512, ST_HALTED = 1024 };
enum { CTL_FLUSH = 1, CTL_SERVE = 2, CTL_CLEAR_BUS_RESET = 4, CTL_CLEAR_BOT_RESET = 8, CTL_RELEASE = 32, CTL_HALT = 64, CTL_CLEAR_LOST = 128 };
enum { TX_LIMIT = 3576, STALL_MS = 3000 };   // le port accepte tant que le niveau ne dépasse pas 3 576
enum { SENSE_NONE = 0, SENSE_NOT_READY = 0x023a00, SENSE_MEDIUM_ERROR_READ = 0x031100, SENSE_MEDIUM_ERROR_WRITE = 0x030c00,
       SENSE_ILLEGAL_OPCODE = 0x052000, SENSE_LBA_RANGE = 0x052100, SENSE_ILLEGAL_FIELD = 0x052400,
       SENSE_MEDIA_CHANGED = 0x062800, SENSE_WRITE_PROTECTED = 0x072700 };
enum { BUFFER_BLOCKS = 8 };

static usb_msc_disk disk;
static usb_msc_stats stats;
static uint32_t sense, pending_attention;
static uint8_t buffer[BUFFER_BLOCKS * 512] __attribute__((aligned(4)));
static uint8_t command[31];
static unsigned command_fill;
static int recovery_required;
static uint32_t phase_bytes;

static uint32_t get32le(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static uint32_t get32be(const uint8_t *p) { return (uint32_t)p[0] << 24 | p[1] << 16 | p[2] << 8 | p[3]; }
static void put32be(uint8_t *p, uint32_t v) { p[0] = v >> 24; p[1] = v >> 16; p[2] = v >> 8; p[3] = v; }
static void put32le(uint8_t *p, uint32_t v) { p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24; }

// Un reset demandé par l'hôte, ou le disque repris par le matériel, interrompt tout transfert.
static int interrupted(uint32_t status) { return (status & (ST_BUS_RESET | ST_BOT_RESET | ST_HALTED | ST_LOST)) || !(status & ST_OWNER); }
static int reset_seen(void) { return interrupted(usb_msc_reg_read(REG_STATUS)); }
static void flush(void)
{
    usb_msc_reg_write(REG_CONTROL, CTL_FLUSH | CTL_CLEAR_BUS_RESET | CTL_CLEAR_BOT_RESET | CTL_CLEAR_LOST);
    unsigned start = usb_msc_ms();
    while ((usb_msc_reg_read(REG_STATUS) & ST_FLUSHING) && usb_msc_ms() - start < 10) {}
    command_fill = 0; phase_bytes = 0;
}
// Seul un reset hôte autorise une nouvelle commande après perte de cadrage.
// La purge locale, un changement de support ou une reprise de propriétaire
// ne constituent pas un Reset Recovery BOT.
static void quarantine(void)
{
    recovery_required=1; command_fill=0; phase_bytes=0;
    usb_msc_reg_write(REG_CONTROL,CTL_HALT | CTL_FLUSH | CTL_CLEAR_LOST);
}
static unsigned cdb_length(unsigned opcode)
{
    switch(opcode) {
    case 0x00: case 0x03: case 0x12: case 0x1a: case 0x1b: case 0x1e: return 6;
    case 0x23: case 0x25: case 0x28: case 0x2a: case 0x2f: case 0x35: case 0x5a: return 10;
    case 0x9e: return 16;
    default: return 0; // les opcodes inconnus sont refusés par short_reply
    }
}

// Émission d'une phase (données ou état). Les octets ne sont validés qu'aux multiples de
// 512 octets depuis le début de la phase, puis à sa fin : l'hôte ne voit donc un paquet court
// qu'en fin de phase, que la liaison soit en High Speed (512) ou en Full Speed (64).
// Écrit des octets vers l'hôte (source NULL : zéros). 0 : réussi.
static int send(const uint8_t *source, uint32_t count)
{
    unsigned start = usb_msc_ms();
    while (count) {
        uint32_t status = usb_msc_reg_read(REG_STATUS);
        if (interrupted(status)) return -1;
        uint32_t part = 512 - (phase_bytes & 511);
        if (part > count) part = count;
        if (TX_LIMIT - (status >> 16) < part) {
            if (usb_msc_ms() - start > STALL_MS) { ++stats.timeouts; return -1; }
            continue;
        }
        // Par mots de quatre octets (premier octet dans les bits 7:0), puis le reste octet par octet.
        uint32_t i = 0;
        for (; i + 4 <= part; i += 4) {
            uint32_t word = 0;
            if (source) memcpy(&word, source + i, 4);
            usb_msc_reg_write(REG_TX4, word);
        }
        for (; i < part; ++i) usb_msc_reg_write(REG_TX, source ? source[i] : 0);
        if (source) source += part;
        phase_bytes += part; count -= part;
        if (!(phase_bytes & 511)) usb_msc_reg_write(REG_COMMIT, 0);
        start = usb_msc_ms();
    }
    return 0;
}
// Termine la phase et attend que l'hôte ait tout pris. 0 : réussi.
static int send_done(void)
{
    if (phase_bytes & 511) usb_msc_reg_write(REG_COMMIT, 0);
    phase_bytes = 0;
    unsigned start = usb_msc_ms();
    for (;;) {
        uint32_t status = usb_msc_reg_read(REG_STATUS);
        if (interrupted(status)) return -1;
        if (status & ST_TX_IDLE) return 0;
        if (usb_msc_ms() - start > STALL_MS) { ++stats.timeouts; return -1; }
    }
}
// Lit des octets de l'hôte (destination NULL : jetés). 0 : réussi.
static int receive(uint8_t *destination, uint32_t count)
{
    unsigned start = usb_msc_ms(), idle = 0;
    while (count) {
        if (reset_seen()) return -1;
        if (count >= 4) {
            // Autant de mots de quatre octets que le port en annonce de complets.
            uint32_t words = usb_msc_reg_read(REG_RX_COUNT) / 4;
            if (words > count / 4) words = count / 4;
            if (words) {
                for (uint32_t i = 0; i < words; ++i) {
                    uint32_t word = usb_msc_reg_read(REG_RX4);
                    if (destination) { memcpy(destination, &word, 4); destination += 4; }
                }
                count -= words * 4; idle = 0; start = usb_msc_ms();
                continue;
            }
        }
        uint32_t value = usb_msc_reg_read(REG_RX);
        if (!(value & 0x80000000U)) {
            if (destination) *destination++ = (uint8_t)value;
            --count; idle = 0;
            continue;
        }
        if (++idle < 64) continue;
        idle = 0;
        if (reset_seen()) return -1;
        if (usb_msc_ms() - start > STALL_MS) { ++stats.timeouts; return -1; }
    }
    // RX_COUNT décrit les octets disponibles avant les lectures RX4. Un
    // reset peut vider le port pendant ce lot, y compris sa dernière lecture.
    // Ne jamais valider ce tampon vers disk.write sans relire l'état.
    return reset_seen() ? -1 : 0;
}

static int range_ok(uint32_t block, uint32_t count) { return block <= disk.blocks && count <= disk.blocks - block; }

// Prépare dans buffer une réponse courte ; renvoie sa longueur, ou -1 avec sense renseigné.
static int short_reply(const uint8_t *cb, unsigned cb_length)
{
    memset(buffer, 0, 64);
    switch (cb[0]) {
    case 0x03: {                                    // REQUEST SENSE
        buffer[0] = 0x70; buffer[2] = sense >> 16; buffer[7] = 10; buffer[12] = sense >> 8; buffer[13] = sense;
        sense = SENSE_NONE;
        return cb[4] < 18 ? cb[4] : 18;
    }
    case 0x12: {                                    // INQUIRY
        unsigned allocation = cb[3] << 8 | cb[4];
        int length;
        if (cb[1] & 1) {
            if (cb[2] == 0x00) { buffer[3] = 2; buffer[4] = 0x00; buffer[5] = 0x80; length = 6; }
            else if (cb[2] == 0x80) { buffer[1] = 0x80; buffer[3] = 8; memcpy(buffer + 4, "11252024", 8); length = 12; }
            else { sense = SENSE_ILLEGAL_FIELD; return -1; }
        } else {
            buffer[1] = 0x80;                       // support amovible
            buffer[2] = 0x04; buffer[3] = 0x02; buffer[4] = 31;
            memcpy(buffer + 8, "ElectrosConsole SD      1.00", 28);
            length = 36;
        }
        return (unsigned)length < allocation ? length : (int)allocation;
    }
    case 0x1a:                                      // MODE SENSE (6)
        buffer[0] = 3; buffer[2] = disk.write_protected ? 0x80 : 0;
        return cb[4] < 4 ? cb[4] : 4;
    case 0x5a: {                                    // MODE SENSE (10)
        unsigned allocation = cb[7] << 8 | cb[8];
        buffer[1] = 6; buffer[3] = disk.write_protected ? 0x80 : 0;
        return allocation < 8 ? (int)allocation : 8;
    }
    case 0x23: {                                    // READ FORMAT CAPACITIES
        unsigned allocation = cb[7] << 8 | cb[8];
        buffer[3] = 8;
        put32be(buffer + 4, disk.blocks ? disk.blocks : 0xffffffffU);
        buffer[8] = disk.blocks ? 2 : 3; buffer[10] = 2;
        return allocation < 12 ? (int)allocation : 12;
    }
    case 0x25:                                      // READ CAPACITY (10)
        if (!disk.blocks) { sense = SENSE_NOT_READY; return -1; }
        put32be(buffer, disk.blocks - 1); put32be(buffer + 4, 512);
        return 8;
    case 0x9e:                                      // READ CAPACITY (16)
        if ((cb[1] & 31) != 0x10 || cb_length < 16) { sense = SENSE_ILLEGAL_FIELD; return -1; }
        if (!disk.blocks) { sense = SENSE_NOT_READY; return -1; }
        put32be(buffer + 4, disk.blocks - 1); put32be(buffer + 8, 512);
        { uint32_t allocation = get32be(cb + 10); return allocation < 32 ? (int)allocation : 32; }
    }
    sense = SENSE_ILLEGAL_OPCODE;
    return -1;
}

// Exécute la commande reçue. Renvoie -1 si le transfert a été interrompu (pas d'état à émettre).
static int execute(void)
{
    const uint8_t *cb = command + 15;
    uint32_t tag = get32le(command + 4), host_length = get32le(command + 8), done = 0;
    int host_in = command[12] >> 7, status = 0;
    unsigned cb_length = command[14];
    stats.last_opcode = cb[0];

    // Après un changement de support, la première commande autre que INQUIRY ou
    // REQUEST SENSE échoue avec UNIT ATTENTION.
    if (pending_attention && cb[0] != 0x12 && cb[0] != 0x03) {
        sense = pending_attention; pending_attention = 0; status = 1;
    } else if (cb[0] == 0x28 || cb[0] == 0x2a) {     // READ (10), WRITE (10)
        uint32_t block = get32be(cb + 2), count = cb[7] << 8 | cb[8];
        int writing = cb[0] == 0x2a;
        if (!disk.blocks) { sense = SENSE_NOT_READY; status = 1; }
        else if (!range_ok(block, count)) { sense = SENSE_LBA_RANGE; status = 1; }
        else if (writing && disk.write_protected) { sense = SENSE_WRITE_PROTECTED; status = 1; }
        else if (count && (host_in == writing || host_length < count * 512)) status = 2;
        else while (count) {
            uint32_t part = count < BUFFER_BLOCKS ? count : BUFFER_BLOCKS;
            if (writing) {
                if (receive(buffer, part * 512)) return -1;
                done += part * 512;
                if (disk.write(disk.context, block, buffer, part)) { sense = SENSE_MEDIUM_ERROR_WRITE; status = 1; break; }
                stats.written_blocks += part;
            } else {
                if (disk.read(disk.context, block, buffer, part)) { sense = SENSE_MEDIUM_ERROR_READ; status = 1; break; }
                if (send(buffer, part * 512)) return -1;
                done += part * 512;
                stats.read_blocks += part;
            }
            block += part; count -= part;
        }
    } else if (cb[0] == 0x00 || cb[0] == 0x1b || cb[0] == 0x1e || cb[0] == 0x2f || cb[0] == 0x35) {
        // TEST UNIT READY, START STOP UNIT, PREVENT ALLOW MEDIUM REMOVAL, VERIFY (10), SYNCHRONIZE CACHE
        if (cb[0] != 0x1e && !disk.blocks) { sense = SENSE_NOT_READY; status = 1; }
        else if (cb[0] == 0x1e && (cb[4] & 1)) { sense = SENSE_ILLEGAL_FIELD; status = 1; }   // verrouillage impossible
        else if (cb[0] == 0x35 && disk.sync && disk.sync(disk.context)) { sense = SENSE_MEDIUM_ERROR_WRITE; status = 1; }
    } else {
        int length = short_reply(cb, cb_length);
        if (length < 0) status = 1;
        else if (length > 0) {
            if (!host_in && host_length) status = 2;
            else {
                uint32_t part = (uint32_t)length < host_length ? (uint32_t)length : host_length;
                if (send(buffer, part)) return -1;
                done = part;
            }
        }
    }
    // Complète la phase de données annoncée par l'hôte.
    if (done < host_length) {
        if (host_in ? send(NULL, host_length - done) : receive(NULL, host_length - done)) return -1;
    }
    if (host_in && host_length && send_done()) return -1;
    uint8_t csw[13];
    put32le(csw, 0x53425355); put32le(csw + 4, tag); put32le(csw + 8, host_length - done); csw[12] = (uint8_t)status;
    if (send(csw, 13) || send_done()) return -1;
    ++stats.commands;
    if (status) ++stats.failed;
    return 0;
}

void usb_msc_init(const usb_msc_disk *d)
{
    memset(&stats, 0, sizeof stats);
    disk = *d; sense = SENSE_NONE;
    pending_attention = d->blocks ? SENSE_MEDIA_CHANGED : 0;
    command_fill = 0; phase_bytes = 0; recovery_required = 0;
    usb_msc_reg_write(REG_CONTROL, CTL_SERVE | CTL_CLEAR_BUS_RESET | CTL_CLEAR_BOT_RESET | CTL_CLEAR_LOST);
}
void usb_msc_release(void) { usb_msc_reg_write(REG_CONTROL, CTL_RELEASE); }
int usb_msc_serving(void) { return (usb_msc_reg_read(REG_STATUS) & ST_OWNER) != 0; }
void usb_msc_media(const usb_msc_disk *d)
{
    disk = *d;
    pending_attention = d->blocks ? SENSE_MEDIA_CHANGED : SENSE_NOT_READY;
}
const usb_msc_stats *usb_msc_statistics(void) { return &stats; }
int usb_msc_online(int *high_speed)
{
    uint32_t status = usb_msc_reg_read(REG_STATUS);
    if (high_speed) *high_speed = (status & ST_HIGH_SPEED) != 0;
    return (status & ST_ONLINE) != 0;
}

int usb_msc_poll(void)
{
    uint32_t status = usb_msc_reg_read(REG_STATUS);
    if (status & (ST_BUS_RESET | ST_BOT_RESET)) {
        ++stats.resets; recovery_required=0;
        if(status & ST_OWNER)flush();
        else usb_msc_reg_write(REG_CONTROL,CTL_CLEAR_BUS_RESET | CTL_CLEAR_BOT_RESET | CTL_CLEAR_LOST);
        return 0;
    }
    if (status & ST_HALTED) recovery_required=1;
    if (recovery_required) return 0;
    if (!(status & ST_OWNER)) {
        // Pas encore accordé, ou repris par le matériel après un long silence : redemander.
        if (!(status & ST_SERVE)) {
            ++stats.takeovers;
            pending_attention = disk.blocks ? SENSE_MEDIA_CHANGED : 0;
            command_fill = 0; phase_bytes = 0;
            usb_msc_reg_write(REG_CONTROL, CTL_SERVE | CTL_CLEAR_LOST);
        }
        return 0;
    }
    if (status & ST_LOST) { ++stats.losses; ++stats.failed; quarantine(); return 0; }
    if (!(status & ST_RX)) return 0;
    // Le garde matériel valide les frontières de paquet. Ici, aucune recherche
    // de signature dans des octets parasites : le premier désaccord verrouille BOT.
    static const uint8_t signature[4] = { 0x55, 0x53, 0x42, 0x43 };
    unsigned start = usb_msc_ms();
    while (command_fill < 31) {
        uint32_t value = usb_msc_reg_read(REG_RX);
        if (value & 0x80000000U) {
            if (command_fill == 0) return 0;
            if (reset_seen()) return 0;
            if (usb_msc_ms() - start > 100) { ++stats.timeouts; ++stats.failed; quarantine(); return 0; }
            continue;
        }
        uint8_t byte = (uint8_t)value;
        if (command_fill < 4 && byte != signature[command_fill]) {
            stats.resyncs += command_fill + 1;
            ++stats.failed; quarantine(); return 1;
        } else command[command_fill++] = byte;
    }
    command_fill = 0;
    if (reset_seen()) return 0;
    unsigned required=cdb_length(command[15]);
    if (command[13] != 0 || (command[12] & 0x7f) || command[14] < 1 || command[14] > 16 ||
        (required && command[14] != required)) {
        ++stats.failed; quarantine();
        return 1;
    }
    if (execute()) {
        ++stats.failed;
        status = usb_msc_reg_read(REG_STATUS);
        if ((status & ST_OWNER) && !(status & (ST_BUS_RESET | ST_BOT_RESET))) quarantine();
    }
    return 1;
}
