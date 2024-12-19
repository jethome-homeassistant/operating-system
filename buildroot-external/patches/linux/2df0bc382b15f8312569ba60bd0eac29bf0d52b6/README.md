# j310 vendor kernel — intentionally no patches

Present-but-empty so Buildroot skips the flat `../*.patch` (a version directory
REPLACES the flat one, it does not supplement it — see `Config.in:735`). The
mainline patches there do not apply to the vendor 5.15 tree.

Everything this kernel needs is committed upstream in
github.com/jethome-iot/linux-kernel instead of being carried here.

The directory name must equal BR2_LINUX_KERNEL_CUSTOM_REPO_VERSION — rename it
whenever that tag changes.
