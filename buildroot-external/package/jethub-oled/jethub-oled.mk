################################################################################
#
# jethub-oled
#
################################################################################

JETHUB_OLED_VERSION = 1.0
JETHUB_OLED_LICENSE = Apache License 2.0
JETHUB_OLED_LICENSE_FILES = $(BR2_EXTERNAL_HAOS_PATH)/../LICENSE
JETHUB_OLED_SITE = $(BR2_EXTERNAL_HAOS_PATH)/package/jethub-oled/src
JETHUB_OLED_SITE_METHOD = local
JETHUB_OLED_DEPENDENCIES = host-dtc
JETHUB_OLED_INSTALL_IMAGES = YES

# Boot logo as a DT overlay; hassos-hook.sh copies $(BINARIES_DIR)/*.dtbo to
# the boot partition, overlays= in boot-env.txt enables it
define JETHUB_OLED_BUILD_CMDS
	$(HOST_DIR)/bin/dtc -@ -I dts -O dtb \
		-o $(@D)/jethub-oled-splash.dtbo \
		$(BR2_EXTERNAL_HAOS_PATH)/package/jethub-oled/splash/jethub-oled-splash.dtso
endef

define JETHUB_OLED_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/jethub-oled.py $(TARGET_DIR)/usr/sbin/jethub-oled
endef

define JETHUB_OLED_INSTALL_INIT_SYSTEMD
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_HAOS_PATH)/package/jethub-oled/jethub-oled.service \
		$(TARGET_DIR)/usr/lib/systemd/system/jethub-oled.service
	$(INSTALL) -d $(TARGET_DIR)/etc/systemd/system/haos-hardware.target.wants
	ln -sf /usr/lib/systemd/system/jethub-oled.service \
		$(TARGET_DIR)/etc/systemd/system/haos-hardware.target.wants/jethub-oled.service
endef

define JETHUB_OLED_INSTALL_IMAGES_CMDS
	$(INSTALL) -D -m 0644 $(@D)/jethub-oled-splash.dtbo \
		$(BINARIES_DIR)/jethub-oled-splash.dtbo
endef

$(eval $(generic-package))
