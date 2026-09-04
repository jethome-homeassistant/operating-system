#!/bin/bash
# shellcheck disable=SC2155

function haos_pre_image() {
    local BOOT_DATA="$(path_boot_dir)"

    cp "${BINARIES_DIR}/boot.scr" "${BOOT_DATA}/boot.scr"
    mkdir -p "${BOOT_DATA}/amlogic"

    local dtb
    dtb="$(find "${BUILD_DIR}"/linux-*/common_drivers/arch/arm64/boot/dts/amlogic \
        -name "${KERNEL_DTB}" -print -quit 2>/dev/null)"
    if [ -z "${dtb}" ]; then
        echo "ERROR: ${KERNEL_DTB} not found in the kernel build tree"
        return 1
    fi
    cp "${dtb}" "${BOOT_DATA}/amlogic/"

    if ls "${BINARIES_DIR}"/*.dtbo 1> /dev/null 2>&1; then
        echo "Found .dtbo files in ${BINARIES_DIR}"
        mkdir -p "${BOOT_DATA}/overlays"
        cp "${BINARIES_DIR}"/*.dtbo "${BOOT_DATA}/overlays/"
    fi
    cp "${BOARD_DIR}/boot-env.txt" "${BOOT_DATA}/hassos-config.txt" || true
    cp "${BOARD_DIR}/cmdline.txt" "${BOOT_DATA}/cmdline.txt"
}

function haos_post_image() {
    convert_disk_image_xz
    convert_disk_image_burn
}
