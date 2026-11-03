# Immutable Linux test fixture

`mmc_spi.c` is the unmodified Linux 6.12.112 `drivers/mmc/host/mmc_spi.c`,
SHA-256 `33997892d8f86f31d774959a375b05705b96c8c8d75f9c64f95def9237318b3c`.
Its upstream license and notices are preserved. This vendor fixture is exempt
from the project's maintained-code line limit.

The clock-order regression extracts the real function, applies the project
patch in a temporary directory, and tests the original and patched behavior.
Keeping this fixed input allows regressions to run before downloading/building
Linux; the production driver still comes from the pinned upstream source archive.
