"""Constants for the myXplora integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "myxplora"
MANUFACTURER = "Xplora"

# Config entry keys (CONF_EMAIL / CONF_PASSWORD come from homeassistant.const)
CONF_COUNTRY_CODE = "country_code"
CONF_PHONE = "phone_number"
CONF_TIMEZONE = "timezone"
CONF_LANGUAGE = "language"

DEFAULT_LANGUAGE = "en-US"
DEFAULT_TIMEZONE = "Europe/Stockholm"

# Slow, passive polling — see FINDINGS.md. Default 90 min; floor kept high so
# nobody accidentally reproduces the active-polling ban.
CONF_SCAN_MINUTES = "scan_minutes"
DEFAULT_SCAN_MINUTES = 90
MIN_SCAN_MINUTES = 30

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=DEFAULT_SCAN_MINUTES)
