
################################################################################
#
# amlogic-boot-fip-j310
#
################################################################################

AMLOGIC_BOOT_FIP_J310_VERSION = 0195df574f251c4bd97fa3a8a64aca503ddd3d56
AMLOGIC_BOOT_FIP_J310_SITE = https://github.com/jethome-iot/amlogic-boot-fip.git
AMLOGIC_BOOT_FIP_J310_SITE_METHOD = git
AMLOGIC_BOOT_FIP_J310_INSTALL_IMAGES = YES
AMLOGIC_BOOT_FIP_J310_DEPENDENCIES = uboot

AMLOGIC_BOOT_FIP_J310_LICENSE = PROPRIETARY
AMLOGIC_BOOT_FIP_J310_REDISTRIBUTE = NO

AMLOGIC_BOOT_FIP_J310_BINS = u-boot.bin u-boot.bin.sd.bin u-boot.bin.usb

define AMLOGIC_BOOT_FIP_J310_BUILD_CMDS
    mkdir -p $(@D)/fip
    cp $(BINARIES_DIR)/u-boot.bin $(@D)/fip/bl33.bin
    cd "$(@D)"; ./build-fip.sh $(call qstrip,$(BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310_BOARD)) $(@D)/fip/bl33.bin $(@D)/fip
endef

ifeq ($(BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310),y)
ifeq ($(call qstrip,$(BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310_BOARD)),)
$(error No board u-boot firmware config name specified, check your BR2_PACKAGE_AMLOGIC_BOOT_FIP_J310_BOARD setting)
endif
endif

define AMLOGIC_BOOT_FIP_J310_INSTALL_IMAGES_CMDS
	$(foreach f,$(AMLOGIC_BOOT_FIP_J310_BINS), \
			cp -dpf "$(@D)/fip/$(f)" "$(BINARIES_DIR)/"
	)
endef

$(eval $(generic-package))
