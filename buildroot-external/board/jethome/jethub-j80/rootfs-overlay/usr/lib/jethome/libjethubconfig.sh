#!/bin/sh
# shellcheck disable=SC2034

GPIO_ACTIVE_LOW=0
GPIO_ACTIVE_HIGH=1

configure_leds() {
    echo "${0}: Configure LEDs ..."
    # LED
    configure_led 1 73 0 ${GPIO_ACTIVE_HIGH}
}

reset_zigbee() {
    echo "${0}: Reset Zigbee module ..."
    wait_line ZigBeeRESET || return 1
    gset ZigBeeBOOT=1
    gpulse ZigBeeRESET
}

reset_zwave() {
    echo "${0}: Reset Z-Wave module ..."
    # gpio_set 1 90 1 ${GPIO_ACTIVE_HIGH}
    gpio_set 1 89 1 ${GPIO_ACTIVE_HIGH}
    sleep 1
    gpio_set 1 89 0 ${GPIO_ACTIVE_HIGH}
}

eth_leds() {
    echo "${0}: Configure Ethernet leds ..."
    /usr/lib/jethome/jethub_set-eth_leds
}

ADDITIONALFUNC="configure_leds reset_zigbee eth_leds"
# Enable for second module
#ADDITIONALFUNC="${ADDITIONALFUNC} reset_zwave"
