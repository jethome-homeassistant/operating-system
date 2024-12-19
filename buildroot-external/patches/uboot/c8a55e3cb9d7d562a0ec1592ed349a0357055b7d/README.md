# j310 vendor U-Boot — intentionally no patches

Present-but-empty so Buildroot skips the flat `../0001-CMD-read-string-from-
fileinto-env.patch` (a version directory REPLACES the flat one, it does not
supplement it — see `Config.in:735`). That patch targets U-Boot 2026.04 and
does not apply to the vendor tree.

Nothing here needs it either: the vendor tree has no `fileenv` command, so
`board/jethome/jethub-j310/uboot-boot.ush` sets the kernel command line
directly instead of reading it back from `cmdline.txt`.

The directory name must equal BR2_TARGET_UBOOT_CUSTOM_REPO_VERSION — rename it
whenever the pin moves, or the flat patch silently comes back and the build
fails while applying it.
