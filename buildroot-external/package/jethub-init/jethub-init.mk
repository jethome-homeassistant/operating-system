################################################################################
#
# jethub-init
#
################################################################################

JETHUB_INIT_VERSION = 73a4b6eedbb1042052859846fedc8eae7ca494ba
JETHUB_INIT_SITE = https://github.com/jethome-iot/jethub-init
JETHUB_INIT_SITE_METHOD = git
JETHUB_INIT_LICENSE = PROPRIETARY

JETHUB_INIT_BOARD = $(call qstrip,$(BR2_PACKAGE_JETHUB_INIT_BOARD))

ifeq ($(BR2_PACKAGE_JETHUB_INIT),y)
ifeq ($(JETHUB_INIT_BOARD),)
$(error No JetHub board specified, set BR2_PACKAGE_JETHUB_INIT_BOARD (j80/j100/j200))
endif
endif

define JETHUB_INIT_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/haos-ash/jethub-init \
		$(TARGET_DIR)/usr/lib/jethome/jethub-init
	$(INSTALL) -D -m 0644 $(@D)/haos-ash/$(JETHUB_INIT_BOARD)/libjethubconfig.sh \
		$(TARGET_DIR)/usr/lib/jethome/libjethubconfig.sh
endef

$(eval $(generic-package))
