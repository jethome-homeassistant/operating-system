
################################################################################
#
# jethome-burn
#
################################################################################

JETHOME_BURN_VERSION = fd60e5bff4e1f84634c97fde43656c86293710b8
JETHOME_BURN_SITE = https://github.com/jethome-iot/jethome-tools
JETHOME_BURN_SITE_METHOD = git
JETHOME_BURN_INSTALL_IMAGES = YES

JETHOME_BURN_LICENSE = PROPRIETARY
JETHOME_BURN_REDISTRIBUTE = NO

JETHOME_BURN_TOOLS_DIR = $(HOST_DIR)/share/jethome-tools

define JETHOME_BURN_INSTALL_IMAGES_CMDS
	rm -rf "$(JETHOME_BURN_TOOLS_DIR)"
	mkdir -p "$(JETHOME_BURN_TOOLS_DIR)"
	cp -dpRf "$(@D)/." "$(JETHOME_BURN_TOOLS_DIR)/"
	chmod +x "$(JETHOME_BURN_TOOLS_DIR)/convert.sh"
endef

$(eval $(generic-package))
