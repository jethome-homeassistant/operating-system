#!/bin/bash
# shellcheck disable=SC2034
#
# JetHub D2 (J80). Zigbee EFR32 control lines are named in the DTS (AO bank:
# ZigBeeRESET=GPIOAO_6, ZigBeeBOOT=GPIOAO_9) — addressed by name (gset/gpulse).
# Z-Wave RESET/SUSPEND and the LED are on the periphs bank (stable), by chip+line.

GPIO_ACTIVE_HIGH=1

# Set LED states
LEDS=(
    # LED
    "1 73 0 ${GPIO_ACTIVE_HIGH}"
)

reset_zigbee() {
    echo "${0}: Reset Zigbee module ..."
    wait_line ZigBeeRESET || return 1
    gset ZigBeeBOOT=1
    gpulse ZigBeeRESET
}

reset_zwave() {
    echo "${0}: Reset Z-Wave module ..."
    # Optional SUSPEND pin
    # gpio_set 1 90 1 ${GPIO_ACTIVE_HIGH}
    gpio_set 1 89 1 ${GPIO_ACTIVE_HIGH}
    sleep 1
    gpio_set 1 89 0 ${GPIO_ACTIVE_HIGH}
}

eth_leds() {
    echo "${0}: Configure Ethernet leds ..."
    /usr/sbin/jethub_set-eth_leds
}

ADDITIONALFUNC="eth_leds reset_zigbee"
# Enable for second module
#ADDITIONALFUNC="${ADDITIONALFUNC} reset_zwave"
