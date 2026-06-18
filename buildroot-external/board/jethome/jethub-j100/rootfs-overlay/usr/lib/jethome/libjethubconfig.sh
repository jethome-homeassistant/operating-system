#!/bin/bash
# shellcheck disable=SC2034
#
# JetHub D1 (J100). Lines are named in the DTS (j1xx.dtsi): ZigBeeBOOT(36),
# ZigBeeRESET(41), LedRed(26), LedGreen(27). Zigbee reset is addressed by name
# (gset/gpulse). LEDs are driven by chip+line (SoC chip 0 is stable).

GPIOCHIPNUMBER=0
GPIO_ACTIVE_LOW=0

# LED states at boot: both OFF (active-low).
LEDS=(
    # LED RED
    "${GPIOCHIPNUMBER} 26 0 ${GPIO_ACTIVE_LOW}"
    # LED GREEN
    "${GPIOCHIPNUMBER} 27 0 ${GPIO_ACTIVE_LOW}"
)

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
    # No ds2482 node in the DTS: instantiate the i2c device manually.
    sh -c "echo ds2482 0x18 > /sys/bus/i2c/devices/i2c-0/new_device" 2>/dev/null || true
}

ADDITIONALFUNC="reset_zigbee config_1wire"
