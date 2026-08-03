
################################################################################
#
# amlogic-boot-fip-j310
#
################################################################################

AMLOGIC_BOOT_FIP_J310_VERSION = f1b7b257a7bff747e1b8d370919a3b43494a21a5
AMLOGIC_BOOT_FIP_J310_SITE = https://github.com/jethome-iot/amlogic-boot-fip.git
AMLOGIC_BOOT_FIP_J310_SITE_METHOD = git
AMLOGIC_BOOT_FIP_J310_INSTALL_IMAGES = YES
AMLOGIC_BOOT_FIP_J310_DEPENDENCIES = uboot

AMLOGIC_BOOT_FIP_J310_LICENSE = PROPRIETARY
AMLOGIC_BOOT_FIP_J310_REDISTRIBUTE = NO

# NOTE: this list is deliberately package-prefixed. Do NOT reuse the unprefixed
# AMLOGIC_BOOT_BINS variable owned by the amlogic-boot-fip-e package: both .mk
# files are parsed unconditionally by external.mk, so a shared '+=' variable
# would leak this package's file list into amlogic-boot-fip-e (and vice versa)
# and break the j80/j100/j200 image install step.
#
# The s7.inc rule for ${O}/u-boot.bin produces all three files below:
#   u-boot.bin        - raw eMMC/SPI bootloader image
#   u-boot.bin.sd.bin - SD/eMMC image with the leading AMLBOOT payload sector
#   u-boot.bin.usb    - USB (boot-from-USB / burn mode) bootloader image
AMLOGIC_BOOT_FIP_J310_BINS = u-boot.bin u-boot.bin.sd.bin u-boot.bin.usb

define AMLOGIC_BOOT_FIP_J310_BUILD_CMDS
    mkdir -p $(@D)/fip
    cp $(BINARIES_DIR)/u-boot.bin $(@D)/fip/bl33.bin
    cd "$(@D)"; ./build-fip.sh $(call qstrip,$(BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310_BOARD)) $(@D)/fip/bl33.bin $(@D)/fip
endef

ifeq ($(BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310),y)
ifeq ($(call qstrip,$(BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310_BOARD)),)
$(error No board u-boot firmware config name specified, check your BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310_BOARD setting)
endif # qstrip BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310_BOARD
endif

define AMLOGIC_BOOT_FIP_J310_INSTALL_IMAGES_CMDS
	$(foreach f,$(AMLOGIC_BOOT_FIP_J310_BINS), \
			cp -dpf "$(@D)/fip/$(f)" "$(BINARIES_DIR)/"
	)
endef

$(eval $(generic-package))
