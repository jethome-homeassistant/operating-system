# j310 vendor U-Boot — intentionally no patches

Present-but-empty so Buildroot skips the flat `../0001-CMD-read-string-from-
fileinto-env.patch` (a version directory REPLACES the flat one, it does not
supplement it — see `Config.in:735`). That patch targets U-Boot 2026.04 and
does not apply to the vendor tree.

The `fileenv` command that `board/jethome/jethub-j310/uboot-boot.ush` needs is
committed upstream in github.com/jethome-iot/u-boot instead.

The directory name must equal BR2_TARGET_UBOOT_CUSTOM_REPO_VERSION — rename it
whenever that tag changes.
