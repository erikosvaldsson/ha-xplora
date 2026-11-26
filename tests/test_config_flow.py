"""Config and options flow tests.

The Xplora login is patched out: nothing here talks to the Xplora cloud.
"""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.myxplora.api import XploraAuthError
from custom_components.myxplora.const import (
    CONF_COUNTRY_CODE,
    CONF_PHONE,
    CONF_SCAN_MINUTES,
    DOMAIN,
)

LOGIN = "custom_components.myxplora.config_flow.XploraApi.async_login"
SETUP_ENTRY = "custom_components.myxplora.async_setup_entry"
USER_INPUT = {
    CONF_COUNTRY_CODE: "+46",
    CONF_EMAIL: "Someone@Example.com",
    CONF_PASSWORD: "secret",
}


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


async def test_creates_entry(hass: HomeAssistant) -> None:
    flow_id = await _start(hass)
    # Keep the new entry from setting up the integration (and polling).
    with patch(LOGIN) as login, patch(SETUP_ENTRY, return_value=True) as setup:
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
        await hass.async_block_till_done()
    login.assert_awaited_once()
    setup.assert_awaited_once()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "someone@example.com"


async def test_needs_email_or_phone(hass: HomeAssistant) -> None:
    flow_id = await _start(hass)
    with patch(LOGIN) as login:
        result = await hass.config_entries.flow.async_configure(
            flow_id, {**USER_INPUT, CONF_EMAIL: "", CONF_PHONE: ""}
        )
    login.assert_not_awaited()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "need_email_or_phone"}


async def test_invalid_auth(hass: HomeAssistant) -> None:
    flow_id = await _start(hass)
    with patch(LOGIN, side_effect=XploraAuthError):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass: HomeAssistant) -> None:
    flow_id = await _start(hass)
    with patch(LOGIN, side_effect=TimeoutError):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="someone@example.com").add_to_hass(hass)
    flow_id = await _start(hass)
    with patch(LOGIN):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_scan_interval(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="someone@example.com")
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_MINUTES: 120}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SCAN_MINUTES: 120}
