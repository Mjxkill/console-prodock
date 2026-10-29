# ProDock2025071717 — SD-Chain Audit Report (GLM R3, corrections du superviseur)

Method: offline, file-only audit by `audit.py` (run as `python3 -B audit.py`). No
hardware access: the board, its SD slot, memory bus and GPU are unobservable here;
`hardware_access=false`, `hardware_validated=false` and `r4_post_route_verified=false`
are reported honestly. Result summary: `checks_passed=14`, `checks_failed=2`
(both failures are R3/R4 post-route ROM verification, which are not completable
offline and are documented below). Every check below lists its evidence source;
delegated measurements are labeled as such and were never re-measured.

## 1. Inputs integrity
All 31 entries in `input_manifest.json` were re-hashed and re-sized locally:
sha256+size matched for 31/31 (including `console_test.bin` 20936 B,
`image.c` 1429 B, `UBOOT.BIN` 258140 B, `r3_rom_result.json`, `r4_candidate.json`,
`r4_ip_result.json`, `busybox.config` 38014 B, `kernel.config` 52112 B).

## 2. Boot ROM layout and decoder source (R-phase facts)
- `itcm.ld` MEMORY: ITCM 0x80000000 (64K), ILM 0xa0000000 (64K), DLM 0xa0200000
  (32K); `.nds_vector` KEEP section is first; `ENTRY(_start)`.
- Symbols: reset_vector=0x80000000, _start=0x8000000c, __data_start=0xa0000000,
  _edata=0xa0000550, _end=0xa0000b58, _heap_end=0xa0010000, _stack=0xa0207ff0,
  __data_lmastart=0x80004c78; rom_size=20936 == own read of `console_test.bin`;
  _start inside the ITCM region, _stack inside DLM; rom_available=44600
  == ITCM 64K − rom_size.
- `image.c` PDCKBOOT decoder contract: the magic is spelled in source as a declared
  8-char initializer `magic[8]={'P','D','C','K','B','O','O','T'}` — it parses to
  'PDCKBOOT' but is neither a contiguous ASCII string nor a hex constant; detection
  is semantic (found the declaration, decoded the char list). `image.h` supplies
  PD_HEADER=40, `struct pd_image {kind,load,entry,size,crc}` and `pd_crc`.
- Cross-check with the REAL supplied decoder: `inputs/rom/image.c` was compiled
  with gcc inside a TemporaryDirectory and probed; calibration pristine header
  returns rc=0 with fields (kind, load, entry, size, payload-CRC at header offset
  28) matching this audit's `validate_header`; breaking the magic field flips
  rc to -1 — a real discriminator, no bypass.

## 3. SD image headers and CRC chain (small files read whole here)
- `UBOOT.BIN`: kind=1, load=0x06000000, entry=0x06000000, size=258100, abi=0x01ff;
  header CRC field == recomputed 0x5b80e424; payload CRC own=0x36762fef ==
  manifest == `package_result.json` list; sha256 == manifest; binary_measurements
  cross-agrees on all fields.
- `LUMA.BIN`: kind=3, load=0xa0000000, entry=0xa000000c, size=27128, abi=0x01ff;
  header CRC 0x48dfcc25 recomputed; payload CRC 0x258711a0 chain agrees.
- `ORBITAL.BIN`: kind=4, load=0xa0000000, entry=0xa000000c, size=45056, abi=0x01ff;
  header CRC 0x4b5c16c1 recomputed; payload CRC 0xbb0e69ff chain agrees.

## 4. Delegated large-file measurement (never read here; supervisor-supplied)
- `LINUX.BIN` 25673840 B: hex-prefix header kind=2, load=0x07c00000,
  entry=0x07c00000, size=25673800; header CRC field 0x228d1889 recomputed
  0x228d1889; delegated payload CRC 3668906789 (0xdaaf1325) == manifest; sha256 matches
  manifest and package list.
- `LUMA.DAT`: kind=5, load=0x04000000, entry=0x00000000, size=3245216; payload
  CRC 805361842 chain agrees. `ORBITAL.DAT`: kind=6, load=0x05000000, entry=0,
  size=5781728; payload CRC 2494705352 chain agrees.
- `fw_payload.bin` 25673800 B == LINUX.BIN payload_bytes; `LUMA3D.ELF`
  sha256 a8485ce6d5e34ed46617a2b663278f14333fd20ee47396198d4296e087b76ebd ==
  supplied `GAME.SHA` digest.

## 5. Adversarial decoder probe (19 cases)
Real UBOOT.BIN header mutated across boundary cases (1 accept / 18 reject):
kind-field swap, load base ±, entry offsets, out-of-payload entry, size field,
truncation and header-CRC breaks. This audit's transcription and the compiled
REAL decoder agree on all 19 cases (disagreements: none; every reject rc≠0,
every accept rc=0 with exact field match).

## 6. U-Boot bootpath, RAM map and carveout
- `board.c`: mmc 0:1 then 0:0 fallback, read buffer 0x10000000, size limit
  PD_HEADER+0x02000000, pd_crc header gate, memcpy to im->load; file picks
  LINUX.BIN/LUMA.DAT/LUMA.BIN/ORBITAL.DAT/ORBITAL.BIN.
- `sd_boot.c`: GPU-ABI gate word 0xe9000000; loads /PRODOCK/UBOOT.BIN.
- Memory: SDRAM base 0x06000000; scratch window [0x10000000,0x1187c070)
  (max in-flight 25673840 B, including the 40-byte header); LINUX destination [0x07c00000,0x0947c048) never
  reaches scratch and starts above U-Boot monitor end 0x06800000.
- Carveout [0x00800000,0x06000000) (linux/manifest.json gpu_memory
  [8388608, 92274688]) hosts the LUMA.DAT/ORBITAL.DAT payload windows.

## 7. Linux kernel and launchers
Kernel =y options for the SD stack: MMC=1000, MMC_BLOCK=1003, MMC_SPI=1013,
VFAT_FS=1640, DEVTMPFS=580, PROC_FS=1653, SYSFS=1659, TMPFS=1660,
UNIX98_PTYS=763, BLK_DEV_INITRD=148; CONFIG_CMDLINE empty. fw_payload
load/entry 0x07c00000 lies above the carveout end.

Launchers (`launcher`, `launcher_packed`, `launcher_usb`): ILM helper loads
0xa0000000 with sizes 11856/12184/11960 B, entry 0xa000000c == load+12, fully
inside ILM [0xa0000000,0xa0010000) — validated. The stage addresses
launcher_packed=0x10000000 and launcher_usb=0x08000000 are compressed-payload
staging addresses, NOT ILM load locations; they are recorded as address-only
auxiliary JTAG records (no extent invented). The direct SD chain
ROM→U-Boot→fw_payload never executes these launchers.
Manifest flags: opt_in=True, release_qualified=False, hardware_validation=False.

## 8. Rootfs opt-in autostart
- `init` (sha verified): order selftest → prodock-autostart → `exec /sbin/init`
  (byte offsets 203 < 725 < 878).
- `prodock-autostart` (sha verified): ro+exec mount `-t vfat -o ro,exec` of
  /mnt/sd with MOUNT_ROUNDS=4 retries over partition and whole-disk targets;
  fixed game LUMA3D.ELF verified by sha256sum against $GAME_SHA and executed
  exactly once with `--festival`; kernel opt-out token `prodock.autoplay=0`
  honored; missing profile or `enabled=0` fails CLOSED (stays disabled);
  cleanup unmounts only its own mounts.
- `etc/console-autostart` is exactly 26 B: `profile=prodock/enabled=1`.
- Busybox applets required as EXACT `CONFIG_X=y` lines (line numbers in
  busybox.config): ASH 1132, CAT 221, MKDIR 294, MOUNT 670, UMOUNT 711, SLEEP 316,
  GREP 484, SHA256SUM 286, ECHO 254, TEST 336, ASH_TEST 1146, POWEROFF 504,
  UNAME 350, SYNC 328, FEATURE_SH_MATH 1192. CONFIG_ASH_TEST=y supplies the
  shell `test`/`[` builtin used by the scripts (standalone CONFIG_TEST=y is the
  separate binary at line 336).

## 9. FAT32 media
boot_sector.bin: bps=512 spc=1 resvd=32 nfats=2 rootents=0 totsec32=262144
media 0xf8 fatsz32=2017 (FAT needs 2017 sectors — equal), clusters=258078,
total 134217728 B == package file_image; sig 0x55AA; partition area
446..509 all zero; oem=mkfs.fat; ffconf _MIN_SS/_MAX_SS present at lines
162/163 with _USE_LFN=0 (long filenames disabled; boot names are valid 8.3).

## 10. Package and root proof (supplied, not re-performed)
- package manifest sha == input_manifest entry for manifest.json.
- `root_physical_install.json`: installed=True, readback_verified=True; its
  `readback` is a dict keyed by 8 file names, each {bytes, sha256}; iterated with
  `.items()` and compared against the sd manifest files: 8/8 match
  (GAME.SHA 77, LINUX.BIN 25673840, LUMA.BIN 27168, LUMA.DAT 3245256,
  LUMA3D.ELF 16649200, ORBITAL.BIN 45096, ORBITAL.DAT 5781768, UBOOT.BIN 258140).
  This is a SUPPLIED post-install root proof; no own SD read was performed.
- bootsector-implied media size 134217728 == package file_image 134217728.
- Packaging-time hardware flags: {hardware False, mounted_fat_installer_tested
  False, hardware_tested False}.

## 11. R3 — post-route VO ROM check: FAILED in the supplied post-route evidence
`r3_rom_result.json` declares the firmware sha
d8ab75277c4cb4eb2a4123fbdf269d96fa8a5cd44cb84eaa11c8e3fdf66d8ae8 but the
supplied post-route ROM image holds
4e8fb93e0215d513e3a9c7ed7d3ca2b95dbff10716bf257a1962814959ad6b2f. First
divergence at ROM byte address 0x80000029 (expected 0x22 (34 decimal), observed 0xa2 (162 decimal));
20556 of 20936 payload bytes differ; 44600 B padding with 38122 nonzero bytes.
The result is qualified POST_ROUTE_VO_ROM_INITIALIZATION_ONLY. The chain is
therefore NOT hardware-validated; `r3_post_route_rom=false` is recorded.

## 12. R4 — rebuild candidate: NO post-route ROM verification exists
`r4_candidate.json` marks verification required with new_synthesis=True;
`r4_ip_result.json` sets `rom_post_route_verification_required=True`, but no
post-route ROM hash for R4 exists, so the direct-verify step cannot run.
`r4_post_route_rom=false` (post-route proof pending in the captured inputs), `r4_post_route_verified=false`.
The R4 firmware sha d8ab75277c4cb4eb… matches the supplied direct-ROM
console_test.bin, so the rebuild target is consistent; only post-route proof
is missing.

## 13. Findings
- `gpu-carveout-write` — NOT a source bug. LUMA.DAT and ORBITAL.DAT are baremetal
  demo payloads loaded only by the separate U-Boot bootmenu alternatives
  `prodockboot luma` / `prodockboot orbital` (config.h bootmenu_1/bootmenu_2);
  the default entry `prodockboot linux` loads LINUX.BIN only, and the image()
  helper runs for exactly one selected menu entry — never concurrent with Linux.
  Their windows sit in external DDR3 (later reserved by gpu_memory), not any
  'GPU SRAM'. Recorded as an intentional alternative path.
- `r3-blocker`, `r4-pending` — see sections 11 and 12.

## 14. Limitations
- No hardware access per CONTRACT: board boot, SD media and GPU behavior are
  unobservable here; hardware_access/hardware_validated=false by design.
- Files >1MiB are never read; delegated measurements in binary_measurements.json
  and the root_install readback are SUPERVISOR-SUPPLIED measurements (large-file
  sizes, hashes, post-install proof), cross-checked here but never re-measured
  or re-performed.
- No product image is rebuilt or written; the gcc probe compiles the SUPPLIED
  decoder inside a TemporaryDirectory solely to cross-check validate_header;
  TemporaryDirectory cleans all probe artifacts.
## Revue indépendante du superviseur

Ce document corrige la copie du CRC Linux, la région de `_start` et le comptage du tampon de lecture. Le code exige maintenant les options noyau exactement `=y`, l'en-tête complet pour les fichiers dont seuls les champs mesurés ont été fournis, et ne transforme plus une mesure de CRC/SHA absente en validation. Les tests adverses du superviseur couvrent ces cas sans modifier les données originales. Le résultat matériel reste non qualifié. R4 « en attente » décrit uniquement les preuves capturées au début de cette mission, pas un suivi en direct de la compilation root.
