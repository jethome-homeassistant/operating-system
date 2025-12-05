#!/bin/sh
# ==============================================================================
# If hassos-supervisor.service is dead then reboot
# ==============================================================================

SERVICE=hassos-supervisor.service

if ! systemctl is-active --quiet "$SERVICE"; then
    echo "[check-hassos-supervisor] $SERVICE is not active, rebooting" >&2
    reboot -f
fi