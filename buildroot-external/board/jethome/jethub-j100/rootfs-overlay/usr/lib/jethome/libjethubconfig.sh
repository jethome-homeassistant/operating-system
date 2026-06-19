#!/bin/sh
# shellcheck disable=SC2034

GPIOCHIPNUMBER=0
GPIO_ACTIVE_LOW=0
GPIO_ACTIVE_HIGH=1

configure_leds() {
    echo "${0}: Configure LEDs ..."
    configure_led ${GPIOCHIPNUMBER} 26 0 ${GPIO_ACTIVE_LOW}
    configure_led ${GPIOCHIPNUMBER} 27 0 ${GPIO_ACTIVE_LOW}
}

reset_zigbee() {
    echo "${0}: Reset Zigbee module ..."
    wait_line ZigBeeRESET || return 1
    gset ZigBeeBOOT=1
    gpulse ZigBeeRESET
}

config_1wire() {
    echo "${0}: Configure 1-Wire ..."
    if ! modprobe ds2482; then
        echo "${0}: *** Error: Failed to load DS2482 kernel module"
        return 1
    fi

    sh -c "echo ds2482 0x18 > /sys/bus/i2c/devices/i2c-0/new_device" 2>/dev/null || true
}

ADDITIONALFUNC="configure_leds reset_zigbee config_1wire"
