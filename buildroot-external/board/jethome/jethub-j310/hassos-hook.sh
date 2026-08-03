#!/bin/bash
# shellcheck disable=SC2155

# shellcheck source=../../../scripts/burn.sh
. "${SCRIPT_DIR}/burn.sh"

function haos_pre_image() {
    local BOOT_DATA="$(path_boot_dir)"

    # The vendor U-Boot for j310 boots with
    #   load mmc 0   0x12000000 boot/boot.scr   (SD card, devnum becomes 0)
    #   load mmc 1:1 0x12000000 boot/boot.scr   (eMMC)
    # (see CONFIG_BOOTCOMMAND in jethome-iot/u-boot configs/jethub_j310_defconfig)
    # so the compiled boot script has to live at boot/boot.scr inside the FAT
    # boot partition.  A second copy is kept at the root of the partition, which
    # is where the other JetHub boards and the U-Boot distro boot_scripts search
    # path expect it - that keeps the image bootable if the bootcmd is ever
    # changed back to the generic one.
    mkdir -p "${BOOT_DATA}/boot"
    cp "${BINARIES_DIR}/boot.scr" "${BOOT_DATA}/boot/boot.scr"
    cp "${BINARIES_DIR}/boot.scr" "${BOOT_DATA}/boot.scr"

    # Kernel device tree.  ${KERNEL_DTB} comes from this board's meta file; the
    # amlogic/ sub-directory matches ${fdtfile} in uboot-boot.ush.
    #
    # The DTB is NOT in ${BINARIES_DIR}: this board uses
    # BR2_LINUX_KERNEL_IMAGE_TARGET_CUSTOM with BR2_LINUX_KERNEL_IMAGE_NAME=
    # "Image", so buildroot's LINUX_INSTALL_IMAGE only copies the kernel image,
    # and LINUX_INSTALL_DTB is a no-op because BR2_LINUX_KERNEL_DTS_SUPPORT is
    # off (the vendor Makefile relocates dtstree into common_drivers/, which
    # buildroot's in-tree DTS machinery cannot handle).  The DTB is therefore
    # built in place by the "Image meson-s7-jethub-j310.dtb" target and has to
    # be fetched out of the kernel build directory - the same trick the JetHome
    # buildroot recovery build uses.
    local kernel_build_dir="${BUILD_DIR:-${BASE_DIR}/build}"
    local dtb_src
    dtb_src="$(find "${kernel_build_dir}" -path "*/common_drivers/arch/arm64/boot/dts/amlogic/${KERNEL_DTB}" -print -quit)"
    if [ -z "${dtb_src}" ] || [ ! -f "${dtb_src}" ]; then
        echo "ERROR: ${KERNEL_DTB} not found under ${kernel_build_dir}" >&2
        return 1
    fi
    echo "Using device tree ${dtb_src}"
    mkdir -p "${BOOT_DATA}/amlogic"
    cp "${dtb_src}" "${BOOT_DATA}/amlogic/${KERNEL_DTB}"

    if ls "${BINARIES_DIR}"/*.dtbo 1> /dev/null 2>&1; then
        echo "Found .dtbo files in ${BINARIES_DIR}"
        mkdir -p "${BOOT_DATA}/overlays"
        cp "${BINARIES_DIR}"/*.dtbo "${BOOT_DATA}/overlays/"
    fi

    cp "${BOARD_DIR}/boot-env.txt" "${BOOT_DATA}/hassos-config.txt"
    cp "${BOARD_DIR}/cmdline.txt" "${BOOT_DATA}/cmdline.txt"
}

function haos_post_image() {
    convert_disk_image_xz

    # Support for creating AmLogic burnable images.  platform.conf is installed
    # by the jethome-burn package, which currently has no j310 board data, so
    # this branch is normally not taken for this board.
    if [ -f "${BINARIES_DIR}/platform.conf" ]; then
        _create_disk_burn
        convert_disk_image_burn_zip
    fi

    return 0
}
