################################################################################
#
# jethub-init
#
################################################################################

JETHUB_INIT_VERSION = 1.4.0
JETHUB_INIT_SOURCE = jethub-init-haos_$(JETHUB_INIT_VERSION).tar.gz
JETHUB_INIT_SITE = https://github.com/jethome-iot/jethub-init/releases/download/v$(JETHUB_INIT_VERSION)
JETHUB_INIT_LICENSE = PROPRIETARY

JETHUB_INIT_BOARD = $(call qstrip,$(BR2_PACKAGE_JETHUB_INIT_BOARD))

ifeq ($(BR2_PACKAGE_JETHUB_INIT),y)
ifeq ($(JETHUB_INIT_BOARD),)
$(error No JetHub board specified, set BR2_PACKAGE_JETHUB_INIT_BOARD (j80/j100/j200/j310))
endif
endif

define JETHUB_INIT_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/$(JETHUB_INIT_BOARD)/jethub-init \
		$(TARGET_DIR)/usr/lib/jethome/jethub-init
endef

$(eval $(generic-package))
