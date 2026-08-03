# U-Boot patches for the JetHome vendor U-Boot (JetHub D3-mini / j310)

This directory is version-scoped for the git-pinned vendor U-Boot 2023.01 used
by `jethub_j310_defconfig`:

    BR2_TARGET_UBOOT_CUSTOM_GIT=y
    BR2_TARGET_UBOOT_CUSTOM_REPO_URL="https://github.com/jethome-iot/u-boot"
    BR2_TARGET_UBOOT_CUSTOM_REPO_VERSION="e7b621dc7d821d56dc6be216e061bb9a59ce4283"

## Why the directory exists

`buildroot/package/pkg-utils.mk` selects `<patchdir>/<PKG_VERSION>/` when that
subdirectory exists and falls back to `<patchdir>/` otherwise. With a git pin
`UBOOT_VERSION` is the git ref, so without this directory the mainline-targeted
`../0001-CMD-read-string-from-fileinto-env.patch` would be force-applied to the
vendor tree and fail:

    checking file cmd/Kconfig
    Hunk #1 FAILED at 1927.
    1 out of 1 hunk FAILED
    checking file cmd/Makefile
    Hunk #1 FAILED at 176.
    1 out of 1 hunk FAILED

`patches/uboot/2024.01/` is the existing in-tree precedent for exactly this.

## Contents

* `0001-CMD-read-string-from-fileinto-env.patch` — the `fileenv` command,
  ported to vendor U-Boot 2023.01. `cmd/fileenv.c` is byte-for-byte identical
  to the mainline HAOS patch; only the `cmd/Kconfig` and `cmd/Makefile` hunk
  contexts were re-based. Verified to apply with zero offset and zero fuzz
  against commit `e7b621dc7d821d56dc6be216e061bb9a59ce4283`.

This patch is mandatory: `buildroot-external/board/jethome/uboot-boot.ush:47`
calls `fileenv` to read `cmdline.txt` into the environment, and vendor U-Boot
2023.01 has no such command.

`CONFIG_CMD_FILEENV=y` already comes from the shared
`buildroot-external/bootloader/uboot.config`. `do_fileenv()` calls
`do_fat_fsload()` from `cmd/fat.c`, which is built because the same shared
fragment sets `CONFIG_DISTRO_DEFAULTS=y` and `DISTRO_DEFAULTS` selects
`CMD_FAT` (vendor `Kconfig:204`).
