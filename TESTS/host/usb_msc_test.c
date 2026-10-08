// Firmware du disque USB (fw_console/usb_msc.c) contre un modèle du port usb_msc_port et d'un
// hôte Bulk-Only. Le modèle reprend les règles du matériel : un octet écrit n'est visible de
// l'hôte qu'après validation, l'hôte prend des paquets de min(reste validé, taille maximale),
// au plus 3 584 octets non acquittés. L'hôte ne lit pas toujours tout de suite (cadence
// pseudo-aléatoire) et vérifie le découpage : données terminées par la longueur annoncée ou
// par un paquet court, puis état de 13 octets dans un paquet à part.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "usb_msc.h"

enum { BLOCKS = 8192, QUEUE = 1 << 20 };
static uint8_t media[BLOCKS * 512], shadow[BLOCKS * 512];
static uint8_t rx[QUEUE]; static unsigned rx_head, rx_tail;
static uint8_t tx[QUEUE]; static unsigned tx_pushed, tx_committed, tx_taken;
static unsigned packet_length[8192], packets, max_packet = 512;
static unsigned status_flags = 0x60, clock_ms, host_lazy, host_stopped, lost, rng = 0x1234567;
static unsigned fail_read_at = ~0U, fail_write_at = ~0U, reset_after_packets = ~0U, grant_delay, drop_owner_after;
static unsigned reset_after_rx = ~0U, receive_reset_bit = 4;
static int checks;
#define CHECK(c) do { ++checks; if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); exit(1); } } while (0)

static unsigned rnd(void) { rng = rng * 1103515245U + 12345U; return rng >> 16 & 0x7fff; }
static void host_take(void)
{
    if (host_stopped || tx_taken == tx_committed) return;
    unsigned n = tx_committed - tx_taken; if (n > max_packet) n = max_packet;
    CHECK(packets < 8192);
    packet_length[packets++] = n; tx_taken += n;
    if (packets == reset_after_packets) { status_flags |= 4; reset_after_packets = ~0U; }
}
uint32_t usb_msc_reg_read(unsigned offset)
{
    if (offset == 0x00) return 0x554d5343;
    if (offset == 0x28) return 1;
    if (offset == 0x04) {
        if(status_flags & 12)status_flags &= ~0x400U; // seul reset hôte déverrouille le garde
        // Le matériel accorde le disque quelques lectures après la demande.
        if ((status_flags & 0x300) == 0x200 && grant_delay-- == 0) status_flags |= 0x100;
        if (drop_owner_after && --drop_owner_after == 0) status_flags &= ~0x300U;
        if (!host_lazy || rnd() % host_lazy == 0) host_take();
        unsigned level = tx_pushed - tx_taken;
        return level << 16 | (lost ? 0x80 : 0) | status_flags | (level == 0 ? 2 : 0) | (rx_head != rx_tail ? 1 : 0);
    }
    if (offset == 0x08) return rx_head == rx_tail ? 0x80000000U : rx[rx_head++];
    if (offset == 0x24) {                         // valeur prudente : parfois moins que le réel
        if (status_flags & 12) return 0;
        unsigned available = rx_tail - rx_head, less = reset_after_rx != ~0U ? 0 : rnd() % 4;
        return available > less ? available - less : 0;
    }
    if (offset == 0x20) {
        // Une purge peut intervenir après RX_COUNT : les lectures déjà
        // lancées rendent alors le registre vidé, pas les anciens octets.
        if (status_flags & 12) return 0;
        CHECK(rx_tail - rx_head >= 4);            // jamais lu sans avoir été annoncé
        uint32_t word = rx[rx_head] | rx[rx_head + 1] << 8 | rx[rx_head + 2] << 16 | (uint32_t)rx[rx_head + 3] << 24;
        rx_head += 4;
        if (rx_head >= reset_after_rx) { status_flags |= receive_reset_bit; reset_after_rx = ~0U; }
        return word;
    }
    CHECK(0); return 0;
}
void usb_msc_reg_write(unsigned offset, uint32_t value)
{
    if (offset == 0x0c) {
        if (!(status_flags & 0x100) || tx_pushed - tx_taken > 3576) lost = 1;
        else { CHECK(tx_pushed < QUEUE); tx[tx_pushed++] = (uint8_t)value; }
    } else if (offset == 0x1c) {
        if (!(status_flags & 0x100) || tx_pushed - tx_taken > 3576) lost = 1;
        else { CHECK(tx_pushed + 4 <= QUEUE); for (int i = 0; i < 4; ++i) tx[tx_pushed++] = (uint8_t)(value >> 8 * i); }
    } else if (offset == 0x10) tx_committed = tx_pushed;
    else if (offset == 0x14) {
        if (value & 1) CHECK(status_flags & 0x100);       // jamais de purge sans avoir le disque
        if (value & 2) { if (!(status_flags & 0x200)) grant_delay = 3; status_flags |= 0x200; }
        if (value & 32) status_flags &= ~0x300U;
        if (value & 64) status_flags |= 0x400U;
        if (value & 1) { rx_head = rx_tail = 0; tx_pushed = tx_committed = tx_taken = 0; packets = 0; }
        if (value & 4) status_flags &= ~4U;
        if (value & 8) status_flags &= ~8U;
        if (value & 128) lost = 0;
    } else CHECK(0);
}
// Un appel sur seize avance d'une milliseconde : un hôte lent du modèle reste loin du délai d'abandon.
unsigned usb_msc_ms(void) { static unsigned calls; if (!(++calls & 15)) ++clock_ms; return clock_ms; }

static int disk_read(void *context, uint32_t block, uint8_t *data, uint32_t count)
{
    (void)context; CHECK(block + count <= BLOCKS);
    if (fail_read_at >= block && fail_read_at < block + count) return 1;
    memcpy(data, media + block * 512, count * 512); return 0;
}
static int disk_write(void *context, uint32_t block, const uint8_t *data, uint32_t count)
{
    (void)context; CHECK(block + count <= BLOCKS);
    if (fail_write_at >= block && fail_write_at < block + count) return 1;
    memcpy(media + block * 512, data, count * 512); return 0;
}
static int synced;
static int disk_sync(void *context) { (void)context; ++synced; return 0; }
static usb_msc_disk disk = { BLOCKS, 0, NULL, disk_read, disk_write, disk_sync };

// Une transaction Bulk-Only complète vue de l'hôte. Renvoie l'état ; *residue renseigné.
static uint32_t tag = 0x1000;
static uint8_t reply[1 << 17];
static void queue_command(const uint8_t *cb, unsigned cb_length, int in, uint32_t length)
{
    uint8_t *c = rx + rx_tail;
    memset(c, 0, 31); c[0] = 0x55; c[1] = 0x53; c[2] = 0x42; c[3] = 0x43;
    ++tag; c[4] = tag; c[5] = tag >> 8; c[6] = tag >> 16; c[7] = tag >> 24;
    c[8] = length; c[9] = length >> 8; c[10] = length >> 16; c[11] = length >> 24;
    c[12] = in ? 0x80 : 0; c[14] = cb_length; memcpy(c + 15, cb, cb_length);
    rx_tail += 31;
}
static int bot(const uint8_t *cb, unsigned cb_length, int in, uint32_t length, const uint8_t *out, uint32_t *residue)
{
    CHECK(tx_taken == tx_pushed);
    if (rx_head == rx_tail) rx_head = rx_tail = 0;
    tx_pushed = tx_committed = tx_taken = 0; packets = 0;
    queue_command(cb, cb_length, in, length);
    if (!in && length) { memcpy(rx + rx_tail, out, length); rx_tail += length; }
    int handled = 0;
    for (int i = 0; i < 4 && !handled; ++i) handled = usb_msc_poll();
    CHECK(handled);
    while (tx_taken != tx_committed) host_take();
    CHECK(tx_committed == tx_pushed);
    // Découpage en paquets : données puis état.
    unsigned p = 0, data = 0;
    if (in && length) {
        for (;;) {
            CHECK(p < packets);
            unsigned n = packet_length[p++]; data += n;
            CHECK(data <= length);
            if (data == length || n < max_packet) break;
        }
        CHECK(data == length);            // ce firmware complète toujours la longueur annoncée
        memcpy(reply, tx, data);
    }
    CHECK(p + 1 == packets && packet_length[p] == 13);
    const uint8_t *s = tx + data;
    CHECK(s[0] == 0x55 && s[1] == 0x53 && s[2] == 0x42 && s[3] == 0x53);
    CHECK((uint32_t)(s[4] | s[5] << 8 | s[6] << 16 | (uint32_t)s[7] << 24) == tag);
    if (residue) *residue = s[8] | s[9] << 8 | s[10] << 16 | (uint32_t)s[11] << 24;
    CHECK(rx_head == rx_tail);            // toutes les données annoncées ont été lues
    return s[12];
}
static uint32_t request_sense(void)
{
    uint8_t cb[6] = { 0x03, 0, 0, 0, 18, 0 }; uint32_t residue;
    CHECK(bot(cb, 6, 1, 18, NULL, &residue) == 0 && residue == 0 && reply[0] == 0x70 && reply[7] == 10);
    return reply[2] << 16 | reply[12] << 8 | reply[13];
}
static int rw(int write, uint32_t block, unsigned count, uint8_t *data, uint32_t *residue)
{
    uint8_t cb[10] = { write ? 0x2a : 0x28, 0, block >> 24, block >> 16, block >> 8, block, 0, count >> 8, count, 0 };
    int status = bot(cb, 10, !write, count * 512, data, residue);
    if (!write) memcpy(data, reply, count * 512);
    return status;
}

static void suite(void)
{
    uint32_t residue; uint8_t cb[16]; static uint8_t data[128 * 512];
    // Le disque est demandé puis accordé par le matériel ; rien n'est lu avant.
    status_flags &= ~0x300U;
    usb_msc_init(&disk);
    CHECK((status_flags & 0x300) == 0x200 && !usb_msc_serving());
    rx_head = rx_tail = 0; memset(cb, 0, 16); queue_command(cb, 6, 0, 0);
    CHECK(usb_msc_poll() == 0 && usb_msc_poll() == 0 && rx_head == 0);
    for (int i = 0; i < 8 && !usb_msc_serving(); ++i) usb_msc_poll();
    CHECK(usb_msc_serving());
    rx_head = rx_tail = 0;
    // Identification et capacité, comme les demande Linux.
    memset(cb, 0, 16); cb[0] = 0x12; cb[4] = 36;
    CHECK(bot(cb, 6, 1, 36, NULL, &residue) == 0 && residue == 0);
    CHECK(reply[0] == 0 && reply[1] == 0x80 && reply[4] == 31 && !memcmp(reply + 8, "Electros", 8) && !memcmp(reply + 16, "Console SD", 10));
    cb[4] = 255;                                         // l'hôte annonce 255, la réponse fait 36
    CHECK(bot(cb, 6, 1, 255, NULL, &residue) == 0 && residue == 255 - 36 && reply[36] == 0 && reply[254] == 0);
    cb[1] = 1; cb[2] = 0x80; cb[4] = 64;
    CHECK(bot(cb, 6, 1, 64, NULL, &residue) == 0 && residue == 52 && !memcmp(reply + 4, "11252024", 8));
    cb[2] = 0x83;
    CHECK(bot(cb, 6, 1, 64, NULL, &residue) == 1 && residue == 64 && request_sense() == 0x052400);
    memset(cb, 0, 16);                                                                  // TEST UNIT READY
    CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 1 && request_sense() == 0x062800);        // le support vient d'arriver
    CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 0 && residue == 0);
    cb[0] = 0x25;
    CHECK(bot(cb, 10, 1, 8, NULL, &residue) == 0 && residue == 0);
    CHECK(reply[0] == 0 && reply[1] == 0 && reply[2] == (BLOCKS - 1) >> 8 && reply[3] == ((BLOCKS - 1) & 255) && reply[6] == 2 && reply[7] == 0);
    memset(cb, 0, 16); cb[0] = 0x23; cb[8] = 252;
    CHECK(bot(cb, 10, 1, 252, NULL, &residue) == 0 && residue == 240 && reply[3] == 8 && reply[8] == 2 && reply[10] == 2);
    memset(cb, 0, 16); cb[0] = 0x1a; cb[2] = 0x3f; cb[4] = 192;
    CHECK(bot(cb, 6, 1, 192, NULL, &residue) == 0 && residue == 188 && reply[0] == 3 && reply[2] == 0);
    memset(cb, 0, 16); cb[0] = 0x5a; cb[2] = 0x3f; cb[8] = 192;
    CHECK(bot(cb, 10, 1, 192, NULL, &residue) == 0 && residue == 184 && reply[1] == 6);
    memset(cb, 0, 16); cb[0] = 0x9e; cb[1] = 0x10; cb[13] = 32;
    CHECK(bot(cb, 16, 1, 32, NULL, &residue) == 0 && residue == 0 && reply[6] == (BLOCKS - 1) >> 8 && reply[10] == 2);
    memset(cb, 0, 16); cb[0] = 0x1e; cb[4] = 1;
    CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 1 && request_sense() == 0x052400);
    cb[4] = 0; CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 0);
    memset(cb, 0, 16); cb[0] = 0x1b; cb[4] = 1; CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 0);
    memset(cb, 0, 16); cb[0] = 0x35; synced = 0; CHECK(bot(cb, 10, 0, 0, NULL, &residue) == 0 && synced == 1);
    // Écritures et lectures de tailles variées, vérifiées contre une copie.
    static const unsigned sizes[] = { 1, 2, 7, 8, 9, 16, 31, 64, 128 };
    for (unsigned round = 0; round < 60; ++round) {
        unsigned count = sizes[rnd() % 9], block = rnd() % (BLOCKS - count + 1);
        if (round == 0) block = 0;
        if (round == 1) block = BLOCKS - count;
        if (rnd() & 1) {
            for (unsigned i = 0; i < count * 512; ++i) data[i] = (uint8_t)rnd();
            memcpy(shadow + block * 512, data, count * 512);
            CHECK(rw(1, block, count, data, &residue) == 0 && residue == 0);
        } else {
            memset(data, 0xee, sizeof data);
            CHECK(rw(0, block, count, data, &residue) == 0 && residue == 0);
            CHECK(!memcmp(data, shadow + block * 512, count * 512));
        }
    }
    CHECK(!memcmp(media, shadow, sizeof media));
    // L'hôte annonce plus que la commande : complément de zéros et résidu.
    { uint8_t c[10] = { 0x28, 0, 0, 0, 0, 5, 0, 0, 2, 0 };
      CHECK(bot(c, 10, 1, 4 * 512, NULL, &residue) == 0 && residue == 2 * 512 && !memcmp(reply, shadow + 5 * 512, 1024) && reply[1024] == 0 && reply[2047] == 0); }
    // Erreurs : hors capacité, opcode inconnu, sens ou longueur incohérents.
    CHECK(rw(0, BLOCKS - 1, 2, data, &residue) == 1 && residue == 1024 && request_sense() == 0x052100);
    CHECK(rw(1, BLOCKS, 1, data, &residue) == 1 && residue == 512 && request_sense() == 0x052100);
    CHECK(!memcmp(media, shadow, sizeof media));
    memset(cb, 0, 16); cb[0] = 0xa8;
    CHECK(bot(cb, 12, 1, 4096, NULL, &residue) == 1 && residue == 4096 && request_sense() == 0x052000);
    CHECK(request_sense() == 0);
    { uint8_t c[10] = { 0x28, 0, 0, 0, 0, 0, 0, 0, 1, 0 };
      CHECK(bot(c, 10, 0, 512, data, &residue) == 2 && residue == 512);          // lecture annoncée en sortie
      CHECK(bot(c, 10, 1, 0, NULL, &residue) == 2);                             // sans phase de données
      c[8] = 4; CHECK(bot(c, 10, 1, 512, NULL, &residue) == 2 && residue == 512); // trop court
      c[0] = 0x2a; c[8] = 1; CHECK(bot(c, 10, 1, 512, NULL, &residue) == 2 && residue == 512); }
    CHECK(!memcmp(media, shadow, sizeof media));
    // Défauts du support.
    fail_read_at = 1000;
    CHECK(rw(0, 990, 16, data, &residue) == 1 && residue == 8 * 512);
    CHECK(!memcmp(data, shadow + 990 * 512, 8 * 512) && data[8 * 512] == 0 && data[16 * 512 - 1] == 0);
    CHECK(request_sense() == 0x031100);
    fail_read_at = ~0U; fail_write_at = 2000;
    CHECK(rw(1, 2000, 4, data, &residue) == 1 && request_sense() == 0x030c00);
    fail_write_at = ~0U;
    CHECK(!memcmp(media, shadow, sizeof media));
    // Protection en écriture, retrait puis insertion du support.
    disk.write_protected = 1; usb_msc_media(&disk);
    memset(cb, 0, 16);
    CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 1 && request_sense() == 0x062800);
    CHECK(rw(1, 3, 1, data, &residue) == 1 && residue == 512 && request_sense() == 0x072700);
    cb[0] = 0x1a; cb[4] = 4; CHECK(bot(cb, 6, 1, 4, NULL, &residue) == 0 && reply[2] == 0x80);
    disk.write_protected = 0; disk.blocks = 0; usb_msc_media(&disk);
    memset(cb, 0, 16);
    CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 1 && request_sense() == 0x023a00);
    CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 1 && request_sense() == 0x023a00);
    cb[0] = 0x25; CHECK(bot(cb, 10, 1, 8, NULL, &residue) == 1 && residue == 8 && request_sense() == 0x023a00);
    CHECK(rw(0, 0, 1, data, &residue) == 1 && request_sense() == 0x023a00);
    disk.blocks = BLOCKS; usb_msc_media(&disk);
    memset(cb, 0, 16);
    CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 1 && request_sense() == 0x062800);
    CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 0);
    CHECK(!memcmp(media, shadow, sizeof media));
    // Octets parasites : verrouillage jusqu'au reset BOT, jamais de recherche
    // d'une signature pouvant transformer le suffixe en commande d'écriture.
    { unsigned before = usb_msc_statistics()->resyncs;
      static const uint8_t junk[9] = { 0, 0x55, 0x55, 0x53, 0x42, 0x99, 0x55, 0x53, 0x10 };
      CHECK(rx_head == rx_tail); rx_head = rx_tail = 0; memcpy(rx, junk, 9); rx_tail = 9;
      memset(cb, 0, 16); queue_command(cb, 6, 0, 0);
      tx_pushed = tx_committed = tx_taken = 0; packets = 0;
      int handled = 0; for (int i = 0; i < 4 && !handled; ++i) handled = usb_msc_poll();
      while (tx_taken != tx_committed) host_take();
      CHECK(handled && packets == 0 && (status_flags & 0x400) && usb_msc_statistics()->resyncs == before + 1);
      CHECK(usb_msc_poll()==0 && tx_pushed==0);
      status_flags|=8;CHECK(usb_msc_poll()==0 && !(status_flags & 0x400)); }
    // Reset du bus au milieu d'une lecture : abandon, purge, puis commande suivante normale.
    { unsigned before = usb_msc_statistics()->resets;
      uint8_t c[10] = { 0x28, 0, 0, 0, 0, 0, 0, 0, 64, 0 };
      rx_head = rx_tail = 0; tx_pushed = tx_committed = tx_taken = 0; packets = 0;
      queue_command(c, 10, 1, 64 * 512); reset_after_packets = 10;
      CHECK(usb_msc_poll() == 1);
      CHECK(status_flags & 4);
      CHECK(usb_msc_poll() == 0 && !(status_flags & 4) && usb_msc_statistics()->resets == before + 1 && tx_pushed == 0);
      CHECK(rw(0, 17, 3, data, &residue) == 0 && !memcmp(data, shadow + 17 * 512, 3 * 512)); }
    // Reset pendant WRITE : RX_COUNT a annoncé tout le lot, mais RX4 est
    // purgé pendant sa lecture. Aucune donnée partielle ne doit atteindre
    // le support, même sans nouvelle attente dans receive().
    for (unsigned reset_bit = 4; reset_bit <= 8; reset_bit *= 2) {
      uint8_t c[10] = { 0x2a, 0, 0, 0, 0, 23, 0, 0, 8, 0 };
      rx_head = rx_tail = 0; tx_pushed = tx_committed = tx_taken = 0; packets = 0;
      queue_command(c, 10, 0, 4096); memset(rx + rx_tail, 0xa5, 4096); rx_tail += 4096;
      unsigned before = usb_msc_statistics()->written_blocks;
      reset_after_rx = 31 + 128; receive_reset_bit = reset_bit;
      CHECK(usb_msc_poll() == 1 && (status_flags & reset_bit));
      CHECK(usb_msc_statistics()->written_blocks == before);
      CHECK(!memcmp(media, shadow, sizeof media));
      CHECK(usb_msc_poll() == 0 && !(status_flags & reset_bit));
      CHECK(rw(0, 23, 8, data, &residue) == 0 && !memcmp(data, shadow + 23 * 512, 4096));
    }
    // Hôte qui cesse de lire : abandon après délai, purge, compteur.
    { unsigned before = usb_msc_statistics()->timeouts;
      uint8_t c[10] = { 0x28, 0, 0, 0, 0, 0, 0, 0, 64, 0 };
      rx_head = rx_tail = 0; tx_pushed = tx_committed = tx_taken = 0; packets = 0;
      queue_command(c, 10, 1, 64 * 512); host_stopped = 1;
      CHECK(usb_msc_poll() == 1 && usb_msc_statistics()->timeouts == before + 1 && tx_pushed == 0);
      host_stopped = 0;
      CHECK(status_flags & 0x400);status_flags|=8;CHECK(usb_msc_poll()==0);
      CHECK(rw(0, 40, 2, data, &residue) == 0 && !memcmp(data, shadow + 40 * 512, 1024)); }
    // Disque repris par le matériel (firmware resté muet) : redemandé, puis annoncé à l'hôte.
    { unsigned before = usb_msc_statistics()->takeovers;
      status_flags &= ~0x300U;
      CHECK(usb_msc_poll() == 0 && usb_msc_statistics()->takeovers == before + 1 && (status_flags & 0x200));
      for (int i = 0; i < 8 && !usb_msc_serving(); ++i) usb_msc_poll();
      CHECK(usb_msc_serving());
      memset(cb, 0, 16);
      CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 1 && request_sense() == 0x062800);
      CHECK(rw(0, 77, 5, data, &residue) == 0 && !memcmp(data, shadow + 77 * 512, 5 * 512)); }
    // Disque repris au milieu d'une lecture : abandon sans purge, puis reprise normale.
    { uint8_t c[10] = { 0x28, 0, 0, 0, 0, 0, 0, 0, 64, 0 };
      rx_head = rx_tail = 0; tx_pushed = tx_committed = tx_taken = 0; packets = 0;
      unsigned failed = usb_msc_statistics()->failed;
      queue_command(c, 10, 1, 64 * 512); host_stopped = 1; drop_owner_after = 30;
      CHECK(usb_msc_poll() == 1 && usb_msc_statistics()->failed == failed + 1 && !(status_flags & 0x300));
      rx_head = rx_tail = 0; tx_pushed = tx_committed = tx_taken = 0; host_stopped = 0;
      for (int i = 0; i < 8 && !usb_msc_serving(); ++i) usb_msc_poll();
      CHECK(usb_msc_serving());
      memset(cb, 0, 16);
      CHECK(bot(cb, 6, 0, 0, NULL, &residue) == 1 && request_sense() == 0x062800);
      CHECK(rw(0, 9, 3, data, &residue) == 0 && !memcmp(data, shadow + 9 * 512, 3 * 512)); }
    usb_msc_release();
    CHECK(!(status_flags & 0x300) && !usb_msc_serving());
    CHECK(!lost && usb_msc_statistics()->losses == 0);
}

int main(void)
{
    for (unsigned i = 0; i < sizeof media; ++i) media[i] = shadow[i] = (uint8_t)(i * 7 + i / 512);
    static const unsigned packet_sizes[2] = { 512, 64 }, laziness[3] = { 0, 3, 40 };
    for (unsigned s = 0; s < 2; ++s) for (unsigned l = 0; l < 3; ++l) {
        max_packet = packet_sizes[s]; host_lazy = laziness[l];
        status_flags = s ? 0x20 : 0x60; lost = 0;
        suite();
        const usb_msc_stats *st = usb_msc_statistics();
        printf("paquets de %3u, hôte %s : %u commandes dont %u refusées, %u blocs lus, %u écrits\n", max_packet,
               l == 0 ? "immédiat" : l == 1 ? "irrégulier" : "lent", st->commands, st->failed, st->read_blocks, st->written_blocks);
    }
    printf("USB MSC HOST PASS %d contrôles\n", checks);
    return 0;
}
