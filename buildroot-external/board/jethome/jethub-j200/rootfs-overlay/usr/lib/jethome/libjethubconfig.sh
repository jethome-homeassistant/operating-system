#!/bin/bash
# shellcheck disable=SC2034
#
# JetHub H1 (J200). Relays/DINs/UXM RESET+BOOT sit on the pca9535 i2c expander
# whose gpiochip number is unstable, so they are addressed BY NAME (gset/gpulse;
# names RELAY_*, UXM*_RESET/BOOT come from the DTS). LEDs are on stable SoC banks
# and driven by chip+line.

GPIO_ACTIVE_LOW=0
GPIO_ACTIVE_HIGH=1

# LED states at boot: RED off, GREEN on.
LEDS=(
    # LED RED
    "0 21 0 ${GPIO_ACTIVE_HIGH}"
    # LED GREEN
    "1 11 1 ${GPIO_ACTIVE_HIGH}"
)

uxm_recover() {
    local uxm="$1"
    wait_line "${uxm}_RESET" || return 1
    gset "${uxm}_BOOT=1"
    gpulse "${uxm}_RESET"
    sleep 0.5
    gset "${uxm}_BOOT=0"
    gpulse "${uxm}_RESET"
}

reset_uxm1() {
    echo "${0}: Reset UXM1 module"
    uxm_recover UXM1
}

reset_uxm2() {
    echo "${0}: Reset UXM2 module"
    uxm_recover UXM2
}

config_1wire() {
    echo "${0}: Configure 1-Wire ..."
    if ! modprobe ds2482; then
        echo "${0}: *** Error: Failed to load DS2482 kernel module"
        return 1
    fi
}

ADDITIONALFUNC="reset_uxm1 reset_uxm2 config_1wire"
