# Pro Dock SD boot package

This is the SD package observed booting on **Pro Dock R6**: resident loader →
U-Boot → Linux → automatic LUMA3D startup. Boot and loading work, but are slow.
The original observation used an SRAM-loaded FPGA; persistent FPGA flash
programming is a separate step described in [Releases](../../docs/RELEASES.md).

The package includes Linux, U-Boot, LUMA, ORBITAL, and the LUMA3D executable used
in that SD boot test. The newer [MAZE executable](../luma3d-maze-20261103/README.md)
is available separately; it is not silently substituted into this tested package.

## Copy to an SD card

Use an empty FAT32 filesystem supported by the loader (MBR partition table,
first primary FAT32 partition, or a FAT32 superfloppy). Back up an existing card
before repartitioning it. These commands **copy files and do not format a disk**.

```sh
cd releases/prodock-sd
sha256sum -c SHA256SUMS
mkdir -p ../../build/sd-release
tar -xzf prodock-sd.tar.gz -C ../../build/sd-release
cd ../../build/sd-release
sha256sum -c ../../releases/prodock-sd/FILES.sha256

# Replace this with the mount point of your FAT32 SD filesystem.
SD_MOUNT=/media/$USER/PRODOCK
cp -r PRODOCK "$SD_MOUNT/"
cd "$SD_MOUNT"
sha256sum -c "$OLDPWD/../../releases/prodock-sd/FILES.sha256"
sync
```

Unmount the card using your desktop or `umount "$SD_MOUNT"`, insert it while
the Pro Dock is powered off, then start the board with the R6 FPGA configuration.
The loader reads `/PRODOCK/UBOOT.BIN`; U-Boot then loads `/PRODOCK/LINUX.BIN`.

In Linux, see [the terminal and game commands](../../docs/LINUX_CONSOLE.md).
To rebuild current Linux, U-Boot and SD files, follow
[Installation](../../docs/INSTALLATION.md). Rebuilt packages have their own
manifests; this download retains the exact files associated with the recorded
SD boot result in `MANIFEST.json`.
